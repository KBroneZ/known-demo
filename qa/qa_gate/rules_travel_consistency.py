"""Travel rule (a): contradictions inside one post.

The same named entity (same qualifiers: season, class, 7-day, opens/closes ...) gets two different prices, distances or
dates, or the same event falls on two different weekdays. Conservative on purpose: an entity is a Capitalised phrase,
a sentence that lists several amounts for one entity is an enumeration and is ignored, and mentions only conflict when
their qualifiers are identical. The model layer covers what this heuristic cannot see.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from .findings import BLOCK, WARN, Finding
from .loader import Clinic, Post
from .travel_text import (
    WEEKDAYS,
    Unit,
    dates_in,
    entity_phrases,
    owner_phrase,
    qualifiers,
    quantities,
    safe_date,
    units,
)

WEEKDAY_RE = re.compile(r"\b(" + "|".join(WEEKDAYS) + r")s?\b", re.I)
_LIST_BEFORE = re.compile(r"(?:\bto|\bthrough|\bthru|\band|\bor|\b&|[-–—,/])\s*$", re.I)
_LIST_AFTER = re.compile(r"^\s*(?:to|through|thru|and|or|&|[-–—,/])\s*(?:" + "|".join(WEEKDAYS) + r")", re.I)
PRICE_TOLERANCE, APPROX_TOLERANCE, DISTANCE_TOLERANCE = 0.0, 0.05, 0.05


@dataclass(frozen=True)
class Mention:
    kind: str  # price | distance | date | weekday
    key: tuple
    unit_id: int
    line: int
    shape: str
    lo: float
    hi: float
    approx: bool
    text: str
    entity: str
    items: frozenset = frozenset()  # content words of the unit: what the amount is the price of
    others: frozenset = frozenset()  # other named things before the amount: "River Deck" in "River Deck (Opening Day)"


GENERIC_WORDS = frozenset(
    [
        "costs",
        "cost",
        "price",
        "prices",
        "priced",
        "about",
        "around",
        "approximately",
        "roughly",
        "from",
        "each",
        "every",
        "with",
        "this",
        "that",
        "than",
        "then",
        "also",
        "only",
        "just",
        "have",
        "will",
        "your",
        "you",
        "per",
        "night",
        "free",
        "total",
        "fare",
        "fares",
        "entry",
        "admission",
        "online",
        "booking",
        "book",
        "miles",
        "mile",
        "kilometers",
        "kilometres",
        "long",
        "walk",
        "away",
        "takes",
        "which",
        "where",
        "there",
        "their",
        "these",
        "those",
        "while",
        "into",
        "over",
        "under",
        "after",
        "before",
        "during",
        "early",
        "late",
    ]
)


def _stem(word: str) -> str:
    return word.rstrip("s")[:4]


def item_words(text: str, quals: frozenset[str], names: frozenset[str] = frozenset()) -> frozenset:
    """Content words of a unit, minus generic, qualifier and entity-name words:
    'tasting plate' vs 'walnut torte slice'."""
    skip = {w for q in quals for w in q.split()} | names
    words = re.findall(r"\b[a-z][a-z'-]{2,}\b", text.lower())
    return frozenset(_stem(w) for w in words if w not in GENERIC_WORDS and w not in skip)


# "Standard" vs "Standard Plus": a tier word after the same name makes a different product, not the same entity
TIER_WORDS = frozenset(
    [
        "plus",
        "pro",
        "max",
        "premium",
        "enhanced",
        "deluxe",
        "lite",
        "mini",
        "ultra",
        "elite",
        "prime",
        "express",
        "select",
        "advanced",
        "essential",
        "essentials",
        "basic",
        "classic",
        "family",
        "vip",
        "platinum",
        "gold",
        "silver",
    ]
)


def same_entity(a: str, b: str) -> bool:
    """Same name, or one is the other plus extra words at the end ('donau licht' / 'donau licht boats', 2+ words)."""
    if a == b:
        return True
    ta, tb = a.split(), b.split()
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    extra = long_[len(short) :]
    return len(short) >= 2 and long_[: len(short)] == short and not TIER_WORDS.intersection(extra)


def _nearest(phrases, start: int, end: int, gap: int = 50):
    best = None
    for s, e, name in phrases:
        dist = 0 if (s < end and start < e) else (start - e if e <= start else s - end)
        if dist <= gap and (best is None or dist < best[0]):
            best = (dist, name, (s, e))
    return best


def _quantity_mentions(unit_id: int, unit: Unit, phrases) -> list[Mention]:
    found = []
    names = frozenset(w for _, _, name in phrases for w in name.split())
    for q in quantities(unit.text):
        owner = owner_phrase(phrases, q.start)
        if not owner:
            continue
        quals = qualifiers(unit.text, (owner[0], owner[1]), slots=False)
        found.append(
            Mention(
                q.kind,
                (owner[2], q.kind, q.unit, quals),
                unit_id,
                unit.line,
                q.shape,
                q.lo,
                q.hi,
                q.approx,
                q.text,
                owner[2],
                item_words(unit.text[: q.start], quals, names),
                frozenset(n for _, e, n in phrases if e <= q.start and not same_entity(n, owner[2]) and n != owner[2]),
            )
        )
    seen: dict[tuple, int] = {}
    for m in found:
        seen[m.key] = seen.get(m.key, 0) + 1
    return [m for m in found if seen[m.key] == 1]  # several amounts for one entity in one unit = an enumeration


def _date_mentions(unit_id: int, unit: Unit, phrases) -> list[Mention]:
    found = []
    for d in dates_in(unit.text):
        near = _nearest(phrases, d.start, d.end, 40)
        if not near:
            continue
        year = d.year or 0
        lo, hi = year * 10000 + d.month * 100 + d.day, year * 10000 + d.month2 * 100 + d.day2
        quals = qualifiers(unit.text, near[2])
        found.append(
            Mention(
                "date",
                (near[1], "date", str(year), quals),
                unit_id,
                unit.line,
                "single" if lo == hi else "range",
                lo,
                hi,
                False,
                d.text,
                near[1],
            )
        )
    return found


def _weekday_mentions(unit_id: int, unit: Unit, phrases) -> list[Mention]:
    found = []
    for m in WEEKDAY_RE.finditer(unit.text):
        if _LIST_BEFORE.search(unit.text[: m.start()]) and WEEKDAY_RE.search(
            unit.text[max(0, m.start() - 24) : m.start()]
        ):
            continue
        if _LIST_AFTER.match(unit.text[m.end() :]):
            continue
        near = _nearest(phrases, m.start(), m.end(), 50)
        if not near:
            continue
        value = WEEKDAYS[m.group(1).lower()]
        found.append(
            Mention(
                "weekday",
                (near[1], "weekday", "", qualifiers(unit.text, near[2])),
                unit_id,
                unit.line,
                "single",
                value,
                value,
                False,
                m.group(1).capitalize(),
                near[1],
            )
        )
    return found


def compatible(a: Mention, b: Mention) -> bool:
    tol = (
        APPROX_TOLERANCE
        if (a.approx or b.approx)
        else (DISTANCE_TOLERANCE if a.kind == "distance" else PRICE_TOLERANCE)
    )

    def lo(m: Mention) -> float:
        return m.lo if m.shape != "cap" else 0.0

    def hi(m: Mention) -> float:
        return m.hi if m.shape != "floor" else float("inf")

    shapes = {a.shape, b.shape}
    if shapes <= {"single", "range"}:
        if a.shape == b.shape:
            return abs(a.lo - b.lo) <= tol * max(a.lo, b.lo) and abs(a.hi - b.hi) <= tol * max(a.hi, b.hi)
        single, rng = (a, b) if a.shape == "single" else (b, a)
        return rng.lo * (1 - tol) <= single.lo <= rng.hi * (1 + tol)
    return lo(a) <= hi(b) * (1 + tol) and lo(b) <= hi(a) * (1 + tol)


def different_items(a: Mention, b: Mention) -> bool:
    """Both units say what is being priced and the two descriptions share no word, or each names another thing
    first and the two names differ ("River Deck (Opening Day)" vs "Garden Terrace (Opening Day)"): two
    different products of one place."""
    if a.kind not in ("price", "distance"):
        return False
    return (bool(a.items) and bool(b.items) and not (a.items & b.items)) or (
        bool(a.others) and bool(b.others) and not (a.others & b.others)
    )


_RULE = {
    "price": "numeric_inconsistency",
    "distance": "numeric_inconsistency",
    "date": "date_inconsistency",
    "weekday": "weekday_inconsistency",
}
_DAYNAME = {v: k.capitalize() for k, v in WEEKDAYS.items()}


def _conflicts(mentions: list[Mention]) -> list[Finding]:
    groups: dict[tuple, list[Mention]] = {}
    for m in mentions:
        groups.setdefault(m.key[1:], []).append(m)
    out = []
    for items in groups.values():
        pair = next(
            (
                (a, b)
                for i, a in enumerate(items)
                for b in items[i + 1 :]
                if a.unit_id != b.unit_id
                and same_entity(a.entity, b.entity)
                and not different_items(a, b)
                and not compatible(a, b)
            ),
            None,
        )
        if pair:
            a, b = pair
            what = {"price": "price", "distance": "distance", "date": "date", "weekday": "day of the week"}[a.kind]
            also = (a.line,) if a.line != b.line else ()
            out.append(
                Finding(
                    _RULE[a.kind],
                    WARN,
                    b.line,
                    f"{a.text} (line {a.line}) vs {b.text}",
                    f"'{a.entity}' is given two different {what}s in the same post; keep one.",
                    also=also,
                )
            )
    return out


def _calendar_findings(unit: Unit, title_year: int | None) -> list[Finding]:
    out = []
    for d in dates_in(unit.text):
        if (d.month, d.day) != (d.month2, d.day2):
            continue
        year = d.year or title_year
        before = re.search(r"\b(" + "|".join(WEEKDAYS) + r")s?\b[,.]?\s*(?:the\s+)?$", unit.text[: d.start], re.I)
        after = re.match(r"\s*[(,]?\s*(" + "|".join(WEEKDAYS) + r")\b", unit.text[d.end :], re.I)
        said = before or after
        real = safe_date(year, d.month, d.day) if year else None
        if said and real and WEEKDAYS[said.group(1).lower()] != real.weekday():
            out.append(
                Finding(
                    "weekday_date_mismatch",
                    BLOCK,
                    unit.line,
                    f"{said.group(1)} {d.text}",
                    f"{d.text} {year} is a {_DAYNAME[real.weekday()]}, not {said.group(1).capitalize()}.",
                )
            )
    return out


def _title_year(post: Post) -> int | None:
    years = set(re.findall(r"\b((?:19|20)\d\d)\b", str(post.frontmatter.get("title", ""))))
    return int(years.pop()) if len(years) == 1 else None


def run(post: Post, site: Clinic | None, today: date | None = None) -> list[Finding]:
    mentions: list[Mention] = []
    out: list[Finding] = []
    title_year = _title_year(post)
    for unit_id, unit in enumerate(units(post)):
        if unit.skipped:
            continue
        phrases = entity_phrases(unit.text)
        mentions += _quantity_mentions(unit_id, unit, phrases)
        mentions += _date_mentions(unit_id, unit, phrases)
        mentions += _weekday_mentions(unit_id, unit, phrases)
        out += _calendar_findings(unit, title_year)
    return out + _conflicts(mentions)

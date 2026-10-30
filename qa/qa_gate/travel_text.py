"""Text helpers shared by the travel rules: sentence units, named-entity phrases, amounts, distances and dates."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from .links import MD_URL
from .loader import Post

MONTHS = {
    m: i
    for i, names in enumerate(
        (
            "january jan",
            "february feb",
            "march mar",
            "april apr",
            "may",
            "june jun",
            "july jul",
            "august aug",
            "september sep sept",
            "october oct",
            "november nov",
            "december dec",
        ),
        1,
    )
    for m in names.split()
}
WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
SKIP_SECTIONS = re.compile(r"^(?:sources?|references?|further reading|credits|photo credits)\b", re.I)
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")
_ABBREV = re.compile(r"\b(Dr|Mr|Mrs|Ms|St|Mt|Ft|vs|No|Inc|Co|approx|e\.g|i\.e)\.", re.I)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(\[“])")


@dataclass(frozen=True)
class Unit:
    line: int
    text: str
    section: str
    paragraph: int

    @property
    def skipped(self) -> bool:
        return bool(SKIP_SECTIONS.match(self.section))


def clean_markdown(text: str) -> str:
    text = re.sub(rf"!\[[^\]]*\]\({MD_URL}[^)]*\)", " ", text)
    text = re.sub(rf"\[([^\]]*)\]\({MD_URL}[^)]*\)", r"\1", text)
    text = re.sub(r"<https?://[^>]*>|https?://\S+", " ", text)
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"[*_]{1,3}", "", text)
    text = re.sub(r"^\s*(?:>\s*)+|^\s*[-+*]\s+|^\s*\d+[.)]\s+", "", text)
    return text.replace("|", " | ").strip()


def units(post: Post) -> list[Unit]:
    """One unit per sentence, or per table row. Headings only set the current section."""
    out, section, para = [], "", 0
    for lineno, raw in post.prose:
        if not raw.strip():
            para += 1
            continue
        heading = HEADING_RE.match(raw)
        if heading:
            section, para = heading.group(1).strip(), para + 1
            continue
        if re.match(r"^\s*\|?\s*:?-{3,}", raw):
            continue
        text = clean_markdown(raw)
        if not text:
            continue
        if "|" in text:
            out.append(Unit(lineno, text, section, para))
            continue
        protected = _ABBREV.sub(lambda m: m.group(0).replace(".", "․"), text)
        for sentence in _SENTENCE_END.split(protected):
            if sentence.strip():
                out.append(Unit(lineno, sentence.replace("․", ".").strip(), section, para))
    return out


# --- named entities ----------------------------------------------------------------------------------------

_CAP = r"[A-Z][\w'’\-]*"
PHRASE_RE = re.compile(rf"{_CAP}(?:\s+(?:(?:of|de|la|del|da|do|du|von|van|to|&)\s+)?{_CAP})*")
NUMBERED = {
    "day",
    "stage",
    "terminal",
    "route",
    "line",
    "gate",
    "platform",
    "pier",
    "stop",
    "zone",
    "room",
    "level",
    "floor",
    "week",
    "part",
    "step",
    "option",
    "plan",
    "lot",
    "exit",
    "block",
}
LEAD_STOP = {
    "the",
    "a",
    "an",
    "this",
    "that",
    "these",
    "those",
    "if",
    "when",
    "while",
    "for",
    "from",
    "at",
    "in",
    "on",
    "by",
    "with",
    "plan",
    "book",
    "expect",
    "prices",
    "price",
    "entry",
    "tickets",
    "ticket",
    "admission",
    "you",
    "your",
    "we",
    "our",
    "it",
    "its",
    "there",
    "here",
    "also",
    "then",
    "later",
    "today",
    "note",
    "tip",
    "pro",
    "pick",
    "take",
    "visit",
    "go",
    "add",
    "check",
    "arrive",
    "skip",
    "most",
    "many",
    "some",
    "each",
    "every",
    "all",
    "one",
    "two",
    "three",
    "best",
    "top",
    "free",
    "cost",
    "costs",
    "fare",
    "fares",
    "how",
    "what",
    "why",
    "where",
    "which",
    "who",
    "do",
    "does",
    "don't",
    "can",
    "will",
    "should",
    "could",
    "would",
    "is",
    "are",
    "was",
    "were",
    "be",
    "but",
    "and",
    "or",
    "so",
    "as",
    "to",
    "of",
    "not",
    "no",
    "yes",
    "after",
    "before",
    "during",
    "since",
    "until",
    "once",
    "per",
    "both",
    "either",
    "neither",
    "another",
    "other",
    "such",
    "just",
    "only",
    "even",
    "still",
    "now",
    "however",
    "instead",
    "meanwhile",
    "overall",
    "finally",
    "first",
    "second",
    "third",
    "next",
    "last",
}
EDGE_NAMES = set(MONTHS) | set(WEEKDAYS) | {"i"}


def entity_phrases(text: str, at_unit_start_ok: bool = False) -> list[tuple[int, int, str]]:
    """(start, end, normalised phrase) of named-entity phrases: runs of Capitalised words. Months, weekdays and
    sentence-opening function words are trimmed; a lone capitalised first word is not an entity."""
    out = []
    for m in PHRASE_RE.finditer(text):
        tokens = list(re.finditer(r"\S+", m.group()))
        lo, hi = 0, len(tokens)
        while lo < hi and (
            tokens[lo].group().lower() in LEAD_STOP
            or tokens[lo].group().lower().strip("'’s") in EDGE_NAMES
            or tokens[lo].group().lower() in EDGE_NAMES
        ):
            lo += 1
        while hi > lo and tokens[hi - 1].group().lower() in EDGE_NAMES:
            hi -= 1
        if lo >= hi:
            continue
        start, end = m.start() + tokens[lo].start(), m.start() + tokens[hi - 1].end()
        kept = [t.group() for t in tokens[lo:hi]]
        tail = re.match(r"\s+(\d{1,2})\b", text[end:])
        if tail and kept[-1].lower() in NUMBERED:
            kept.append(tail.group(1))
            end += tail.end()
        if all(t.isupper() or len(t) == 1 for t in kept) or (len(kept) == 1 and len(kept[0]) == 1):
            continue  # US, TX, SOLD OUT, a stray "T" from "3T": acronyms and flags are not names
        if len(kept) == 1 and start == 0 and not at_unit_start_ok:
            continue  # "Prices ..." / "Plan ...": a capitalised word only because it opens the sentence
        out.append((start, end, " ".join(kept).lower()))
    return out


QUALIFIERS = (
    "peak",
    "off-peak",
    "off peak",
    "low season",
    "high season",
    "shoulder season",
    "summer",
    "winter",
    "spring",
    "autumn",
    "fall",
    "child",
    "children",
    "kids",
    "senior",
    "student",
    "member",
    "economy",
    "business class",
    "first class",
    "standard",
    "premium",
    "basic",
    "deluxe",
    "single",
    "double",
    "return",
    "round-trip",
    "round trip",
    "one-way",
    "one way",
    "weekday",
    "weekdays",
    "weekend",
    "weekends",
    "per night",
    "per day",
    "per week",
    "per hour",
    "opens",
    "closes",
    "starts",
    "begins",
    "ends",
    "departs",
    "arrives",
    "deadline",
    "check-in",
    "check-out",
    "from",
    "until",
)
_QUAL_RE = re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(q) for q in QUALIFIERS) + r")(?![\w-])", re.I)
_DURATION_RE = re.compile(r"\b\d+[- ]?(?:day|night|hour|week|month|year|person|people|guest|passenger)s?\b", re.I)


SLOT_QUALIFIERS = frozenset(
    {"opens", "closes", "starts", "begins", "ends", "departs", "arrives", "deadline", "check-in", "check-out"}
)


def qualifiers(text: str, exclude: tuple[int, int] | None = None, slots: bool = True) -> frozenset[str]:
    """Words that change what a number is about (season, class, who pays, opens/closes, 7-day ...). Numbered entities
    in the same unit ("Day 1") count too, so 'Day 1 ... $20' and 'Day 2 ... $30' do not collide."""
    found = {m.group().lower() for m in _QUAL_RE.finditer(text) if m.group().lower() not in ("from", "until")}
    if not slots:  # opens/closes/starts ... separate two dates, but not two prices ("boarding opens 30 minutes before")
        found -= SLOT_QUALIFIERS
    found |= {re.sub(r"\s+", "-", m.group().lower()).rstrip("s") for m in _DURATION_RE.finditer(text)}
    for s, e, phrase in entity_phrases(text, True):
        if (s, e) != exclude and re.search(r"\d$", phrase):
            found.add(phrase)
    return frozenset(found)


def owner_phrase(phrases: list[tuple[int, int, str]], pos: int, max_gap: int = 70) -> tuple[int, int, str] | None:
    """The nearest named-entity phrase that ends before `pos` in the same unit."""
    before = [p for p in phrases if p[1] <= pos and pos - p[1] <= max_gap]
    return max(before, key=lambda p: p[1]) if before else None


# --- quantities --------------------------------------------------------------------------------------------

_CODES = (
    "USD|EUR|GBP|JPY|CNY|KRW|INR|VND|THB|IDR|MYR|SGD|PHP|HKD|TWD|AUD|NZD|CAD|CHF|SEK|NOK|DKK|PLN|CZK|HUF|TRY|AED|"
    "ZAR|MXN|BRL|ARS|CLP|COP|PEN|EGP|MAD|ISK|ILS"
)
_CUR = rf"(?:US\$|CA\$|A\$|[$£€¥₫₩₹฿₱]|(?:{_CODES})(?=\s?\d))"
_AMT = r"\d[\d,]*(?:\.\d+)?"
MONEY_RE = re.compile(
    rf"(?P<cur>{_CUR})\s?(?P<a>{_AMT})(?P<ak>[kK])?(?:\s?(?:-|–|to)\s?(?:{_CUR})?\s?(?P<b>{_AMT})(?P<bk>[kK])?)?(?P<plus>\+)?"
)
DIST_RE = re.compile(
    r"(?<![\w$£€¥])(?P<a>\d+(?:\.\d+)?)(?:\s?(?:-|–|to)\s?(?P<b>\d+(?:\.\d+)?))?\s?(?P<u>miles?|mi|km|kilomet(?:er|re)s?)\b(?P<plus>\+)?",
    re.I,
)
APPROX_WORDS = ("~", "about", "around", "approx", "roughly", "circa", "c.")
FLOOR_WORDS = ("from", "starting at", "starts at", "at least", "over", "more than", "minimum")
CAP_WORDS = ("up to", "under", "at most", "less than", "max", "maximum")


RATE_RE = re.compile(
    r"^\s*(?:/|per\s+|a\s+|each\s+)(mo(?:nth)?|y(?:ea)?r)\b|^\s*(monthly|yearly|annually)\b",
    re.I,
)


def _num(text: str, k: str | None = None) -> float:
    return float(text.replace(",", "")) * (1000 if k else 1)


def bound_kind(before: str, plus: str | None, is_range: bool) -> str:
    low = before.lower()[-18:]
    if is_range:
        return "range"
    if plus or any(w in low for w in FLOOR_WORDS):
        return "floor"
    if any(w in low for w in CAP_WORDS):
        return "cap"
    return "single"


def is_approx(before: str) -> bool:
    return any(w in before.lower()[-14:] for w in APPROX_WORDS)


@dataclass(frozen=True)
class Quantity:
    kind: str  # price | distance
    unit: str  # currency symbol or 'km'
    shape: str  # single | range | floor | cap
    lo: float
    hi: float
    approx: bool
    start: int
    end: int
    text: str


def quantities(text: str) -> list[Quantity]:
    out = []
    for m in MONEY_RE.finditer(text):
        lo = _num(m.group("a"), m.group("ak"))
        hi = _num(m.group("b"), m.group("bk")) if m.group("b") else lo
        shape = bound_kind(text[: m.start()], m.group("plus"), bool(m.group("b")))
        cur = {"US$": "$", "USD": "$", "CA$": "CAD", "A$": "AUD"}.get(m.group("cur"), m.group("cur"))
        rate = RATE_RE.match(text[m.end() :])
        if rate:  # "$50/month" is a rate, not the same quantity as a one-off "$400"
            cur += "/" + ("month" if (rate.group(1) or rate.group(2)).lower().startswith(("mo", "month")) else "year")
        out.append(
            Quantity("price", cur, shape, lo, hi, is_approx(text[: m.start()]), m.start(), m.end(), m.group().strip())
        )
    for m in DIST_RE.finditer(text):
        factor = 1.609344 if m.group("u").lower().startswith("mi") else 1.0
        lo = float(m.group("a")) * factor
        hi = float(m.group("b")) * factor if m.group("b") else lo
        shape = bound_kind(text[: m.start()], m.group("plus"), bool(m.group("b")))
        out.append(
            Quantity(
                "distance", "km", shape, lo, hi, is_approx(text[: m.start()]), m.start(), m.end(), m.group().strip()
            )
        )
    return sorted(out, key=lambda q: q.start)


# --- dates -----------------------------------------------------------------------------------------------

_MON = r"(?:" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\.?"
_YEAR = r"(?:,?\s*(?P<y>(?:19|20)\d\d))?"
_RANGE = r"(?:\s?(?:-|–|—|to|through)\s?(?:(?P<m2>" + _MON + r")\s+)?(?P<d2>\d{1,2})(?:st|nd|rd|th)?)?"
_RANGE_SAME_MONTH = r"(?:\s?(?:-|–|—|to|through)\s?(?P<d2>\d{1,2})(?:st|nd|rd|th)?)?"
DATE_PATTERNS = (  # Month D[-D2|-Month2 D2][, YYYY]   and   D[-D2] Month[ YYYY]
    re.compile(r"\b(?P<m>" + _MON + r")\s+(?P<d>\d{1,2})(?:st|nd|rd|th)?" + _RANGE + _YEAR + r"\b", re.I),
    re.compile(
        r"\b(?P<d>\d{1,2})(?:st|nd|rd|th)?" + _RANGE_SAME_MONTH + r"\s+(?:of\s+)?(?P<m>" + _MON + r")" + _YEAR + r"\b",
        re.I,
    ),
)


@dataclass(frozen=True)
class DateMention:
    start: int
    end: int
    month: int
    day: int
    month2: int
    day2: int
    year: int | None
    text: str


def _month(name: str) -> int:
    return MONTHS[name.lower().rstrip(".")]


def _date_from(m: re.Match) -> DateMention | None:
    groups = m.groupdict()
    month = _month(groups["m"])
    day = int(groups["d"])
    d2 = int(groups["d2"]) if groups.get("d2") else day
    m2 = _month(groups["m2"]) if groups.get("m2") else month
    if not (1 <= day <= 31 and 1 <= d2 <= 31):
        return None
    return DateMention(m.start(), m.end(), month, day, m2, d2, int(groups["y"]) if groups.get("y") else None, m.group())


def dates_in(text: str) -> list[DateMention]:
    """Month-and-day mentions ("June 16-20, 2026", "18 June"). A bare month or year is not a date mention."""
    found: list[DateMention] = []
    for rx in DATE_PATTERNS:
        for m in rx.finditer(text):
            d = _date_from(m)
            if d and not any(o.start < d.end and d.start < o.end for o in found):
                found.append(d)
    return sorted(found, key=lambda d: d.start)


def safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def parse_any_date(value) -> date | None:
    """ISO (2026-03-01), 'March 1, 2026', '1 March 2026' or 'March 2026' (the 1st). None if it is not a date."""
    text = str(value or "").strip()
    iso = re.search(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)", text)
    if iso:
        return safe_date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
    for d in dates_in(text):
        if d.year:
            return safe_date(d.year, d.month, d.day)
    m = re.search(rf"\b({_MON})\s+(\d{{4}})\b", text, re.I)
    return safe_date(int(m.group(2)), MONTHS[m.group(1).lower().rstrip(".")], 1) if m else None

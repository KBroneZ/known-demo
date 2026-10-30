"""Travel rule (b): staleness. An event date or a year in the title already past, a review stamp that is only the
publish date, and prices stated with no as-of date (or an old one)."""

from __future__ import annotations

import re
from datetime import date

from .findings import WARN, Finding
from .loader import Clinic, Post
from .rules_structure import _key_line
from .spans import inside_citation
from .travel_text import MONTHS, dates_in, parse_any_date, quantities, safe_date, units

DEFAULT_REVIEW_MAX_AGE_DAYS = 180
DEFAULT_STAMP_GRACE_DAYS = 30
ASOF_UNIT_RE = re.compile(
    r"\b(?:as of|checked|reviewed|updated|verified|verification|confirmed|published|accessed|retrieved|last updated)\b",
    re.I,
)
PAST_RE = re.compile(
    r"\b(?:was|were|had|took place|held|ended|opened|closed|launched|founded|built|completed|last year|"
    r"previously|used to|ran|began in|since|fielded|surveyed|conducted|published|released|announced|reported|"
    r"introduced|changed|affected|switched|broke|raised|increased|rolled out|took effect|came into effect|signed|"
    r"amended|issued)\b",
    re.I,
)
ASOF_RE = re.compile(
    r"\b(?:as of|prices? (?:checked|verified|updated|confirmed)|(?:checked|verified|confirmed) (?:on|in)|"
    r"correct as of|current as of|accurate as of|last checked)\b",
    re.I,
)
PRICE_ASOF_RE = re.compile(r"prices?", re.I)
REVIEWED_RE = re.compile(r"\blast reviewed[:\s]+([^\n|]+)", re.I)


def _days(value, key: str, site: Clinic, default: int) -> int:
    return int(site.get(key, default) or default)


def check_title_year(post: Post, today: date) -> list[Finding]:
    title = str(post.frontmatter.get("title", ""))
    years = [int(y) for y in re.findall(r"\b((?:19|20)\d\d)\b", title)]
    if years and max(years) < today.year:
        return [
            Finding(
                "stale_year_title",
                WARN,
                _key_line(post, "title"),
                title,
                f"The title names {max(years)} but it is already {today.year}; "
                "update the title and the facts, or retire the post.",
            )
        ]
    return []


def _resolve_year(mention, post: Post) -> int | None:
    if mention.year:
        return mention.year
    title_years = [int(y) for y in re.findall(r"\b((?:19|20)\d\d)\b", str(post.frontmatter.get("title", "")))]
    if title_years:
        return max(title_years)
    published = parse_any_date(post.frontmatter.get("date"))
    if not published:
        return None
    year = published.year
    start = safe_date(year, mention.month, mention.day)
    return year + 1 if start and start < published else year


def _history(mention, end: date, text: str, published: date | None) -> bool:
    """A date from an earlier year than the post, or one that sits inside a '(source: ...)' citation, is history or
    a reference, not an event the post presents as coming."""
    return bool(published and end.year < published.year) or inside_citation(text, mention.start)


def check_event_dates(post: Post, today: date) -> list[Finding]:
    out = []
    published = parse_any_date(post.frontmatter.get("date"))
    for unit in units(post):
        if unit.skipped or ASOF_UNIT_RE.search(unit.text) or PAST_RE.search(unit.text):
            continue
        for d in dates_in(unit.text):
            year = _resolve_year(d, post)
            end = (
                safe_date(year + (1 if (d.month2, d.day2) < (d.month, d.day) else 0), d.month2, d.day2)
                if year
                else None
            )
            if end and end < today and not _history(d, end, unit.text, published):
                out.append(
                    Finding(
                        "event_date_past",
                        WARN,
                        unit.line,
                        d.text.strip(),
                        f"This date is already past ({end.isoformat()}) and the sentence is not written as history; "
                        "update it from the organiser's page or remove it.",
                    )
                )
    return out


def _review_stamp(post: Post) -> tuple[date | None, int]:
    value, line = post.frontmatter.get("last_reviewed"), _key_line(post, "last_reviewed")
    if value:
        return parse_any_date(value), line
    for lineno, text in post.prose:
        m = REVIEWED_RE.search(text)
        if m:
            return parse_any_date(m.group(1)), lineno
    return None, 0


def check_review(post: Post, site: Clinic, today: date) -> list[Finding]:
    published = parse_any_date(post.frontmatter.get("date"))
    stamp, line = _review_stamp(post)
    grace = _days(None, "stamp_grace_days", site, DEFAULT_STAMP_GRACE_DAYS)
    limit = _days(None, "review_max_age_days", site, DEFAULT_REVIEW_MAX_AGE_DAYS)
    if stamp and published and stamp == published and (today - published).days > grace:
        return [
            Finding(
                "review_stamp_is_publish_date",
                WARN,
                line,
                stamp.isoformat(),
                f"'Last reviewed' is the publish date and the post is {(today - published).days} days old; "
                "it reads as a template stamp, not a review.",
            )
        ]
    last = stamp or parse_any_date(post.frontmatter.get("updated")) or published
    if last and (today - last).days > limit:
        return [
            Finding(
                "review_overdue",
                WARN,
                line,
                last.isoformat(),
                f"Last review or update was {(today - last).days} days ago (limit {limit}); re-check the facts.",
            )
        ]
    return []


def _as_of_dates(post: Post) -> list[date]:
    found = []
    declared = parse_any_date(post.frontmatter.get("prices_as_of"))
    if declared:
        found.append(declared)
    for _, text in post.prose:
        has_price = any(q.kind == "price" for q in quantities(text))
        for m in ASOF_RE.finditer(text):
            if not (has_price or PRICE_ASOF_RE.match(m.group())):
                continue  # "as of December 2022" about luggage rules does not date the prices
            parsed = parse_any_date(text[m.end() : m.end() + 40])
            if parsed:
                found.append(parsed)
    return found


def check_prices_dated(post: Post, site: Clinic, today: date) -> list[Finding]:
    priced = [(u.line, q.text) for u in units(post) if not u.skipped for q in quantities(u.text) if q.kind == "price"]
    if not priced:
        return []
    first = priced[0]
    others = tuple(sorted({line for line, _ in priced} - {first[0]}))[
        :30
    ]  # the finding is about every line that states a price
    as_of = _as_of_dates(post)
    if not as_of:
        return [
            Finding(
                "price_no_as_of",
                WARN,
                first[0],
                first[1],
                "Prices are stated with no as-of date; add 'prices checked <month year>' near them.",
                also=others,
            )
        ]
    limit = _days(None, "review_max_age_days", site, DEFAULT_REVIEW_MAX_AGE_DAYS)
    newest = max(as_of)
    if (today - newest).days > limit:
        return [
            Finding(
                "price_as_of_old",
                WARN,
                first[0],
                newest.isoformat(),
                f"The newest as-of date for the prices is {(today - newest).days} days old (limit {limit}); "
                "re-check them.",
            )
        ]
    return []


def run(post: Post, site: Clinic, today: date) -> list[Finding]:
    return (
        check_title_year(post, today)
        + check_event_dates(post, today)
        + check_review(post, site, today)
        + check_prices_dated(post, site, today)
    )


__all__ = ["MONTHS", "run"]

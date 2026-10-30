"""Travel rules (c) unsupported first-hand claims and (d) the site's own ruleset from site.yaml.

Every check is switched on by the key that configures it: a site.yaml without `bylines` does not check bylines."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from . import links
from .findings import BLOCK, WARN, Finding
from .loader import Clinic, Post
from .negation import is_negated
from .rules_structure import DATE_RE, SLUG_RE, _key_line
from .travel_text import HEADING_RE, SKIP_SECTIONS, clean_markdown

REQUIRED_FIELDS = ("title", "description", "slug", "date", "updated", "author", "category")
MIN_EVIDENCE_WORDS = 25
NOT_CLAIMED = re.compile(
    r"(?:\bhaven'?t|\bhave not|\bhasn'?t|\bdidn'?t|\bdid not|\bnever|\bnot yet|"
    r"\bunable to|\bcouldn'?t|\bcan'?t)\s+(?:\w+\s+)?$",
    re.I,
)
VERIFIED_CLAIMS = (  # claims of testing or checking: need an evidence block (blocking)
    r"\b(?:we|i|our (?:team|editors?|writers?|reviewers?|staff))\s+(?:\w+\s+){0,2}?"
    r"(?:tested|verified|cross-?checked|cross-?referenced|inspected|audited|measured|vetted)\b",
    r"\beditor'?s?'? verification\b",
    r"\bour editors? (?:verified|checked|cross-?referenced|confirmed|tested)\b",
    r"\b(?:personally|independently) (?:tested|verified|checked)\b",
    r"\bhands-on (?:test|testing|review)\b|\bfirst-?hand (?:test|testing|experience)\b",
)
EXPERIENCE_CLAIMS = (  # a person says they were there or tried it (warn)
    r"\b(?:we|i|our (?:team|editors?|writers?|reviewers?|staff|contributors?))\s+(?:\w+\s+){0,2}?"
    r"(?:tried|stayed|visited|flew|ate|walked|hiked|drove|slept|dined|lived|spent|rode|timed|counted|queued|"
    r"checked|confirmed|compared|booked|sampled)\b",
)
PASSIVE_TESTED = re.compile(r"(?<![-\w])tested\s+(?:across|in|on|over|by us|by our)\b", re.I)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", text.lower()).strip()


def check_frontmatter(post: Post, site: Clinic) -> list[Finding]:
    if post.frontmatter_error:
        return [Finding("frontmatter_invalid", BLOCK, 1, post.frontmatter_error, "Frontmatter missing or unparseable.")]
    fm, out = post.frontmatter, []
    for key in REQUIRED_FIELDS:
        if not fm.get(key):
            out.append(Finding("frontmatter_missing_field", BLOCK, 1, key, f"Required field '{key}' is missing."))
    for key in ("date", "updated"):
        if fm.get(key) and not DATE_RE.match(str(fm[key])):
            out.append(
                Finding(
                    "frontmatter_bad_value",
                    BLOCK,
                    _key_line(post, key),
                    f"{key}: {fm[key]}",
                    f"'{key}' must be YYYY-MM-DD.",
                )
            )
    if fm.get("slug") and not SLUG_RE.match(str(fm["slug"])):
        out.append(
            Finding(
                "frontmatter_bad_value",
                BLOCK,
                _key_line(post, "slug"),
                f"slug: {fm['slug']}",
                "Slug must be lowercase-hyphenated.",
            )
        )
    bylines = {_norm(b) for b in site.get("bylines") or []}
    if bylines and fm.get("author") and _norm(re.sub(r"^by\s+", "", str(fm["author"]), flags=re.I)) not in bylines:
        out.append(
            Finding(
                "byline_not_allowed",
                BLOCK,
                _key_line(post, "author"),
                f"author: {fm['author']}",
                "The author is not on the site's byline list.",
            )
        )
    titles = {_norm(t) for t in site.get("author_titles") or []}
    if titles and fm.get("author_title") and _norm(str(fm["author_title"])) not in titles:
        out.append(
            Finding(
                "byline_title_not_allowed",
                BLOCK,
                _key_line(post, "author_title"),
                f"author_title: {fm['author_title']}",
                "The author's title is not one the site allows.",
            )
        )
    return out


def headings(post: Post) -> list[tuple[int, int, str]]:
    """(line, level, text) of every heading in the prose."""
    found = []
    for lineno, raw in post.prose:
        m = HEADING_RE.match(raw)
        if m:
            found.append((lineno, len(raw.strip()) - len(raw.strip().lstrip("#")), m.group(1)))
    return found


def check_sections(post: Post, site: Clinic) -> list[Finding]:
    have = [_norm(text) for _, _, text in headings(post)]
    return [
        Finding(
            "missing_required_section", BLOCK, 0, section, f"The site requires a '{section}' section in every post."
        )
        for section in site.get("required_sections") or []
        if not any(h.startswith(_norm(section)) for h in have)
    ]


def _scannable(text: str) -> str:
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return re.sub(r"<https?://[^>]*>|https?://\S+|`[^`]*`", " ", text)


def check_banned(post: Post, site: Clinic) -> list[Finding]:
    banned = [str(b) for b in site.get("banned_characters") or []]
    if not banned:
        return []
    lines = [(lineno, text) for lineno, text in post.prose]
    lines += [(_key_line(post, key), str(post.frontmatter.get(key, ""))) for key in ("title", "description")]
    out = []
    for lineno, text in lines:
        scan = _scannable(text)
        for char in banned:
            if char in scan:
                out.append(Finding("banned_character", WARN, lineno, char, f"The site's editorial rules ban '{char}'."))
    return out


def _is_affiliate(url: str, site: Clinic) -> bool:
    cfg = site.get("affiliate") or {}
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if any(host == h.lower() or host.endswith("." + h.lower()) for h in cfg.get("hosts") or []):
        return True
    query = {k.lower() for k in parse_qs(parsed.query)}
    return bool(query & {str(p).lower() for p in cfg.get("params") or []})


def check_affiliate(post: Post, site: Clinic) -> list[Finding]:
    phrases = [str(p).lower() for p in (site.get("affiliate") or {}).get("disclosure_phrases") or []]
    if not phrases:
        return []
    first = next(
        ((n, u) for n, u in links.extract_links(post) if u.startswith("http") and _is_affiliate(u, site)), None
    )
    disclosed = any(p in post.prose_text.lower() for p in phrases)
    if first and not disclosed:
        return [
            Finding(
                "affiliate_disclosure_missing",
                BLOCK,
                first[0],
                first[1][:100],
                "The post has an affiliate link but no affiliate disclosure (FTC 16 CFR 255; site rule).",
            )
        ]
    if not first and not disclosed and (site.get("affiliate") or {}).get("disclosure_on_every_post"):
        return [
            Finding(
                "affiliate_disclosure_missing",
                BLOCK,
                0,
                "",
                "The site's rules put an affiliate disclosure footer on every post, and this post has none.",
            )
        ]
    return []


def _evidence_ranges(post: Post, site: Clinic) -> tuple[bool, set[int]]:
    """(has a real evidence block, line numbers inside evidence sections)."""
    names = [_norm(n) for n in site.get("evidence_headings") or []]
    heads = headings(post)
    inside, real = set(), False
    for i, (lineno, level, text) in enumerate(heads):
        if not any(_norm(text).startswith(n) for n in names):
            continue
        end = next((h[0] for h in heads[i + 1 :] if h[1] <= level), 10**9)
        body = [(n, t) for n, t in post.prose if lineno < n < end]
        inside.update(n for n, _ in body)
        real = real or sum(len(t.split()) for _, t in body) >= MIN_EVIDENCE_WORDS
    return real, inside


def _denied(text: str, match: re.Match) -> bool:
    """'we have not tested', 'never tried', 'we haven't ...': the post says it did NOT do the thing."""
    return (
        bool(re.search(r"\b(?:not|never|no)\b|n't", match.group(), re.I))
        or is_negated(text, match.start())
        or bool(NOT_CLAIMED.search(text[: match.start()]))
    )


def _first_claim(text: str, patterns, passive: bool = False):
    for p in patterns:
        for m in re.finditer(p, text, re.I):
            if not _denied(text, m):
                return m
    if passive:
        return PASSIVE_TESTED.search(text)
    return None


def _source_lines(post: Post) -> set[int]:
    """Lines under a Sources/References heading: they quote other sites' headlines
    ("We Tested Them in 11 Countries")."""
    inside, active = set(), False
    for lineno, raw in post.prose:
        heading = HEADING_RE.match(raw)
        if heading:
            active = bool(SKIP_SECTIONS.match(heading.group(1).strip()))
        elif active:
            inside.add(lineno)
    return inside


def check_first_hand(post: Post, site: Clinic) -> list[Finding]:
    real, inside = _evidence_ranges(post, site)
    if real:
        return []
    inside = inside | _source_lines(post)
    out = []
    candidates = [(_key_line(post, key), str(post.frontmatter.get(key, "")), True) for key in ("title", "description")]
    for lineno, raw in post.prose:
        is_heading = bool(HEADING_RE.match(raw))
        candidates.append((lineno, clean_markdown(re.sub(r"^\s*#+\s*", "", raw)), is_heading))
    for lineno, text, passive_ok in candidates:
        if lineno in inside or not text.strip():
            continue
        strong = _first_claim(text, VERIFIED_CLAIMS, passive_ok)
        weak = None if strong else _first_claim(text, EXPERIENCE_CLAIMS)
        hit, severity = (strong, BLOCK) if strong else (weak, WARN)
        if hit:
            out.append(
                Finding(
                    "unsupported_first_hand_claim",
                    severity,
                    lineno,
                    hit.group().strip()[:90],
                    "A first-hand testing or verification claim with no evidence block (who tested, when, what) "
                    "in the post; add the evidence or rewrite it as sourced reporting.",
                )
            )
    return out


def run(post: Post, site: Clinic) -> list[Finding]:
    return (
        check_frontmatter(post, site)
        + check_sections(post, site)
        + check_banned(post, site)
        + check_affiliate(post, site)
        + check_first_hand(post, site)
    )

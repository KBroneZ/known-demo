"""Brand mention and citation extraction (regex/alias layer).

Deterministic, explainable, no network. An optional LLM judge (judge.py) can be
layered on top and reconciled with this output.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from urllib.parse import urlparse


@dataclass(frozen=True)
class Brand:
    id: str
    name: str
    aliases: tuple[str, ...] = ()
    domains: tuple[str, ...] = ()
    # What may be shared outside the machine (reports/numbers with --anonymize): "Practice A", practice-a.example
    public_id: str | None = None
    public_name: str | None = None
    public_domain: str | None = None

    @property
    def all_names(self) -> tuple[str, ...]:
        return (self.name, *self.aliases)


@dataclass(frozen=True)
class Mention:
    brand_id: str
    offset: int  # offset in the normalized text
    position: int  # 1 = first tracked brand named in the answer
    alias: str
    negative: bool = False


@dataclass
class Extraction:
    mentions: list[Mention] = field(default_factory=list)
    citations: list[tuple[str, str, str | None]] = field(default_factory=list)  # url, domain, brand_id

    @property
    def mentioned_ids(self) -> set[str]:
        return {m.brand_id for m in self.mentions}

    @property
    def cited_ids(self) -> set[str]:
        return {b for _, _, b in self.citations if b}


_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_POSSESSIVE = re.compile(r"['’]s\b")
_NEGATIVE_CUES = re.compile(
    r"\b(avoid|steer clear|not recommend|wouldn't recommend|would not recommend|"
    r"don't recommend|do not recommend|complaints? (?:about|against)|worst)\b"
)
_SENTENCE_END = re.compile(r"[.!?]\s")


def normalize(text: str) -> str:
    """Lowercase, strip accents/markdown, keep sentence punctuation.

    Sentence punctuation is kept on purpose: 'protect your oak. Dentistry is'
    must not match the brand alias 'oak dentistry'.
    """
    text = _MD_LINK.sub(r"\1", text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c)).casefold()
    text = text.replace("&", " and ")
    text = _POSSESSIVE.sub("", text)
    text = re.sub(r"['’`*_#]", "", text)
    text = re.sub(r"[-–—/]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _alias_regex(alias: str) -> re.Pattern[str]:
    tokens = normalize(alias).split(" ")
    body = r"\s+".join(re.escape(t) for t in tokens)
    return re.compile(rf"(?<![a-z0-9]){body}(?![a-z0-9])")


def find_mentions(text: str, brands: Sequence[Brand]) -> list[Mention]:
    """All tracked brands named in text, ordered by first appearance."""
    norm = normalize(text)
    spans: list[tuple[int, int, str, str]] = []
    for brand in brands:
        for alias in brand.all_names:
            for m in _alias_regex(alias).finditer(norm):
                spans.append((m.start(), m.end(), brand.id, alias))
    # longest match wins when spans of different brands overlap
    spans.sort(key=lambda s: -(s[1] - s[0]))
    accepted: list[tuple[int, int, str, str]] = []
    for s in spans:
        if any(s[2] != a[2] and s[0] < a[1] and a[0] < s[1] for a in accepted):
            continue
        accepted.append(s)
    first: dict[str, tuple[int, int, str]] = {}
    for start, end, bid, alias in accepted:
        if bid not in first or start < first[bid][0]:
            first[bid] = (start, end, alias)
    ordered = sorted(first.items(), key=lambda kv: kv[1][0])
    out = []
    for pos, (bid, (start, _end, alias)) in enumerate(ordered, start=1):
        out.append(Mention(bid, start, pos, alias, _is_negative(norm, start)))
    return out


def _is_negative(norm: str, start: int) -> bool:
    """Heuristic: a negative cue earlier in the same sentence as the mention."""
    sentence_start = 0
    for m in _SENTENCE_END.finditer(norm, 0, start):
        sentence_start = m.end()
    return bool(_NEGATIVE_CUES.search(norm[sentence_start:start]))


_URL = re.compile(r"https?://[^\s)\]>\"'<]+")


def urls_in_text(text: str) -> list[str]:
    """URLs written in an answer (markdown links or bare), in order, without duplicates."""
    seen: dict[str, None] = {}
    for m in _URL.finditer(text or ""):
        seen.setdefault(m.group(0).rstrip(".,;:!?"), None)
    return list(seen)


def domain_of(url: str) -> str:
    """Lowercase hostname without port and leading 'www.'; '' if unparseable."""
    url = url.strip()
    if not url:
        return ""
    if "://" not in url:
        url = "http://" + url
    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        return ""
    host = host.lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def host_matches(host: str, domain: str) -> bool:
    domain = domain.lower().removeprefix("www.")
    return bool(host) and (host == domain or host.endswith("." + domain))


def match_citations(urls: Iterable[str], brands: Sequence[Brand]) -> list[tuple[str, str, str | None]]:
    rows = []
    for url in urls:
        host = domain_of(url)
        brand_id = next(
            (b.id for b in brands if any(host_matches(host, d) for d in b.domains)),
            None,
        )
        rows.append((url, host, brand_id))
    return rows


def extract(answer: str, cited_urls: Iterable[str], brands: Sequence[Brand]) -> Extraction:
    return Extraction(
        mentions=find_mentions(answer or "", brands),
        citations=match_citations(cited_urls, brands),
    )

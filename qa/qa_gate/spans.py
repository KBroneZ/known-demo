"""Where inside a line a match sits: inside quotation marks, inside a citation, or in a question.

A phrase that is quoted, cited from another site or asked as a question is not a statement the post makes about
itself, so content rules use these helpers to skip such matches."""

from __future__ import annotations

import re

from .links import MD_URL

_CITE_OPEN = re.compile(r"\((?:sources?|via|per|cited by)\s*:", re.I)
_SOURCES_LINE = re.compile(r"^\s*(?:[-*]\s*)?sources?\s*:", re.I)


def inside_quotes(text: str, pos: int) -> bool:
    """True when `pos` lies between a pair of straight or curly double quotes on this line."""
    straight = text.count('"', 0, pos) % 2 == 1
    curly = text.count("“", 0, pos) > text.count("”", 0, pos)
    return straight or curly


def _paren_end(text: str, start: int) -> int:
    depth = 0
    for i in range(start, len(text)):
        depth += text[i] == "("
        depth -= text[i] == ")"
        if depth == 0:
            return i + 1
    return len(text)


def inside_citation(text: str, pos: int) -> bool:
    """True inside a '(source: ...)' parenthetical or on a line that starts with 'Sources:'."""
    if _SOURCES_LINE.match(text):
        return True
    return any(m.start() <= pos < _paren_end(text, m.start()) for m in _CITE_OPEN.finditer(text))


def inside_question(text: str, pos: int) -> bool:
    """True when the sentence holding `pos` ends with a question mark."""
    end = re.search(r"[.!?](?=\s|$|[\"'”)])", text[pos:])
    return bool(end) and text[pos + end.start()] == "?"


def quoted_or_cited(text: str, pos: int) -> bool:
    return inside_quotes(text, pos) or inside_citation(text, pos)


_LINK_TEXT = re.compile(rf"\[([^\]]*)\]\(\s*<?https?://{MD_URL}[^)]*\)")


def inside_link_text(text: str, pos: int) -> bool:
    """True when `pos` is in the anchor text of a link to another site: that text is usually the headline of a page."""
    return any(m.start(1) <= pos < m.end(1) for m in _LINK_TEXT.finditer(text))

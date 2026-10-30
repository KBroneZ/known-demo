"""Clause-bounded negation: is a match negated by a word attached to it, not by anything earlier in the sentence?

"No dentist can guarantee X" is negated; "There is no doubt that we guarantee X" and
"They are not cheap, but we guarantee X" are not. Only the clause that holds the match counts
(clause = text since the last . ! ? ; : , dash, or a conjunction such as but/and/yet), and only
negation words within the last few tokens before the match.
"""

from __future__ import annotations

import re

NEGATION_WORDS = frozenset(
    {
        "not",
        "no",
        "never",
        "nor",
        "without",
        "cannot",
        "can't",
        "cant",
        "don't",
        "dont",
        "doesn't",
        "doesnt",
        "won't",
        "wont",
        "isn't",
        "aren't",
        "wasn't",
        "weren't",
        "shouldn't",
        "couldn't",
        "wouldn't",
        "nobody",
        "neither",
    }
)
CLAUSE_BREAK_RE = re.compile(r"[.!?;:,\n—–]|\s-\s|\b(?:but|and|yet|however|although|though|while|so)\b", re.I)
WINDOW_TOKENS = 3
_TOKEN_RE = re.compile(r"[A-Za-z']+")


def clause_before(text: str, start: int) -> str:
    """Text of the clause that contains position `start`, up to `start`."""
    head = text[:start]
    last = 0
    for m in CLAUSE_BREAK_RE.finditer(head):
        last = m.end()
    return head[last:]


def is_negated(text: str, start: int, window: int = WINDOW_TOKENS) -> bool:
    tokens = [t.lower().replace("’", "'") for t in _TOKEN_RE.findall(clause_before(text, start).replace("’", "'"))]
    return any(t in NEGATION_WORDS for t in tokens[-window:])

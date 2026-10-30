"""Authorized external sources: a short pool of pages that were opened and are known to load."""

from __future__ import annotations

from pathlib import Path

from .clinicdata import PIPELINE_ROOT, miniyaml

POOL_PATH = PIPELINE_ROOT / "sources" / "authorized-sources.yaml"


def load_pool(path: Path = POOL_PATH) -> list[dict]:
    return miniyaml.loads(path.read_text(encoding="utf-8"))["sources"]


GENERIC = {"teeth", "tooth", "dental", "dentist", "dentists", "care", "family", "dentistry", "and", "the", "for"}


def pick_sources(keywords: list[str], pool: list[dict], limit: int = 3) -> list[dict]:
    """Sources whose `covers` terms overlap the topic keywords, best overlap first. Generic words never count."""
    words = {w.lower() for kw in keywords for w in kw.replace("-", " ").split() if len(w) > 2} - GENERIC
    scored = []
    for src in pool:
        terms = {w.lower() for c in src["covers"] for w in c.replace("-", " ").split() if len(w) > 2} - GENERIC
        score = len(words & terms)
        if score:
            scored.append((score, src))
    scored.sort(key=lambda pair: -pair[0])
    return [s for _, s in scored[:limit]]

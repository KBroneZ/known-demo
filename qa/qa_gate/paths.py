"""Paths written into reports must not reveal who ran the gate or where their disk is laid out."""

from __future__ import annotations

from pathlib import Path

DEMO_ROOT = Path(__file__).resolve().parent.parent.parent


def display_path(path: str | Path) -> str:
    """Posix path relative to the `demo/` folder, or just the file name when the path lies outside it."""
    p = Path(path)
    try:
        return p.resolve().relative_to(DEMO_ROOT).as_posix()
    except (ValueError, OSError):
        return p.as_posix() if not p.is_absolute() else p.name

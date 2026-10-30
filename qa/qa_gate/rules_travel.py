"""Travel profile: the deterministic rules for a site driven by a site.yaml with `profile: travel`."""

from __future__ import annotations

from datetime import date

from . import rules_travel_consistency, rules_travel_fresh, rules_travel_site
from .findings import Finding
from .loader import Clinic, Post

PROFILE = "travel"


def is_travel(site: Clinic) -> bool:
    return site.get("profile") == PROFILE


def run(post: Post, site: Clinic, today: date | None = None) -> list[Finding]:
    """Site ruleset (frontmatter, sections, banned characters, affiliate disclosure, byline), first-hand claims,
    staleness and in-post consistency. `today` is the check date; tests and evaluations pin it."""
    today = today or date.today()
    return (
        rules_travel_site.run(post, site)
        + rules_travel_fresh.run(post, site, today)
        + rules_travel_consistency.run(post, site, today)
    )

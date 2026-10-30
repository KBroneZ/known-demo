"""Anonymized view of results: real practice names never leave the machine.

Real names live in a git-ignored config (`config/austin_real.local.yaml`). Each brand there carries
`public_id` / `public_name` / `public_domain` ("practice-a", "Practice A", "practice-a.example"). With
`--anonymize` the report and numbers are built from the real database and then relabelled; lists of
other businesses are dropped (only their count is kept).
"""

from __future__ import annotations

import string
from dataclasses import replace

from .config import Config
from .extract import Brand, host_matches


def anonymize_config(cfg: Config) -> Config:
    """Config whose brands carry only public labels (used for rendering and for the example config)."""
    brands = []
    for i, b in enumerate(cfg.brands):
        letter = string.ascii_uppercase[i]
        pid = b.public_id or f"practice-{letter.lower()}"
        brands.append(
            Brand(
                id=pid,
                name=b.public_name or f"Practice {letter}",
                aliases=(),
                domains=(b.public_domain or f"{pid}.example",),
                public_id=pid,
                public_name=b.public_name or f"Practice {letter}",
                public_domain=b.public_domain or f"{pid}.example",
            )
        )
    return replace(cfg, brands=tuple(brands), notes=cfg.public_notes, name="austin-dental-first-batch")


def remap_data(data: dict, cfg: Config) -> dict:
    """Relabel a build() result: brand ids, tracked domains; drop the list of other business names."""
    pub = anonymize_config(cfg)
    ids = {b.id: p.id for b, p in zip(cfg.brands, pub.brands, strict=True)}
    domains = [(d, p.domains[0]) for b, p in zip(cfg.brands, pub.brands, strict=True) for d in b.domains]

    def public_domain(domain: str) -> str | None:
        return next((pd for d, pd in domains if host_matches(domain, d)), None)

    out = dict(data)
    out["rates"] = {ids[b]: v for b, v in data["rates"].items()}
    out["sov"] = {e: {ids[b]: x for b, x in v.items()} for e, v in data["sov"].items()}
    out["heat"] = {ids[b]: v for b, v in data["heat"].items()}
    out["examples"] = {
        e: {**ex, "reps": [{**r, "named": [ids[b] for b in r["named"]]} for r in ex["reps"]]}
        for e, ex in data["examples"].items()
    }
    tops = []
    for t in data["top_domains"]:
        pd = public_domain(t["domain"])
        tops.append({**t, "domain": pd} if pd else t)
    out["top_domains"] = tops
    out["other_businesses"] = []
    out["other_hidden"] = True
    return out


def anonymize_validation(result: dict, cfg: Config) -> dict:
    """Relabel an evaluate_real() result and drop free-text notes (they can quote real names)."""
    pub = anonymize_config(cfg)
    ids = {b.id: p.id for b, p in zip(cfg.brands, pub.brands, strict=True)}
    errors = [
        {
            **e,
            "note": "",
            "false_positive": [ids.get(x, x) for x in e["false_positive"]],
            "false_negative": [ids.get(x, x) for x in e["false_negative"]],
        }
        for e in result["errors"]
    ]
    return {**result, "errors": errors}

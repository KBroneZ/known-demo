#!/usr/bin/env python3
"""Build the seeded-error copies from the clean posts and write seeded-errors.json.

The ten errors below are the single source of truth: each one replaces `original` with
`injected` in one clean post. Re-run after editing a clean post:  python fixtures/build_seeded.py
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLEAN, SEEDED = HERE / "posts" / "clean", HERE / "posts" / "seeded"

P1, P2 = "01-how-often-dental-cleaning.md", "02-dental-implants-vs-bridges.md"
P3, P4 = "03-is-teeth-whitening-safe.md", "04-dental-emergency-austin.md"

ERRORS = [
    {
        "id": "E01",
        "file": P1,
        "category": "NAP mismatch (phone)",
        "rules": ["nap_phone_mismatch"],
        "description": "Phone number differs from the ficha.",
        "original": "You can reach us at (512) 555-0142, or visit us",
        "injected": "You can reach us at (512) 555-0187, or visit us",
        "snippet": "(512) 555-0187",
    },
    {
        "id": "E02",
        "file": P1,
        "category": "Typical AI phrases",
        "rules": ["ai_phrase"],
        "description": "Generic AI opener and 'delve'.",
        "original": "Ask five people how often they see the dentist and you will hear five answers.",
        "injected": (
            "In today's fast-paced world, maintaining a healthy smile is more important than ever. Let's delve into "
            "how often you should really see the dentist."
        ),
        "snippet": "In today's fast-paced world",
    },
    {
        "id": "E03",
        "file": P1,
        "category": "Broken link",
        "rules": ["link_broken"],
        "description": "Hallucinated NIDCR URL that returns 404.",
        "original": "https://www.nidcr.nih.gov/health-info/gum-disease)",
        "injected": "https://www.nidcr.nih.gov/health-info/gum-disease-treatment-guidelines-2026)",
        "snippet": "gum-disease-treatment-guidelines-2026",
    },
    {
        "id": "E04",
        "file": P2,
        "category": "Invented statistic, no source",
        "rules": ["unsourced_stat"],
        "description": "Made-up implant success figure with no citation.",
        "original": "and the choice depends on your health, your bone and your goals.",
        "injected": (
            "and the choice depends on your health, your bone and your goals. Studies show that 98% of dental implants "
            "are still working after 25 years."
        ),
        "snippet": "Studies show that 98%",
    },
    {
        "id": "E05",
        "file": P2,
        "category": "Prohibited promise",
        "rules": ["prohibited_promise"],
        "description": "Lifetime guarantee on an implant.",
        "original": "No dentist can predict exactly how long a restoration will last in your mouth.",
        "injected": "Our implants come with a lifetime guarantee, so your new tooth is guaranteed to last.",
        "snippet": "lifetime guarantee",
    },
    {
        "id": "E06",
        "file": P2,
        "category": "Incoherent schema",
        "rules": ["schema_mismatch"],
        "description": "JSON-LD author is a dentist who is not the post author nor on the roster.",
        "original": '"name": "Dr. Elena Marsh"}, "publisher"',
        "injected": '"name": "Dr. Brian Walsh"}, "publisher"',
        "snippet": '"name": "Dr. Brian Walsh"',
    },
    {
        "id": "E07",
        "file": P3,
        "category": "Invented testimonial",
        "rules": ["fake_testimonial"],
        "description": "Patient quote with no testimonial on file.",
        "original": "## Who should talk to a dentist first",
        "injected": (
            "> \"I was terrified of whitening, but Dr. Oyelaran made it painless and my smile has never looked "
            "better!\" — Jessica R., Austin patient\n\n## Who should talk to a dentist first"
        ),
        "snippet": "Jessica R., Austin patient",
    },
    {
        "id": "E08",
        "file": P3,
        "category": "Unsupported 'best dentist'",
        "rules": ["unsupported_superlative"],
        "description": "'Best dentist in Austin' with no basis.",
        "original": "Call (512) 555-0142 to book.",
        "injected": "Patients choose us because we are the best dentist in Austin. Call (512) 555-0142 to book.",
        "snippet": "the best dentist in Austin",
    },
    {
        "id": "E09",
        "file": P4,
        "category": "False/dangerous medical claim",
        "rules": ["medical_myth"],
        "description": "Says to scrub a knocked-out tooth with soap (it damages the root).",
        "original": "If it is dirty, rinse it gently with water. Do not scrub it.",
        "injected": "If it is dirty, scrub it clean with soap and water before putting it back.",
        "snippet": "scrub it clean with soap",
    },
    {
        "id": "E10",
        "file": P4,
        "category": "Chatbot residue",
        "rules": ["chatbot_residue"],
        "description": "'As an AI language model' left in the text.",
        "original": "This is general information and not a substitute for professional advice.",
        "injected": "As an AI language model, I cannot provide medical advice, but I hope this helps!",
        "snippet": "As an AI language model",
    },
]


def build() -> list[dict]:
    SEEDED.mkdir(parents=True, exist_ok=True)
    texts = {p.name: p.read_text(encoding="utf-8") for p in CLEAN.glob("*.md")}
    for err in ERRORS:
        text = texts[err["file"]]
        if text.count(err["original"]) != 1:
            raise SystemExit(f"{err['id']}: 'original' must occur exactly once in {err['file']}")
        texts[err["file"]] = text.replace(err["original"], err["injected"])
    for name, text in texts.items():
        (SEEDED / name).write_text(text, encoding="utf-8", newline="\n")
    out = []
    for err in ERRORS:
        lines = texts[err["file"]].splitlines()
        hits = [i + 1 for i, line in enumerate(lines) if err["snippet"] in line]
        if len(hits) != 1:
            raise SystemExit(f"{err['id']}: snippet must appear on exactly one line (found {hits})")
        out.append({**err, "file": f"seeded/{err['file']}", "line": hits[0]})
    return out


if __name__ == "__main__":
    errors = build()
    payload = {
        "description": "10 errors seeded into copies of the 4 clean posts. Built by fixtures/build_seeded.py.",
        "clinic": "Bluebonnet Hollow Dental (fictional)",
        "errors": errors,
    }
    (HERE / "seeded-errors.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(errors)} seeded errors in {len({e['file'] for e in errors})} posts")

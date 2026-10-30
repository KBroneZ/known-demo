from pathlib import Path

import pytest

from qa_gate.loader import load_clinic, parse_post_text

QA_ROOT = Path(__file__).resolve().parent.parent

BASE_FM = """---
title: "A Short Title"
description: "A description that is long enough to sit inside the recommended range for search snippets."
slug: a-short-title
date: 2026-09-01
updated: 2026-09-02
author: Dr. Elena Marsh
reviewed_by: Dr. Marcus Oyelaran
category: preventive-care
---
"""


@pytest.fixture(scope="session")
def clinic():
    return load_clinic(QA_ROOT / "fixtures" / "clinic.yaml")


@pytest.fixture
def make_post():
    def _make(body: str, frontmatter: str = BASE_FM):
        return parse_post_text(frontmatter + body)

    return _make


def rules_of(findings):
    return [f.rule for f in findings]

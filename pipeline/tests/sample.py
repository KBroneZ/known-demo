"""Shared sample draft, candidate and fakes for the tests."""

from datetime import date

from dental_pipeline import claude, runner, topics

GOOD = (
    '''---
title: "Is Professional Teeth Whitening Safe for Sensitive Teeth?"
description: "Whitening can cause short-term sensitivity. Here is what to ask your dentist before you start and \
what to expect."
faq:
  - question: "Can sensitive teeth be whitened?"
    answer: "Often yes, with a plan from your dentist, but a few mouths should wait."
---

Whitening is usually safe when a dentist checks your mouth first, though sensitive teeth need a plan. '''
    + " ".join(["Your dentist will look at enamel, gums and existing fillings before choosing a method."] * 30)
    + "\n"
)


def cand():
    return topics.Candidate(
        "Is whitening safe for sensitive teeth?",
        "Teeth whitening",
        "teeth-whitening",
        "whitening",
        "seed",
        "seed",
        0,
        0,
        "n/a",
    )


_FINDINGS = {
    "CORREGIR": [{"rule": "ai_phrase", "severity": "warn", "line": 3, "evidence": "delve", "message": "m"}],
    "BLOQUEAR": [
        {"rule": "prohibited_promise", "severity": "block", "line": 3, "evidence": "guarantee", "message": "m"}
    ],
}


def make_call(text, cost=0.04, stage="draft"):
    return claude.Call(stage, "sonnet", text, cost, 3.0, 1000, 800, 0)


def verdicts(*seq):
    """Fake review(): returns the next verdict from `seq` each time it is called."""
    it = iter(seq)

    def fake(post_file, site, work_dir, name, qa_model, use_model=True, offline=False, link_cache=None):
        v = next(it, "PUBLICAR")  # calls past the scripted ones (the final pre-publish check) pass
        return {
            "name": name,
            "rules_verdict": v,
            "rules_findings": _FINDINGS.get(v, []),
            "model": {"status": "skipped"},
            "verdict": v,
        }

    return fake


def run(env, monkeypatch, seq):
    """Run one post through the pipeline in `env`, with review() scripted to return `seq`."""
    site, tmp = env
    monkeypatch.setattr(runner.review, "review", verdicts(*seq))
    config = runner.Config(today=date(2026, 10, 30), use_model_qa=False)
    return runner.run_post(cand(), site, config, tmp / "out"), site, tmp

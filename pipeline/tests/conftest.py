import json
import shutil
from datetime import date

import pytest
from sample import GOOD, cand, make_call

from dental_pipeline import brief, clinicdata, draft, review, runner
from dental_pipeline.clinicdata import QA_ROOT
from qa_gate import links, llm


@pytest.fixture(scope="session")
def site_a():
    return clinicdata.load_site("clinic-a")


@pytest.fixture(scope="session")
def site_b():
    return clinicdata.load_site("clinic-b")


@pytest.fixture
def env(site_a, tmp_path, monkeypatch):
    """clinic-a with its posts folder and clinic.yaml in a temp dir, so publishing never touches the real site."""
    (tmp_path / "web" / "src" / "content" / "posts").mkdir(parents=True)
    shutil.copy(site_a.root / "clinic.yaml", tmp_path / "web" / "clinic.yaml")
    fake_site = type(site_a)(site_a.id, tmp_path / "web", site_a.clinic, dict(site_a.posts))
    monkeypatch.setattr(runner.claude, "call", lambda stage, prompt, model, system, **kw: make_call(GOOD, stage=stage))
    return fake_site, tmp_path


@pytest.fixture
def model_says(monkeypatch, site_a, tmp_path):
    """Run review() for real with a scripted `claude -p` answer, so the QA layer's own parsing is exercised."""
    cache = links.load_cache(QA_ROOT / "fixtures" / "link-cache.json")
    text = draft.assemble(
        draft.parse_answer(GOOD), brief.build_brief(site_a, cand()), "whitening-sensitive-teeth", date.today()
    )

    def _say(answer):
        monkeypatch.setattr(llm.shutil, "which", lambda name: "claude")
        payload = json.dumps({"result": answer, "total_cost_usd": 0.004})
        monkeypatch.setattr(llm, "_run", lambda *a, **k: (0, payload, ""))
        return review.review(text, site_a, tmp_path, "r0", "haiku", use_model=True, offline=True, link_cache=cache)

    return _say

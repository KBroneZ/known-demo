from pathlib import Path

from vistrack.config import load_config
from vistrack.validate import evaluate, load_gold

ROOT = Path(__file__).resolve().parent.parent


def test_gold_set_regression_floor():
    """Floor, not a target: first measured values were mention P=R=0.943, citation P=R=1.0, 36/40 exact."""
    cfg = load_config(ROOT / "config" / "austin_real.yaml")
    res = evaluate(load_gold(ROOT / "gold" / "gold_set.jsonl"), cfg.brands)
    assert res["n_items"] >= 40
    assert res["mentioned"]["precision"] >= 0.94 and res["mentioned"]["recall"] >= 0.94
    assert res["cited"]["precision"] == 1.0 and res["cited"]["recall"] == 1.0
    # the four documented hard cases are the only allowed misses
    assert {e["id"] for e in res["errors"]} <= {"g11", "g29", "g30", "g38"}


def test_gold_labels_use_known_brand_ids():
    cfg = load_config(ROOT / "config" / "austin_real.yaml")
    known = {b.id for b in cfg.brands}
    for item in load_gold(ROOT / "gold" / "gold_set.jsonl"):
        assert set(item["mentioned"]) <= known and set(item["cited"]) <= known

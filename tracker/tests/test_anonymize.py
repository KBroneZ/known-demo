import json
from pathlib import Path

from vistrack import db
from vistrack.analysis import build
from vistrack.anonymize import anonymize_config, anonymize_validation, remap_data
from vistrack.config import load_config
from vistrack.engines.base import RawResult
from vistrack.report import render
from vistrack.runner import _store_result

ROOT = Path(__file__).resolve().parent.parent

LOCAL = """
name: t
repetitions: 2
market: {city: Austin, region: Texas, country: US, timezone: America/Chicago, lat: 30.2, lng: -97.7, \
dfs_location_name: "Austin,Texas,United States"}
public_notes: Public note about Practice A only.
notes: Private note about Zeta Dental and Dr. Quimby.
brands:
  - {id: zeta-dental, name: Zeta Dental, aliases: [Dr. Quimby], domains: [zetadental.com], \
public_id: practice-a, public_name: Practice A, public_domain: practice-a.example}
  - {id: omega-smiles, name: Omega Smiles, domains: [omegasmiles.com]}
prompts: [{id: p01, text: "best dentist in Austin"}]
"""


class Eng:
    key, model, tool_version = "codex_cli", "m", "t"


def seeded(tmp_path):
    cfg_path = tmp_path / "c.local.yaml"
    cfg_path.write_text(LOCAL, encoding="utf-8")
    cfg = load_config(cfg_path)
    conn = db.connect(tmp_path / "t.db")
    p = type("P", (), {"id": "p01", "text": "best dentist in Austin"})()
    for rep, text in enumerate(
        ["Try Zeta Dental. See https://www.zetadental.com/x", "Dr. Quimby and Omega Smiles."], 1
    ):
        _store_result(
            cfg, conn, Eng(), p, rep, RawResult(answer_text=text, raw={"t": text}), "b", False, tmp_path / "raw", None
        )
    conn.execute("INSERT INTO other_business SELECT id, 'Secret Competitor Clinic' FROM run")
    conn.commit()
    return cfg, conn


def test_anonymize_config_uses_public_labels_and_falls_back_to_letters(tmp_path):
    cfg, _ = seeded(tmp_path)
    pub = anonymize_config(cfg)
    assert [(b.id, b.name, b.domains) for b in pub.brands] == [
        ("practice-a", "Practice A", ("practice-a.example",)),
        ("practice-b", "Practice B", ("practice-b.example",)),
    ]
    assert pub.notes == "Public note about Practice A only."


def test_remap_data_relabels_and_drops_other_businesses(tmp_path):
    cfg, conn = seeded(tmp_path)
    d = remap_data(build(conn, cfg, "b"), cfg)
    assert set(d["rates"]) == {"practice-a", "practice-b"} and d["rates"]["practice-a"]["codex_cli"]["k"] == 2
    assert d["other_businesses"] == [] and d["other_hidden"] and d["other_distinct"] == 1


def test_anonymized_report_has_no_real_names_but_local_report_does(tmp_path):
    cfg, conn = seeded(tmp_path)
    shared = render(conn, cfg, "b", tmp_path / "shared.html", anonymize=True).read_text(encoding="utf-8")
    local = render(conn, cfg, "b", tmp_path / "local.html").read_text(encoding="utf-8")
    for secret in ("Zeta", "zetadental", "Omega", "omegasmiles", "Quimby", "Secret Competitor"):
        assert secret not in shared, secret
    assert "Practice A" in shared
    assert "Zeta Dental" in local and "Secret Competitor Clinic" not in shared


def test_anonymize_validation_relabels_ids_and_drops_notes(tmp_path):
    cfg, _ = seeded(tmp_path)
    res = {
        "errors": [
            {
                "id": "run3",
                "who": "regex",
                "note": "mentions Zeta Dental",
                "false_positive": [],
                "false_negative": ["zeta-dental"],
            }
        ]
    }
    out = anonymize_validation(res, cfg)["errors"][0]
    assert out["note"] == "" and out["false_negative"] == ["practice-a"]
    assert "zeta" not in json.dumps(out).lower()


def test_shared_example_config_has_no_real_names():
    cfg = load_config(ROOT / "config" / "austin_real.yaml")
    assert all(b.name.startswith(("Practice", "The Practice")) for b in cfg.brands)
    assert all(d.endswith(".example") for b in cfg.brands for d in b.domains)

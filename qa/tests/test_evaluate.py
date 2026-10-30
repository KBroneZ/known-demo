import evaluate
import pytest


def _err(**kw):
    base = {
        "id": "E1",
        "snippet": "lifetime guarantee",
        "injected": "Our implants come with a lifetime guarantee, so it lasts.",
        "rules": ["prohibited_promise"],
        "line": 5,
        "file": "seeded/x.md",
    }
    return {**base, **kw}


def test_model_quote_must_overlap_the_injected_text():
    err = _err()
    assert evaluate._matches(err, "Our implants come with a lifetime guarantee, so it lasts.")
    assert evaluate._matches(err, "come with a LIFETIME   guarantee")
    # same paragraph, different sentence: the loose old matcher would have counted this as a hit
    assert not evaluate._matches(err, "Habits such as grinding your teeth and smoking play a part.")
    assert not evaluate._matches(err, "short")


def test_curly_quotes_are_normalised():
    err = _err(snippet="dentist’s advice", injected="")
    assert evaluate._matches(err, "follow your dentist's advice carefully")


def test_snapshot_without_missed_line_raises(tmp_path):
    errors = [{"id": "H01"}, {"id": "H02"}]
    snap = tmp_path / "snap.md"
    snap.write_text("# header reworded\n- **Recall:** 10/10\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Missed"):
        evaluate.snapshot_ids(errors, str(snap))


def test_snapshot_parses_missed_and_none(tmp_path):
    errors = [{"id": "H01"}, {"id": "H02"}, {"id": "H03"}]
    snap = tmp_path / "snap.md"
    snap.write_text("- **Missed:** H01, H03\n", encoding="utf-8")
    assert evaluate.snapshot_ids(errors, str(snap)) == {"H02"}
    snap.write_text("- **Missed:** none\n", encoding="utf-8")
    assert evaluate.snapshot_ids(errors, str(snap)) == {"H01", "H02", "H03"}
    snap.write_text("- **Missed:** H99\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unknown"):
        evaluate.snapshot_ids(errors, str(snap))

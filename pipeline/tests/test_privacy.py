"""Reports and run files must not carry the absolute path of the machine that made them."""

from pathlib import Path

from qa_gate.paths import DEMO_ROOT, display_path

USER_MARKERS = ("C:" + "/Users", "C:" + chr(92) + "Users", "and" + "ia")  # split so this file does not match itself
TEXT_SUFFIXES = {".json", ".md", ".yaml", ".txt", ".py", ".patch", ".diff"}


def test_display_path_is_relative_to_demo():
    assert display_path(DEMO_ROOT / "web" / "sites" / "clinic-a" / "x.md") == "web/sites/clinic-a/x.md"
    shown = display_path("reports/prompts/a.md")  # a relative path is resolved against the working directory
    assert not Path(shown).is_absolute() and shown.endswith("reports/prompts/a.md")


def test_paths_outside_demo_keep_only_the_file_name(tmp_path):
    outside = tmp_path / "secret-folder" / "post.md"
    outside.parent.mkdir()
    outside.write_text("x")
    assert display_path(outside) == "post.md"


def test_no_generated_or_source_file_names_the_user():
    hits = []
    for folder in ("qa", "pipeline"):
        for path in (DEMO_ROOT / folder).rglob("*"):
            if (
                not path.is_file()
                or path.suffix not in TEXT_SUFFIXES
                or "__pycache__" in path.parts
                or ".pytest_cache" in path.parts
            ):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if any(marker in text for marker in USER_MARKERS):
                hits.append(path.relative_to(DEMO_ROOT).as_posix())
    assert hits == []

"""Publishing registers /blog/<slug> in clinic.yaml `pages`, and changes nothing else."""

from sample import run

from dental_pipeline import runner, sitefiles
from qa_gate import miniyaml


def pages_of(tmp):
    return miniyaml.loads((tmp / "web" / "clinic.yaml").read_text(encoding="utf-8"))["pages"]


def test_publishing_adds_exactly_one_route_line(env, monkeypatch):
    _site, tmp = env
    before = (tmp / "web" / "clinic.yaml").read_text(encoding="utf-8")
    res, *_ = run(env, monkeypatch, ["PUBLICAR"])
    after = (tmp / "web" / "clinic.yaml").read_text(encoding="utf-8")
    assert res["pages_route_added"] is True and f"/blog/{res['slug']}" in pages_of(tmp)
    assert len(after.splitlines()) == len(before.splitlines()) + 1
    assert [line for line in before.splitlines() if line not in after.splitlines()] == []
    assert [line for line in after.splitlines() if line not in before.splitlines()] == [f"  - /blog/{res['slug']}"]


def test_nothing_is_added_when_the_post_is_not_published(env, monkeypatch):
    _site, tmp = env
    before = (tmp / "web" / "clinic.yaml").read_text(encoding="utf-8")
    run(env, monkeypatch, ["BLOQUEAR"])
    assert (tmp / "web" / "clinic.yaml").read_text(encoding="utf-8") == before


def test_route_registration_is_idempotent_and_goes_after_the_last_blog_route(tmp_path):
    path = tmp_path / "clinic.yaml"
    path.write_text("name: X\npages:\n  - /\n  - /blog\n  - /blog/a\n  - /contact\nother: 1\n", encoding="utf-8")
    assert sitefiles.add_page_route(path, "/blog/b") is True
    assert sitefiles.add_page_route(path, "/blog/b") is False
    assert (
        path.read_text(encoding="utf-8")
        == "name: X\npages:\n  - /\n  - /blog\n  - /blog/a\n  - /blog/b\n  - /contact\nother: 1\n"
    )


def test_site_without_a_pages_list_is_left_alone(tmp_path):
    path = tmp_path / "clinic.yaml"
    path.write_text("name: X\nother: 1\n", encoding="utf-8")
    assert sitefiles.add_page_route(path, "/blog/b") is False
    assert path.read_text(encoding="utf-8") == "name: X\nother: 1\n"


def test_crlf_files_keep_their_line_endings(tmp_path):
    path = tmp_path / "clinic.yaml"
    path.write_bytes(b"name: X\r\npages:\r\n  - /\r\n  - /blog\r\n")
    sitefiles.add_page_route(path, "/blog/z")
    assert path.read_bytes() == b"name: X\r\npages:\r\n  - /\r\n  - /blog\r\n  - /blog/z\r\n"


def test_list_item_on_the_last_line_without_newline(tmp_path):
    path = tmp_path / "clinic.yaml"
    path.write_text("pages:\n  - /blog", encoding="utf-8")
    sitefiles.add_page_route(path, "/blog/z")
    assert path.read_text(encoding="utf-8") == "pages:\n  - /blog\n  - /blog/z\n"


def test_failed_registration_rolls_the_post_back(env, monkeypatch):
    def boom(path, route):
        raise sitefiles.PagesEditError("disk full")

    monkeypatch.setattr(runner.sitefiles, "add_page_route", boom)
    res, site, _ = run(env, monkeypatch, ["PUBLICAR"])
    assert res["status"] == "needs-human" and "nothing was published" in res["error"]
    assert list(site.posts_dir.glob("*.md")) == []


def test_sync_registers_existing_posts_once(tmp_path):
    posts = tmp_path / "src" / "content" / "posts"
    posts.mkdir(parents=True)
    (posts / "one.md").write_text("---\nslug: one\n---\nx", encoding="utf-8")
    (posts / "two.md").write_text("---\nslug: two\n---\nx", encoding="utf-8")
    (tmp_path / "clinic.yaml").write_text("pages:\n  - /\n  - /blog/one\n", encoding="utf-8")
    assert sitefiles.sync_posts(tmp_path) == ["/blog/two"]
    assert sitefiles.sync_posts(tmp_path) == []


def test_approve_also_registers_the_route(env, monkeypatch):
    res, site, tmp = run(env, monkeypatch, ["CORREGIR", "CORREGIR", "CORREGIR"])
    assert f"/blog/{res['slug']}" not in pages_of(tmp)
    runner.approve(tmp / "out" / res["dir"], site, "Andrew")
    assert f"/blog/{res['slug']}" in pages_of(tmp)

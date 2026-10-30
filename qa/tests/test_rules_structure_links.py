import json

from conftest import BASE_FM, rules_of

from qa_gate import links
from qa_gate import rules_structure as rs
from qa_gate.findings import BLOCK, INFO, WARN, Finding, verdict_for, worst_verdict
from qa_gate.loader import parse_post_text


def _schema(**overrides):
    block = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": "A Short Title",
        "datePublished": "2026-09-01",
        "dateModified": "2026-09-02",
        "author": {"@type": "Person", "name": "Dr. Elena Marsh"},
        "publisher": {"@type": "Dentist", "name": "Bluebonnet Hollow Dental"},
        "url": "https://www.bluebonnethollowdental.example/blog/a-short-title",
    }
    block.update(overrides)
    return f'Body.\n<script type="application/ld+json">\n{json.dumps(block)}\n</script>\n'


def test_valid_frontmatter_and_schema_pass(make_post, clinic):
    assert rs.run(make_post(_schema()), clinic) == []


def test_missing_frontmatter_blocks(clinic):
    findings = rs.check_frontmatter(parse_post_text("Just text"), clinic)
    assert rules_of(findings) == ["frontmatter_invalid"]


def test_missing_required_field(make_post, clinic):
    fm = BASE_FM.replace("reviewed_by: Dr. Marcus Oyelaran\n", "")
    assert "frontmatter_missing_field" in rules_of(rs.check_frontmatter(make_post("x", fm), clinic))


def test_bad_date_and_updated_before_date(make_post, clinic):
    fm = BASE_FM.replace("date: 2026-09-01", "date: 09/01/2026")
    assert "frontmatter_bad_value" in rules_of(rs.check_frontmatter(make_post("x", fm), clinic))
    fm = BASE_FM.replace("updated: 2026-09-02", "updated: 2026-08-01")
    assert "frontmatter_bad_value" in rules_of(rs.check_frontmatter(make_post("x", fm), clinic))


def test_author_must_be_on_roster(make_post, clinic):
    fm = BASE_FM.replace("author: Dr. Elena Marsh", "author: Dr. Brian Walsh")
    assert "dentist_not_in_roster" in rules_of(rs.check_frontmatter(make_post("x", fm), clinic))


def test_description_length_warns(make_post, clinic):
    fm = BASE_FM.replace(
        'description: "A description that is long enough to sit inside the recommended range for search snippets."',
        'description: "Too short."',
    )
    findings = rs.check_frontmatter(make_post("x", fm), clinic)
    assert [f.severity for f in findings if f.rule == "frontmatter_length"] == [WARN]


def test_missing_schema_warns(make_post, clinic):
    assert rules_of(rs.check_schema(make_post("No schema."), clinic)) == ["schema_missing"]


def test_invalid_json_blocks(make_post, clinic):
    body = '<script type="application/ld+json">\n{"@context": }\n</script>\n'
    assert "schema_invalid_json" in rules_of(rs.check_schema(make_post(body), clinic))


def test_schema_mismatches_block(make_post, clinic):
    for override in (
        {"headline": "Other"},
        {"datePublished": "2026-01-01"},
        {"author": {"@type": "Person", "name": "Dr. Brian Walsh"}},
        {"publisher": {"name": "Other Dental"}},
        {"url": "https://x.example/blog/other"},
        {"telephone": "(512) 555-0100"},
    ):
        findings = rs.check_schema(make_post(_schema(**override)), clinic)
        assert "schema_mismatch" in rules_of(findings), override


def test_schema_line_points_at_json_not_tag(make_post, clinic):
    post = make_post(_schema(headline="Other"))
    finding = rs.check_schema(post, clinic)[0]
    assert "headline" in post.lines[finding.line - 1]


def test_faq_must_match_visible_text(make_post, clinic):
    faq = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": "Does it hurt?", "acceptedAnswer": {"@type": "Answer", "text": "Not much."}}
        ],
    }
    page = f'Does it hurt?\n\nNot much.\n<script type="application/ld+json">\n{json.dumps(faq)}\n</script>\n'
    assert "schema_mismatch" not in rules_of(rs.check_schema(make_post(_schema() + page), clinic))
    bad = page.replace('Not much.\n<script', 'Never.\n<script', 1)
    assert "schema_mismatch" in rules_of(rs.check_schema(make_post(_schema() + bad), clinic))


# links ---------------------------------------------------------------------


def test_extract_links_markdown_and_bare(make_post):
    post = make_post("See [a](https://a.example/x) and https://b.example/y. Also [i](/blog) and [m](mailto:a@b.c).")
    urls = [u for _, u in links.extract_links(post)]
    assert "https://a.example/x" in urls and "https://b.example/y" in urls and "/blog" in urls
    assert urls.count("https://a.example/x") == 1


def test_extract_links_keeps_balanced_parentheses_in_the_url(make_post):
    post = make_post(
        "See [Ferry (boat)](https://wiki.example/wiki/Ferry_(boat)) and [b](https://b.example/a_(x)_(y)).\n\n"
        "Then (see [c](https://c.example/z)) after."
    )
    urls = [u for _, u in links.extract_links(post)]
    assert urls == ["https://wiki.example/wiki/Ferry_(boat)", "https://b.example/a_(x)_(y)", "https://c.example/z"]


def test_internal_links_checked_against_ficha(make_post, clinic):
    post = make_post(
        "[ok](/services/cleanings-exams) [gone](/services/veneers) "
        "[abs](https://www.bluebonnethollowdental.example/blog/)"
    )
    findings, _ = links.check_links(post, clinic, offline=True)
    assert [(f.rule, f.evidence) for f in findings] == [("link_broken_internal", "/services/veneers")]


def test_offline_uses_cache_and_flags_unknown_as_warn(make_post, clinic):
    post = make_post("[a](https://a.example/ok) [b](https://a.example/dead) [c](https://a.example/new)")
    today = __import__("datetime").date.today().isoformat()
    cache = {
        "https://a.example/ok": {"status": 200, "checked": today},
        "https://a.example/dead": {"status": 404, "checked": today},
    }
    findings, fresh = links.check_links(post, clinic, offline=True, cache=cache)
    by_url = {f.evidence: f for f in findings}
    assert fresh == {}
    assert by_url["https://a.example/dead"].rule == "link_broken" and by_url["https://a.example/dead"].severity == BLOCK
    assert (
        by_url["https://a.example/new"].rule == "link_unverified" and by_url["https://a.example/new"].severity == WARN
    )
    assert "https://a.example/ok" not in by_url


def test_classify_statuses():
    f = links.classify
    assert f(1, "u", {"status": 200}, False) is None
    assert f(1, "u", {"status": 301}, False) is None
    assert f(1, "u", {"status": 404}, False).severity == BLOCK
    assert f(1, "u", {"status": 410}, False).severity == BLOCK
    assert f(1, "u", {"error": "nxdomain"}, False).severity == BLOCK
    assert f(1, "u", {"error": "dns_temp"}, False).severity == WARN
    assert f(1, "u", {"status": 403}, False).severity == WARN
    assert f(1, "u", {"error": "timeout"}, False).severity == WARN


def test_online_mode_uses_fetch(make_post, clinic, monkeypatch):
    calls = []
    monkeypatch.setattr(links, "fetch_status", lambda url, timeout=0: calls.append(url) or {"status": 404})
    post = make_post("[a](https://a.example/x)\n\n[again](https://a.example/x)")
    findings, fresh = links.check_links(post, clinic, offline=False)
    assert calls == ["https://a.example/x"]  # deduplicated
    assert len(findings) == 2 and fresh == {"https://a.example/x": {"status": 404}}


# verdicts ------------------------------------------------------------------


def test_verdict_logic():
    block = Finding("r", BLOCK, 1, "", "")
    warn = Finding("r", WARN, 1, "", "")
    info = Finding("r", INFO, 1, "", "")
    assert verdict_for([]) == "PUBLICAR"
    assert verdict_for([info]) == "PUBLICAR"
    assert verdict_for([info, warn]) == "CORREGIR"
    assert verdict_for([warn, block]) == "BLOQUEAR"
    assert worst_verdict("PUBLICAR", "BLOQUEAR", "CORREGIR") == "BLOQUEAR"


def test_frontmatter_findings_point_at_the_key_line(make_post, clinic):
    fm = BASE_FM.replace("author: Dr. Elena Marsh", "author: Dr. Priya Shah")
    post = make_post("x", fm)
    finding = next(f for f in rs.check_frontmatter(post, clinic) if f.rule == "dentist_not_in_roster")
    assert post.lines[finding.line - 1].startswith("author:")


def test_dns_failure_is_retried_once(monkeypatch):
    calls = []

    def fake(url, timeout):
        calls.append(url)
        return {"error": "dns_temp"} if len(calls) == 1 else {"status": 200}

    monkeypatch.setattr(links, "_fetch_once", fake)
    monkeypatch.setattr(links.time, "sleep", lambda s: None)
    assert links.fetch_status("https://x.example/") == {"status": 200}
    assert len(calls) == 2


def test_head_404_falls_back_to_get(monkeypatch):
    import urllib.error
    import urllib.request

    class Resp:
        status = 200

        def geturl(self):
            return "https://x.example/"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=0):
        if req.get_method() == "HEAD":
            raise urllib.error.HTTPError(req.full_url, 404, "nf", {}, None)
        return Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert links._fetch_once("https://x.example/", 1)["status"] == 200


def test_get_404_is_still_dead(monkeypatch):
    import urllib.error
    import urllib.request

    def fake_urlopen(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 404, "nf", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert links._fetch_once("https://x.example/", 1) == {"status": 404}


def _post_with_ld(make_post, payload) -> object:
    return make_post(f'Body.\n<script type="application/ld+json">\n{json.dumps(payload)}\n</script>\n')


def test_malformed_json_ld_never_crashes(make_post, clinic):
    base = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": "A Short Title",
        "datePublished": "2026-09-01",
        "dateModified": "2026-09-02",
    }
    weird = [
        {**base, "publisher": "Bluebonnet Hollow Dental", "author": "Dr. Elena Marsh"},
        {**base, "publisher": ["x"], "author": ["Dr. Elena Marsh"]},
        {**base, "publisher": None, "author": 42, "url": {"@id": "https://x.example/a-short-title"}},
        {**base, "publisher": {"telephone": 5125550142}},
        {**base, "@type": ["BlogPosting", "Article"]},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": {"@type": "Question", "name": "Q?"}},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": ["just a string", None, 3]},
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": ["Q?"], "acceptedAnswer": [{"text": "a"}]}],
        },
        [base, "string", 5],
        "just a string",
    ]
    for payload in weird:
        rs.run(_post_with_ld(make_post, payload), clinic)  # must not raise


def test_publisher_as_string_is_compared(make_post, clinic):
    payload = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": "A Short Title",
        "datePublished": "2026-09-01",
        "dateModified": "2026-09-02",
        "publisher": "Other Dental",
    }
    assert "schema_mismatch" in rules_of(rs.check_schema(_post_with_ld(make_post, payload), clinic))


def test_nested_publisher_telephone_is_checked(make_post, clinic):
    payload = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "publisher": {"name": "Bluebonnet Hollow Dental", "telephone": "(512) 555-0199"},
    }
    findings = rs.check_schema(_post_with_ld(make_post, payload), clinic)
    assert any(f.rule == "schema_mismatch" and "telephone" in f.evidence for f in findings)


# H4 / M3 / M4 ----------------------------------------------------------------


def test_offline_cache_miss_never_gives_publish(make_post, clinic):
    post = make_post("See [a source](https://www.nidcr.nih.gov/health-info/totally-fake-page-xyz).")
    findings, _ = links.check_links(post, clinic, offline=True, cache={})
    assert verdict_for(findings) == "CORREGIR"
    assert rules_of(findings) == ["link_unverified"]


def test_stale_cache_entry_counts_as_a_miss():
    from datetime import date

    cache = {"u": {"status": 200, "checked": "2026-01-01"}}
    assert links.cache_lookup(cache, "u", 30, today=date(2026, 1, 20)) == cache["u"]
    assert links.cache_lookup(cache, "u", 30, today=date(2026, 3, 1)) is None
    assert links.cache_lookup(cache, "u", None, today=date(2030, 1, 1)) == cache["u"]
    assert links.cache_lookup({"u": {"status": 200}}, "u", 30) is None  # undated entries are not trusted
    assert links.cache_lookup({}, "u", 30) is None


def test_only_definitive_results_are_persisted():
    assert links.is_persistable({"status": 200}) and links.is_persistable({"status": 404})
    assert links.is_persistable({"error": "nxdomain"})
    for result in ({"status": 503}, {"status": 429}, {"status": 403}, {"error": "timeout"}, {"error": "dns_temp"}):
        assert not links.is_persistable(result), result


def test_redirect_to_home_is_a_soft_404_warning():
    result = {"status": 200, "final": "https://x.example/"}
    finding = links.classify(1, "https://x.example/guides/old-page", result, False)
    assert finding.rule == "link_redirects_home" and finding.severity == WARN
    assert links.classify(1, "https://x.example/", result, False) is None


def test_relative_links_are_resolved_and_checked(make_post, clinic):
    post = make_post("[ok](../services/cleanings-exams) [also ok](/blog) [bad](services/does-not-exist) [bad2](../x)")
    findings, _ = links.check_links(post, clinic, offline=True)
    assert sorted(f.evidence for f in findings) == ["../x", "services/does-not-exist"]
    assert {f.rule for f in findings} == {"link_broken_internal"}


class _Handler:
    """Local HTTP server: /ok -> 200, /gone -> 404 (HEAD and GET), /headfail -> HEAD 404 but GET 200,
    /old -> 302 to /."""


def _serve():
    import http.server
    import threading

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _answer(self, head):
            if self.path == "/ok" or (self.path == "/headfail" and not head):
                self.send_response(200)
            elif self.path == "/old":
                self.send_response(302)
                self.send_header("Location", "/")
            elif self.path == "/":
                self.send_response(200)
            else:
                self.send_response(404)
            self.end_headers()

        def do_HEAD(self):
            self._answer(True)

        def do_GET(self):
            self._answer(False)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_live_fetch_against_a_local_server():
    server = _serve()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        assert links.fetch_status(f"{base}/ok")["status"] == 200
        assert links.fetch_status(f"{base}/gone")["status"] == 404
        assert links.fetch_status(f"{base}/headfail")["status"] == 200
        old = links.fetch_status(f"{base}/old")
        assert old["status"] == 200 and old["final"].rstrip("/") == base
        assert links.classify(1, f"{base}/old", old, False).rule == "link_redirects_home"
    finally:
        server.shutdown()

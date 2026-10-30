"""Review 08 / M7 and L9: raw HTML, dangerous link schemes, and links that point at the local machine."""

import pytest
from conftest import rules_of

from qa_gate import links
from qa_gate import rules_content as rc


@pytest.mark.parametrize(
    "text",
    [
        "Call us. <script>alert(1)</script>",
        'See <iframe src="https://evil.example"></iframe> below.',
        '<img src=x onerror="alert(1)">',
        "Text <style>body{display:none}</style>",
        "<!-- hidden note -->",
        '<a href="https://x.example">click</a>',
        "line with </div> closing",
        "<br/>",
    ],
)
def test_raw_html_is_blocked(make_post, clinic, text):
    findings = rc.check_raw_html(make_post(text), clinic)
    assert rules_of(findings) == ["raw_html"] and findings[0].severity == "block"


@pytest.mark.parametrize(
    "text",
    [
        "Plain text with a < b and c > d comparison.",
        "Read <https://www.nidcr.nih.gov/health-info/tooth-decay> for details.",
        "Mail us at <hello@example.org>.",
        "Use the **bold** and `code` Markdown freely.",
    ],
)
def test_markdown_and_autolinks_are_not_raw_html(make_post, clinic, text):
    assert rc.check_raw_html(make_post(text), clinic) == []


def test_json_ld_script_block_is_not_prose(make_post, clinic):
    body = 'Body.\n<script type="application/ld+json">\n{"a": 1}\n</script>\n'
    assert rc.check_raw_html(make_post(body), clinic) == []


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "JavaScript:alert(1)",
        "data:text/html;base64,PHNjcmlwdD4=",
        "vbscript:msgbox(1)",
        "file:///etc/passwd",
        "ftp://x.example/file",
        "JAVASCRIPT:void(0)",
    ],
)
def test_dangerous_schemes_block(make_post, clinic, url):
    post = make_post(f"Click [here]({url}) now.")
    findings, _ = links.check_links(post, clinic, offline=True)
    assert rules_of(findings) == ["link_bad_scheme"], url
    assert findings[0].severity == "block"


@pytest.mark.parametrize(
    "url", ["mailto:hello@example.org", "tel:+15125550142", "https://www.mouthhealthy.org/", "/contact", "#top"]
)
def test_normal_schemes_are_left_alone(make_post, clinic, url):
    findings, _ = links.check_links(make_post(f"[x]({url})"), clinic, offline=True)
    assert "link_bad_scheme" not in rules_of(findings)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8080/admin",
        "http://127.0.0.1/",
        "http://10.0.0.5/x",
        "http://192.168.1.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://2130706433/",
        "http://0x7f000001/",
        "http://printer.local/",
        "http://intranet/",
        "http://db.internal/x",
    ],
)
def test_private_hosts_are_blocked_and_never_fetched(make_post, clinic, url, monkeypatch):
    called = []
    monkeypatch.setattr(links, "fetch_status", lambda u, timeout=0: called.append(u) or {"status": 200})
    findings, fresh = links.check_links(make_post(f"[x]({url})"), clinic, offline=False)
    assert rules_of(findings) == ["link_private_host"] and findings[0].severity == "block"
    assert called == [] and fresh == {}


def test_public_hosts_are_still_checked(make_post, clinic, monkeypatch):
    called = []
    monkeypatch.setattr(links, "fetch_status", lambda u, timeout=0: called.append(u) or {"status": 200})
    findings, _ = links.check_links(
        make_post("[x](https://www.nidcr.nih.gov/health-info/tooth-decay) [y](http://8.8.8.8/)"), clinic
    )
    assert findings == [] and len(called) == 2


def test_is_private_host_unit():
    for host in (
        "localhost",
        "LOCALHOST",
        "127.0.0.1",
        "10.1.2.3",
        "172.16.0.1",
        "::1",
        "fe80::1",
        "0.0.0.0",
        "metadata.internal",
    ):
        assert links.is_private_host(host), host
    for host in ("www.ada.org", "8.8.8.8", "2606:4700::1111", "nidcr.nih.gov"):
        assert not links.is_private_host(host), host


def test_whitespace_cannot_hide_a_scheme():
    assert links.link_scheme("java	script:alert(1)") == "javascript"
    assert links.link_scheme(" javascript:x") == "javascript"
    assert links.link_scheme("/relative/path") == "" and links.link_scheme("services/page") == ""


def test_malformed_url_is_a_finding_not_a_crash(make_post, clinic):
    findings, _ = links.check_links(make_post("[x](http://[bad/path)"), clinic, offline=True)
    assert "link_malformed" in rules_of(findings)


def test_a_markdown_link_is_not_counted_twice(make_post):
    post = make_post("[x](https://www.ada.org/a) and https://www.ada.org/b")
    assert [u for _, u in links.extract_links(post)] == ["https://www.ada.org/a", "https://www.ada.org/b"]

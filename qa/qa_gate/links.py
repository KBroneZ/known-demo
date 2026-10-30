"""Link extraction and checking: internal links against the ficha page list, external via HEAD.

External checking has an offline mode that reads a recorded cache instead of the network, so
runs are reproducible. A URL the network cannot settle (403, 429, 5xx, timeout) is a warning,
not a verdict on the link.
"""

from __future__ import annotations

import ipaddress
import json
import re
import socket
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

from .findings import BLOCK, WARN, Finding
from .loader import Clinic, Post

# A Markdown link target may hold balanced parentheses, as in https://en.wikipedia.org/wiki/Titan_(submersible).
MD_URL = r"(?:[^()\s<>]|\([^()\s<>]*\))+"
MD_LINK_RE = re.compile(rf"\[([^\]]*)\]\(\s*<?({MD_URL})>?(?:\s+\"[^\"]*\")?\s*\)")
BARE_URL_RE = re.compile(r"https?://[^\s)\]<>\"']+")
USER_AGENT = "Mozilla/5.0 (compatible; content-qa-gate/1.0)"
HEAD_FALLBACK_CODES = {400, 403, 405, 501}
DEAD_CODES = {404, 410}
DEFAULT_TIMEOUT = 10.0
CACHE_MAX_AGE_DAYS = 30
NXDOMAIN_ERRNOS = {getattr(socket, "EAI_NONAME", -2), 11001}  # 11001 = WSAHOST_NOT_FOUND on Windows


def extract_links(post: Post) -> list[tuple[int, str]]:
    seen, out = set(), []
    for lineno, text in post.prose:
        md = list(MD_LINK_RE.finditer(text))
        urls = [m.group(2) for m in md]
        inside = [m.span() for m in md]  # a bare-URL match inside a Markdown link is the same link, not a second one
        urls += [
            m.group().rstrip(".,;")
            for m in BARE_URL_RE.finditer(text)
            if not any(a <= m.start() < b for a, b in inside)
        ]
        for url in urls:
            if (lineno, url) not in seen:
                seen.add((lineno, url))
                out.append((lineno, url))
    return out


def load_cache(path: str | Path | None) -> dict:
    if not path or not Path(path).exists():
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_cache(path: str | Path, cache: dict) -> None:
    Path(path).write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fetch_once(url: str, timeout: float) -> dict:
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return {"status": resp.status, "final": resp.geturl()}
        except urllib.error.HTTPError as exc:
            # some servers answer HEAD with 404/405 and serve GET fine: only GET can declare a link dead
            if method == "HEAD" and (exc.code in HEAD_FALLBACK_CODES or exc.code in DEAD_CODES):
                continue
            return {"status": exc.code, **({"final": exc.geturl()} if exc.geturl() and exc.geturl() != url else {})}
        except urllib.error.URLError as exc:
            reason = exc.reason
            if isinstance(reason, socket.gaierror):
                return {"error": "nxdomain" if reason.errno in NXDOMAIN_ERRNOS else "dns_temp"}
            if isinstance(reason, (socket.timeout, TimeoutError)):
                return {"error": "timeout"}
            return {"error": "other"}
        except TimeoutError:
            return {"error": "timeout"}
        except (OSError, ValueError):
            return {"error": "other"}
    return {"error": "other"}


def fetch_status(url: str, timeout: float = DEFAULT_TIMEOUT, retry_wait: float = 1.5) -> dict:
    """Return {'status': int, 'final': url} or {'error': 'nxdomain'|'dns_temp'|'timeout'|'other'}.

    A DNS failure is retried once: a transient resolver error must not block a live page."""
    result = _fetch_once(url, timeout)
    if result.get("error") in ("nxdomain", "dns_temp"):
        time.sleep(retry_wait)
        result = _fetch_once(url, timeout)
    return result


def is_persistable(result: dict) -> bool:
    """Only definitive answers are worth replaying offline: not timeouts, 5xx, 403/429 or resolver hiccups."""
    status = result.get("status")
    if status is not None:
        return 200 <= status < 400 or status in DEAD_CODES
    return result.get("error") == "nxdomain"


def cache_lookup(cache: dict, url: str, max_age_days: int | None, today: date | None = None) -> dict | None:
    """Cached result for a URL, or None when missing or older than max_age_days."""
    entry = cache.get(url)
    if entry is None:
        return None
    if max_age_days is not None:
        try:
            checked = date.fromisoformat(str(entry.get("checked", "")))
        except ValueError:
            return None
        if ((today or date.today()) - checked).days > max_age_days:
            return None
    return entry


LOCALE_ROOT_RE = re.compile(r"^/[a-z]{2}(?:[-_][a-zA-Z]{2,4})?/?$")


def _is_root_path(path: str) -> bool:
    """The site root, or a language root such as /en/ or /fr-ca: redirecting that to / is the home page itself."""
    return path in ("", "/") or bool(LOCALE_ROOT_RE.match(path))


def classify(lineno: int, url: str, result: dict | None, offline: bool = False) -> Finding | None:
    if result is None:
        return Finding(
            "link_unverified",
            WARN,
            lineno,
            url,
            "External link not verified: no usable cached result (offline) - check it online or by hand.",
        )
    if result.get("status") in DEAD_CODES or result.get("error") in ("nxdomain", "dns"):
        what = result.get("status") or "domain does not resolve"
        return Finding("link_broken", BLOCK, lineno, url, f"External link is dead ({what}).")
    status = result.get("status")
    if status is not None and 200 <= status < 400:
        final_path = urlparse(str(result.get("final") or url)).path
        if final_path in ("", "/") and not _is_root_path(urlparse(url).path):
            return Finding(
                "link_redirects_home",
                WARN,
                lineno,
                url,
                "Link redirects to the site's home page (soft 404?); check the target.",
            )
        return None
    detail = status or result.get("error")
    return Finding("link_unverifiable", WARN, lineno, url, f"Link could not be confirmed ({detail}); check by hand.")


BLOCKED_CODES = {401, 403, 429, 451}  # anti-bot, login wall, rate limit, legal block: the page may well be alive
_SECOND_LEVEL = {"co", "com", "org", "net", "gov", "ac", "edu"}


def registrable_domain(host: str) -> str:
    """Last two labels of a host (three for co.uk-style names). Enough to tell a move to another site from www/https."""
    labels = host.lower().strip(".").split(".")
    if len(labels) >= 3 and labels[-2] in _SECOND_LEVEL and len(labels[-1]) == 2:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def classify_travel(lineno: int, url: str, result: dict | None, offline: bool = False) -> Finding | None:
    """Travel profile: 401/403/429/451 are inconclusive (a warning, never dead), and a link whose final address is on a
    different registrable domain is reported (the site moved, so the post points at a stale address)."""
    if result is not None and result.get("final"):
        old, new = urlparse(url).hostname or "", urlparse(str(result["final"])).hostname or ""
        if (
            old
            and new
            and registrable_domain(old) != registrable_domain(new)
            and (result.get("status") in BLOCKED_CODES or classify(lineno, url, result, offline) is None)
        ):
            return Finding(
                "link_moved_domain",
                WARN,
                lineno,
                url,
                f"The link now ends on {new}; update the URL to the new address."
                + (
                    f" That page answers {result['status']} to automated requests, so it is not confirmed alive."
                    if result.get("status") in BLOCKED_CODES
                    else ""
                ),
            )
    if result is not None and result.get("status") in BLOCKED_CODES:
        return Finding(
            "link_blocked",
            WARN,
            lineno,
            url,
            f"The site answered {result['status']} (anti-bot or login wall): "
            "the link is inconclusive, not dead; open it by hand or use a browser check.",
        )
    return classify(lineno, url, result, offline)


ALLOWED_SCHEMES = {"http", "https", "mailto", "tel"}
_SCHEME_RE = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.\-]*):")
PRIVATE_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home.arpa", ".intranet")


def link_scheme(url: str) -> str:
    """Lowercase scheme of a link ('' for relative links). Whitespace and control characters, which browsers strip
    inside a scheme ("java\\tscript:"), are removed first so they cannot hide one."""
    cleaned = re.sub(r"[\s\x00-\x1f]", "", url)
    m = _SCHEME_RE.match(cleaned)
    return m.group(1).lower() if m else ""


def is_private_host(host: str) -> bool:
    """True for localhost, private/loopback/link-local IPs (any notation) and internal-looking names.
    The link checker must not be turned into a way to probe the machine or network it runs on."""
    host = host.strip("[]").lower().rstrip(".")
    if not host:
        return True
    if host == "localhost" or host.endswith(PRIVATE_SUFFIXES) or ("." not in host and ":" not in host):
        return True
    if host.isdigit() or host.startswith("0x"):  # 2130706433 and 0x7f000001 both mean 127.0.0.1
        return True
    try:
        return not ipaddress.ip_address(host).is_global
    except ValueError:
        return False


def _internal_path(url: str, clinic: Clinic, base_path: str = "/") -> str | None:
    """Site path when the link is internal (absolute, same-host or relative), else None."""
    if url.startswith(("#", "mailto:", "tel:", "data:", "javascript:")):
        return None
    parsed = urlparse(url)
    if parsed.scheme or url.startswith("//"):
        if not clinic.host or parsed.netloc.lower() != clinic.host:
            return None
        path = parsed.path or "/"
    elif not parsed.path:
        return None  # query-only link: same page
    else:
        path = urljoin(base_path, parsed.path)  # relative links resolve like a browser would
    return path.rstrip("/") or "/"


def _is_affiliate_redirector(url: str, clinic: Clinic) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(
        host == h.lower() or host.endswith("." + h.lower()) for h in (clinic.get("affiliate") or {}).get("hosts") or []
    )


def check_links(
    post: Post,
    clinic: Clinic,
    offline: bool = False,
    cache: dict | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_age_days: int | None = CACHE_MAX_AGE_DAYS,
) -> tuple[list[Finding], dict]:
    """Return (findings, fresh_results) where fresh_results are URLs fetched from the network."""
    pages = {p.rstrip("/") or "/" for p in clinic.get("pages") or []}
    # server-side redirect endpoints (affiliate cloaking such as /go/booking) are not in a sitemap but are not broken
    redirect_prefixes = tuple(p.rstrip("/") + "/" for p in clinic.get("redirect_prefixes") or [])
    base_path = f"/blog/{post.frontmatter.get('slug') or 'post'}"
    cache = cache or {}
    findings: list[Finding] = []
    external: list[tuple[int, str]] = []
    for lineno, url in extract_links(post):
        try:
            urlparse(url)
        except ValueError:
            findings.append(Finding("link_malformed", BLOCK, lineno, url[:100], "Link is not a valid URL."))
            continue
        scheme = link_scheme(url)
        if scheme and scheme not in ALLOWED_SCHEMES:
            findings.append(
                Finding(
                    "link_bad_scheme",
                    BLOCK,
                    lineno,
                    url[:100],
                    f"Link scheme '{scheme}:' is not allowed in a post (only http, https, mailto, tel).",
                )
            )
            continue
        path = _internal_path(url, clinic, base_path)
        if path is not None:
            if path not in pages and not path.startswith(redirect_prefixes):
                findings.append(
                    Finding(
                        "link_broken_internal",
                        BLOCK,
                        lineno,
                        url,
                        "Internal link points to a page that is not in the ficha page list.",
                    )
                )
        elif url.startswith("http"):
            if is_private_host(urlparse(url).hostname or ""):
                findings.append(
                    Finding(
                        "link_private_host",
                        BLOCK,
                        lineno,
                        url[:100],
                        "Link points at a local or private address; it is not fetched and must not be published.",
                    )
                )
                continue
            external.append((lineno, url))
    fresh: dict = {}
    if offline:
        results = {url: cache_lookup(cache, url, max_age_days) for _, url in external}
    else:
        unique = sorted({url for _, url in external})
        with ThreadPoolExecutor(max_workers=8) as pool:
            fresh = dict(zip(unique, pool.map(lambda u: fetch_status(u, timeout), unique), strict=True))
        results = fresh
    judge = classify_travel if clinic.get("profile") == "travel" else classify
    for lineno, url in external:
        finding = judge(lineno, url, results.get(url), offline)
        if (
            finding
            and finding.rule in ("link_redirects_home", "link_moved_domain")
            and _is_affiliate_redirector(url, clinic)
        ):
            continue  # an affiliate short link is meant to land on the merchant's site with the tracking tag
        if finding:
            findings.append(finding)
    return findings, fresh

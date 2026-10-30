"""Topic stage: turn real patient questions into post topics.

Source used here: public question titles from r/askdentists, read through the Arctic Shift archive API
(https://arctic-shift.photon-reddit.com), which needs no account. Only title, score, comment count and post id are
kept; no usernames or text. Results are cached in topics/cache/ so a run is repeatable and polite to the API.

What it is not: Austin patients, search volume or "People also ask". Those need Search Console, a SERP API or the
clinic's own front-desk questions; `topics/seed.yaml` documents them and holds a hand-written fallback list.
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import date

from . import intent
from .clinicdata import PIPELINE_ROOT, Site, miniyaml

API = "https://arctic-shift.photon-reddit.com/api/posts/search"
CACHE_DIR = PIPELINE_ROOT / "topics" / "cache"
SEED_PATH = PIPELINE_ROOT / "topics" / "seed.yaml"
USER_AGENT = "dental-post-pipeline-demo/0.1 (research prototype)"
QUESTION_START = re.compile(r"^(how|why|what|when|is|are|can|could|should|do|does|will|would|which)\b", re.I)
MIN_COMMENTS = 3
REQUEST_GAP_SECONDS = 2.5
STOP_WORDS = {"and", "the", "for", "with", "care", "same", "day", "tooth", "colored"}


@dataclass(frozen=True)
class Candidate:
    question: str
    service: str  # service name from clinic.yaml
    service_slug: str | None
    keyword: str  # the alias searched for
    source: str  # "reddit:r/askdentists" or "seed"
    source_id: str
    comments: int
    score: int
    retrieved: str
    related: tuple[str, ...] = ()
    intent: str = ""  # which search-style intent the wording matched (see intent.py); "" for seed questions
    patient_wording: str = ""  # the original title, when `question` is the canonical query built from it


def is_question(title: str) -> bool:
    title = title.strip()
    return 25 <= len(title) <= 140 and (title.endswith("?") or bool(QUESTION_START.match(title)))


def fetch_titles(keyword: str, limit: int = 25, fetch=None) -> list[dict]:
    """Titles of r/askdentists posts that contain `keyword`; `fetch` is injectable for tests."""
    params = {
        "subreddit": "askdentists",
        "title": keyword,
        "limit": str(limit),
        "fields": "title,score,num_comments,id,created_utc",
    }
    url = f"{API}?{urllib.parse.urlencode(params)}"
    if fetch is not None:
        return fetch(url)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.load(resp)
            if data.get("data") is not None:
                return data["data"]
        except (OSError, ValueError):
            pass
        time.sleep(REQUEST_GAP_SECONDS * (attempt + 2))  # the API asks clients to slow down
    return []


def cached_titles(site_id: str, keyword: str, refresh: bool = False, fetch=None) -> tuple[list[dict], str]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{site_id}__{re.sub(r'[^a-z0-9]+', '-', keyword.lower())}.json"
    if path.exists() and not refresh:
        blob = json.loads(path.read_text(encoding="utf-8"))
        return blob["titles"], blob["retrieved"]
    titles = fetch_titles(keyword, fetch=fetch)
    if fetch is None:
        time.sleep(REQUEST_GAP_SECONDS)
    retrieved = date.today().isoformat()
    kept = [{k: t[k] for k in ("id", "title", "score", "num_comments") if k in t} for t in titles]
    if kept:  # never cache an empty answer: it is usually a rate limit, not "no questions"
        path.write_text(
            json.dumps({"keyword": keyword, "retrieved": retrieved, "titles": kept}, indent=1), encoding="utf-8"
        )
    return kept, retrieved


def covered_services(site: Site) -> set[str]:
    """Services an existing post already covers (by its `service` field or its slug)."""
    covered = {fm.get("service") for fm in site.posts.values() if fm.get("service")}
    slugs = " ".join(site.posts)
    for s in site.data["services"]:
        words = [w for w in re.split(r"\W+", s["name"].lower()) if w and w not in STOP_WORDS]
        if s.get("slug") in covered or any(w in slugs for w in words if len(w) > 4):
            covered.add(s.get("slug") or s["name"])
    return covered


def candidates_for(site: Site, refresh: bool = False, fetch=None) -> list[Candidate]:
    """One topic per uncovered service: the most discussed real question that passes the topic filter."""
    covered = covered_services(site)
    out: list[Candidate] = []
    for service in site.data["services"]:
        if (service.get("slug") or service["name"]) in covered:
            continue
        keyword = (service.get("aliases") or [service["name"].lower()])[0]
        titles, retrieved = cached_titles(site.id, keyword, refresh, fetch)
        questions = [t for t in titles if is_question(t["title"]) and t.get("num_comments", 0) >= MIN_COMMENTS]
        questions.sort(key=lambda t: (-t.get("num_comments", 0), -t.get("score", 0)))
        for t in questions:
            verdict = intent.classify(t["title"], service)
            if not verdict.accepted:
                continue
            related = tuple(
                x["title"] for x in questions if x is not t and intent.is_general_about(x["title"], service)
            )[:4]
            out.append(
                Candidate(
                    verdict.query,
                    service["name"],
                    service.get("slug"),
                    keyword,
                    "reddit:r/askdentists",
                    t["id"],
                    t.get("num_comments", 0),
                    t.get("score", 0),
                    retrieved,
                    related,
                    verdict.intent,
                    t["title"],
                )
            )
            break
    out.sort(key=lambda c: -c.comments)
    return out


def explain(site: Site, fetch=None) -> list[dict]:
    """Every question title considered for the uncovered services, with the filter's decision
    (for `topics --explain`)."""
    covered = covered_services(site)
    rows = []
    for service in site.data["services"]:
        if (service.get("slug") or service["name"]) in covered:
            rows.append(
                {"service": service["name"], "title": "", "comments": 0, "decision": "skipped: already has a post"}
            )
            continue
        keyword = (service.get("aliases") or [service["name"].lower()])[0]
        titles, _ = cached_titles(site.id, keyword, False, fetch)
        for t in sorted(titles, key=lambda x: -x.get("num_comments", 0)):
            if not is_question(t["title"]):
                decision = "rejected: not phrased as a question"
            elif t.get("num_comments", 0) < MIN_COMMENTS:
                decision = f"rejected: fewer than {MIN_COMMENTS} comments"
            else:
                v = intent.classify(t["title"], service)
                decision = f"accepted as {v.intent}: {v.query}" if v.accepted else f"rejected: {v.reason}"
            rows.append(
                {
                    "service": service["name"],
                    "title": t["title"],
                    "comments": t.get("num_comments", 0),
                    "decision": decision,
                }
            )
    return rows


def seed_candidates(site: Site) -> list[Candidate]:
    """Hand-written fallback questions (topics/seed.yaml) for services with no usable real question."""
    seeds = miniyaml.loads(SEED_PATH.read_text(encoding="utf-8")).get("questions", [])
    names = {s["name"]: s for s in site.data["services"]}
    covered = covered_services(site)
    return [
        Candidate(
            q["question"],
            q["service"],
            names[q["service"]].get("slug"),
            q["service"].lower(),
            "seed",
            "seed",
            0,
            0,
            "n/a",
        )
        for q in seeds
        if q["service"] in names and (names[q["service"]].get("slug") or q["service"]) not in covered
    ]


def choose(site: Site, count: int, refresh: bool = False, fetch=None) -> list[Candidate]:
    picked = candidates_for(site, refresh, fetch)[:count]
    if len(picked) < count:
        have = {c.service for c in picked}
        picked += [c for c in seed_candidates(site) if c.service not in have][: count - len(picked)]
    return picked


def to_json(candidates: list[Candidate]) -> str:
    return json.dumps([asdict(c) for c in candidates], indent=2)

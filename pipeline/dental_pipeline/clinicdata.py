"""Read a website clinic.yaml and expose what the pipeline needs: the QA ficha, facts, routes and existing posts.

The website's clinic.yaml is a superset of the QA fixture. The QA gate wants a `pages` list; the website only
requires one for clinic-a, so it is derived here from the same rules the theme uses for routes.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parent.parent
DEMO_ROOT = PIPELINE_ROOT.parent
WEB_ROOT = DEMO_ROOT / "web"
QA_ROOT = DEMO_ROOT / "qa"
# The QA gate is a sibling folder of this repo, not an installed package, so it goes on the path before the import.
if str(QA_ROOT) not in sys.path:
    sys.path.insert(0, str(QA_ROOT))

from qa_gate import miniyaml  # noqa: E402
from qa_gate.loader import Clinic, parse_post_text  # noqa: E402

STATIC_ROUTES = ("/", "/about", "/contact", "/faq", "/services", "/team", "/blog")
DAY_NAMES = {
    "mon": "Monday",
    "tue": "Tuesday",
    "wed": "Wednesday",
    "thu": "Thursday",
    "fri": "Friday",
    "sat": "Saturday",
    "sun": "Sunday",
}
DAY_ORDER = list(DAY_NAMES)


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def clock(t: str) -> str:
    """'08:00' -> '8 a.m.', '13:30' -> '1:30 p.m.' (same wording as the theme)."""
    hour, minute = (int(x) for x in t.split(":"))
    suffix = "p.m." if hour >= 12 else "a.m."
    hh = 12 if hour % 12 == 0 else hour % 12
    return f"{hh} {suffix}" if minute == 0 else f"{hh}:{minute:02d} {suffix}"


def _day_range(days: list[str]) -> str:
    idx = sorted(DAY_ORDER.index(d) for d in days)
    names = [DAY_NAMES[DAY_ORDER[i]] for i in idx]
    if len(names) == 1:
        return names[0]
    if all(idx[i] == idx[i - 1] + 1 for i in range(1, len(idx))):
        return f"{names[0]} through {names[-1]}"
    return ", ".join(names[:-1]) + " and " + names[-1]


def hours_sentence(data: dict) -> str:
    parts = [f"{_day_range(h['days'])} from {clock(h['open'])} to {clock(h['close'])}" for h in data["hours"]]
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + ", and on " + parts[-1]


def hours_wording(data: dict) -> str:
    sentence = f"We are open {hours_sentence(data)}"
    return sentence if sentence.endswith(".") else sentence + "."


@dataclass(frozen=True)
class Site:
    id: str
    root: Path
    clinic: Clinic
    posts: dict  # slug -> frontmatter dict of existing posts

    @property
    def data(self) -> dict:
        return self.clinic.data

    @property
    def posts_dir(self) -> Path:
        return self.root / "src" / "content" / "posts"

    def service_pages(self) -> list[dict]:
        return [s for s in self.data["services"] if s.get("slug")]


def derive_pages(data: dict, post_slugs) -> list[str]:
    pages = list(STATIC_ROUTES)
    pages += [f"/services/{s['slug']}" for s in data["services"] if s.get("slug")]
    pages += [f"/blog/{slug}" for slug in sorted(post_slugs)]
    return pages


def load_site(site_id: str, web_root: Path = WEB_ROOT) -> Site:
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", site_id or ""):
        raise ValueError(f"invalid site id {site_id!r}: lowercase letters, digits and dashes only")
    root = web_root / "sites" / site_id
    text = (root / "clinic.yaml").read_text(encoding="utf-8")
    data = miniyaml.loads(text)
    posts = {}
    posts_dir = root / "src" / "content" / "posts"
    for path in sorted(posts_dir.glob("*.md")):
        post = parse_post_text(path.read_text(encoding="utf-8"), path)
        posts[post.frontmatter.get("slug", path.stem)] = post.frontmatter
    enriched = {**data, "pages": derive_pages(data, posts)}
    return Site(site_id, root, Clinic(enriched, text), posts)


def list_sites(web_root: Path = WEB_ROOT) -> list[str]:
    return sorted(p.name for p in (web_root / "sites").iterdir() if (p / "clinic.yaml").exists())


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


COVERAGE_WORDS = ("in network", "in-network", "benefits", "insurance")


def conditional_statements(data: dict) -> tuple[list[str], list[str]]:
    """Verbatim sentences from the services' own text: price and insurance statements (they carry their conditions) and
    emergency/911 instructions (a post that mentions symptoms must not contradict them)."""
    prices, safety = [], []
    for service in data["services"]:
        texts = list(service.get("body") or []) + [f["answer"] for f in service.get("faq", [])]
        for text in texts:
            for sentence in _sentences(text):
                if ("$" in sentence or any(w in sentence.lower() for w in COVERAGE_WORDS)) and sentence not in prices:
                    prices.append(sentence)
                if ("911" in sentence or "emergency room" in sentence) and sentence not in safety:
                    safety.append(sentence)
    return prices, safety


def facts_block(site: Site) -> str:
    """The only facts a post may state about the clinic, rendered with the website's own wording."""
    d, n = site.data, site.data["nap"]
    street = f"{n['street']}, {n['suite']}" if n.get("suite") else n["street"]
    lines = [
        f"- Clinic name: {d['name']}",
        f"- Phone: {n['phone']}",
        f"- Address: {street}, {n['city']}, {n['state']} {n['zip']}",
        f"- Hours (use this exact wording): {hours_wording(d)}",
    ]
    if d.get("emergency_line"):
        lines.append(f"- After-hours instruction: {d['emergency_line']}")
    for key, value in (d.get("prices") or {}).items():
        lines.append(f"- Published price '{key}': {value}")
    if d.get("insurance_accepted"):
        lines.append(f"- Insurance carriers: {', '.join(d['insurance_accepted'])}")
    for dentist in d["dentists"]:
        lines.append(f"- Dentist: {dentist['name']}, {dentist['credentials']} - {dentist['focus']}")
    prices, safety = conditional_statements(d)
    if prices:
        lines.append(
            "- Price and insurance statements as the clinic publishes them "
            "(repeat only WITH their conditions, in this wording):"
        )
        lines += [f"    * {s}" for s in prices]
    if safety:
        lines.append(
            "- Safety instructions (never contradict them; repeat when you discuss pain, swelling or injuries):"
        )
        lines += [f"    * {s}" for s in safety]
    return "\n".join(lines)

"""Topic filter: is this a service the clinic offers, and does it map to a question people actually search?

Reddit titles are personal stories ("my dentist said...", "as white as the whites in my eyes"). They show what worries
patients, but they are not what anyone types into a search box. So a title only becomes a topic when

  1. it is about a service in the clinic's own `clinic.yaml` and not about one the clinic does not list, and
  2. its wording matches one of a small set of search-style intents (cost, pain, safety, how long it lasts or takes,
     what to expect afterwards, how often, urgency, whether you need it).

The post is then written for the canonical query ("Is teeth whitening safe?"); the Reddit title is kept as "how patients
put it", with its comment count as a rough sign of interest.

ASSUMPTION [sin verificar]: the eight intents are the usual shapes of dental search queries. No search-volume data was
consulted. Validating a topic needs Search Console on the client's site, a keyword tool, or the front desk's questions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# procedures a patient may ask about that the demo clinics do not list; a title about them is not our topic
NOT_OFFERED = (
    "wisdom tooth",
    "wisdom teeth",
    "veneer",
    "denture",
    "sedation",
    "tmj",
    "oral surgeon",
    "orthodontist",
    "braces",
    "gum graft",
    "periodontist",
    "sleep apnea",
    "botox",
)

# (name, regex on the lowercased title, query template). First match wins, so keep the specific ones first.
INTENTS = (
    ("cost", r"\b(cost|price|how much|expensive|afford|cheap|insurance cover)", "How much {do} {s} cost?"),
    ("pain", r"\b(hurt|hurts|pain|painful|numb|sore|soreness|ache)\b", "{Do} {s} hurt?"),
    ("safety", r"\b(safe|safety|damage|damaging|harm|harmful|risk|risks|side effect)", "{Is} {s} safe?"),
    ("lifespan", r"\b(last|lasts|lasting|how many years|wear out|replace|replacement)\b", "How long {do} {s} last?"),
    ("duration", r"\b(how long|take|takes|time)\b", "How long {do} {s} take?"),
    (
        "recovery",
        r"\b(recover|recovery|heal|healing|aftercare|what to expect)\b"
        r"|\bafter (a |the )?(procedure|treatment|surgery)\b",
        "What to expect after {s}",
    ),
    ("frequency", r"\b(how often|twice a year|every (six|6) months|yearly)\b", "How often should you get {s}?"),
    (
        "urgency",
        r"\b(can (this|it) wait|urgent|emergency|swelling|bleeding|how soon|asap)\b",
        "When should you see a dentist about {s}?",
    ),
    (
        "decision",
        r"\bvs\.?\s|\bversus\b|\binstead of\b|\bworth it\b|\bis \w+( \w+)? needed\b|\bdo you need\b",
        "Do you need {s}? How to decide",
    ),
)

# service-name keyword -> (subject used in a query, plural?)
SUBJECTS = (
    ("root canal", ("a root canal", False)),
    ("filling", ("tooth-colored fillings", True)),
    ("crown", ("a dental crown", False)),
    ("whitening", ("teeth whitening", False)),
    ("implant", ("dental implants", True)),
    ("aligner", ("clear aligners", True)),
    ("checkup", ("a dental checkup", False)),
    ("emergency", ("a dental emergency", False)),
    ("child", ("a child's dental visit", False)),
    ("pediatric", ("a child's dental visit", False)),
)


# first-person words and numbers (ages, dates) mark a personal case, which is a story, not a query
PERSONAL = re.compile(r"\b(i|i'm|i've|i'd|i'll|my|me|mine|we|our|she|he|her|his|daughter|son|wife|husband)\b|\d", re.I)


@dataclass(frozen=True)
class Verdict:
    accepted: bool
    reason: str
    intent: str = ""
    query: str = ""


def subject_for(service_name: str) -> tuple[str, bool]:
    lowered = service_name.lower()
    for key, value in SUBJECTS:
        if key in lowered:
            return value
    return lowered, False


def render_query(template: str, subject: str, plural: bool) -> str:
    verbs = {"do": "do" if plural else "does", "Do": "Do" if plural else "Does", "Is": "Are" if plural else "Is"}
    query = template.format(s=subject, **verbs)
    return query[0].upper() + query[1:]


def about_service(title: str, service: dict) -> bool:
    terms = [service["name"].lower()] + [a.lower() for a in service.get("aliases", [])]
    lowered = title.lower()
    return any(re.search(rf"\b{re.escape(t)}", lowered) for t in terms if len(t) > 3)


def is_general_about(title: str, service: dict) -> bool:
    """Used for the 'other questions patients asked' in a brief: the same hygiene as a topic, minus the intent test."""
    lowered = title.lower()
    return about_service(title, service) and not PERSONAL.search(title) and not any(t in lowered for t in NOT_OFFERED)


def classify(title: str, service: dict) -> Verdict:
    lowered = title.lower()
    if not about_service(title, service):
        return Verdict(False, "not about this service")
    for term in NOT_OFFERED:
        if term in lowered:
            return Verdict(False, f"mentions '{term}', which the clinic does not list")
    if PERSONAL.search(title):
        return Verdict(False, "a personal case (first person or a number), not a general question")
    subject, plural = subject_for(service["name"])
    for name, pattern, template in INTENTS:
        if re.search(pattern, lowered):
            return Verdict(True, "ok", name, render_query(template, subject, plural))
    return Verdict(False, "no search-style intent in the wording")

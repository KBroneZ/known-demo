"""Deterministic checks of a post against the clinic ficha (NAP, dentists, prices, insurance, hours, services)."""

from __future__ import annotations

import re

from .findings import BLOCK, WARN, Finding
from .loader import Clinic, Post
from .negation import is_negated

PHONE_RE = re.compile(r"(?<![\w$])\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}(?!\d)")
PHONE_COMPACT_RE = re.compile(r"(?<![\w$.])\d{10}(?!\d)")
ADDRESS_RE = re.compile(
    r"\b(\d{2,5})\s+((?:[A-Z][\w.']*\s+){1,4}?)"
    r"(Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Parkway|Pkwy|Court|Ct)\b\.?"
)
ZIP_RE = re.compile(r"\b(?:TX|Texas)\s+(\d{5})\b")
DENTIST_RE = re.compile(r"\bDr\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z'\-]+)?)")
PRICE_RE = re.compile(r"\$\s?\d[\d,]*(?:\.\d{2})?")
CARRIERS = (
    "Delta Dental",
    "Cigna",
    "MetLife",
    "Aetna",
    "Guardian",
    "United Concordia",
    "UnitedHealthcare",
    "Humana",
    "Blue Cross",
    "Anthem",
    "Principal",
    "Medicaid",
    "Medicare",
)
STREET_ABBREV = {
    "street": "st",
    "avenue": "ave",
    "road": "rd",
    "boulevard": "blvd",
    "drive": "dr",
    "lane": "ln",
    "parkway": "pkwy",
    "court": "ct",
}
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DAY_WORDS = {
    "monday": "mon",
    "mon": "mon",
    "tuesday": "tue",
    "tue": "tue",
    "tues": "tue",
    "wednesday": "wed",
    "wed": "wed",
    "thursday": "thu",
    "thu": "thu",
    "thur": "thu",
    "thurs": "thu",
    "friday": "fri",
    "fri": "fri",
    "saturday": "sat",
    "sat": "sat",
    "sunday": "sun",
    "sun": "sun",
}
_DAY = r"(?:mon|tues?|wed(?:nes)?|thu(?:rs?)?|fri|sat(?:ur)?|sun)(?:day)?s?"
_TIME = r"\d{1,2}(?::\d{2})?\s*[ap]\.?m\.?"
HOURS_RE = re.compile(
    rf"\b(?P<d1>{_DAY})\b(?:\s*(?:through|thru|to|[-–—])\s*(?P<d2>{_DAY})\b)?"
    rf"[^.\n]{{0,30}}?(?P<t1>{_TIME})\s*(?:to|until|till|[-–—])\s*(?P<t2>{_TIME})",
    re.I,
)
SERVICE_CLAIM_RE = re.compile(r"\bwe\s+(?:also\s+)?(?:offer|provide|perform|specialize\s+in)\s+([^.;:\n]+)", re.I)


def _norm_street(text: str) -> str:
    words = re.sub(r"[.,]", "", text.lower()).split()
    return " ".join(STREET_ABBREV.get(w, w) for w in words)


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def _clip(text: str, n: int = 90) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def check_phones(post: Post, clinic: Clinic) -> list[Finding]:
    out = []
    for lineno, text in post.prose:
        for m in list(PHONE_RE.finditer(text)) + list(PHONE_COMPACT_RE.finditer(text)):
            if _digits(m.group()) != clinic.phone_digits:
                out.append(
                    Finding(
                        "nap_phone_mismatch",
                        BLOCK,
                        lineno,
                        m.group().strip(),
                        f"Phone does not match the ficha ({clinic.get('nap', {}).get('phone')}).",
                    )
                )
        for m in re.finditer(r"tel:([+\d()\-.\s]+)", text):
            if _digits(m.group(1)).lstrip("1") != clinic.phone_digits.lstrip("1"):
                out.append(
                    Finding(
                        "nap_phone_mismatch",
                        BLOCK,
                        lineno,
                        m.group().strip(),
                        "tel: link does not match the ficha phone.",
                    )
                )
    return out


def check_address(post: Post, clinic: Clinic) -> list[Finding]:
    nap = clinic.get("nap", {})
    want = _norm_street(nap.get("street", ""))
    out = []
    for lineno, text in post.prose:
        for m in ADDRESS_RE.finditer(text):
            found = _norm_street(f"{m.group(1)} {m.group(2)} {m.group(3)}")
            if found != want:
                out.append(
                    Finding(
                        "nap_address_mismatch",
                        BLOCK,
                        lineno,
                        _clip(m.group()),
                        f"Street address does not match the ficha ({nap.get('street')}).",
                    )
                )
        for m in ZIP_RE.finditer(text):
            if m.group(1) != str(nap.get("zip")):
                out.append(
                    Finding(
                        "nap_address_mismatch",
                        BLOCK,
                        lineno,
                        m.group(),
                        f"ZIP does not match the ficha ({nap.get('zip')}).",
                    )
                )
    return out


def check_clinic_name(post: Post, clinic: Clinic) -> list[Finding]:
    words = clinic.name.split()
    if len(words) < 3:
        return []
    prefix = " ".join(words[:-1])
    pattern = re.compile(rf"\b{re.escape(prefix)}\s+\w+", re.I)
    out = []
    for lineno, text in post.prose:
        for m in pattern.finditer(text):
            if not m.group().lower().startswith(clinic.name.lower()):
                out.append(
                    Finding(
                        "nap_name_variant",
                        WARN,
                        lineno,
                        m.group(),
                        f"Clinic name differs from the ficha ({clinic.name}).",
                    )
                )
    return out


def dentist_names(clinic: Clinic) -> set[str]:
    """Lowercase allowed forms: 'elena marsh', 'marsh'."""
    names = set()
    for d in clinic.get("dentists", []) or []:
        parts = re.sub(r"^dr\.?\s+", "", d["name"].lower()).split()
        names.add(" ".join(parts))
        names.add(parts[-1])
    return names


def check_dentists(post: Post, clinic: Clinic) -> list[Finding]:
    allowed = dentist_names(clinic)
    out = []
    for lineno, text in post.prose:
        for m in DENTIST_RE.finditer(text):
            words = m.group(1).lower().split()
            # "Dr. Marsh Our team" captures a stray capitalised word: accept the surname alone
            if " ".join(words) not in allowed and words[0] not in allowed:
                out.append(
                    Finding(
                        "dentist_not_in_roster",
                        BLOCK,
                        lineno,
                        m.group().strip(),
                        "Dentist name is not in the ficha roster.",
                    )
                )
    return out


def _price_key(text: str) -> str:
    """'$129.00' and '$129' compare equal."""
    return f"{float(re.sub(r'[^0-9.]', '', text) or 0):.2f}"


def check_prices(post: Post, clinic: Clinic) -> list[Finding]:
    allowed = {_price_key(v) for v in (clinic.get("prices") or {}).values()}
    out = []
    for lineno, text in post.prose:
        for m in PRICE_RE.finditer(text):
            if _price_key(m.group()) not in allowed:
                out.append(
                    Finding(
                        "price_not_in_ficha",
                        BLOCK,
                        lineno,
                        m.group(),
                        "Price is not published in the ficha.",
                    )
                )
    return out


def check_insurance(post: Post, clinic: Clinic) -> list[Finding]:
    accepted = {c.lower() for c in clinic.get("insurance_accepted") or []}
    out = []
    for lineno, text in post.prose:
        for carrier in CARRIERS:
            m = re.search(rf"\b{re.escape(carrier)}\b", text)
            if m and carrier.lower() not in accepted and not is_negated(text, m.start()):
                out.append(
                    Finding(
                        "insurance_not_in_ficha",
                        BLOCK,
                        lineno,
                        carrier,
                        "Carrier is not listed as accepted in the ficha.",
                    )
                )
    return out


def _to_minutes(token: str) -> int:
    m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*([ap])", token.lower().replace(".", ""))
    hour, minute, ap = int(m.group(1)) % 12, int(m.group(2) or 0), m.group(3)
    return (hour + (12 if ap == "p" else 0)) * 60 + minute


def _ficha_hours(clinic: Clinic) -> dict[str, tuple[int, int]]:
    out = {}
    for block in clinic.get("hours") or []:
        hh, mm = (int(x) for x in str(block["open"]).split(":"))
        ch, cm = (int(x) for x in str(block["close"]).split(":"))
        for day in block["days"]:
            out[day] = (hh * 60 + mm, ch * 60 + cm)
    return out


def _day_key(word: str) -> str:
    word = word.lower()
    return DAY_WORDS[word] if word in DAY_WORDS else DAY_WORDS[word.rstrip("s")]  # "Sundays" -> "sunday"


def _expand_days(d1: str, d2: str | None) -> list[str]:
    a = _day_key(d1)
    if not d2:
        return [a]
    b = _day_key(d2)
    i, j = DAYS.index(a), DAYS.index(b)
    return list(DAYS[i : j + 1]) if i <= j else [a, b]


def check_hours(post: Post, clinic: Clinic) -> list[Finding]:
    want = _ficha_hours(clinic)
    out = []
    for lineno, text in post.prose:
        for m in HOURS_RE.finditer(text):
            try:
                days = _expand_days(m.group("d1"), m.group("d2"))
                span = (_to_minutes(m.group("t1")), _to_minutes(m.group("t2")))
            except (KeyError, ValueError, AttributeError):
                continue
            bad = [d for d in days if want.get(d) != span]
            if bad:
                out.append(
                    Finding(
                        "hours_mismatch",
                        BLOCK,
                        lineno,
                        _clip(m.group()),
                        f"Hours for {', '.join(bad)} do not match the ficha.",
                    )
                )
    return out


def _service_aliases(clinic: Clinic) -> set[str]:
    aliases = set()
    for s in clinic.get("services") or []:
        aliases.add(s["name"].lower())
        aliases.update(a.lower() for a in s.get("aliases") or [])
    return aliases


def check_services(post: Post, clinic: Clinic) -> list[Finding]:
    aliases = _service_aliases(clinic)
    out = []
    for lineno, text in post.prose:
        for m in SERVICE_CLAIM_RE.finditer(text):
            items = [i.strip().lower() for i in re.split(r",|\band\b|\bor\b", m.group(1)) if i.strip()]
            unknown = [i for i in items if not any(a in i or i in a for a in aliases)]
            if unknown:
                out.append(
                    Finding(
                        "service_not_in_ficha",
                        WARN,
                        lineno,
                        _clip(m.group()),
                        f"Service claim not found in the ficha: {', '.join(unknown)}.",
                    )
                )
    return out


def run(post: Post, clinic: Clinic) -> list[Finding]:
    out: list[Finding] = []
    for check in (
        check_phones,
        check_address,
        check_clinic_name,
        check_dentists,
        check_prices,
        check_insurance,
        check_hours,
        check_services,
    ):
        out.extend(check(post, clinic))
    return out

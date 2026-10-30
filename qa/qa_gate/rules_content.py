"""Deterministic content-risk rules: chatbot residue, AI tells, promises, superlatives,
testimonials, known dental myths and unsourced statistics."""

from __future__ import annotations

import re

from .findings import BLOCK, INFO, WARN, Finding
from .loader import Clinic, Post, paragraphs
from .negation import is_negated

CHATBOT_PATTERNS = (
    r"\bas an? (?:ai|artificial intelligence)(?: language model| assistant)?\b",
    r"\bas an? (?:large )?language model\b",
    r"\bi(?:'m| am) (?:just )?an? (?:ai|language model)\b",
    r"\bi (?:cannot|can't|am unable to|do not have the ability to) (?:browse|provide medical|give medical|access)\b",
    r"\bi hope this helps\b",
    r"\blet me know if you(?:'d| would)? (?:like|want|need)\b",
    r"\bhere(?:'s| is) (?:a |the |your )?(?:revised|updated|rewritten|draft|improved) (?:version|post|draft)\b",
    r"^\s*(?:certainly|sure|absolutely|of course)[!,]",
    r"\bgreat question\b",
    r"\bfeel free to (?:ask|reach out to) me\b",
    r"\bmy (?:knowledge|training) (?:cutoff|data)\b",
)
PLACEHOLDER_PATTERNS = (
    r"\[(?:insert|add|your|clinic|name|link|source|citation|todo|tbd|city|phone)[^\]]*\]",
    r"\{\{[^}]+\}\}",
    r"\bTODO\b|\bTBD\b|\blorem ipsum\b|\bXX+%",
)
AI_PHRASES = (
    r"in today'?s (?:fast[- ]paced|digital|modern|ever[- ]changing)\b",
    r"in the ever[- ]evolving\b",
    r"\bdelv(?:e|es|ing)\b",
    r"\btapestry\b",
    r"navigate the (?:complexities|world|landscape)",
    r"it(?:'s| is) (?:important|worth|crucial) (?:to )?(?:note|noting|remember)",
    r"\bgame[- ]?chang(?:er|ing)\b",
    r"\bseamless(?:ly)?\b",
    r"\belevate your\b",
    r"\blook no further\b",
    r"\bembark on\b",
    r"\ba testament to\b",
    r"let'?s (?:dive|delve|explore|unpack)\b",
    r"\bdive (?:in|into|deeper)\b",
    r"\bin (?:conclusion|summary)\b",
    r"\bat the end of the day\b",
    r"plays? a (?:crucial|vital|pivotal|key) role",
    r"\brest assured\b",
    r"\bunlock(?:s|ing)? the (?:power|secret|potential)\b",
    r"\bcomprehensive guide\b|\bultimate guide\b",
    r"\bin the realm of\b|\blandscape of\b",
    r"\bnot just [^.]{1,40}, (?:it'?s|but) ",
    r"\bwhether you(?:'re| are) [^.]{1,50}, (?:or|we)\b",
    r"\bsmile (?:of your dreams|makeover journey)\b",
)
PROHIBITED_PROMISES = (
    r"\bguarantee[sd]?\b",
    r"\b100\s?%\s*(?:success|safe|painless|effective|risk[- ]free|satisfaction)",
    r"\brisk[- ]free\b",
    r"\bpermanent(?:ly)?\s+(?:cure|fix|solution|results?)\b",
    r"\blast(?:s)?\s+(?:a|your|for a)\s+lifetime\b|\bfor life\b",
    r"\b(?:cure[sd]?)\b",
    r"\bresults? (?:are|is) (?:certain|assured)\b",
    r"\b(?:promis(?:e|es|ed)|pledg(?:e|es|ed)|assur(?:e|es|ed))\s+(?:you\s+)?(?:a|an|the|that|results?|perfect|flawless|pain|your)\b",
    r"\bnever (?:fail|fails|hurt|hurts|need)\b",
    r"\blast(?:s|ing)?\s+(?:forever|indefinitely)\b",
    r"\b(?:cannot|can't|can never|will never)\s+(?:return|come back|recur|reappear|break|fall out|wear out)\b",
)
# "<clinic or dentist> <verb> every/all ..." is an operational promise the ficha cannot back up
ABSOLUTE_CLINIC_RE = re.compile(
    r"\b(?:we|our (?:team|dentists?|office)|dr\.?\s+[A-Z][\w'\-]+(?:\s+[A-Z][\w'\-]+)?)\s+"
    r"(?:\w+\s+){0,2}?(?:complete[sd]?|finish(?:es)?|perform[sd]?|fix(?:es)?|save[sd]?|resolve[sd]?)"
    r"\s+(?:every|all|each)\b",
    re.I,
)
SUPERLATIVE_WORDS = (
    r"best|finest|top[- ]rated|top|#1|number[- ]one|leading|premier|most trusted|highest[- ]rated|"
    r"award[- ]winning|second to none|unmatched|unrivaled|unrivalled|unbeatable"
)
SELF_SUPERLATIVE_TEMPLATE = (
    r"\b(?:we(?:'re| are)|our (?:practice|clinic|office|team|dentists?)(?: is| are)?|__CLINIC__(?: is)?)\b"
    r"[^.!?]{0,40}?\b(?:" + SUPERLATIVE_WORDS + r")\b"
)
SUPERLATIVE_RE = re.compile(
    r"\b(?:best|finest|top[- ]rated|top|#1|number[- ]one|leading|premier|"
    r"most trusted|highest[- ]rated|award[- ]winning)"
    r"\s+(?:[\w\-]+\s+){0,2}?(?:dentist|dentists|dentistry|"
    r"dental (?:practice|office|clinic|care|provider|team)|practice|clinic)\b",
    re.I,
)
TESTIMONIAL_PATTERNS = (
    r"[\"“][^\"”]{20,}[\"”]\s*[-–—]\s*[A-Z][a-z]+",
    r"^\s*>.*[-–—]\s*[A-Z][a-z]+\b",
    r"\b(?:one|a|another|our)\s+(?:of our\s+)?patients?\s+(?:told|said|shared|wrote|recently said|recently told)\b",
    r"\bpatient (?:review|testimonial|story)\b",
    r"\b(?:5|five)[- ]star (?:reviews?|ratings?)\b",
    r"\bwhat our patients (?:are )?say",
    r"\b(?:says|said|told us|shared)[:,]?\s*[\"“]",
    r"[\"”],?\s*(?:says|said|writes|wrote|shared)\s+[A-Z][a-z]+",
    r"\b(?:a|one) (?:recent|happy|satisfied|longtime) patient\b",
    r"\b(?:a|one|another)\s+(?:\w+\s+){0,2}patients?\b[^.]{0,100}"
    r"\b(?:told|said|shared|wrote|reported|came in|walked in)\b",
    r"[\"“]\s*(?:I|We|My)\b[^\"”]{20,}[\"”]",  # a quoted first-person statement reads as a patient voice
)
MYTHS = (
    (
        r"\bfluorides?\s+(?:is|are)\s+(?:a\s+)?(?:poison|toxic|dangerous|harmful)",
        "Fluoride at dental doses is not poison; this contradicts ADA guidance.",
    ),
    (
        r"\broot canals?\s+(?:cause|causes|leads? to|is linked to|are linked to)\s+"
        r"(?:cancer|disease|illness|arthritis)",
        "Root canals do not cause systemic disease.",
    ),
    (
        r"\b(?:scrub|scrubbing|scrubs)\s+(?:it|the tooth|the root)\b"
        r"|\b(?:rinse|wash|clean)\s+(?:it|the tooth)\s+with soap\b",
        "Knocked-out teeth must not be scrubbed or soaped; rinse gently with water or milk.",
    ),
    (
        r"\bbrush(?:ing)?\s+harder\s+(?:removes|cleans|is better|works)|\bthe harder you brush\b",
        "Brushing harder damages gums and enamel; it does not clean better.",
    ),
    (r"\bbaby teeth\s+(?:don'?t|do not|doesn'?t)\s+(?:matter|need)", "Baby teeth need care."),
    (
        r"\bsugar[- ]free\s+\w+\s+(?:can'?t|cannot|never)\s+cause",
        "Sugar-free products can still contribute to decay (acid, other carbs).",
    ),
    (r"\bbleeding gums?\s+(?:is|are)\s+(?:normal|nothing)", "Bleeding gums are a sign of gum disease, not normal."),
    (
        r"\bantibiotics?\s+(?:will|can|should)\s+(?:cure|fix)\s+(?:a\s+)?(?:cavity|cavities|toothache)",
        "Antibiotics do not fix cavities.",
    ),
    (r"\bdon'?t need to (?:floss|see a dentist)\b", "Skipping flossing or dental visits is not safe advice."),
    (
        r"\baspirin\s+(?:directly\s+)?(?:against|on|onto|next to)\s+(?:the\s+|your\s+)?(?:gum|tooth|teeth)",
        "Aspirin placed on gums or teeth burns the tissue; swallow it as directed.",
    ),
    (r"\bwhitening\s+(?:kills|damages)\s+the\s+(?:nerve|tooth)", "Professional whitening does not kill the tooth."),
)
STAT_PATTERNS = (
    r"\b\d+(?:\.\d+)?\s?%",
    r"\b\d+\s+(?:out of|in)\s+\d+\b",
    r"\b(?:studies|research|surveys?|trials|data|statistics|experts|researchers|scientists)\s+(?:(?:have|has|also|consistently|repeatedly|clearly)\s+)*(?:show|shown|shows|suggest|suggests|found|find|finds|indicate|indicates|confirm|confirms|demonstrate[sd]?|prove[sd]?)\b",
    r"\baccording to (?:a |the |one )?(?:recent |new |major )?(?:study|survey|report|research)\b",
    r"\b(?:clinically|scientifically) proven\b",
    # a universal quantifier tied to a fixed number or duration: "every adult ... in six weeks"
    r"\b(?:every|all|each)\b[^.]{0,60}?\b(?:in|within|after|by)\s+(?:just\s+|only\s+)?(?:about\s+)?"
    r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|twelve)\s+(?:days?|weeks?|months?|years?|hours?)\b",
)
LINK_RE = re.compile(r"\]\(https?://|https?://")


def _first_match(patterns, text: str, flags=re.I):
    for p in patterns:
        m = re.search(p, text, flags)
        if m:
            return m
    return None


def _sentence_start(text: str, pos: int) -> int:
    cut = max(text.rfind(". ", 0, pos), text.rfind("! ", 0, pos), text.rfind("? ", 0, pos))
    return cut + 2 if cut >= 0 else 0


def check_chatbot(post: Post, clinic: Clinic) -> list[Finding]:
    out = []
    for lineno, text in post.prose:
        m = _first_match(CHATBOT_PATTERNS, text)
        if m:
            out.append(
                Finding("chatbot_residue", BLOCK, lineno, m.group().strip(), "Chatbot residue left in the draft.")
            )
        p = _first_match(PLACEHOLDER_PATTERNS, text, 0)
        if p:
            out.append(Finding("placeholder", BLOCK, lineno, p.group().strip(), "Placeholder left in the draft."))
    return out


def check_ai_phrases(post: Post, clinic: Clinic) -> list[Finding]:
    out = []
    for lineno, text in post.prose:
        for pattern in AI_PHRASES:
            for m in re.finditer(pattern, text, re.I):
                out.append(
                    Finding(
                        "ai_phrase",
                        WARN,
                        lineno,
                        m.group().strip(),
                        "Typical AI-writing phrase; rewrite with a concrete detail.",
                    )
                )
    dashes = sum(text.count("—") for _, text in post.prose)
    words = max(1, sum(len(t.split()) for _, t in post.prose))
    if dashes / words * 1000 > 8:
        out.append(
            Finding(
                "ai_em_dash_density",
                INFO,
                0,
                f"{dashes} em dashes / {words} words",
                "High em-dash density is a style tell (weak signal).",
            )
        )
    return out


def check_promises(post: Post, clinic: Clinic) -> list[Finding]:
    out = []
    for lineno, text in post.prose:
        for pattern in PROHIBITED_PROMISES:
            for m in re.finditer(pattern, text, re.I):
                if is_negated(text, m.start()):
                    continue
                out.append(
                    Finding(
                        "prohibited_promise",
                        BLOCK,
                        lineno,
                        m.group().strip(),
                        "Outcome guarantee or absolute claim; not allowed in dental advertising.",
                    )
                )
    return out


def check_superlatives(post: Post, clinic: Clinic) -> list[Finding]:
    """A link in the paragraph does not prove the clinic is 'best', so only ficha awards excuse it.

    Two shapes: '<superlative> ... dentist/practice' and 'we are / our team ... <superlative>'."""
    out = []
    if clinic.get("awards"):
        return out
    self_re = re.compile(SELF_SUPERLATIVE_TEMPLATE.replace("__CLINIC__", re.escape(clinic.name)), re.I)
    for lineno, text in post.prose:
        spans = [m for rx in (SUPERLATIVE_RE, self_re) for m in rx.finditer(text)]
        for m in spans[:1]:  # one finding per line is enough
            out.append(
                Finding(
                    "unsupported_superlative",
                    WARN,
                    lineno,
                    m.group().strip(),
                    "'Best/top' claim with no verifiable basis in the ficha.",
                )
            )
    return out


def check_testimonials(post: Post, clinic: Clinic) -> list[Finding]:
    if clinic.get("testimonials_on_file"):
        return []
    out = []
    for lineno, text in post.prose:
        m = _first_match(TESTIMONIAL_PATTERNS, text, re.I | re.M)
        if m:
            out.append(
                Finding(
                    "fake_testimonial",
                    BLOCK,
                    lineno,
                    m.group().strip()[:90],
                    "Patient testimonial with none on file (FTC 16 CFR 465 risk).",
                )
            )
    return out


def check_myths(post: Post, clinic: Clinic) -> list[Finding]:
    out = []
    for lineno, text in post.prose:
        for pattern, why in MYTHS:
            m = re.search(pattern, text, re.I)
            if m and not is_negated(text, m.start()):
                out.append(Finding("medical_myth", BLOCK, lineno, m.group().strip(), why))
    return out


def check_unsourced_stats(post: Post, clinic: Clinic) -> list[Finding]:
    out = []
    for para in paragraphs(post):
        if any(LINK_RE.search(t) for _, t in para):
            continue
        for lineno, text in para:
            m = _first_match(STAT_PATTERNS, text)
            if m:
                s = _sentence_start(text, m.start())
                out.append(
                    Finding(
                        "unsourced_stat",
                        WARN,
                        lineno,
                        text[s : s + 110].strip(),
                        "Statistic or study claim with no source link in the paragraph.",
                    )
                )
    return out


RAW_HTML_RE = re.compile(r"<!--|</?[a-zA-Z][\w:-]*(?:\s[^<>]*)?/?>")


def check_raw_html(post: Post, clinic: Clinic) -> list[Finding]:
    """Posts are Markdown. A raw tag (script, iframe, img onerror, style ...) is never intended and the site
    renders it."""
    out = []
    for lineno, text in post.prose:
        m = RAW_HTML_RE.search(text)
        if m:
            out.append(
                Finding(
                    "raw_html",
                    BLOCK,
                    lineno,
                    m.group()[:80],
                    "Raw HTML in a Markdown post; remove it (autolinks like <https://...> are fine).",
                )
            )
    return out


def check_clinic_absolutes(post: Post, clinic: Clinic) -> list[Finding]:
    out = []
    for lineno, text in post.prose:
        m = ABSOLUTE_CLINIC_RE.search(text)
        if m:
            out.append(
                Finding(
                    "absolute_clinic_claim",
                    WARN,
                    lineno,
                    m.group().strip(),
                    "Absolute claim about how the clinic or a dentist works; the ficha does not support it.",
                )
            )
    return out


def run_generic(post: Post, clinic: Clinic) -> list[Finding]:
    """Rules that are not about dentistry (chatbot residue, AI phrases, raw HTML), for other site profiles."""
    out: list[Finding] = []
    for check in (check_chatbot, check_ai_phrases, check_raw_html):
        out.extend(check(post, clinic))
    return out


def run(post: Post, clinic: Clinic) -> list[Finding]:
    out: list[Finding] = []
    for check in (
        check_chatbot,
        check_ai_phrases,
        check_promises,
        check_superlatives,
        check_testimonials,
        check_myths,
        check_unsourced_stats,
        check_clinic_absolutes,
        check_raw_html,
    ):
        out.extend(check(post, clinic))
    return out

"""Frontmatter and JSON-LD schema checks (valid, complete, coherent with the post and the ficha)."""

from __future__ import annotations

import json
import re

from .findings import BLOCK, WARN, Finding
from .loader import Clinic, Post
from .rules_facts import dentist_names

REQUIRED_FIELDS = ("title", "description", "slug", "date", "updated", "author", "reviewed_by", "category")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TITLE_MAX = 70
DESC_MIN, DESC_MAX = 70, 160


def _person_key(name: str) -> str:
    name = re.sub(r",.*$", "", str(name).lower())
    return re.sub(r"^dr\.?\s+", "", name).strip()


def _key_line(post: Post, key: str) -> int:
    """1-based file line of a frontmatter key (1 when it is absent)."""
    for idx in range(1, max(post.frontmatter_end - 1, 1)):
        if post.lines[idx].startswith(f"{key}:"):
            return idx + 1
    return 1


def check_frontmatter(post: Post, clinic: Clinic) -> list[Finding]:
    if post.frontmatter_error:
        return [Finding("frontmatter_invalid", BLOCK, 1, post.frontmatter_error, "Frontmatter missing or unparseable.")]
    fm, out = post.frontmatter, []
    for key in REQUIRED_FIELDS:
        if not fm.get(key):
            out.append(Finding("frontmatter_missing_field", BLOCK, 1, key, f"Required field '{key}' is missing."))
    for key in ("date", "updated"):
        if fm.get(key) and not DATE_RE.match(str(fm[key])):
            out.append(
                Finding(
                    "frontmatter_bad_value",
                    BLOCK,
                    _key_line(post, key),
                    f"{key}: {fm[key]}",
                    f"'{key}' must be YYYY-MM-DD.",
                )
            )
    if fm.get("date") and fm.get("updated") and str(fm["updated"]) < str(fm["date"]):
        out.append(
            Finding(
                "frontmatter_bad_value",
                BLOCK,
                1,
                f"updated {fm['updated']} < date {fm['date']}",
                "'updated' is earlier than 'date'.",
            )
        )
    if fm.get("slug") and not SLUG_RE.match(str(fm["slug"])):
        out.append(
            Finding(
                "frontmatter_bad_value",
                BLOCK,
                _key_line(post, "slug"),
                f"slug: {fm['slug']}",
                "Slug must be lowercase-hyphenated.",
            )
        )
    if fm.get("title") and len(str(fm["title"])) > TITLE_MAX:
        out.append(
            Finding(
                "frontmatter_length",
                WARN,
                _key_line(post, "title"),
                str(fm["title"]),
                f"Title longer than {TITLE_MAX} characters.",
            )
        )
    desc = str(fm.get("description") or "")
    if desc and not DESC_MIN <= len(desc) <= DESC_MAX:
        out.append(
            Finding(
                "frontmatter_length",
                WARN,
                _key_line(post, "description"),
                f"{len(desc)} chars",
                f"Description should be {DESC_MIN}-{DESC_MAX} characters.",
            )
        )
    allowed = dentist_names(clinic)
    for key in ("author", "reviewed_by"):
        if fm.get(key) and _person_key(fm[key]) not in allowed:
            out.append(
                Finding(
                    "dentist_not_in_roster",
                    BLOCK,
                    _key_line(post, key),
                    f"{key}: {fm[key]}",
                    f"'{key}' is not on the ficha dentist roster.",
                )
            )
    return out


def _load_blocks(post: Post) -> tuple[list[tuple[int, dict]], list[Finding]]:
    blocks, findings = [], []
    for lineno, raw in post.jsonld:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            findings.append(Finding("schema_invalid_json", BLOCK, lineno, str(exc)[:80], "JSON-LD is not valid JSON."))
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict):
                blocks.append((lineno, item))
    return blocks, findings


def _norm(text: str) -> str:
    return re.sub(r"\W+", " ", str(text).lower()).strip()


def _mismatch(lineno: int, field: str, schema_val, post_val) -> Finding:
    return Finding(
        "schema_mismatch",
        BLOCK,
        lineno,
        f"{field}: schema={schema_val!r} vs post={post_val!r}",
        f"JSON-LD '{field}' does not match the post.",
    )


def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _name_of(value) -> str:
    """Name of a schema.org Person/Organization given as str, dict, or a list of either."""
    first = _as_list(value)[0] if _as_list(value) else None
    if isinstance(first, str):
        return first
    if isinstance(first, dict) and isinstance(first.get("name"), str):
        return first["name"]
    return ""


def _text_of(value) -> str:
    first = _as_list(value)[0] if _as_list(value) else None
    if isinstance(first, str):
        return first
    if isinstance(first, dict) and isinstance(first.get("text"), str):
        return first["text"]
    return ""


def _kinds(item: dict) -> set[str]:
    return {str(k) for k in _as_list(item.get("@type"))}


def _phones(value) -> list:
    """Every 'telephone' value anywhere in a JSON-LD tree."""
    found = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "telephone":
                found.append(child)
            else:
                found.extend(_phones(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_phones(child))
    return found


def _check_blogposting(lineno: int, item: dict, post: Post, clinic: Clinic) -> list[Finding]:
    fm, out = post.frontmatter, []
    pairs = (("headline", fm.get("title")), ("datePublished", fm.get("date")), ("dateModified", fm.get("updated")))
    for field, want in pairs:
        if want is not None and str(item.get(field)) != str(want):
            out.append(_mismatch(lineno, field, item.get(field), want))
    author = _name_of(item.get("author"))
    if fm.get("author") and _person_key(author) != _person_key(fm["author"]):
        out.append(_mismatch(lineno, "author.name", author, fm["author"]))
    elif author and _person_key(author) not in dentist_names(clinic):
        out.append(
            Finding("schema_mismatch", BLOCK, lineno, f"author.name={author!r}", "Schema author is not on the roster.")
        )
    pub = _name_of(item.get("publisher"))
    if pub and pub != clinic.name:
        out.append(_mismatch(lineno, "publisher.name", pub, clinic.name))
    url = item.get("url") or item.get("mainEntityOfPage")
    url = url.get("@id", "") if isinstance(url, dict) else str(url or "")
    if url and fm.get("slug") and not str(url).rstrip("/").endswith(str(fm["slug"])):
        out.append(_mismatch(lineno, "url", url, f".../{fm['slug']}"))
    return out


def _check_faq(lineno: int, item: dict, post: Post) -> list[Finding]:
    text = _norm(post.prose_text)
    out = []
    for q in _as_list(item.get("mainEntity")):
        if not isinstance(q, dict):
            out.append(Finding("schema_invalid", BLOCK, lineno, str(q)[:60], "FAQPage entry is not a Question object."))
            continue
        question = q.get("name") if isinstance(q.get("name"), str) else ""
        answer = _text_of(q.get("acceptedAnswer"))
        if not question or _norm(question) not in text:
            out.append(
                Finding(
                    "schema_mismatch",
                    BLOCK,
                    lineno,
                    f"FAQ question not in post: {question[:60]}",
                    "FAQPage question is not visible in the post text.",
                )
            )
        elif _norm(answer) not in text:
            out.append(
                Finding(
                    "schema_mismatch",
                    BLOCK,
                    lineno,
                    f"FAQ answer differs: {answer[:60]}",
                    "FAQPage answer does not match the answer shown in the post.",
                )
            )
    return out


def check_schema(post: Post, clinic: Clinic) -> list[Finding]:
    blocks, out = _load_blocks(post)
    if not post.jsonld:
        return [Finding("schema_missing", WARN, 0, "", "No JSON-LD block in the post.")]
    kinds = set().union(*(_kinds(item) for _, item in blocks)) if blocks else set()
    if blocks and "BlogPosting" not in kinds:
        out.append(Finding("schema_missing", WARN, 0, ", ".join(sorted(kinds)), "No BlogPosting JSON-LD found."))
    for lineno, item in blocks:
        if item.get("@context") not in ("https://schema.org", "http://schema.org"):
            out.append(
                Finding("schema_invalid", BLOCK, lineno, str(item.get("@context")), "Missing or wrong @context.")
            )
        item_kinds = _kinds(item)
        if "BlogPosting" in item_kinds:
            out.extend(_check_blogposting(lineno, item, post, clinic))
        if "FAQPage" in item_kinds:
            out.extend(_check_faq(lineno, item, post))
        for phone in _phones(item):
            if not isinstance(phone, str) or re.sub(r"\D", "", phone).lstrip("1") != clinic.phone_digits.lstrip("1"):
                out.append(_mismatch(lineno, "telephone", phone, clinic.get("nap", {}).get("phone")))
    return out


def run(post: Post, clinic: Clinic) -> list[Finding]:
    return check_frontmatter(post, clinic) + check_schema(post, clinic)

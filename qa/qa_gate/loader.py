"""Load the clinic ficha and parse a markdown post into frontmatter, prose and JSON-LD."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from . import miniyaml

_SCRIPT_OPEN = re.compile(r"<script\b[^>]*application/ld\+json[^>]*>", re.I)
_SCRIPT_CLOSE = re.compile(r"</script>", re.I)
_FENCE = re.compile(r"^\s*(```|~~~)")


@dataclass(frozen=True)
class Post:
    path: Path
    frontmatter: dict
    frontmatter_error: str | None
    lines: tuple[str, ...]
    prose: tuple[tuple[int, str], ...]  # (1-based line, text) outside frontmatter/code/JSON-LD
    jsonld: tuple[tuple[int, str], ...]  # (1-based first line, raw JSON text)
    frontmatter_end: int = 0  # 1-based line of the closing '---' (0 = no frontmatter)

    @property
    def name(self) -> str:
        return self.path.stem

    @property
    def prose_text(self) -> str:
        return "\n".join(text for _, text in self.prose)


@dataclass(frozen=True)
class Clinic:
    data: dict
    raw_text: str = ""
    host: str = field(init=False, default="")

    def __post_init__(self):
        object.__setattr__(self, "host", urlparse(self.data.get("website", "")).netloc.lower())

    def get(self, key, default=None):
        return self.data.get(key, default)

    @property
    def name(self) -> str:
        return self.data.get("name", "")

    @property
    def phone_digits(self) -> str:
        return re.sub(r"\D", "", self.data.get("nap", {}).get("phone", ""))


def load_clinic(path: str | Path) -> Clinic:
    text = Path(path).read_text(encoding="utf-8")
    return Clinic(miniyaml.loads(text), text)


def parse_post_text(text: str, path: str | Path = "post.md") -> Post:
    lines = text.splitlines()
    fm: dict = {}
    fm_error = None
    body_start = 0
    fm_end = 0
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if end is None:
            fm_error = "frontmatter opened with '---' but never closed"
            body_start = len(lines)
        else:
            try:
                parsed = miniyaml.loads("\n".join(lines[1:end]))
                fm = parsed if isinstance(parsed, dict) else {}
                if not isinstance(parsed, dict):
                    fm_error = "frontmatter is not a key/value map"
            except miniyaml.YamlError as exc:
                fm_error = f"frontmatter is not valid YAML: {exc}"
            body_start = end + 1
            fm_end = end + 1
    else:
        fm_error = "no frontmatter block (file must start with '---')"

    prose: list[tuple[int, str]] = []
    jsonld: list[tuple[int, str]] = []
    in_fence = False
    script_start = 0
    script_buf: list[str] = []
    for idx in range(body_start, len(lines)):
        line, lineno = lines[idx], idx + 1
        if script_start:
            close = _SCRIPT_CLOSE.search(line)
            script_buf.append(line[: close.start()] if close else line)
            if close:
                # report the line where the JSON itself starts, not the <script> tag line
                first = next((k for k, chunk in enumerate(script_buf) if chunk.strip()), 0)
                jsonld.append((script_start + first, "\n".join(script_buf)))
                script_start, script_buf = 0, []
            continue
        opener = _SCRIPT_OPEN.search(line)
        if opener:
            rest = line[opener.end() :]
            close = _SCRIPT_CLOSE.search(rest)
            if close:
                jsonld.append((lineno, rest[: close.start()]))
            else:
                script_start, script_buf = lineno, [rest]
            continue
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            prose.append((lineno, line))
    if script_start:  # unterminated script: keep what we saw so the schema rule can fail it
        jsonld.append((script_start, "\n".join(script_buf)))
    return Post(Path(path), fm, fm_error, tuple(lines), tuple(prose), tuple(jsonld), fm_end)


def load_post(path: str | Path) -> Post:
    return parse_post_text(Path(path).read_text(encoding="utf-8"), path)


def paragraphs(post: Post) -> list[list[tuple[int, str]]]:
    """Group prose lines into paragraphs (blank-line separated)."""
    out, cur = [], []
    for lineno, text in post.prose:
        if text.strip():
            cur.append((lineno, text))
        elif cur:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out

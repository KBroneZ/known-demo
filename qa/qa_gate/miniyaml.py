"""Tiny YAML-subset parser so the gate runs on the Python stdlib alone.

Supported: nested maps, lists of scalars or maps, inline ``[a, b]`` lists,
quoted and plain scalars, ``#`` comments. Not supported: anchors, block scalars
(``|`` / ``>``), flow maps, multi-document files. Fixtures are written within this
subset; tests compare the output with PyYAML when it is installed.
"""

from __future__ import annotations

import re

_INT = re.compile(r"^-?\d+$")
_FLOAT = re.compile(r"^-?\d+\.\d+$")


class YamlError(ValueError):
    pass


def _strip_comment(line: str) -> str:
    quote = ""
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i]
    return line


def _split_top(text: str, sep: str) -> list[str]:
    parts, buf, quote = [], [], ""
    for ch in text:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch == sep:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return parts


def _scalar(raw: str):
    raw = raw.strip()
    if raw == "" or raw in ("~", "null"):
        return None
    if raw[0] in "\"'" and raw[-1] == raw[0] and len(raw) >= 2:
        inner = raw[1:-1]
        inner = inner.replace('\\"', '"').replace("\\\\", "\\") if raw[0] == '"' else inner.replace("''", "'")
        return inner
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        return [] if not inner else [_scalar(p) for p in _split_top(inner, ",")]
    if raw in ("true", "True"):
        return True
    if raw in ("false", "False"):
        return False
    if _INT.match(raw):
        return int(raw)
    if _FLOAT.match(raw):
        return float(raw)
    return raw


def _split_key(text: str):
    """Return (key, rest) when text is ``key: rest`` / ``key:``; else None."""
    if text[:1] in "\"'":
        return None
    for m in re.finditer(r":(?:\s|$)", text):
        return text[: m.start()].strip(), text[m.end() :].strip()
    return None


def _parse_block(lines, i, indent):
    text = lines[i][1]
    if text == "-" or text.startswith("- "):
        return _parse_list(lines, i, indent)
    return _parse_map(lines, i, indent)


def _parse_map(lines, i, indent):
    out: dict = {}
    while i < len(lines):
        ind, text = lines[i]
        if ind < indent or text == "-" or text.startswith("- "):
            break
        if ind > indent:
            raise YamlError(f"unexpected indent at {text!r}")
        kv = _split_key(text)
        if kv is None:
            raise YamlError(f"expected 'key: value', got {text!r}")
        key, rest = kv
        if key in out:
            raise YamlError(f"duplicate key {key!r}")
        i += 1
        if rest:
            out[key] = _scalar(rest)
        elif i < len(lines) and (lines[i][0] > indent or (lines[i][0] == indent and lines[i][1].startswith("- "))):
            out[key], i = _parse_block(lines, i, lines[i][0])
        else:
            out[key] = None
    return out, i


def _parse_list(lines, i, indent):
    out: list = []
    while i < len(lines):
        ind, text = lines[i]
        if ind != indent or not (text == "-" or text.startswith("- ")):
            break
        item = text[1:].strip()
        if not item:
            i += 1
            val, i = _parse_block(lines, i, lines[i][0])
        elif _split_key(item) is not None:
            lines[i] = (indent + 2, item)
            val, i = _parse_map(lines, i, indent + 2)
        else:
            val, i = _scalar(item), i + 1
        out.append(val)
    return out, i


def loads(text: str):
    lines = []
    for raw in text.splitlines():
        stripped = _strip_comment(raw).rstrip()
        if stripped.strip():
            lines.append((len(stripped) - len(stripped.lstrip(" ")), stripped.strip()))
    if not lines:
        return {}
    value, end = _parse_block(lines, 0, lines[0][0])
    if end != len(lines):
        raise YamlError(f"could not parse near {lines[end][1]!r}")
    return value

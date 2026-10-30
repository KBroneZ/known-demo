"""The one edit the pipeline makes to a site's clinic.yaml: add a /blog/<slug> route to the `pages` list.

`pages` is the site's route contract (check-links compares it with the built routes), so publishing a post without it
fails the website's gate. Only that list changes, by one inserted line, and the result is verified.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from qa_gate import miniyaml
from qa_gate.loader import parse_post_text

PAGES_ANY = re.compile(r"^pages:")  # the key, in any form
PAGES_BLOCK = re.compile(r"^pages:\s*(#.*)?$")  # the form this module can edit: a block list on the following lines
LIST_ITEM = re.compile(r"^(\s*)-\s+(\S.*?)\s*$")  # indented or not: `pages:` then `- /about` is valid YAML
COMMENT = re.compile(r"^\s*#")


class PagesEditError(RuntimeError):
    pass


def add_page_route(yaml_path: Path, route: str) -> bool:
    """Insert `- <route>` into the top-level `pages:` block list.

    Returns False only when the site has no `pages` key (no route contract) or the route is already listed. If the key
    exists in a form this cannot edit (inline list, no items) it raises: a silent no-op would publish a post that makes
    the website's own check fail."""
    with open(yaml_path, encoding="utf-8", newline="") as fh:  # newline="": keep the file's own line endings
        original = fh.read()
    lines = original.splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines) if PAGES_ANY.match(line)), None)
    if start is None:
        return False
    if not PAGES_BLOCK.match(lines[start].rstrip("\r\n")):
        raise PagesEditError("`pages` is written as an inline list or a scalar; add the route to it by hand")
    items = []
    for j in range(start + 1, len(lines)):
        text = lines[j].rstrip("\r\n")
        m = LIST_ITEM.match(text)
        if m:
            items.append((j, m.group(1), m.group(2)))
        elif not COMMENT.match(text):
            break
    if not items:
        raise PagesEditError("`pages:` exists but no list items could be read under it")
    if any(value == route for _, _, value in items):
        return False
    blog_items = [it for it in items if it[2].startswith("/blog/")]
    at, indent, _ = (blog_items or items)[-1]
    eol = "\r\n" if lines[at].endswith("\r\n") else "\n"
    if not lines[at].endswith(("\n", "\r")):  # list item was the last line of the file
        lines[at] += eol
    lines.insert(at + 1, f"{indent}- {route}{eol}")
    updated = "".join(lines)
    verify_only_pages_changed(original, updated, route)
    write_atomic(yaml_path, updated)
    return True


def write_atomic(path: Path, text: str) -> None:
    """Write beside the target and swap it in, so a crash mid-write cannot leave a truncated clinic.yaml."""
    tmp = path.with_name(f".{path.name}.tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    os.replace(tmp, path)


def verify_only_pages_changed(before: str, after: str, route: str) -> None:
    old, new = miniyaml.loads(before), miniyaml.loads(after)
    if {k: v for k, v in old.items() if k != "pages"} != {k: v for k, v in new.items() if k != "pages"}:
        raise PagesEditError("clinic.yaml changed outside `pages`")
    if route not in new["pages"]:
        raise PagesEditError("the route did not land in `pages`")
    if len(after.splitlines()) != len(before.splitlines()) + 1:
        raise PagesEditError("expected exactly one added line")


def sync_posts(site_root: Path) -> list[str]:
    """Add a route for every post file that has none yet. Returns the routes added (idempotent)."""
    added = []
    for post in sorted((site_root / "src" / "content" / "posts").glob("*.md")):
        slug = parse_post_text(post.read_text(encoding="utf-8")).frontmatter.get("slug", post.stem)
        if add_page_route(site_root / "clinic.yaml", f"/blog/{slug}"):
            added.append(f"/blog/{slug}")
    return added

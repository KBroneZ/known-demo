import json

import pytest

from qa_gate import miniyaml
from qa_gate.loader import paragraphs, parse_post_text


def test_scalars_and_nested_maps():
    data = miniyaml.loads('a: 1\nb: "x: y"  # comment\nc:\n  d: true\n  e: [1, "two", three]\n')
    assert data == {"a": 1, "b": "x: y", "c": {"d": True, "e": [1, "two", "three"]}}


def test_list_of_maps_and_scalars():
    data = miniyaml.loads("items:\n  - name: A\n    tags: [x, y]\n  - name: B\nplain:\n  - one\n  - two\n")
    assert data["items"] == [{"name": "A", "tags": ["x", "y"]}, {"name": "B"}]
    assert data["plain"] == ["one", "two"]


def test_hash_inside_quotes_is_not_a_comment():
    assert miniyaml.loads('price: "$#1"')["price"] == "$#1"


def test_bad_indent_raises():
    with pytest.raises(miniyaml.YamlError):
        miniyaml.loads("a: 1\n   b: 2\n")


def test_matches_pyyaml_on_the_ficha():
    yaml = pytest.importorskip("yaml")
    from conftest import QA_ROOT

    text = (QA_ROOT / "fixtures" / "clinic.yaml").read_text(encoding="utf-8")
    assert json.loads(json.dumps(miniyaml.loads(text), sort_keys=True)) == json.loads(
        json.dumps(yaml.safe_load(text), sort_keys=True, default=str)
    )


def test_post_parsing_separates_frontmatter_prose_and_jsonld():
    text = (
        '---\ntitle: T\n---\nHello\n```\ncode line\n```\n<script type="application/ld+json">\n{"a": 1}\n</script>\n'
        'Bye\n'
    )
    post = parse_post_text(text)
    assert post.frontmatter == {"title": "T"}
    assert [t for _, t in post.prose] == ["Hello", "Bye"]
    assert post.jsonld == ((9, '\n{"a": 1}\n'.strip("\n")),) or post.jsonld[0][0] == 9
    assert json.loads(post.jsonld[0][1]) == {"a": 1}


def test_missing_and_unclosed_frontmatter():
    assert parse_post_text("no frontmatter here").frontmatter_error
    assert "never closed" in parse_post_text("---\ntitle: x\nbody").frontmatter_error


def test_line_numbers_are_file_lines():
    post = parse_post_text("---\ntitle: T\n---\nfirst\n\nsecond\n")
    assert [n for n, _ in post.prose] == [4, 5, 6]
    assert [[n for n, _ in p] for p in paragraphs(post)] == [[4], [6]]


def test_duplicate_keys_raise():
    with pytest.raises(miniyaml.YamlError, match="duplicate"):
        miniyaml.loads("a: 1\nb: 2\na: 3\n")

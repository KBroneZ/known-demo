import pytest

from vistrack.extract import Brand, domain_of, extract, find_mentions, host_matches, normalize

DEE = Brand("dee", "Practice D Dental", ("Prac D Dental",), ("practice-d.example",))
ENAMEL = Brand("enamel", "Practice E Dentistry", (), ("practice-e.example",))
WORKS = Brand("works", "Practice G Smile Studio", (), ("practice-g.example",))
HDOC = Brand("hdoc", "Practice H Cosmetic Dentistry by Dr. H, DDS", ("Practice H Cosmetic Dentistry by Dr. H",), ())
AAY = Brand("ay", "Practice A Smiles", (), ("practice-a.example",))
BRANDS = [DEE, ENAMEL, WORKS, HDOC, AAY]


def ids(text):
    return [m.brand_id for m in find_mentions(text, BRANDS)]


def test_normalize_handles_case_accents_markdown_and_possessives():
    assert normalize("**Practice D Dental’s** Café") == "practice d dental cafe"
    assert normalize("[Practice E Dentistry](https://x.com)") == "practice e dentistry"
    assert normalize("Smith & Sons") == "smith and sons"


def test_mention_basic_alias_and_order():
    got = find_mentions("Try Practice A Smiles, then Prac D Dental.", BRANDS)
    assert [(m.brand_id, m.position) for m in got] == [("ay", 1), ("dee", 2)]


def test_sentence_break_blocks_false_match():
    assert ids("Visit Practice E. Dentistry in Austin varies a lot.") == []


def test_word_boundaries():
    assert ids("Practice E Dentistryland is a theme park") == []
    assert ids("Practice D Lake is lovely") == []


def test_longest_match_wins_across_brands():
    generic = Brand("generic", "Practice H Cosmetic Dentistry", (), ())
    got = find_mentions("Practice H Cosmetic Dentistry by Dr. H is downtown.", [generic, HDOC])
    assert [m.brand_id for m in got] == ["hdoc"]


def test_repeated_brand_counts_once_at_first_offset():
    got = find_mentions("Practice E Dentistry is good. Practice E Dentistry is open Saturday.", BRANDS)
    assert len(got) == 1 and got[0].offset == 0


def test_whitespace_and_hyphen_variants():
    assert ids("practice   a\nsmiles") == ["ay"]
    assert ids("Practice-A-Smiles") == ["ay"]


def test_negative_cue_same_sentence_only():
    neg = find_mentions("I would avoid Practice G Smile Studio for weekends.", BRANDS)
    assert neg[0].negative
    pos = find_mentions("Avoid long waits. Practice G Smile Studio is quick.", BRANDS)
    assert not pos[0].negative


@pytest.mark.parametrize(
    "url,host",
    [
        ("https://www.Example.com/a?utm=1", "example.com"),
        ("example.com/path", "example.com"),
        ("http://example.com:8080/x", "example.com"),
        ("https://sub.example.com./", "sub.example.com"),
        ("", ""),
    ],
)
def test_domain_of(url, host):
    assert domain_of(url) == host


def test_host_matches_subdomain_but_not_lookalikes():
    assert host_matches("blog.practice-d.example", "practice-d.example")
    assert host_matches("practice-d.example", "www.practice-d.example")
    assert not host_matches("notpractice-d.example", "practice-d.example")
    assert not host_matches("practice-d.example.evil.xyz", "practice-d.example")


def test_extract_combines_mentions_and_citations():
    ex = extract("Practice D Dental is nice.", ["https://practice-d.example/x", "https://yelp.com/y"], BRANDS)
    assert ex.mentioned_ids == {"dee"} and ex.cited_ids == {"dee"}
    assert [d for _, d, _ in ex.citations] == ["practice-d.example", "yelp.com"]


def test_extract_empty():
    ex = extract("", [], BRANDS)
    assert not ex.mentions and not ex.citations

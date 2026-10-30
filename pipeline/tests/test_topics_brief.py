from dental_pipeline import brief, clinicdata, intent, sources, topics


def titles(*items):
    return [{"id": f"id{i}", "title": t, "score": 1, "num_comments": c} for i, (t, c) in enumerate(items)]


def test_is_question():
    assert topics.is_question("Is professional teeth whitening safe for sensitive teeth?")
    assert topics.is_question("how long does a filling last before it needs replacing")
    assert not topics.is_question("My crown fell off")
    assert not topics.is_question("Short?")


def test_candidates_pick_the_most_discussed_question_and_skip_covered_services(site_a, tmp_path, monkeypatch):
    monkeypatch.setattr(topics, "CACHE_DIR", tmp_path)

    def fake_fetch(url):
        return titles(
            ("Does a filling hurt more than an extraction would?", 9),
            ("filling", 50),
            ("Should I worry about a filling on a back tooth?", 4),
        )

    cands = topics.candidates_for(site_a, fetch=fake_fetch)
    by_service = {c.service: c for c in cands}
    top = by_service["Tooth-colored fillings"]
    assert top.question == "Do tooth-colored fillings hurt?" and top.patient_wording.startswith("Does a filling hurt")
    assert top.comments == 9  # the 50-comment title is not a question
    assert "Dental implants" not in by_service and "Emergency dental care" not in by_service  # already have posts


def test_empty_archive_answer_is_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(topics, "CACHE_DIR", tmp_path)
    topics.cached_titles("clinic-a", "filling", fetch=lambda url: [])
    assert list(tmp_path.glob("*.json")) == []


def test_seed_fallback_fills_missing_services(site_b, tmp_path, monkeypatch):
    monkeypatch.setattr(topics, "CACHE_DIR", tmp_path)
    picked = topics.choose(site_b, 2, fetch=lambda url: [])
    assert {c.source for c in picked} == {"seed"} and len(picked) == 2


def test_derived_pages_include_services_and_posts(site_a, site_b):
    assert "/services/teeth-whitening" in site_a.clinic.get("pages")
    assert "/blog/dental-emergency-austin" in site_a.clinic.get("pages")
    assert "/services/clear-aligners" in site_b.clinic.get("pages")  # clinic-b has no `pages` key; it is derived


def test_hours_wording_matches_the_theme(site_a, site_b):
    assert (
        clinicdata.hours_wording(site_a.data)
        == "We are open Monday through Thursday from 8 a.m. to 5 p.m., and on Friday from 8 a.m. to 1 p.m."
    )
    assert (
        "Monday, Tuesday and Thursday from 9 a.m. to 6 p.m., Wednesday from 11 a.m. to 7 p.m."
        in clinicdata.hours_wording(site_b.data)
    )


def test_brief_uses_only_ficha_facts_and_authorized_sources(site_a):
    cand = topics.Candidate(
        "Is professional teeth whitening safe for sensitive teeth?",
        "Teeth whitening",
        "teeth-whitening",
        "whitening",
        "seed",
        "seed",
        0,
        0,
        "n/a",
    )
    b = brief.build_brief(site_a, cand)
    pool = {s["url"] for s in sources.load_pool()}
    assert b["sources"] and all(s["url"] in pool for s in b["sources"])
    assert b["sources"][0]["url"].endswith("teeth-whitening")
    assert b["author"] != b["reviewer"]
    assert "(512) 555-0142" in b["facts"] and "$395" in b["facts"]
    assert "/services/teeth-whitening" in {link["url"] for link in b["internal_links"]}
    assert "Authorized external sources" in brief.render_markdown(b)


def test_topic_without_a_source_says_so(site_b):
    cand = topics.Candidate("Do I need a zzzz?", "Tooth-colored fillings", None, "zzzz", "seed", "seed", 0, 0, "n/a")
    b = brief.build_brief(site_b, cand)
    if not b["sources"]:
        assert "link to nothing external" in brief.render_markdown(b)


def test_source_pool_urls_are_https_and_unique():
    urls = [s["url"] for s in sources.load_pool()]
    assert len(urls) == len(set(urls)) and all(u.startswith("https://") for u in urls)


def test_facts_keep_price_conditions_and_safety_sentences(site_a, site_b):
    facts_a, facts_b = clinicdata.facts_block(site_a), clinicdata.facts_block(site_b)
    assert "paying without insurance" in facts_b and "$110" in facts_b
    assert "911" in facts_b and "911" in facts_a


# topic filter ---------------------------------------------------------------------


def svc(site, name):
    return next(s for s in site.data["services"] if s["name"] == name)


def test_general_questions_become_canonical_search_queries(site_a):
    whitening = svc(site_a, "Teeth whitening")
    v = intent.classify("Is teeth whitening safe for sensitive teeth?", whitening)
    assert v.accepted and v.intent == "safety" and v.query == "Is teeth whitening safe?"
    fillings = svc(site_a, "Tooth-colored fillings")
    assert (
        intent.classify("How much does a composite filling cost?", fillings).query
        == "How much do tooth-colored fillings cost?"
    )
    assert (
        intent.classify("Does a root canal hurt?", svc(site_a, "Root canal therapy")).query == "Does a root canal hurt?"
    )


def test_the_whitening_eye_whites_title_is_rejected(site_a):
    v = intent.classify(
        "will teeth whitening be able to get my teeth as white as the whites in my eyes?",
        svc(site_a, "Teeth whitening"),
    )
    assert not v.accepted  # first person words and no search-style intent


def test_personal_cases_are_not_topics(site_a):
    v = intent.classify("My dentist said my filling is cracked, is this safe?", svc(site_a, "Tooth-colored fillings"))
    assert not v.accepted and "personal" in v.reason
    assert not intent.classify(
        "Is whitening safe at 34?", svc(site_a, "Teeth whitening")
    ).accepted  # a number is a personal detail


def test_services_the_clinic_does_not_list_are_rejected(site_a):
    v = intent.classify("Does a filling hurt more than removing wisdom teeth?", svc(site_a, "Tooth-colored fillings"))
    assert not v.accepted and "wisdom" in v.reason


def test_title_must_be_about_the_service(site_a):
    assert not intent.classify("Is mouthwash safe?", svc(site_a, "Teeth whitening")).accepted


def test_title_without_a_search_intent_is_rejected(site_a):
    v = intent.classify(
        "Whitening strips versus trays for crowded lower teeth, opinions welcome", svc(site_a, "Teeth whitening")
    )
    assert v.accepted and v.intent == "decision"  # a vs. b is an intent
    assert not intent.classify("Teeth whitening and mouthwash colors", svc(site_a, "Teeth whitening")).accepted


def test_candidate_keeps_the_patient_wording(site_a, tmp_path, monkeypatch):
    monkeypatch.setattr(topics, "CACHE_DIR", tmp_path)

    def fake(url):
        return titles(("Is a tooth-colored filling safe for adults?", 7), ("How much does a filling cost?", 5))

    cands = topics.candidates_for(site_a, fetch=fake)
    top = next(c for c in cands if c.service == "Tooth-colored fillings")
    assert (
        top.patient_wording == "Is a tooth-colored filling safe for adults?"
        and top.question == "Are tooth-colored fillings safe?"
    )
    assert top.intent == "safety" and "How much does a filling cost?" in top.related


def test_every_reddit_title_failing_the_filter_falls_back_to_the_seed_list(site_b, tmp_path, monkeypatch):
    monkeypatch.setattr(topics, "CACHE_DIR", tmp_path)
    picked = topics.choose(site_b, 2, fetch=lambda url: titles(("My filling fell out, what do I do?", 9)))
    assert {c.source for c in picked} == {"seed"}


def test_seed_questions_are_general_and_about_offered_services(site_a, site_b):
    seeds = clinicdata.miniyaml.loads(topics.SEED_PATH.read_text(encoding="utf-8"))["questions"]
    offered = {s["name"] for site in (site_a, site_b) for s in site.data["services"]}
    for q in seeds:
        assert q["service"] in offered, q
        assert not intent.PERSONAL.search(q["question"]), q
        assert not any(term in q["question"].lower() for term in intent.NOT_OFFERED), q
        assert q["question"].endswith("?"), q


def test_insurance_wording_is_the_clinics_own_not_a_rule_of_ours(site_a, site_b):
    for site in (site_a, site_b):
        facts = clinicdata.facts_block(site)
        assert "in network" in facts  # the ficha says it, so the brief must not forbid it
        assert "not 'in network'" not in facts

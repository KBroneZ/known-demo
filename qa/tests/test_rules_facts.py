from conftest import rules_of

from qa_gate import rules_facts as rf


def test_correct_phone_formats_pass(make_post, clinic):
    for text in ("Call (512) 555-0142.", "Call 512-555-0142.", "Call 512.555.0142 today.", "Call 5125550142 now."):
        assert rf.check_phones(make_post(text), clinic) == []


def test_wrong_phone_blocks(make_post, clinic):
    findings = rf.check_phones(make_post("Call (512) 555-0187."), clinic)
    assert rules_of(findings) == ["nap_phone_mismatch"]
    assert findings[0].severity == "block"


def test_tel_link_mismatch(make_post, clinic):
    assert rules_of(rf.check_phones(make_post("[call](tel:+15125550999)"), clinic)) == ["nap_phone_mismatch"]
    assert rf.check_phones(make_post("[call](tel:+15125550142)"), clinic) == []


def test_address_and_zip(make_post, clinic):
    ok = "Find us at 2214 Meridian Park Drive, Suite 110, Austin, TX 78704."
    assert rf.check_address(make_post(ok), clinic) == []
    assert rf.check_address(make_post("We are at 2214 Meridian Park Dr, Austin."), clinic) == []
    assert rules_of(rf.check_address(make_post("We are at 2241 Meridian Park Drive."), clinic)) == [
        "nap_address_mismatch"
    ]
    assert rules_of(rf.check_address(make_post("Austin, TX 78701"), clinic)) == ["nap_address_mismatch"]


def test_clinic_name_variant(make_post, clinic):
    assert rf.check_clinic_name(make_post("Visit Bluebonnet Hollow Dental today."), clinic) == []
    assert rules_of(rf.check_clinic_name(make_post("Visit Bluebonnet Hollow Dentistry."), clinic)) == [
        "nap_name_variant"
    ]


def test_dentist_roster(make_post, clinic):
    assert rf.check_dentists(make_post("Dr. Elena Marsh and Dr. Oyelaran will see you."), clinic) == []
    findings = rf.check_dentists(make_post("Dr. Brian Walsh will see you."), clinic)
    assert rules_of(findings) == ["dentist_not_in_roster"]


def test_prices_only_from_ficha(make_post, clinic):
    assert rf.check_prices(make_post("The exam is $129 and whitening is $395."), clinic) == []
    assert rules_of(rf.check_prices(make_post("Whitening is just $199."), clinic)) == ["price_not_in_ficha"]


def test_insurance_carriers(make_post, clinic):
    assert rf.check_insurance(make_post("We take Delta Dental and Cigna."), clinic) == []
    findings = rf.check_insurance(make_post("We accept Aetna and Delta Dental."), clinic)
    assert [f.evidence for f in findings] == ["Aetna"]


def test_hours_match_and_mismatch(make_post, clinic):
    ok = "We are open Monday through Thursday from 8 a.m. to 5 p.m., and on Friday from 8 a.m. to 1 p.m."
    assert rf.check_hours(make_post(ok), clinic) == []
    assert rf.check_hours(make_post("Open Mon-Thu 8:00 am - 5:00 pm."), clinic) == []
    assert rules_of(rf.check_hours(make_post("Open Monday through Friday from 8 a.m. to 6 p.m."), clinic)) == [
        "hours_mismatch"
    ]
    assert rules_of(rf.check_hours(make_post("We are open Saturday from 9 a.m. to 1 p.m."), clinic)) == [
        "hours_mismatch"
    ]


def test_service_claims(make_post, clinic):
    assert rf.check_services(make_post("We offer checkups and teeth whitening."), clinic) == []
    findings = rf.check_services(make_post("We offer sedation dentistry."), clinic)
    assert rules_of(findings) == ["service_not_in_ficha"]


def test_plural_day_names_are_checked(make_post, clinic):
    assert rules_of(rf.check_hours(make_post("We are open Sundays from 9:00 a.m. to 1:00 p.m."), clinic)) == [
        "hours_mismatch"
    ]
    assert rf.check_hours(make_post("Open Mondays through Thursdays from 8 a.m. to 5 p.m."), clinic) == []


def test_price_formats_are_normalised(make_post, clinic):
    assert rf.check_prices(make_post("The exam is $129.00 and whitening is $395."), clinic) == []
    assert rf.check_prices(make_post("The exam is $1,129."), clinic) != []


def test_negated_carrier_is_not_flagged(make_post, clinic):
    assert rf.check_insurance(make_post("We do not accept Aetna."), clinic) == []
    assert rules_of(rf.check_insurance(make_post("We accept Aetna."), clinic)) == ["insurance_not_in_ficha"]


def test_dentist_followed_by_capitalised_word(make_post, clinic):
    assert rf.check_dentists(make_post("Ask Dr. Marsh Our team is friendly."), clinic) == []
    assert rules_of(rf.check_dentists(make_post("Ask Dr. Walsh Our team is friendly."), clinic)) == [
        "dentist_not_in_roster"
    ]

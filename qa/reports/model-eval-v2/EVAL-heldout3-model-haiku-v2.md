# QA gate evaluation (heldout3 set)

Link mode: **offline (cached link results)**. Errors: 12 in 4 posts. Clean posts: 4.

- **Recall:** 9/12 = 75%
- **Precision (block+warn findings):** 53% (9 true / 8 false)
- **False positives on clean posts:** 0
- **Missed:** H3-01, H3-07, H3-10

| ID | Category | Detected | Findings on the injected line |
|---|---|---|---|
| H3-01 | medical-misinformation | **NO** | - |
| H3-02 | outcome-guarantee | yes | `prohibited_promise` |
| H3-03 | unsupported-clinic-claim | yes | `absolute_clinic_claim` |
| H3-04 | outcome-guarantee | yes | `prohibited_promise` |
| H3-05 | price-not-on-sheet | yes | `price_not_in_ficha` |
| H3-06 | insurance-not-accepted | yes | `insurance_not_in_ficha` |
| H3-07 | medical-misinformation | **NO** | - |
| H3-08 | wrong-author | yes | `dentist_not_in_roster` |
| H3-09 | invented-statistic | yes | `unsourced_stat` |
| H3-10 | medical-misinformation | **NO** | - |
| H3-11 | hours-error | yes | `hours_mismatch` |
| H3-12 | internal-link-missing-page | yes | `link_broken_internal` |

## Verdicts

| Post | Verdict |
|---|---|
| clean/01-how-often-dental-cleaning.md | PUBLICAR |
| clean/02-dental-implants-vs-bridges.md | PUBLICAR |
| clean/03-is-teeth-whitening-safe.md | PUBLICAR |
| clean/04-dental-emergency-austin.md | PUBLICAR |
| heldout3/01-root-canal-myths.md | BLOQUEAR |
| heldout3/02-tooth-colored-fillings.md | BLOQUEAR |
| heldout3/03-clear-aligners-for-adults.md | BLOQUEAR |
| heldout3/04-childs-first-dental-visit.md | BLOQUEAR |

## Unmatched block/warn findings

- heldout3/01-root-canal-myths.md:0 `schema_missing` ''
- heldout3/01-root-canal-myths.md:44 `link_unverifiable` 'https://www.aae.org/patients/root-canal-treatment/what-is-a-root-canal/root-canal-explained/'
- heldout3/01-root-canal-myths.md:45 `link_unverifiable` 'https://www.aae.org/patients/your-office-visit/post-treatment-care/'
- heldout3/02-tooth-colored-fillings.md:0 `schema_missing` ''
- heldout3/03-clear-aligners-for-adults.md:0 `schema_missing` ''
- heldout3/03-clear-aligners-for-adults.md:42 `link_broken_internal` 'https://www.bluebonnethollowdental.example/services/clear-aligners'
- heldout3/04-childs-first-dental-visit.md:0 `schema_missing` ''
- heldout3/04-childs-first-dental-visit.md:45 `link_unverifiable` 'https://www.cdc.gov/oral-health/prevention/oral-health-tips-for-children.html'

## Model layer

| Layer | Recall | Precision (block+warn) | Notes |
|---|---|---|---|
| Rules only | 3/12 | n/a (recall from the snapshot rule state) | 0 false alarms on clean posts |
| Model only | 11/12 | 52% (11 true / 10 false) | 6 off-target block/warn on clean posts; missed H3-01; cost $0.0227 |
| Rules + model | 11/12 | n/a (mixed rule states) | model adds: H3-02, H3-03, H3-04, H3-07, H3-08, H3-09, H3-10, H3-11 |
- with the model layer on, 4/4 clean posts are no longer PUBLICAR; 0 findings about the fixture-only 'fictional practice' line were ignored

Off-target model findings (block/warn):

- clean/01-how-often-dental-cleaning.md [block/fact_vs_ficha] 'We are in network with Delta Dental, Cigna and MetLife': The ficha lists Delta Dental, Cigna and MetLife only as accepted insurance and says nothing about in-network contracts, so 'in network' asse
- clean/01-how-often-dental-cleaning.md [warn/unsourced_claim] 'reviewed_by: Dr. Elena Marsh': The front matter attributes a clinical review to a named dentist, but nothing in the ficha or the post supports that a review took place, so
- clean/02-dental-implants-vs-bridges.md [warn/broken_or_fake_source] "The ADA's [MouthHealthy page on bridges](https://www.mouthhealthy.org/all-topics-a-z/bridg": I cannot verify that this exact URL exists or says what the sentence claims, so the citation is unverified and must not be published as-is.
- clean/02-dental-implants-vs-bridges.md [warn/unsourced_claim] 'most patients describe soreness afterward rather than sharp pain': This is a statistic-like statement about patient experience with no source, and a reader could take it as established fact.
- clean/03-is-teeth-whitening-safe.md [warn/broken_or_fake_source] 'https://www.mouthhealthy.org/all-topics-a-z/teeth-whitening': I cannot verify that this ADA MouthHealthy path exists, so the link may be broken or invented and cannot be confirmed to support the whiteni
- clean/04-dental-emergency-austin.md [block/false_medical_claim] 'Pain that lasts more than a day or two, or comes with fever or swelling, needs a prompt ex': Fever or swelling with a toothache can signal a spreading infection that needs same-day urgent care, and the post's own intro sends swelling
- heldout3/01-root-canal-myths.md [block/other] 'Follow the instructions from your dentist, and contact the office if pain is severe, swell': The ficha's emergency instruction is omitted, so readers with severe pain or swelling after hours are not told to call the main number and f
- heldout3/02-tooth-colored-fillings.md [block/other] 'contact your dental office rather than trying to adjust the filling yourself': The ficha gives an after-hours safety instruction (call the main number and follow the prompt for the on-call dentist), and the post omits i
- heldout3/03-clear-aligners-for-adults.md [block/broken_or_fake_source] 'https://www.bluebonnethollowdental.example/services/clear-aligners': The ficha lists the clinic's existing pages, and /services/clear-aligners is not among them, so this internal link would point to a nonexist
- heldout3/03-clear-aligners-for-adults.md [warn/other] 'pain, a bite that feels different, or other unexpected symptoms should be discussed with y': The ficha gives an after-hours emergency instruction, but the post sends pain and bite changes only to a routine discussion and omits any ur

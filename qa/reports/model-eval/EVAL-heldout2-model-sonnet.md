# QA gate evaluation (heldout2 set)

Link mode: **offline (cached link results)**. Errors: 10 in 4 posts. Clean posts: 4.

- **Recall:** 10/10 = 100%
- **Precision (block+warn findings):** 100% (11 true / 0 false)
- **False positives on clean posts:** 0
- **Missed:** none

| ID | Category | Detected | Findings on the injected line |
|---|---|---|---|
| K01 | nap | yes | `hours_mismatch` |
| K02 | ai_phrase | yes | `ai_phrase`, `ai_phrase` |
| K03 | broken_link | yes | `link_broken` |
| K04 | unsourced_stat | yes | `unsourced_stat` |
| K05 | prohibited_promise | yes | `prohibited_promise` |
| K06 | schema | yes | `schema_mismatch` |
| K07 | medical_false | yes | `medical_myth` |
| K08 | testimonial | yes | `fake_testimonial` |
| K09 | superlative | yes | `unsupported_superlative` |
| K10 | chatbot | yes | `chatbot_residue` |

## Verdicts

| Post | Verdict |
|---|---|
| clean/01-how-often-dental-cleaning.md | PUBLICAR |
| clean/02-dental-implants-vs-bridges.md | PUBLICAR |
| clean/03-is-teeth-whitening-safe.md | PUBLICAR |
| clean/04-dental-emergency-austin.md | PUBLICAR |
| heldout2/01-how-often-dental-cleaning.md | BLOQUEAR |
| heldout2/02-dental-implants-vs-bridges.md | BLOQUEAR |
| heldout2/03-is-teeth-whitening-safe.md | BLOQUEAR |
| heldout2/04-dental-emergency-austin.md | BLOQUEAR |

## Model layer

| Layer | Recall | Precision (block+warn) | Notes |
|---|---|---|---|
| Rules only | 7/10 | n/a (recall from the snapshot rule state) | 0 false alarms on clean posts |
| Model only | 10/10 | 43% (10 true / 13 false) | 4 off-target block/warn on clean posts; missed none; cost $0.2575 |
| Rules + model | 10/10 | n/a (mixed rule states) | model adds: K04, K05, K08 |
- with the model layer on, 2/4 clean posts are no longer PUBLICAR; 0 findings about the fixture-only 'fictional practice' line were ignored

Off-target model findings (block/warn):

- clean/01-how-often-dental-cleaning.md [warn/unsourced_claim] 'Tartar builds up on a timeline that is similar for most people': Tartar formation rates vary considerably between individuals, no source is given, and the claim conflicts with the post's own 'heavy tartar 
- clean/01-how-often-dental-cleaning.md [warn/fact_vs_ficha] 'We are in network with Delta Dental, Cigna and MetLife': The ficha lists these carriers as accepted, not as in network, and in-network status is a specific contractual claim that cannot be verified
- clean/01-how-often-dental-cleaning.md [warn/unsourced_claim] 'If you are new to us and paying without insurance, the new patient exam with X-rays is $12': The ficha confirms the $129 new patient exam with X-rays but does not say it applies only to patients paying without insurance.
- clean/03-is-teeth-whitening-safe.md [warn/unsourced_claim] 'Whitening is one of the most requested cosmetic treatments, and one of the most misunderst': The claim that whitening is among the most requested cosmetic treatments is a checkable statistic-style statement with no source, and the fi
- heldout2/01-how-often-dental-cleaning.md [block/broken_or_fake_source] '[cleanings and exams page](/services/cleanings-exams)': The ficha lists /services/cleanings-exams as the page path but the post links to /services/cleanings-exams, which does not exist; the valid 
- heldout2/01-how-often-dental-cleaning.md [warn/fact_vs_ficha] 'We are in network with Delta Dental, Cigna and MetLife': The ficha says these carriers are accepted, not that the clinic is in network, so the stronger claim is unsupported.
- heldout2/02-dental-implants-vs-bridges.md [warn/unsourced_claim] 'while a bridge is typically completed in fewer visits': Treatment-timeline comparison is checkable but has no supporting source and varies by case.
- heldout2/02-dental-implants-vs-bridges.md [warn/unsourced_claim] 'most patients describe soreness afterward rather than sharp pain': A statement about what most patients experience is unsourced and could set a pain expectation the clinic cannot guarantee.
- heldout2/02-dental-implants-vs-bridges.md [warn/schema_incoherent] '"publisher": {"@type": "Dentist", "name": "Bluebonnet Hollow Dental", "telephone": "(512) ': A Dentist is a local business type used as the publisher of a BlogPosting, where Organization is expected, and it lacks a url or address; th
- heldout2/03-is-teeth-whitening-safe.md [warn/unsourced_claim] 'Whitening is one of the most requested cosmetic treatments, and one of the most misunderst': This is a checkable popularity claim with no supporting source or clinic data.
- heldout2/03-is-teeth-whitening-safe.md [warn/unsourced_claim] 'Pregnancy or breastfeeding, where many dentists advise waiting.': The claim about what many dentists advise is plausible but has no cited ADA or NIDCR support.
- heldout2/03-is-teeth-whitening-safe.md [warn/schema_incoherent] '"publisher": {"@type": "Dentist", "name": "Bluebonnet Hollow Dental", "telephone": "(512) ': A Dentist is a local business type, not a valid publisher, which should be an Organization, and the JSON-LD omits the address even though th
- heldout2/04-dental-emergency-austin.md [warn/schema_incoherent] '"publisher": {"@type": "Dentist"': A BlogPosting publisher should be an Organization, and this entry omits the address and URL that appear in the visible text. The reviewer (D

# QA gate evaluation (heldout set)

Link mode: **offline (cached link results)**. Errors: 10 in 4 posts. Clean posts: 4.

- **Recall:** 10/10 = 100%
- **Precision (block+warn findings):** 100% (10 true / 0 false)
- **False positives on clean posts:** 0
- **Missed:** none

| ID | Category | Detected | Findings on the injected line |
|---|---|---|---|
| H01 | nap | yes | `insurance_not_in_ficha` |
| H02 | unsourced_stat | yes | `unsourced_stat` |
| H03 | superlative | yes | `unsupported_superlative` |
| H04 | broken_link | yes | `link_broken` |
| H05 | prohibited_promise | yes | `prohibited_promise` |
| H06 | chatbot | yes | `chatbot_residue` |
| H07 | medical_false | yes | `medical_myth` |
| H08 | testimonial | yes | `fake_testimonial` |
| H09 | schema | yes | `schema_mismatch` |
| H10 | ai_phrase | yes | `ai_phrase` |

## Verdicts

| Post | Verdict |
|---|---|
| clean/01-how-often-dental-cleaning.md | PUBLICAR |
| clean/02-dental-implants-vs-bridges.md | PUBLICAR |
| clean/03-is-teeth-whitening-safe.md | PUBLICAR |
| clean/04-dental-emergency-austin.md | PUBLICAR |
| heldout/01-how-often-dental-cleaning.md | BLOQUEAR |
| heldout/02-dental-implants-vs-bridges.md | BLOQUEAR |
| heldout/03-is-teeth-whitening-safe.md | BLOQUEAR |
| heldout/04-dental-emergency-austin.md | BLOQUEAR |

## Model layer

| Layer | Recall | Precision (block+warn) | Notes |
|---|---|---|---|
| Rules only | 7/10 | n/a (recall from the snapshot rule state) | 0 false alarms on clean posts |
| Model only | 8/10 | 53% (8 true / 7 false) | 6 off-target block/warn on clean posts; missed H04, H10; cost $0.0225 |
| Rules + model | 10/10 | n/a (mixed rule states) | model adds: H03, H07, H08 |
- with the model layer on, 4/4 clean posts are no longer PUBLICAR; 1 findings about the fixture-only 'fictional practice' line were ignored

Off-target model findings (block/warn):

- clean/01-how-often-dental-cleaning.md [block/fact_vs_ficha] 'We are in network with Delta Dental, Cigna and MetLife': The ficha lists Delta Dental, Cigna and MetLife only as accepted insurance and says nothing about in-network contracts, so 'in network' asse
- clean/01-how-often-dental-cleaning.md [warn/unsourced_claim] 'reviewed_by: Dr. Elena Marsh': The front matter attributes a clinical review to a named dentist, but nothing in the ficha or the post supports that a review took place, so
- clean/02-dental-implants-vs-bridges.md [warn/broken_or_fake_source] "The ADA's [MouthHealthy page on bridges](https://www.mouthhealthy.org/all-topics-a-z/bridg": I cannot verify that this exact URL exists or says what the sentence claims, so the citation is unverified and must not be published as-is.
- clean/02-dental-implants-vs-bridges.md [warn/unsourced_claim] 'most patients describe soreness afterward rather than sharp pain': This is a statistic-like statement about patient experience with no source, and a reader could take it as established fact.
- clean/03-is-teeth-whitening-safe.md [warn/broken_or_fake_source] 'https://www.mouthhealthy.org/all-topics-a-z/teeth-whitening': I cannot verify that this ADA MouthHealthy path exists, so the link may be broken or invented and cannot be confirmed to support the whiteni
- clean/04-dental-emergency-austin.md [block/false_medical_claim] 'Pain that lasts more than a day or two, or comes with fever or swelling, needs a prompt ex': Fever or swelling with a toothache can signal a spreading infection that needs same-day urgent care, and the post's own intro sends swelling
- heldout/03-is-teeth-whitening-safe.md [warn/broken_or_fake_source] 'https://www.mouthhealthy.org/all-topics-a-z/teeth-whitening': I cannot verify this URL from the provided materials, and the path structure looks unusual for the ADA MouthHealthy site, so the citation ma

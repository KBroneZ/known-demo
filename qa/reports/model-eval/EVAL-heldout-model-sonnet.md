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
| Model only | 10/10 | 53% (10 true / 9 false) | 4 off-target block/warn on clean posts; missed none; cost $0.2571 |
| Rules + model | 10/10 | n/a (mixed rule states) | model adds: H03, H07, H08 |
- with the model layer on, 2/4 clean posts are no longer PUBLICAR; 0 findings about the fixture-only 'fictional practice' line were ignored

Off-target model findings (block/warn):

- clean/01-how-often-dental-cleaning.md [warn/unsourced_claim] 'Tartar builds up on a timeline that is similar for most people': Tartar formation rates vary considerably between individuals, no source is given, and the claim conflicts with the post's own 'heavy tartar 
- clean/01-how-often-dental-cleaning.md [warn/fact_vs_ficha] 'We are in network with Delta Dental, Cigna and MetLife': The ficha lists these carriers as accepted, not as in network, and in-network status is a specific contractual claim that cannot be verified
- clean/01-how-often-dental-cleaning.md [warn/unsourced_claim] 'If you are new to us and paying without insurance, the new patient exam with X-rays is $12': The ficha confirms the $129 new patient exam with X-rays but does not say it applies only to patients paying without insurance.
- clean/03-is-teeth-whitening-safe.md [warn/unsourced_claim] 'Whitening is one of the most requested cosmetic treatments, and one of the most misunderst': The claim that whitening is among the most requested cosmetic treatments is a checkable statistic-style statement with no source, and the fi
- heldout/01-how-often-dental-cleaning.md [warn/broken_or_fake_source] '[cleanings and exams page](/services/cleanings-exams)': This internal link does not exist in the ficha pages list; the real page is /services/cleanings-exams only as listed, and the post uses '/se
- heldout/02-dental-implants-vs-bridges.md [warn/unsourced_claim] 'most patients describe soreness afterward rather than sharp pain': This is a checkable statement about patient experience with no source or clinic data behind it.
- heldout/03-is-teeth-whitening-safe.md [warn/broken_or_fake_source] "The ADA's [MouthHealthy page on teeth whitening](https://www.mouthhealthy.org/all-topics-a": I cannot verify that this exact URL exists or resolves, although MouthHealthy is a real ADA site and a whitening topic page plausibly exists
- heldout/03-is-teeth-whitening-safe.md [warn/unsourced_claim] 'Whitening is safe for most healthy mouths when done correctly.': A blanket safety assurance in the meta description is stronger than the body text, which says 'generally considered safe', and it has no cit
- heldout/04-dental-emergency-austin.md [warn/unsourced_claim] 'A dental cement from a pharmacy can hold it in place temporarily, but a dentist needs to s': Advice on temporary dental cement is consistent with ADA guidance but is not backed by a cited source and omits that the crown should be cle

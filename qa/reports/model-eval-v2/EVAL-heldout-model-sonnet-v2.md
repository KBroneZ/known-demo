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
| Model only | 9/10 | 75% (9 true / 3 false) | 0 off-target block/warn on clean posts; missed H10; cost $0.2499 |
| Rules + model | 10/10 | n/a (mixed rule states) | model adds: H03, H07, H08 |
- with the model layer on, 0/4 clean posts are no longer PUBLICAR; 0 findings about the fixture-only 'fictional practice' line were ignored

Off-target model findings (block/warn):

- heldout/01-how-often-dental-cleaning.md [block/broken_or_fake_source] '[cleanings and exams page](/services/cleanings-exams)': This internal link does not exist in the ficha pages list; the correct path is /services/cleanings-exams only if listed, and the listed page
- heldout/02-dental-implants-vs-bridges.md [warn/broken_or_fake_source] "The ADA's [MouthHealthy page on bridges](https://www.mouthhealthy.org/all-topics-a-z/bridg": I cannot confirm this exact MouthHealthy URL exists, so the source is unverified.
- heldout/02-dental-implants-vs-bridges.md [block/fact_vs_ficha] 'The new patient exam with X-rays is $129.': The $129 price matches the ficha, but the post states it as unconditional and also places it in the insurance context without saying it appl

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
| Model only | 9/10 | 50% (9 true / 9 false) | 4 off-target block/warn on clean posts; missed H10; cost $0.2636 |
| Rules + model | 10/10 | n/a (mixed rule states) | model adds: H03, H07, H08 |
- with the model layer on, 1/4 clean posts are no longer PUBLICAR; 0 findings about the fixture-only 'fictional practice' line were ignored

Off-target model findings (block/warn):

- clean/01-how-often-dental-cleaning.md [block/fact_vs_ficha] 'We are in network with Delta Dental, Cigna and MetLife': The ficha says these carriers are accepted, not that the clinic is in network, so the post makes a stronger insurance claim than the source 
- clean/01-how-often-dental-cleaning.md [warn/fact_vs_ficha] 'our front desk can check your benefits before you come in': Benefit verification by the front desk is not in the ficha, so it is an unverified claim about how the clinic works.
- clean/01-how-often-dental-cleaning.md [warn/fact_vs_ficha] 'If you are new to us and paying without insurance, the new patient exam with X-rays is $12': The ficha lists $129 for the new patient exam with X-rays and attaches no 'paying without insurance' condition, so the post invents a pricin
- clean/01-how-often-dental-cleaning.md [block/false_medical_claim] 'Tartar builds up on a timeline that is similar for most people': Tartar buildup varies considerably between people, and this contradicts the post's own later mention of heavy tartar buildup as a reason for
- heldout/01-how-often-dental-cleaning.md [warn/fact_vs_ficha] 'If you are new to us and paying without insurance, the new patient exam with X-rays is $12': The $129 price matches the ficha, but the added condition 'paying without insurance' is not in the ficha, so the stated condition is invente
- heldout/01-how-often-dental-cleaning.md [block/broken_or_fake_source] '[cleanings and exams page](/services/cleanings-exams)': This internal link is not in the ficha's page list; the real page is /services/cleanings-exams only under that exact path, and '/services/cl
- heldout/02-dental-implants-vs-bridges.md [block/fact_vs_ficha] 'The new patient exam with X-rays is $129.': The $129 matches the ficha figure but drops the ficha's price condition (new patients only), and its placement in the Cost and coverage sect
- heldout/02-dental-implants-vs-bridges.md [warn/broken_or_fake_source] '[MouthHealthy page on bridges](https://www.mouthhealthy.org/all-topics-a-z/bridges)': This exact MouthHealthy URL cannot be verified from here and may not exist.
- heldout/04-dental-emergency-austin.md [block/fact_vs_ficha] 'We offer same-day emergency visits when we have room in the schedule, and the emergency ex': The ficha lists the $95 emergency exam as a price without any condition, but the sentence ties same-day visits to schedule availability, whi

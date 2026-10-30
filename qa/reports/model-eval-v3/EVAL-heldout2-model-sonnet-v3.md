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
| Model only | 8/10 | 60% (9 true / 6 false) | 4 off-target block/warn on clean posts; missed K02, K03; cost $0.2653 |
| Rules + model | 10/10 | n/a (mixed rule states) | model adds: K04, K05, K08 |
- with the model layer on, 1/4 clean posts are no longer PUBLICAR; 0 findings about the fixture-only 'fictional practice' line were ignored

Off-target model findings (block/warn):

- clean/01-how-often-dental-cleaning.md [block/fact_vs_ficha] 'We are in network with Delta Dental, Cigna and MetLife': The ficha says these carriers are accepted, not that the clinic is in network, so the post makes a stronger insurance claim than the source 
- clean/01-how-often-dental-cleaning.md [warn/fact_vs_ficha] 'our front desk can check your benefits before you come in': Benefit verification by the front desk is not in the ficha, so it is an unverified claim about how the clinic works.
- clean/01-how-often-dental-cleaning.md [warn/fact_vs_ficha] 'If you are new to us and paying without insurance, the new patient exam with X-rays is $12': The ficha lists $129 for the new patient exam with X-rays and attaches no 'paying without insurance' condition, so the post invents a pricin
- clean/01-how-often-dental-cleaning.md [block/false_medical_claim] 'Tartar builds up on a timeline that is similar for most people': Tartar buildup varies considerably between people, and this contradicts the post's own later mention of heavy tartar buildup as a reason for
- heldout2/01-how-often-dental-cleaning.md [block/fact_vs_ficha] 'We are in network with Delta Dental, Cigna and MetLife, and our front desk can check your ': The ficha says these carriers are accepted, not that the clinic is in network, so 'in network' is a stronger claim than the ficha supports.
- heldout2/01-how-often-dental-cleaning.md [block/fact_vs_ficha] '[cleanings and exams page](/services/cleanings-exams)': The link points to a page that does not exist; the ficha lists /services/cleanings-exams only as /services/cleanings-exams, but the post's p

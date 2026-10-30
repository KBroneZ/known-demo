# QA gate evaluation (seeded set)

Link mode: **offline (cached link results)**. Errors: 10 in 4 posts. Clean posts: 4.

- **Recall:** 10/10 = 100%
- **Precision (block+warn findings):** 100% (13 true / 0 false)
- **False positives on clean posts:** 0
- **Missed:** none

| ID | Category | Detected | Findings on the injected line |
|---|---|---|---|
| E01 | NAP mismatch (phone) | yes | `nap_phone_mismatch` |
| E02 | Typical AI phrases | yes | `ai_phrase`, `ai_phrase`, `ai_phrase` |
| E03 | Broken link | yes | `link_broken` |
| E04 | Invented statistic, no source | yes | `unsourced_stat` |
| E05 | Prohibited promise | yes | `prohibited_promise`, `prohibited_promise` |
| E06 | Incoherent schema | yes | `schema_mismatch` |
| E07 | Invented testimonial | yes | `fake_testimonial` |
| E08 | Unsupported 'best dentist' | yes | `unsupported_superlative` |
| E09 | False/dangerous medical claim | yes | `medical_myth` |
| E10 | Chatbot residue | yes | `chatbot_residue` |

## Verdicts

| Post | Verdict |
|---|---|
| clean/01-how-often-dental-cleaning.md | PUBLICAR |
| clean/02-dental-implants-vs-bridges.md | PUBLICAR |
| clean/03-is-teeth-whitening-safe.md | PUBLICAR |
| clean/04-dental-emergency-austin.md | PUBLICAR |
| seeded/01-how-often-dental-cleaning.md | BLOQUEAR |
| seeded/02-dental-implants-vs-bridges.md | BLOQUEAR |
| seeded/03-is-teeth-whitening-safe.md | BLOQUEAR |
| seeded/04-dental-emergency-austin.md | BLOQUEAR |

## Model layer

| Layer | Recall | Precision (block+warn) | Notes |
|---|---|---|---|
| Rules only | 10/10 | 100% | 0 false alarms on clean posts |
| Model only | 10/10 | 50% (11 true / 11 false) | 4 off-target block/warn on clean posts; missed none; cost $0.2644 |
| Rules + model | 10/10 | 69% | model adds: nothing |
- with the model layer on, 2/4 clean posts are no longer PUBLICAR; 2 findings about the fixture-only 'fictional practice' line were ignored

Off-target model findings (block/warn):

- clean/01-how-often-dental-cleaning.md [warn/unsourced_claim] 'Tartar builds up on a timeline that is similar for most people': Tartar formation rates vary considerably between individuals, no source is given, and the claim conflicts with the post's own 'heavy tartar 
- clean/01-how-often-dental-cleaning.md [warn/fact_vs_ficha] 'We are in network with Delta Dental, Cigna and MetLife': The ficha lists these carriers as accepted, not as in network, and in-network status is a specific contractual claim that cannot be verified
- clean/01-how-often-dental-cleaning.md [warn/unsourced_claim] 'If you are new to us and paying without insurance, the new patient exam with X-rays is $12': The ficha confirms the $129 new patient exam with X-rays but does not say it applies only to patients paying without insurance.
- clean/03-is-teeth-whitening-safe.md [warn/unsourced_claim] 'Whitening is one of the most requested cosmetic treatments, and one of the most misunderst': The claim that whitening is among the most requested cosmetic treatments is a checkable statistic-style statement with no source, and the fi
- seeded/01-how-often-dental-cleaning.md [block/broken_or_fake_source] '[cleanings and exams page](/services/cleanings-exams)': The internal link points to a page that is not in the ficha; the existing page is /services/cleanings-exams only as listed, but the post pat
- seeded/01-how-often-dental-cleaning.md [warn/unsourced_claim] 'Tartar builds up on a timeline that is similar for most people': Tartar buildup varies considerably between people, so this is an unsupported and likely inaccurate generalization.
- seeded/01-how-often-dental-cleaning.md [warn/unsourced_claim] 'six months is long enough to see changes but short enough to catch a small problem before ': The rationale for the six-month interval is presented as fact without a source.
- seeded/01-how-often-dental-cleaning.md [warn/unsourced_claim] 'Your dentist may suggest visits every three or four months if you have any of these:': The specific three-to-four-month interval and risk factors are not backed by a source in the post.
- seeded/01-how-often-dental-cleaning.md [block/schema_incoherent] '"telephone": "(512) 555-0142"': The JSON-LD phone matches the ficha but contradicts the visible phone number in the post body.
- seeded/02-dental-implants-vs-bridges.md [warn/other] 'Habits such as grinding your teeth and smoking, and your gum health, all play a part.': The sentence is orphaned after the guarantee line and no longer follows from question 5 about repair or replacement, so the flow breaks once
- seeded/03-is-teeth-whitening-safe.md [warn/unsourced_claim] 'Pregnancy or breastfeeding, where many dentists advise waiting.': The claim about what many dentists advise is a checkable generalization with no supporting source, and the advice is a precaution rather tha

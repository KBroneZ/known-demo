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
| Model only | 10/10 | 48% (10 true / 11 false) | 6 off-target block/warn on clean posts; missed none; cost $0.0183 |
| Rules + model | 10/10 | 68% | model adds: nothing |
- with the model layer on, 4/4 clean posts are no longer PUBLICAR; 2 findings about the fixture-only 'fictional practice' line were ignored

Off-target model findings (block/warn):

- clean/01-how-often-dental-cleaning.md [warn/fact_vs_ficha] 'We are in network with Delta Dental, Cigna and MetLife': The ficha lists only Delta Dental, Cigna and MetLife as accepted insurance and says nothing about contracted in-network status, so the post 
- clean/01-how-often-dental-cleaning.md [warn/unsourced_claim] 'Tartar builds up on a timeline that is similar for most people': This claim about how uniform tartar buildup is across patients has no link or citation, and the post does not back it with dental guidance.
- clean/02-dental-implants-vs-bridges.md [warn/broken_or_fake_source] "The ADA's [MouthHealthy page on bridges](https://www.mouthhealthy.org/all-topics-a-z/bridg": I cannot verify that this MouthHealthy URL path exists or that it matches the claim, and the path structure looks unusual for that site.
- clean/02-dental-implants-vs-bridges.md [warn/unsourced_claim] 'most patients describe soreness afterward rather than sharp pain.': This statement about typical patient experience has no citation or clinic data behind it.
- clean/03-is-teeth-whitening-safe.md [warn/unsourced_claim] 'Whitening is one of the most requested cosmetic treatments, and one of the most misunderst': The claim that whitening is among the most requested cosmetic treatments has no source and cannot be verified from the ficha or any linked p
- clean/04-dental-emergency-austin.md [warn/broken_or_fake_source] "The ADA's [MouthHealthy page on dental emergencies](https://www.mouthhealthy.org/all-topic": I could not verify that this URL resolves or that the page supports the description of its contents, so the claim is unverified.
- seeded/01-how-often-dental-cleaning.md [warn/fact_vs_ficha] 'We are in network with Delta Dental, Cigna and MetLife': The ficha only says these carriers are accepted; 'in network' is a stronger contractual claim that the ficha does not support.
- seeded/01-how-often-dental-cleaning.md [warn/unsourced_claim] 'Tartar builds up on a timeline that is similar for most people': This general claim about tartar formation rate has no supporting link and is not verifiable from the ficha or the cited sources.
- seeded/02-dental-implants-vs-bridges.md [warn/broken_or_fake_source] 'https://www.mouthhealthy.org/all-topics-a-z/bridges': I cannot confirm that this exact MouthHealthy path exists, so the link may be broken or misattributed.
- seeded/04-dental-emergency-austin.md [warn/broken_or_fake_source] 'https://www.mouthhealthy.org/all-topics-a-z/dental-emergencies': I cannot verify that this exact MouthHealthy path exists or that it covers the cases described, so the citation is unverified.
- seeded/04-dental-emergency-austin.md [warn/unsourced_claim] 'If the edge is sharp, a piece of sugar-free gum or dental wax can protect your tongue unti': Sugar-free gum is not standard ADA interim guidance for a chipped tooth, and the sentence has no source, while dental wax is the commonly re

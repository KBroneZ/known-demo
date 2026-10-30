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
| Model only | 9/10 | 55% (11 true / 9 false) | 6 off-target block/warn on clean posts; missed K02; cost $0.0184 |
| Rules + model | 10/10 | n/a (mixed rule states) | model adds: K04, K05, K08 |
- with the model layer on, 4/4 clean posts are no longer PUBLICAR; 1 findings about the fixture-only 'fictional practice' line were ignored

Off-target model findings (block/warn):

- clean/01-how-often-dental-cleaning.md [warn/fact_vs_ficha] 'We are in network with Delta Dental, Cigna and MetLife': The ficha lists only Delta Dental, Cigna and MetLife as accepted insurance and says nothing about contracted in-network status, so the post 
- clean/01-how-often-dental-cleaning.md [warn/unsourced_claim] 'Tartar builds up on a timeline that is similar for most people': This claim about how uniform tartar buildup is across patients has no link or citation, and the post does not back it with dental guidance.
- clean/02-dental-implants-vs-bridges.md [warn/broken_or_fake_source] "The ADA's [MouthHealthy page on bridges](https://www.mouthhealthy.org/all-topics-a-z/bridg": I cannot verify that this MouthHealthy URL path exists or that it matches the claim, and the path structure looks unusual for that site.
- clean/02-dental-implants-vs-bridges.md [warn/unsourced_claim] 'most patients describe soreness afterward rather than sharp pain.': This statement about typical patient experience has no citation or clinic data behind it.
- clean/03-is-teeth-whitening-safe.md [warn/unsourced_claim] 'Whitening is one of the most requested cosmetic treatments, and one of the most misunderst': The claim that whitening is among the most requested cosmetic treatments has no source and cannot be verified from the ficha or any linked p
- clean/04-dental-emergency-austin.md [warn/broken_or_fake_source] "The ADA's [MouthHealthy page on dental emergencies](https://www.mouthhealthy.org/all-topic": I could not verify that this URL resolves or that the page supports the description of its contents, so the claim is unverified.
- heldout2/02-dental-implants-vs-bridges.md [warn/broken_or_fake_source] 'https://www.mouthhealthy.org/all-topics-a-z/bridges': The URL path could not be verified from the available context, so the citation cannot be confirmed to exist or to support the sentence it fo
- heldout2/03-is-teeth-whitening-safe.md [warn/unsupported_superlative] 'Whitening is one of the most requested cosmetic treatments, and one of the most misunderst': The claim that whitening is among the most requested cosmetic treatments has no source and cannot be verified from the ficha or the links pr
- heldout2/04-dental-emergency-austin.md [warn/broken_or_fake_source] "The ADA's [MouthHealthy page on dental emergencies](https://www.mouthhealthy.org/all-topic": I cannot verify from the provided materials that this URL resolves or that the page says what the post claims, so the citation is unconfirme

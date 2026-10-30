# QA gate evaluation (heldout2 set)

Link mode: **offline (cached link results)**. Errors: 10 in 4 posts. Clean posts: 4.

- **Recall:** 9/10 = 90%
- **Precision (block+warn findings):** 50% (10 true / 10 false)
- **False positives on clean posts:** 5
- **Missed:** K03

| ID | Category | Detected | Findings on the injected line |
|---|---|---|---|
| K01 | nap | yes | `hours_mismatch` |
| K02 | ai_phrase | yes | `ai_phrase`, `ai_phrase` |
| K03 | broken_link | **NO** | - |
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
| clean/01-how-often-dental-cleaning.md | CORREGIR |
| clean/02-dental-implants-vs-bridges.md | CORREGIR |
| clean/03-is-teeth-whitening-safe.md | CORREGIR |
| clean/04-dental-emergency-austin.md | CORREGIR |
| heldout2/01-how-often-dental-cleaning.md | BLOQUEAR |
| heldout2/02-dental-implants-vs-bridges.md | BLOQUEAR |
| heldout2/03-is-teeth-whitening-safe.md | BLOQUEAR |
| heldout2/04-dental-emergency-austin.md | BLOQUEAR |

## Unmatched block/warn findings

- clean/01-how-often-dental-cleaning.md:24 `link_unverified` 'https://www.nidcr.nih.gov/health-info/gum-disease'
- clean/01-how-often-dental-cleaning.md:33 `link_unverified` 'https://www.mouthhealthy.org/'
- clean/02-dental-implants-vs-bridges.md:18 `link_unverified` 'https://www.mouthhealthy.org/all-topics-a-z/bridges'
- clean/03-is-teeth-whitening-safe.md:18 `link_unverified` 'https://www.mouthhealthy.org/all-topics-a-z/teeth-whitening'
- clean/04-dental-emergency-austin.md:22 `link_unverified` 'https://www.mouthhealthy.org/all-topics-a-z/dental-emergencies'
- heldout2/01-how-often-dental-cleaning.md:24 `link_unverified` 'https://www.nidcr.nih.gov/health-info/gum-disease'
- heldout2/01-how-often-dental-cleaning.md:33 `link_unverified` 'https://www.mouthhealthy.org/'
- heldout2/02-dental-implants-vs-bridges.md:18 `link_unverified` 'https://www.mouthhealthy.org/all-topics-a-z/bridges'
- heldout2/03-is-teeth-whitening-safe.md:18 `link_unverified` 'https://www.mouthhealthy.org/all-topics-a-z/tooth-whitening-safety'
- heldout2/04-dental-emergency-austin.md:22 `link_unverified` 'https://www.mouthhealthy.org/all-topics-a-z/dental-emergencies'

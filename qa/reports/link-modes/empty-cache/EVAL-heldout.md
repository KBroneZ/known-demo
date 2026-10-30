# QA gate evaluation (heldout set)

Link mode: **offline (cached link results)**. Errors: 10 in 4 posts. Clean posts: 4.

- **Recall:** 9/10 = 90%
- **Precision (block+warn findings):** 45% (9 true / 11 false)
- **False positives on clean posts:** 5
- **Missed:** H04

| ID | Category | Detected | Findings on the injected line |
|---|---|---|---|
| H01 | nap | yes | `insurance_not_in_ficha` |
| H02 | unsourced_stat | yes | `unsourced_stat` |
| H03 | superlative | yes | `unsupported_superlative` |
| H04 | broken_link | **NO** | - |
| H05 | prohibited_promise | yes | `prohibited_promise` |
| H06 | chatbot | yes | `chatbot_residue` |
| H07 | medical_false | yes | `medical_myth` |
| H08 | testimonial | yes | `fake_testimonial` |
| H09 | schema | yes | `schema_mismatch` |
| H10 | ai_phrase | yes | `ai_phrase` |

## Verdicts

| Post | Verdict |
|---|---|
| clean/01-how-often-dental-cleaning.md | CORREGIR |
| clean/02-dental-implants-vs-bridges.md | CORREGIR |
| clean/03-is-teeth-whitening-safe.md | CORREGIR |
| clean/04-dental-emergency-austin.md | CORREGIR |
| heldout/01-how-often-dental-cleaning.md | BLOQUEAR |
| heldout/02-dental-implants-vs-bridges.md | BLOQUEAR |
| heldout/03-is-teeth-whitening-safe.md | BLOQUEAR |
| heldout/04-dental-emergency-austin.md | BLOQUEAR |

## Unmatched block/warn findings

- clean/01-how-often-dental-cleaning.md:24 `link_unverified` 'https://www.nidcr.nih.gov/health-info/gum-disease'
- clean/01-how-often-dental-cleaning.md:33 `link_unverified` 'https://www.mouthhealthy.org/'
- clean/02-dental-implants-vs-bridges.md:18 `link_unverified` 'https://www.mouthhealthy.org/all-topics-a-z/bridges'
- clean/03-is-teeth-whitening-safe.md:18 `link_unverified` 'https://www.mouthhealthy.org/all-topics-a-z/teeth-whitening'
- clean/04-dental-emergency-austin.md:22 `link_unverified` 'https://www.mouthhealthy.org/all-topics-a-z/dental-emergencies'
- heldout/01-how-often-dental-cleaning.md:24 `link_unverified` 'https://www.nidcr.nih.gov/health-info/gum-disease'
- heldout/01-how-often-dental-cleaning.md:33 `link_unverified` 'https://www.mouthhealthy.org/'
- heldout/02-dental-implants-vs-bridges.md:18 `link_unverified` 'https://www.mouthhealthy.org/all-topics-a-z/bridges'
- heldout/02-dental-implants-vs-bridges.md:28 `link_unverified` 'https://www.nidcr.nih.gov/health-info/implant-maintenance-guide'
- heldout/03-is-teeth-whitening-safe.md:18 `link_unverified` 'https://www.mouthhealthy.org/all-topics-a-z/teeth-whitening'
- heldout/04-dental-emergency-austin.md:22 `link_unverified` 'https://www.mouthhealthy.org/all-topics-a-z/dental-emergencies'

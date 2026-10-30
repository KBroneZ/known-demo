# QA gate evaluation (seeded set)

Link mode: **offline (cached link results)**. Errors: 10 in 4 posts. Clean posts: 4.

- **Recall:** 9/10 = 90%
- **Precision (block+warn findings):** 55% (12 true / 10 false)
- **False positives on clean posts:** 5
- **Missed:** E03

| ID | Category | Detected | Findings on the injected line |
|---|---|---|---|
| E01 | NAP mismatch (phone) | yes | `nap_phone_mismatch` |
| E02 | Typical AI phrases | yes | `ai_phrase`, `ai_phrase`, `ai_phrase` |
| E03 | Broken link | **NO** | - |
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
| clean/01-how-often-dental-cleaning.md | CORREGIR |
| clean/02-dental-implants-vs-bridges.md | CORREGIR |
| clean/03-is-teeth-whitening-safe.md | CORREGIR |
| clean/04-dental-emergency-austin.md | CORREGIR |
| seeded/01-how-often-dental-cleaning.md | BLOQUEAR |
| seeded/02-dental-implants-vs-bridges.md | BLOQUEAR |
| seeded/03-is-teeth-whitening-safe.md | BLOQUEAR |
| seeded/04-dental-emergency-austin.md | BLOQUEAR |

## Unmatched block/warn findings

- clean/01-how-often-dental-cleaning.md:24 `link_unverified` 'https://www.nidcr.nih.gov/health-info/gum-disease'
- clean/01-how-often-dental-cleaning.md:33 `link_unverified` 'https://www.mouthhealthy.org/'
- clean/02-dental-implants-vs-bridges.md:18 `link_unverified` 'https://www.mouthhealthy.org/all-topics-a-z/bridges'
- clean/03-is-teeth-whitening-safe.md:18 `link_unverified` 'https://www.mouthhealthy.org/all-topics-a-z/teeth-whitening'
- clean/04-dental-emergency-austin.md:22 `link_unverified` 'https://www.mouthhealthy.org/all-topics-a-z/dental-emergencies'
- seeded/01-how-often-dental-cleaning.md:24 `link_unverified` 'https://www.nidcr.nih.gov/health-info/gum-disease-treatment-guidelines-2026'
- seeded/01-how-often-dental-cleaning.md:33 `link_unverified` 'https://www.mouthhealthy.org/'
- seeded/02-dental-implants-vs-bridges.md:18 `link_unverified` 'https://www.mouthhealthy.org/all-topics-a-z/bridges'
- seeded/03-is-teeth-whitening-safe.md:18 `link_unverified` 'https://www.mouthhealthy.org/all-topics-a-z/teeth-whitening'
- seeded/04-dental-emergency-austin.md:22 `link_unverified` 'https://www.mouthhealthy.org/all-topics-a-z/dental-emergencies'

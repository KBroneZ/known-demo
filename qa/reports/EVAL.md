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

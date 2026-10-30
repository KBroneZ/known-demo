# QA gate evaluation (heldout set)

> Snapshot of the **first, blind** run on the held-out set, before any rule was changed. The held-out errors were written by a separate agent that had not seen the rules. First run: 6/10 (the broken-link URL was not yet in the link cache); with the cache recorded: 7/10, as shown below. Misses H03/H07/H08 led to three rule fixes, so the current `EVAL-heldout.md` (10/10) is no longer blind.


Link mode: **offline (cached link results)**. Errors: 10 in 4 posts. Clean posts: 4.

- **Recall:** 7/10 = 70%
- **Precision (block+warn findings):** 100% (7 true / 0 false)
- **False positives on clean posts:** 0
- **Missed:** H03, H07, H08

| ID | Category | Detected | Findings on the injected line |
|---|---|---|---|
| H01 | nap | yes | `insurance_not_in_ficha` |
| H02 | unsourced_stat | yes | `unsourced_stat` |
| H03 | superlative | **NO** | - |
| H04 | broken_link | yes | `link_broken` |
| H05 | prohibited_promise | yes | `prohibited_promise` |
| H06 | chatbot | yes | `chatbot_residue` |
| H07 | medical_false | **NO** | - |
| H08 | testimonial | **NO** | - |
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
| heldout/04-dental-emergency-austin.md | CORREGIR |

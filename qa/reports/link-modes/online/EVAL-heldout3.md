# QA gate evaluation (heldout3 set)

Link mode: **online**. Errors: 12 in 4 posts. Clean posts: 4.

- **Recall:** 9/12 = 75%
- **Precision (block+warn findings):** 53% (9 true / 8 false)
- **False positives on clean posts:** 0
- **Missed:** H3-01, H3-07, H3-10

| ID | Category | Detected | Findings on the injected line |
|---|---|---|---|
| H3-01 | medical-misinformation | **NO** | - |
| H3-02 | outcome-guarantee | yes | `prohibited_promise` |
| H3-03 | unsupported-clinic-claim | yes | `absolute_clinic_claim` |
| H3-04 | outcome-guarantee | yes | `prohibited_promise` |
| H3-05 | price-not-on-sheet | yes | `price_not_in_ficha` |
| H3-06 | insurance-not-accepted | yes | `insurance_not_in_ficha` |
| H3-07 | medical-misinformation | **NO** | - |
| H3-08 | wrong-author | yes | `dentist_not_in_roster` |
| H3-09 | invented-statistic | yes | `unsourced_stat` |
| H3-10 | medical-misinformation | **NO** | - |
| H3-11 | hours-error | yes | `hours_mismatch` |
| H3-12 | internal-link-missing-page | yes | `link_broken_internal` |

## Verdicts

| Post | Verdict |
|---|---|
| clean/01-how-often-dental-cleaning.md | PUBLICAR |
| clean/02-dental-implants-vs-bridges.md | PUBLICAR |
| clean/03-is-teeth-whitening-safe.md | PUBLICAR |
| clean/04-dental-emergency-austin.md | PUBLICAR |
| heldout3/01-root-canal-myths.md | BLOQUEAR |
| heldout3/02-tooth-colored-fillings.md | BLOQUEAR |
| heldout3/03-clear-aligners-for-adults.md | BLOQUEAR |
| heldout3/04-childs-first-dental-visit.md | BLOQUEAR |

## Unmatched block/warn findings

- heldout3/01-root-canal-myths.md:0 `schema_missing` ''
- heldout3/01-root-canal-myths.md:44 `link_unverifiable` 'https://www.aae.org/patients/root-canal-treatment/what-is-a-root-canal/root-canal-explained/'
- heldout3/01-root-canal-myths.md:45 `link_unverifiable` 'https://www.aae.org/patients/your-office-visit/post-treatment-care/'
- heldout3/02-tooth-colored-fillings.md:0 `schema_missing` ''
- heldout3/03-clear-aligners-for-adults.md:0 `schema_missing` ''
- heldout3/03-clear-aligners-for-adults.md:42 `link_broken_internal` 'https://www.bluebonnethollowdental.example/services/clear-aligners'
- heldout3/04-childs-first-dental-visit.md:0 `schema_missing` ''
- heldout3/04-childs-first-dental-visit.md:45 `link_unverifiable` 'https://www.cdc.gov/oral-health/prevention/oral-health-tips-for-children.html'

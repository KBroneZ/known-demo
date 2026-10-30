# QA gate evaluation (heldout3 set)

Link mode: **offline (cached link results)**. Errors: 12 in 4 posts. Clean posts: 4.

- **Recall:** 3/12 = 25%
- **Precision (block+warn findings):** 23% (3 true / 10 false)
- **False positives on clean posts:** 0
- **Missed:** H3-01, H3-02, H3-03, H3-04, H3-07, H3-08, H3-09, H3-10, H3-11

| ID | Category | Detected | Findings on the injected line |
|---|---|---|---|
| H3-01 | medical-misinformation | **NO** | - |
| H3-02 | outcome-guarantee | **NO** | - |
| H3-03 | unsupported-clinic-claim | **NO** | - |
| H3-04 | outcome-guarantee | **NO** | - |
| H3-05 | price-not-on-sheet | yes | `price_not_in_ficha` |
| H3-06 | insurance-not-accepted | yes | `insurance_not_in_ficha` |
| H3-07 | medical-misinformation | **NO** | - |
| H3-08 | wrong-author | **NO** | - |
| H3-09 | invented-statistic | **NO** | - |
| H3-10 | medical-misinformation | **NO** | - |
| H3-11 | hours-error | **NO** | - |
| H3-12 | internal-link-missing-page | yes | `link_broken_internal` |

## Verdicts

| Post | Verdict |
|---|---|
| clean/01-how-often-dental-cleaning.md | PUBLICAR |
| clean/02-dental-implants-vs-bridges.md | PUBLICAR |
| clean/03-is-teeth-whitening-safe.md | PUBLICAR |
| clean/04-dental-emergency-austin.md | PUBLICAR |
| heldout3/01-root-canal-myths.md | CORREGIR |
| heldout3/02-tooth-colored-fillings.md | BLOQUEAR |
| heldout3/03-clear-aligners-for-adults.md | BLOQUEAR |
| heldout3/04-childs-first-dental-visit.md | BLOQUEAR |

## Unmatched block/warn findings

- heldout3/01-root-canal-myths.md:0 `schema_missing` ''
- heldout3/01-root-canal-myths.md:44 `link_unverifiable` 'https://www.aae.org/patients/root-canal-treatment/what-is-a-root-canal/root-canal-explained/'
- heldout3/01-root-canal-myths.md:45 `link_unverifiable` 'https://www.aae.org/patients/your-office-visit/post-treatment-care/'
- heldout3/02-tooth-colored-fillings.md:0 `schema_missing` ''
- heldout3/03-clear-aligners-for-adults.md:0 `schema_missing` ''
- heldout3/03-clear-aligners-for-adults.md:1 `dentist_not_in_roster` 'author: Dr. Priya Shah'
- heldout3/03-clear-aligners-for-adults.md:42 `link_broken_internal` 'https://www.bluebonnethollowdental.example/services/clear-aligners'
- heldout3/03-clear-aligners-for-adults.md:46 `link_broken` 'https://www.fda.gov/medical-devices/dental-devices/clear-dental-aligners'
- heldout3/04-childs-first-dental-visit.md:0 `schema_missing` ''
- heldout3/04-childs-first-dental-visit.md:45 `link_unverifiable` 'https://www.cdc.gov/oral-health/prevention/oral-health-tips-for-children.html'


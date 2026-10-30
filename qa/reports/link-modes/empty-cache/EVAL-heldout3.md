# QA gate evaluation (heldout3 set)

Link mode: **offline (cached link results)**. Errors: 12 in 4 posts. Clean posts: 4.

- **Recall:** 9/12 = 75%
- **Precision (block+warn findings):** 32% (9 true / 19 false)
- **False positives on clean posts:** 5
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
| clean/01-how-often-dental-cleaning.md | CORREGIR |
| clean/02-dental-implants-vs-bridges.md | CORREGIR |
| clean/03-is-teeth-whitening-safe.md | CORREGIR |
| clean/04-dental-emergency-austin.md | CORREGIR |
| heldout3/01-root-canal-myths.md | BLOQUEAR |
| heldout3/02-tooth-colored-fillings.md | BLOQUEAR |
| heldout3/03-clear-aligners-for-adults.md | BLOQUEAR |
| heldout3/04-childs-first-dental-visit.md | BLOQUEAR |

## Unmatched block/warn findings

- clean/01-how-often-dental-cleaning.md:24 `link_unverified` 'https://www.nidcr.nih.gov/health-info/gum-disease'
- clean/01-how-often-dental-cleaning.md:33 `link_unverified` 'https://www.mouthhealthy.org/'
- clean/02-dental-implants-vs-bridges.md:18 `link_unverified` 'https://www.mouthhealthy.org/all-topics-a-z/bridges'
- clean/03-is-teeth-whitening-safe.md:18 `link_unverified` 'https://www.mouthhealthy.org/all-topics-a-z/teeth-whitening'
- clean/04-dental-emergency-austin.md:22 `link_unverified` 'https://www.mouthhealthy.org/all-topics-a-z/dental-emergencies'
- heldout3/01-root-canal-myths.md:0 `schema_missing` ''
- heldout3/01-root-canal-myths.md:44 `link_unverified` 'https://www.aae.org/patients/root-canal-treatment/what-is-a-root-canal/root-canal-explained/'
- heldout3/01-root-canal-myths.md:45 `link_unverified` 'https://www.aae.org/patients/your-office-visit/post-treatment-care/'
- heldout3/02-tooth-colored-fillings.md:0 `schema_missing` ''
- heldout3/02-tooth-colored-fillings.md:44 `link_unverified` 'https://www.nidcr.nih.gov/health-info/dental-fillings'
- heldout3/02-tooth-colored-fillings.md:45 `link_unverified` 'https://www.ada.org/resources/ada-library/oral-health-topics/materials-for-direct-restorations'
- heldout3/02-tooth-colored-fillings.md:46 `link_unverified` 'https://www.mouthhealthy.org/all-topics-a-z/fillings-tooth-colored/'
- heldout3/03-clear-aligners-for-adults.md:0 `schema_missing` ''
- heldout3/03-clear-aligners-for-adults.md:42 `link_broken_internal` 'https://www.bluebonnethollowdental.example/services/clear-aligners'
- heldout3/03-clear-aligners-for-adults.md:46 `link_unverified` 'https://www.fda.gov/medical-devices/dental-devices/clear-dental-aligners'
- heldout3/03-clear-aligners-for-adults.md:47 `link_unverified` 'https://www.ada.org/sitecore/content/ADA-Organization/ADA/MouthHealthy/home/all-topics-a-z/braces'
- heldout3/04-childs-first-dental-visit.md:0 `schema_missing` ''
- heldout3/04-childs-first-dental-visit.md:44 `link_unverified` 'https://www.aapd.org/resources/parent/faq/'
- heldout3/04-childs-first-dental-visit.md:45 `link_unverified` 'https://www.cdc.gov/oral-health/prevention/oral-health-tips-for-children.html'

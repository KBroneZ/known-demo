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

## Model layer

| Layer | Recall | Precision (block+warn) | Notes |
|---|---|---|---|
| Rules only | 3/12 | 23% | 0 false alarms on clean posts |
| Model only | 12/12 | 54% (13 true / 11 false) | 4 off-target block/warn on clean posts; missed none; cost $0.2649 |
| Rules + model | 12/12 | 43% | model adds: H3-01, H3-02, H3-03, H3-04, H3-07, H3-08, H3-09, H3-10, H3-11 |
- with the model layer on, 2/4 clean posts are no longer PUBLICAR; 0 findings about the fixture-only 'fictional practice' line were ignored

Off-target model findings (block/warn):

- clean/01-how-often-dental-cleaning.md [warn/unsourced_claim] 'Tartar builds up on a timeline that is similar for most people': Tartar formation rates vary considerably between individuals, no source is given, and the claim conflicts with the post's own 'heavy tartar 
- clean/01-how-often-dental-cleaning.md [warn/fact_vs_ficha] 'We are in network with Delta Dental, Cigna and MetLife': The ficha lists these carriers as accepted, not as in network, and in-network status is a specific contractual claim that cannot be verified
- clean/01-how-often-dental-cleaning.md [warn/unsourced_claim] 'If you are new to us and paying without insurance, the new patient exam with X-rays is $12': The ficha confirms the $129 new patient exam with X-rays but does not say it applies only to patients paying without insurance.
- clean/03-is-teeth-whitening-safe.md [warn/unsourced_claim] 'Whitening is one of the most requested cosmetic treatments, and one of the most misunderst': The claim that whitening is among the most requested cosmetic treatments is a checkable statistic-style statement with no source, and the fi
- heldout3/01-root-canal-myths.md [warn/unsourced_claim] 'reviewed_by: Dr. Marcus Oyelaran': The post names a clinical reviewer, but nothing shows a real review took place, and his listed focus (family and pediatric dentistry, clear 
- heldout3/02-tooth-colored-fillings.md [warn/broken_or_fake_source] '[National Institute of Dental and Craniofacial Research: Dental Fillings](https://www.nidc': I cannot verify that this URL exists; NIDCR's actual page paths may differ, and I will not assume it resolves.
- heldout3/03-clear-aligners-for-adults.md [block/fact_vs_ficha] 'https://www.bluebonnethollowdental.example/services/clear-aligners': The ficha's pages list has no /services/clear-aligners page, so this internal link points to a nonexistent page.
- heldout3/03-clear-aligners-for-adults.md [warn/broken_or_fake_source] 'https://www.ada.org/sitecore/content/ADA-Organization/ADA/MouthHealthy/home/all-topics-a-z': This URL exposes an internal 'sitecore/content' CMS path that is unlikely to be a live public page, and I could not verify it.
- heldout3/04-childs-first-dental-visit.md [warn/false_medical_claim] 'Use an age-appropriate amount of fluoride toothpaste based on your dentist’s or doctor’s a': ADA guidance recommends a smear (rice-grain size) of fluoride toothpaste from the first tooth for children under 3, and deferring entirely t
- heldout3/04-childs-first-dental-visit.md [warn/unsourced_claim] '- [American Academy of Pediatric Dentistry: Frequently Asked Questions](https://www.aapd.o': I could not verify that this exact URL exists or covers the claims made, so it is unverified.
- heldout3/04-childs-first-dental-visit.md [warn/unsourced_claim] '- [Centers for Disease Control and Prevention: Oral Health Tips for Children](https://www.': I could not verify that this exact URL is live or supports the post's claims, so it is unverified.

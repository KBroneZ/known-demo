# heldout3: hand adjudication of unmatched findings

Raw numbers (rules frozen, hash in `rules-frozen-before-heldout3.sha256`): see `EVAL-heldout3-rules-raw.md` and
`EVAL-heldout3-model-sonnet-raw.md`. This file only classifies the block/warn findings that did not land on a listed
error line. Classes: **A** real error not on the list, **B** defensible caution (not an error), **C** true false positive.
URLs were opened in a real browser/curl on 2026-10-30 to decide.

## Rules (13 block/warn findings: 3 on listed lines, 10 unmatched)

| Finding | Class | Why |
|---|---|---|
| `dentist_not_in_roster` 03 line 1 `author: Dr. Priya Shah` | **listed (H3-08)** | right detection, but reported on line 1 instead of the author line, so line-matching missed it |
| `schema_missing` x4 (all four posts) | A | posts have no JSON-LD, which the pipeline format requires. Artifact of how the posts were briefed |
| `link_broken_internal` 03 `/services/clear-aligners` | A | page is not in the ficha; same link H3-12 injects in post 04 |
| `link_unverifiable` aae.org x2, cdc.gov x1 | C | sites answer 403 to scripts; all three pages exist (opened in browser) |
| `link_broken` fda.gov clear-dental-aligners | C | transient DNS error at run time; the page returns 200. The gate hard-blocked a live link |

Rules: 3 raw TP; 4 TP once line attribution is ignored; A = 5; C = 4. Precision raw 3/13 = 23%; with A counted as true 9/13 = 69%.

## Model, Sonnet (24 block/warn findings: 13 on listed lines, 11 unmatched)

| Finding | Class | Why |
|---|---|---|
| clean-01 "similar tartar timeline" no source | B | unsourced generalisation, mild |
| clean-01 "in network with Delta Dental..." | B | ficha says accepted, not "in network" |
| clean-01 "paying without insurance ... $129" | A | my clean post adds a condition the ficha does not state |
| clean-03 "most requested cosmetic treatments" | B | unsourced popularity claim |
| heldout3-01 `reviewed_by` Dr. Oyelaran on a root-canal post | B | his listed focus is pediatrics/aligners; not an error |
| heldout3-03 link `/services/clear-aligners` not in ficha | A | real |
| heldout3-04 fluoride-toothpaste amount remark | B | post is vague, not wrong |
| heldout3-02 NIDCR fillings URL "cannot verify" | C | URL returns 200 |
| heldout3-03 ADA `sitecore/...braces` URL "looks internal" | C | URL returns 200 |
| heldout3-04 AAPD FAQ URL, CDC URL "cannot verify" x2 | C | both exist |

Model: A = 2, B = 5, C = 4. Precision raw 13/24 = 54%; with A true 15/24 = 63%; with A+B acceptable 20/24 = 83%.

# QA gate evaluation (travel-heldout set), FIRST PASS with the rules frozen before scoring (v1)

Link mode: **offline (cached link results)**. Errors: 14 in 4 posts. Clean posts: 4.

- **Recall:** 6/14 = 43%
- **Precision (block+warn findings):** 75% (6 true / 2 false)
- **False positives on clean posts:** 0
- **Missed:** B01, B02, B04, B05, B06, B08, B09, B11

| ID | Category | Detected | Findings on the injected line |
|---|---|---|---|
| B01 | numeric-inconsistency | **NO** | - |
| B02 | entity-wrong | **NO** | - |
| B03 | banned-character | yes | `banned_character` |
| B04 | source-mismatch | **NO** | - |
| B05 | seasonality | **NO** | - |
| B06 | weekday-inconsistency | **NO** | - |
| B07 | affiliate-disclosure | yes | `affiliate_disclosure_missing` |
| B08 | first-hand-claim | **NO** | - |
| B09 | stale-review | **NO** | - |
| B10 | stale-date | yes | `event_date_past` |
| B11 | price-no-as-of | **NO** | - |
| B12 | dead-link | yes | `link_broken` |
| B13 | blocked-link | yes | `link_blocked` |
| B14 | broken-internal-link | yes | `link_broken_internal` |

## Verdicts

| Post | Verdict |
|---|---|
| clean/01-lisbon-three-days-walkable-plan.md | PUBLICAR |
| clean/02-iceland-winter-packing-list.md | PUBLICAR |
| clean/03-kyoto-cherry-blossom-season-2027.md | PUBLICAR |
| clean/04-banff-summer-three-day-plan.md | PUBLICAR |
| heldout/01-vienna-three-days-trams-coffee-houses.md | CORREGIR |
| heldout/02-cape-town-four-days-mountain-winelands.md | BLOQUEAR |
| heldout/03-hanoi-old-quarter-two-days.md | BLOQUEAR |
| heldout/04-tallinn-old-town-two-days.md | BLOQUEAR |

## Unmatched block/warn findings

- heldout/01-vienna-three-days-trams-coffee-houses.md:38 `numeric_inconsistency` 'EUR 14 (line 34) vs EUR 6.80'
- heldout/03-hanoi-old-quarter-two-days.md:49 `link_broken_internal` '/blog/vienna-three-days-trams-coffee-houses'

# QA gate evaluation (travel-heldout set)

Link mode: **offline (cached link results)**. Errors: 14 in 4 posts. Clean posts: 4.

- **Recall:** 10/14 = 71%
- **Precision (block+warn findings):** 100% (10 true / 0 false)
- **False positives on clean posts:** 0
- **Missed:** B02, B04, B05, B06

| ID | Category | Detected | Findings on the injected line |
|---|---|---|---|
| B01 | numeric-inconsistency | yes | `numeric_inconsistency` |
| B02 | entity-wrong | **NO** | - |
| B03 | banned-character | yes | `banned_character` |
| B04 | source-mismatch | **NO** | - |
| B05 | seasonality | **NO** | - |
| B06 | weekday-inconsistency | **NO** | - |
| B07 | affiliate-disclosure | yes | `affiliate_disclosure_missing` |
| B08 | first-hand-claim | yes | `unsupported_first_hand_claim` |
| B09 | stale-review | yes | `review_stamp_is_publish_date` |
| B10 | stale-date | yes | `event_date_past` |
| B11 | price-no-as-of | yes | `price_no_as_of` |
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
| heldout/03-hanoi-old-quarter-two-days.md | CORREGIR |
| heldout/04-tallinn-old-town-two-days.md | BLOQUEAR |

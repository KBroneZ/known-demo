# QA gate evaluation (travel-seeded set)

Link mode: **offline (cached link results)**. Errors: 21 in 4 posts. Clean posts: 4.

- **Recall:** 17/21 = 81%
- **Precision (block+warn findings):** 100% (17 true / 0 false)
- **False positives on clean posts:** 0
- **Missed:** T18, T19, T20, T21

| ID | Category | Detected | Findings on the injected line |
|---|---|---|---|
| T01 | numeric-inconsistency | yes | `numeric_inconsistency` |
| T02 | weekday-inconsistency | yes | `weekday_inconsistency` |
| T03 | stale-event-date | yes | `event_date_past` |
| T04 | stale-title-year | yes | `stale_year_title` |
| T05 | stale-review-stamp | yes | `review_stamp_is_publish_date` |
| T06 | price-no-as-of | yes | `price_no_as_of` |
| T07 | first-hand-claim | yes | `unsupported_first_hand_claim` |
| T08 | missing-section | yes | `missing_required_section` |
| T09 | affiliate-disclosure | yes | `affiliate_disclosure_missing` |
| T10 | banned-character | yes | `banned_character` |
| T11 | byline | yes | `byline_not_allowed` |
| T12 | dead-link | yes | `link_broken` |
| T13 | blocked-link | yes | `link_blocked` |
| T14 | weekday-date-mismatch | yes | `weekday_date_mismatch` |
| T15 | broken-internal-link | yes | `link_broken_internal` |
| T16 | distance-inconsistency | yes | `numeric_inconsistency` |
| T17 | date-inconsistency | yes | `date_inconsistency` |
| T18 | entity-wrong | **NO** | - |
| T19 | seasonality | **NO** | - |
| T20 | seasonality | **NO** | - |
| T21 | source-does-not-support-figure | **NO** | - |

## Verdicts

| Post | Verdict |
|---|---|
| clean/01-lisbon-three-days-walkable-plan.md | PUBLICAR |
| clean/02-iceland-winter-packing-list.md | PUBLICAR |
| clean/03-kyoto-cherry-blossom-season-2027.md | PUBLICAR |
| clean/04-banff-summer-three-day-plan.md | PUBLICAR |
| seeded/01-lisbon-three-days-walkable-plan.md | BLOQUEAR |
| seeded/02-iceland-winter-packing-list.md | BLOQUEAR |
| seeded/03-kyoto-cherry-blossom-season-2027.md | BLOQUEAR |
| seeded/04-banff-summer-three-day-plan.md | BLOQUEAR |

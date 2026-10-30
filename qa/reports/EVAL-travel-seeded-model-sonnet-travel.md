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

## Model layer

| Layer | Recall | Precision (block+warn) | Notes |
|---|---|---|---|
| Rules only | 17/21 | 100% | 0 false alarms on clean posts |
| Model only | 13/21 | 38% (13 true / 21 false) | 12 off-target block/warn on clean posts; missed T05, T08, T09, T10, T11, T12, T13, T14; cost $0.2454 |
| Rules + model | 21/21 | 59% | model adds: T18, T19, T20, T21 |
- with the model layer on, 4/4 clean posts are no longer PUBLICAR; 0 findings about the fixture-only 'fictional practice' line were ignored

Off-target model findings (block/warn):

- clean/01-lisbon-three-days-walkable-plan.md [warn/unsupported_first_hand_claim] 'Prices checked October 2026.': The post claims a price verification in a money topic, but gives no method, date of check or person, and the only support is a bare source l
- clean/02-iceland-winter-packing-list.md [warn/unsupported_first_hand_claim] 'The notes and dates are summarised here so you can judge how much weight to give them': The section claims notes and dates are summarised, but it gives no actual dates, per-day notes, weather or results, so the six-day test cann
- clean/03-kyoto-cherry-blossom-season-2027.md [warn/source_does_not_support_figure] 'Both are run by the city tourism office, and tickets are sold in advance.': The only event source is a kyoto-tourism.example spring-lights page, which cannot back the Gion Evening Walk or the claim that the city tour
- clean/03-kyoto-cherry-blossom-season-2027.md [warn/entity_unverified] 'The Kyoto Spring Lights evening walk is on Saturday, March 27, 2027 and lights up several ': I cannot verify that an event called Kyoto Spring Lights exists on this date, and the linked page does not confirm the date.
- clean/03-kyoto-cherry-blossom-season-2027.md [warn/entity_unverified] 'A second evening walk, the Gion Evening Walk, is on Saturday, April 3, 2027.': I cannot verify that a Gion Evening Walk event exists on this date, and no source is linked for it.
- clean/03-kyoto-cherry-blossom-season-2027.md [warn/source_does_not_support_figure] '| Kyoto Spring Lights | March 27, 2027 | ¥1,800 |': The ticket price is a money figure, and the linked page is only an events page with no evidence that it lists ¥1,800.
- clean/03-kyoto-cherry-blossom-season-2027.md [warn/source_does_not_support_figure] '| Gion Evening Walk | April 3, 2027 | ¥1,500 |': The ¥1,500 price has no source, and the only events source is for Spring Lights, so it cannot back this price.
- clean/03-kyoto-cherry-blossom-season-2027.md [warn/unsupported_first_hand_claim] 'Prices checked October 2026.': The post claims a verification that has no evidence, and the sources listed do not show it.
- clean/03-kyoto-cherry-blossom-season-2027.md [warn/entity_unverified] 'Use the Hanami Shuttle on busy weekends; it connects the main blossom spots and costs ¥600': I cannot verify that a Hanami Shuttle exists in Kyoto, and the fare has no source in a money-related context.
- clean/04-banff-summer-three-day-plan.md [warn/unsupported_first_hand_claim] 'Prices checked September 2026.': The post claims the prices were verified but gives no dated evidence or per-figure source, and the post was updated in October.
- clean/04-banff-summer-three-day-plan.md [warn/source_does_not_support_figure] '| Banff park pass | $11 | Per adult, per day |': This is a money figure with no currency and no source next to it; the generic Sources list cannot be tied to this price, and the figure may 
- clean/04-banff-summer-three-day-plan.md [warn/source_does_not_support_figure] '| Bow Valley Shuttle day ticket | $12 | Summer season only |': This is a money figure with no currency and no inline source, so readers cannot tell what the $12 is based on.
- seeded/01-lisbon-three-days-walkable-plan.md [warn/source_does_not_support_figure] 'Prices checked October 2026.': The price-check claim has no evidence and the two prices conflict, so the verification cannot be trusted; the Belém Combi Ticket €12 is also
- seeded/02-iceland-winter-packing-list.md [block/unsupported_first_hand_claim] 'We spent six days in January 2026 walking the same three routes in three jacket and boot c': The section claims notes and dates are summarised, but gives no actual results, dates or per-combination findings, so the testing claim has 
- seeded/03-kyoto-cherry-blossom-season-2027.md [block/internal_inconsistency] 'A second evening walk, the Gion Evening Walk, is on Saturday, April 3, 2027.': The text gives April 3, but the table gives April 10, 2027; readers could book or travel on the wrong date. April 3, 2027 is also a Saturday
- seeded/03-kyoto-cherry-blossom-season-2027.md [warn/source_does_not_support_figure] '| Kyoto Spring Lights | March 27, 2027 | ¥1,800 |': Ticket prices are stated without being tied to a source, and the listed link (kyoto-tourism.example/events/spring-lights) covers only Spring
- seeded/03-kyoto-cherry-blossom-season-2027.md [warn/entity_unverified] 'Both are run by the city tourism office, and tickets are sold in advance.': The organiser claim is not backed by any listed source, and the Gion Evening Walk cannot be verified as an event run by the city tourism off
- seeded/03-kyoto-cherry-blossom-season-2027.md [warn/unsupported_first_hand_claim] 'Prices checked October 2026.': It claims a verification with no evidence or method, and no source in the list supports the prices.
- seeded/03-kyoto-cherry-blossom-season-2027.md [warn/entity_unverified] 'Use the Hanami Shuttle on busy weekends; it connects the main blossom spots and costs ¥600': I cannot verify that a 'Hanami Shuttle' exists in Kyoto, and its fare has no source.
- seeded/04-banff-summer-three-day-plan.md [warn/source_does_not_support_figure] '| Banff park pass | $11 | Per adult, per day |': This is a money figure with no currency and no source next to it; the two sources are only listed at the bottom, so nothing ties them to the
- seeded/04-banff-summer-three-day-plan.md [warn/entity_unverified] 'The Bow Valley Shuttle connects the town of Banff with the main lakes during the summer se': The whole plan depends on this shuttle, but I cannot confirm a service with this name and route; Banff's public transit and the Parks Canada

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

## Model layer

| Layer | Recall | Precision (block+warn) | Notes |
|---|---|---|---|
| Rules only | 6/14 | n/a (recall from the snapshot rule state) | 0 false alarms on clean posts |
| Model only | 8/14 | 36% (9 true / 16 false) | 12 off-target block/warn on clean posts; missed B03, B06, B07, B09, B11, B13; cost $0.2618 |
| Rules + model | 11/14 | n/a (mixed rule states) | model adds: B01, B02, B04, B05, B08 |
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
- heldout/01-vienna-three-days-trams-coffee-houses.md [warn/unsupported_first_hand_claim] 'Prices checked June 2026.': The post claims prices were verified but gives no method, evidence or per-price source, and the table figures conflict with the FAQ.
- heldout/02-cape-town-four-days-mountain-winelands.md [warn/internal_inconsistency] 'Plan your last evening around the Friday night market at the harbourside, where food stall': The prose says Friday but the table lists the Harbourside Night Market on Thursday 17:00 to 21:00, so readers could arrive on the wrong day.
- heldout/02-cape-town-four-days-mountain-winelands.md [warn/source_does_not_support_figure] '| Full-day peninsula tour | Peninsula Day Tours | 08:00 | ZAR 1,150 |': The price and departure time are stated as checked, but the only linked source is a generic 'tour overview' page whose address does not indi
- heldout/02-cape-town-four-days-mountain-winelands.md [warn/source_does_not_support_figure] '| Winelands hop shuttle | Vine Line Shuttles | 09:30 | ZAR 690 |': The source is a 'timetable' page, which may back the departure time but not the ZAR 690 price, and the operator is unverified.

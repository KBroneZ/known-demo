# Content QA gate for AI-written posts (dental clinic profile, plus a travel-site profile)

A pre-publish check for blog posts written by AI for a dental clinic. It compares each post with the
clinic's own data file and returns one verdict per post:

- **BLOQUEAR** (block): something wrong or risky. Do not publish.
- **CORREGIR** (fix): needs a source or a rewrite, then re-run.
- **PUBLICAR** (publish): nothing found. A human still approves.

Every finding goes into a JSON report with the rule, the line number and the offending text, so a reviewer
reads only what the gate flagged.

The clinic, dentists and patients are **fictional** (Bluebonnet Hollow Dental, Austin TX, phone in the
555-01xx range, `.example` domain). Nothing here describes a real practice.

## What it checks

**Layer 1: deterministic rules** (Python standard library, no API keys, about a second per post)

| Check | Examples |
|---|---|
| Clinic facts vs `clinic.yaml` | phone, address, ZIP, hours, dentist names, prices, insurance carriers, services |
| Links | internal links against the page list; external links via HEAD request (10 s timeout); offline mode reads a dated cache |
| Forbidden claims | guarantees and promises, "best dentist in Austin" with no basis, patient testimonials with none on file |
| Medical claims | a curated list of dental myths; statistics or "studies show" with no source link in the paragraph |
| AI tells | typical AI phrases, chatbot residue ("As an AI language model"), placeholders |
| Structure | frontmatter fields and dates; JSON-LD valid and consistent with the post (headline, dates, author, publisher, FAQ text) |

**Layer 2: model review (optional).** The gate always writes a ready-to-paste prompt per post
(`reports/prompts/`). `--llm claude` runs `claude -p` in an isolated mode (no user memory, no skills, no tools,
empty working directory, plain-English system prompt); `--llm codex` uses the `ask-chatgpt` skill. The model can
raise a verdict, never lower it, and its output is treated as unverified.

## Run it

Python 3.10+. Nothing to install to run the gate; `pip install pytest` for the tests.

```bash
python run_gate.py fixtures/posts/clean fixtures/posts/seeded --offline   # replays recorded link results, no network
python run_gate.py my-post.md --clinic my-clinic.yaml                     # live link checks
python run_gate.py my-post.md --llm claude --llm-model sonnet             # add the model layer
python evaluate.py --set seeded|heldout|heldout2|heldout3                 # score the rules (add --online for live links)
python evaluate.py --set heldout2 --with-llm --model-dir reports/model-sonnet   # score the model layer
python -m pytest                                                          # 315 unit tests
```

**Exit codes. CI should fail on any code of 2 or more.**

| Code | Meaning |
|---|---|
| 0 | every post PUBLICAR |
| 1 | worst post is CORREGIR (also: a requested model review did not run) |
| 2 | at least one post is BLOQUEAR, **including a post that crashed the gate** (it fails closed as `gate_internal_error`) |
| 3 | gate error: no posts found, bad path, unexpected crash outside a post |

**Links.** Online, every external link gets a HEAD request (GET if the server mishandles HEAD), 10 s timeout, DNS
failures retried once. Dead = 404/410 or a domain that does not exist. 403/429/5xx/timeouts are "could not confirm"
(CORREGIR). Relative links are resolved against the post URL and checked against the page list. A link that
redirects to the home page is flagged as a possible soft 404.
Offline, a link that is **not in the cache, or whose cached result is older than 30 days, is CORREGIR**
(`link_unverified`), never PUBLICAR. `--update-cache` stores only definitive answers (2xx/3xx, 404/410, NXDOMAIN),
not timeouts or 5xx. `fixtures/link-cache.json` was recorded by online runs on 2026-10-30; the entries for the three
dead-link errors (E03, H04, K03) were added after those errors were written. See the results section for what that
means for the numbers.

## Results (real numbers, from this repo)

Each set = the same 4 clean posts + posts with injected errors. Only `seeded` was written with the rules in view.
The blind sets were written by someone who had not seen the rules: `heldout` and `heldout2` by a separate agent each
(10 errors), `heldout3` by ChatGPT (4 new posts and 12 errors; ChatGPT declined to embed 11 of them, so they were
inserted verbatim by script, between paragraphs, by someone who had not seen the rules). Rules were frozen before each
blind set was scored. A code review of this folder (`research/07-code-review-qa-web.md`) then found real defects.
Everything below is split into "before the review fixes" and "after".

### Review prompt v2 and v3: error vs suggestion (30 Oct, evening)

The model now labels every remark `error` or `suggestion`. A suggestion (wording, a harmless generality, filler) is logged and
never changes the verdict; a missing or unknown kind, or a "suggestion" with severity block, counts as an error. Sonnet,
rules as on their first blind run: **rules + model still 32/32** on the three blind sets with the final prompt (model alone 29/32:
it misses the AI-phrase openers and a dead link, which the rules catch). Haiku with the middle prompt gave 31/32 (it missed
one false medical statement). Precision: 83% with the middle prompt, 58% with the final one, which also counts a claim that is
less conditional than the ficha's wording as an error. Details and caveats in `pipeline/README.md`.

### Later hardening (code review 08, 30 Oct)

Added: block rules for raw HTML, for link schemes other than http/https/mailto/tel (so `javascript:` and `data:` links), for
links to localhost and private addresses (these are never fetched) and for malformed URLs; the model's own verdict is read and
its severity labels are normalised (unknown = block; an unreadable verdict is never PUBLICAR); the `visits?` false alarm in
the statistic rule is removed. The recall and precision figures below did not change (sets re-run: 10/10, 10/10, 10/10, 9/12,
0 false alarms on the clean posts); none of the new rules fires on any fixture.

### Table 1: before the review fixes (as first reported)

| Set | Errors | Rules, first blind run | Sonnet alone | Rules + Sonnet | Sonnet precision (strict) |
|---|---|---|---|---|---|
| `seeded` (not blind) | 10 | 10/10 | 10/10 | 10/10 | 12/22 = 55% |
| `heldout` | 10 | **7/10** | **10/10** | **10/10** | 11/19 = 58% |
| `heldout2` | 10 | **7/10** | **10/10** | **10/10** | 10/23 = 43% |
| `heldout3` | 12 | **3/12** | **12/12** | **12/12** | 13/24 = 54% |
| **Total** | 42 | blind 17/32 = 53% | 42/42 | 42/42 | 46/88 = **52%** |

Rules precision on the blind sets was 7/7, 8/8 and **3/13 = 23%** raw (69% after adjudication, below). Haiku alone:
10/10, 9/10, 9/10 on the first three sets, precision 31/60 = 52%.

### Table 2: after the review fixes

What changed in the code: clause-bounded negation (H5), offline cache misses are CORREGIR and cache age is
enforced (H4), the gate fails closed on crashes and on zero posts (H3), and the model scorer needs the quote to overlap
the injected text instead of just sharing a paragraph (M1). Remeasured on the same files:

| Set | Rules (current code) | Sonnet alone | Sonnet precision (strict matcher) | Haiku alone | Haiku precision |
|---|---|---|---|---|---|
| `seeded` | 10/10 | 10/10 | 11/22 = **50%** | 10/10 | 10/21 = 48% |
| `heldout` | 10/10 | 10/10 | 10/19 = **53%** | 9/10 | 9/19 = 47% |
| `heldout2` | 10/10 | 10/10 | 10/23 = **43%** | 9/10 | 11/20 = 55% |
| `heldout3` | 9/12 | 12/12 | 13/24 = **54%** | not run | - |
| **Total** | | 42/42 | 44/88 = **50%** | 28/30 | 30/60 = **50%** |

- **The model's precision goes down, not up: 52% to 50% for both Sonnet and Haiku.** The old matcher counted
  three off-target remarks as hits because they sat in the same paragraph as an injected error. Recall does not change
  (each of those errors was also caught by a strict match). Half of what the model flags is noise or a defensible
  caution (see the `heldout3` adjudication below).
- **The rules' numbers on these files do not move** (10/10, 10/10, 10/10, 9/12; 0 false alarms on the clean posts),
  because none of the bypass sentences found by the review were in the test sets. The H5 bypasses ("There is no doubt
  that we guarantee ...", "not cheap, but we guarantee ...") were real: they slipped through before, and are
  regression tests now. So the fixes close holes the sets could not see: **these sets do not measure everything.**
- The rules numbers after the fixes are **not blind**: all three blind sets have been used for fixes. "Rules + Sonnet"
  recall of 42/42 uses the rules' first-blind-run state, as in Table 1. No combined precision is quoted because it would
  mix two rule states.

### The dead-link recall no longer hides behind a cache

The three dead-link errors (E03, H04, K03) were detected offline because `fixtures/link-cache.json` holds their 404s,
recorded after the errors were written. So the offline number tested a lookup. Remeasured three ways:

| Link mode | Dead-link errors found | Rules recall (4 sets) | False alarms on the 4 clean posts |
|---|---|---|---|
| Replay the recorded cache (default) | 3/3 | 10/10, 10/10, 10/10, 9/12 | 0 |
| **Live requests** (`evaluate.py --online`) | **3/3** | 10/10, 10/10, 10/10, 9/12 | 0 |
| Empty cache, offline | **0/3**, by design | 9/10, 9/10, 9/10, 9/12 | 5 (every external link is `link_unverified` = CORREGIR) |

Live requests find the same three dead links, so the recall does not depend on the cache. With nothing cached the
gate cannot know a link is dead, and says so (CORREGIR) instead of passing it; before the fix it said PUBLICAR.

### `heldout3`: raw precision is misleading, so I adjudicated by hand

ChatGPT's posts contain real problems that are not on its list, so "not on the list" is not the same as "wrong".
I classified every unmatched block/warn finding (opening the cited URLs in a browser): **A** real error not listed,
**B** defensible caution, **C** true false positive. Details in `reports/heldout3-adjudication.md` (made with the
pre-fix code; the fda.gov false block it lists is fixed, see below).

| | Findings | On the list | A real, unlisted | B defensible | C true false positive | Precision if A counts as true | Precision if A+B are acceptable |
|---|---|---|---|---|---|---|---|
| Rules | 13 | 3 (4 if line attribution is ignored) | 5 | 0 | **4** | 9/13 = 69% | 9/13 = 69% |
| Sonnet | 24 | 13 | 2 | 5 | **4** | 15/24 = 63% | 20/24 = 83% |

- Rules, A: no JSON-LD in any of the four posts (x4; an artifact of how ChatGPT was briefed) and a link to a page
  that does not exist (`/services/clear-aligners`). Rules, C: three links to aae.org / cdc.gov that answer 403 to scripts
  but exist (the gate says "could not confirm"), and one block on an fda.gov link that is live (transient DNS error;
  fixed: DNS failures are retried and only a non-existent domain blocks).
- Sonnet, C: four URLs it said it could not verify (it cannot browse) that all exist. Sonnet also found the missing
  page and a condition my own clean post added to the $129 price.
- The rules missed what rules cannot know: three false medical statements (root canal "cannot feel anything", aligners
  "without a dental professional", first visit "at age three").

### Model layer cost and noise

Cost is the CLI's `total_cost_usd`: Sonnet about $0.033 per post, Haiku about $0.002. With the model layer on,
Sonnet moves 2 of the 4 clean posts from PUBLICAR to CORREGIR/BLOQUEAR (Haiku: all 4, one by flagging the fixture's
own "fictional practice" line). A sensible setup is: rules decide the verdict, the model adds a short list of remarks
for the human. The model prompt names ten finding types, close to the error categories, so it is primed; a real post
can contain a mistake outside them. The model never saw the rules' findings in these runs (`--llm-independent`), and the
Claude CLI ran isolated (no user memory, skills or tools; output checked: plain English JSON). The codex backend
is not isolated like that and gets a 1900 s timeout; treat the post as untrusted input.

### What failed and what was fixed

| Miss or defect | Fix | Generalises? | When |
|---|---|---|---|
| "top-rated dental team" ignored (link in paragraph) | exemption removed; "we are / our team ... leading" form | Yes | after `heldout` |
| `"quote," says Maria T.` testimonial | attribution after the quote; quoted first-person statements; "a recent patient" | Yes | after `heldout` |
| "aspirin directly on the gum" | one more myth-list entry | **No** (a lookup) | after `heldout` |
| "Studies **have** found", "we promise", patient anecdote | wider verb phrases, promise/assure/pledge, "a patient ... told" | Yes | after `heldout2` |
| "Sundays", "last forever", "infection cannot return", "Every adult ... in six weeks", "Dr. X completes every ..." | plural days, absolute outcome patterns, universal quantifier + number, new `absolute_clinic_claim` warning | Yes, partly | post-`heldout3` |
| fda.gov live link hard-blocked; `author:` reported on line 1 | DNS retry, HEAD 404 retried with GET; frontmatter findings point at the key's line | Yes | post-`heldout3` |
| Review H3: zero posts exited 0; a crash exited 1 (same as CORREGIR); `publisher` as a string crashed the gate | exit 3 on zero posts / bad input, a crashing post becomes BLOQUEAR (`gate_internal_error`), JSON-LD fields are type-checked, `telephone` is checked at any depth | Yes | review |
| Review H4: offline cache miss gave PUBLICAR | miss or stale (over 30 days) = CORREGIR; only definitive results are cached | Yes | review |
| Review H5: "no/not/never" anywhere in the previous 45 characters excused a guarantee or a myth | negation must be within 3 tokens in the same clause (not across commas, semicolons, full stops, "but", "and") | Yes | review |
| Review M1-M5 and LOW items | strict model matcher; the blind-snapshot reader raises if it cannot find the `Missed` line (it used to credit the rules with 100%); relative links checked; soft-404 redirect flagged; a model failure prints a warning and exits at least 1; stale model output deleted before a run; report names include the folder; duplicate YAML keys raise; carrier negation ("we do not accept Cigna"); `$129.00` equals `$129`; `Dr. Marsh Our ...` no longer flags a valid dentist | Yes | review |
| 3 false medical statements (heldout3) | not fixed on purpose: adding them would be tailoring. The model layer is the answer | n/a | |

Two caveats the review also asked me to state. First, "0 false alarms on the 4 clean posts" is **one sample of
4 posts counted in every set**, and the rules were tuned while looking at them; it is not 12 independent checks.
Second, the two agents that wrote `heldout` and `heldout2` shared the same ten error categories in their brief (ChatGPT
chose its own for `heldout3`), so those sets test wording variety more than category coverage.

Disclosures: for `heldout2` I saw the writing agent's one-paragraph summary of its errors while finishing the first
fixes, so it was blind to the text but not to a description. The `heldout3` category-to-rule mapping in `evaluate.py`
was fixed before scoring; the snippets are short, blunt sentences, so they are easier to spot than errors woven into
prose. Missing JSON-LD is a warning, not a block, because the real pipeline generates schema from frontmatter. Review
time per post was not measured. All sets are small and about one fictional clinic. All three blind sets are used up;
a fourth is needed before quoting a new recall.

Limits that remain: a false medical statement is caught by the rules only if it is on the myth list. An invented
statistic is flagged because it has no source link, not because it was proven false, and a link in the paragraph only
shows that a source is claimed. Clinical claims still need the clinic's dentist.

## Travel profile (a second site type, 30 Oct)

The same gate also runs on a travel blog. A `site.yaml` with `profile: travel` replaces the clinic ficha and switches
the rules; the dental profile is untouched (all 214 earlier tests still pass and the four dental EVAL reports are
byte-identical before and after). Every check is switched on by the key that configures it, so a site only gets the
rules it declares.

```bash
python run_gate.py post.md --clinic fixtures/travel/site.yaml --today 2026-10-30 --offline \
    --link-cache fixtures/travel/link-cache.json --max-cache-age-days -1
python evaluate.py --set travel-seeded     # or travel-heldout; add --with-llm --model-dir reports/model-sonnet-travel
```

`site.yaml` keys: `redirect_prefixes` (paths such as `/go/` that redirect server-side and are not in the sitemap), `required_sections` (a `## Sources` heading), `banned_characters` (em dash, `...`), `bylines` and
`author_titles`, `evidence_headings` (what counts as a method section), `affiliate` (hosts, query params, disclosure
phrases, optionally `disclosure_on_every_post`), `review_max_age_days`, `stamp_grace_days`, and `pages` (the internal page
list, from the sitemap). `--today` fixes the check date so the staleness rules are reproducible.

| Rule | What it flags |
|---|---|
| (a) `numeric_inconsistency`, `date_inconsistency`, `weekday_inconsistency` | the same named thing with two prices, distances or dates, or one event on two weekdays. Conservative: an entity is a Capitalised phrase, qualifiers (season, child, 7-day, opens/closes) must match, a sentence that lists several amounts is an enumeration, two different items at one place are not compared |
| (a) `weekday_date_mismatch` | "Friday, June 18, 2026" when that date is a Thursday (blocks; arithmetic, not heuristic) |
| (b) `event_date_past`, `stale_year_title`, `review_stamp_is_publish_date`, `review_overdue`, `price_no_as_of`, `price_as_of_old` | dates and years already past, a "Last reviewed" that equals the publish date on an old post, prices with no "prices checked <month year>" |
| (c) `unsupported_first_hand_claim` | "we tested", "our editors verified", "tested across 10 countries" with no evidence section (blocks); "we stayed / our editors rode" (warns) |
| (d) `missing_required_section`, `banned_character`, `byline_not_allowed`, `affiliate_disclosure_missing`, frontmatter | the site's own ruleset from `site.yaml` |
| (e) `link_blocked`, `link_moved_domain`, `link_broken` | 401/403/429/451 are inconclusive (CORREGIR), never dead; a link that ends on another registrable domain is reported; no DNS or 404 is dead (BLOQUEAR) |

The generic content rules (chatbot residue, AI phrases, raw HTML) still run; the dental ones (phone, prices, dentists,
myths, testimonials) do not. The model prompt for travel asks for three things the rules cannot see: whether each named
entity exists and is what the post says, whether the source next to a figure plausibly backs it, and seasonality.

### Travel numbers (real, from this repo)

Fixtures: a fictional site (`tripnotes.example`), 4 clean posts, a **seeded** set (21 errors, written together with the
rules, so it measures coverage and regressions, not generalisation) and a **blind** set (14 errors, 4 posts, written by
a separate Sonnet subagent that was given `site.yaml` and the list of error categories but never saw the code, tests or
my fixtures). The rules were frozen before the blind set was scored (`reports/travel-rules-frozen-before-blind.sha256`).

| Set | Layer | Recall | Precision (block+warn, strict) | Notes |
|---|---|---|---|---|
| Seeded (21, not blind) | Rules only | 17/21 = 81% | 100% (17/0) | 0 false alarms on clean posts; the 4 misses need world knowledge (wrong river, wrong season, wrong daylight hours, a figure cited to the wrong page) |
| Seeded | Sonnet alone | 13/21 | 38% (13/21) | 12 off-target block/warn on the clean posts |
| Seeded | Rules + Sonnet | **21/21** | 59% | the model adds exactly the 4 the rules cannot see |
| **Blind, first pass** (14) | Rules only, frozen | **6/14 = 43%** | 75% (6/2) | 2 unmatched findings: one fixture artifact (my page list lacked the blind slugs), one real false alarm (two items at one café) |
| Blind, first pass | Rules + Sonnet | 11/14 | n/a (mixed rule states) | model adds B01, B02, B04, B05, B08 |
| Blind, after fixes (v2) | Rules only | 10/14 = 71% | 100% (10/0) | **fixed against this set: not a generalisation number** |
| Blind, after fixes (v2) | Sonnet alone | 8/14 | 36% (9/16) | 12 off-target on clean posts |
| Blind, after fixes (v2) | Rules + Sonnet | 13/14 | n/a | the 14th (B06) was found by the model on the *other* sentence of the contradiction, which the strict quote-overlap scorer counts as a miss |

Model cost: 12 calls (4 clean + 4 seeded + 4 blind posts), Sonnet in independent mode, **$0.383 total** (about
$0.03 per post). Weekly quota was kept in mind: one pass, no repeats.

**What the first blind pass found** (8 misses of 14): 3 are model-only by design (entity, source mismatch, seasonality);
5 were rule gaps that generalise, fixed and documented as post-blind: an entity named with an extra word in one place
("Donau Licht" / "Donau Licht Boats"); "per adult" treated as a qualifier that made two prices of the same item look
different; "boarding opens" doing the same; `Last reviewed 2026-06-03.` with a trailing full stop not parsed; VND (and
other currencies) not recognised as prices; and "Our editors rode ..." not matched as a first-hand claim. A guard for
the one real false alarm (two different items sold at one place) and a rule that `price_no_as_of` points at every line
that states a price were added in the same pass. Still missed by the rules: a weekday contradiction between a sentence
and a table row that name the event differently ("Friday night market" / "Harbourside Night Market").

**Honest limits of these numbers.** 14 errors in 4 posts is a tiny blind set; its author had the category list, so it
tests how well known classes are caught, not whether new classes exist; and its recall is now used up. Link results on
the fixtures are scripted (`.example` never resolves): the dead and 403 links are entries in a hand-written cache that the
blind author declared, so they prove the classification, not the network. The model's precision on these fixtures is
pessimistic: every local operator is fictional, so Sonnet reasonably says "I cannot verify that a Hanami Shuttle exists",
and it also flags "Prices checked October 2026" as an unevidenced verification. With the model layer on, **none of the
4 clean posts stays PUBLICAR**; on a site with real entities that noise would differ, and I have not measured it.

I also ran the rules on five public travel posts (read-only, not included here). Changes after that run (each with a
test): table rows that share a category tag in parentheses are different products; the Sources list is not read for
first-hand claims; affiliate short links may land on the merchant's front page; a 403 that also changed domain is
reported as moved.

### Full run on a real blog (30 Oct)

The travel rules were then run on all 224 posts of a public travel blog (rules only, live link checks) and 231 findings
were checked by hand in three stratified samples. Rules changed because of what the audit showed, each with a test
(`tests/test_travel_full_run_fixes.py`): a bare "as an AI" describing a product is not chatbot residue; bracket slots
inside a quoted prompt template and a "TBD" inside a sentence are not placeholders; a claim or an AI phrase inside a
`(source: ...)` citation, a `Sources:` line, a link anchor, quotation marks or a question is not the post speaking;
dates from an earlier year than the post, inside citations, next to past-tense or reporting verbs are history;
an "as of" date counts for prices only when it sits on a line with a price; affiliate short links may end on the
merchant's domain; a language root (`/en/`) redirecting to `/` is not a soft 404; "Standard" and "Standard Plus" are
different products; acronyms, status flags (`SOLD OUT`) and monthly rates are not entities or the same quantity as a
one-off price. The dental numbers and the travel fixture numbers did not change. The remaining false positives are mostly
in `numeric_inconsistency` and `date_inconsistency`, which are heuristics; they stay WARN.

Hand-checked precision on a fresh sample after those fixes: **75% of block findings fully right (95% right or
defensible)**, 62% of all findings (78% with the defensible ones); dead links, missing Sources and moved domains were
right in 93-100% of sampled cases, while the number and date contradiction heuristics were right in 14% and 0%. A single
reviewer labelled everything, and the per-rule samples are small (2 to 24), so treat these as rough. A later
check found one more false dead link: a URL with parentheses (`.../wiki/Titan_(submersible)`) was cut at the first
`)`; link targets now keep balanced parentheses, with a test.

## Files

```
run_gate.py            run the gate        evaluate.py           score rules and model layer
qa_gate/               rules, links, model layer, CLI (stdlib only); rules_travel*.py and travel_text.py are the travel profile
fixtures/clinic.yaml   the ficha: NAP, dentists, hours, services, allowed prices
fixtures/posts/        clean/ seeded/ heldout/ heldout2/ heldout3/   (seeded built by fixtures/build_seeded.py)
fixtures/travel/       site.yaml, posts/{clean,seeded,heldout}, seeded-errors.json, heldout-errors.json, link-cache.json,
                       build_seeded.py (the blind set and heldout-link-status.json were written by a separate agent)
fixtures/*-errors.json error lists; link-cache.json holds link results dated 2026-10-30
tests/                 315 pytest tests (rules, links incl. a local HTTP server, CLI exit codes, scorer, model-answer parsing, travel)
skill/content-qa-gate/ Claude Code skill that explains how to use the gate
reports/               JSON per post, SUMMARY.md, EVAL*.md, blind snapshots (EVAL-*-blind*.md), EVAL-travel-*, model-sonnet-travel/,
                       model-haiku/ and model-sonnet/ (raw model runs), model-eval/ (their scores),
                       link-modes/ (rules scored with an empty cache and with live requests)
```

## Fit with a client pipeline

Run it after the writer step and before the PR: `clinic.yaml` is the only source of truth, the gate blocks the PR on
exit code 2, and the report is attached so the editor reads findings instead of the whole post. Rules cost nothing
and run offline; the model layer adds roughly $0.002 (Haiku) to $0.033 (Sonnet) per post on this prompt.

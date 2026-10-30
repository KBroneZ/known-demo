# Blog post pipeline for dental clinic sites

One command takes a topic to a finished post, or tells you why it stopped. Each post ends as a local "PR" folder you can
read in five minutes; only a post that passes the QA gate is copied to the website.

```
real patient question -> brief (from clinic.yaml) -> draft (Claude Sonnet) -> QA gate (rules + Claude Sonnet)
        PUBLICAR: copy to the site          CORREGIR: auto-fix, QA again, at most 2 rounds
        BLOQUEAR: stop, a person decides    still CORREGIR after 2 rounds: stop, a person decides
```

The clinics are the two fictional demo clinics (`demo/web/sites/clinic-a`, `clinic-b`). Nothing is committed, pushed or
deployed by the pipeline.

## The stages

| Stage | What happens | Made by |
|---|---|---|
| Topic | Real question titles from r/askdentists (public archive API, no account), cached, then a filter (offered service, general question, search-style intent). Falls back to a hand-written seed list. Services that already have a post are skipped. | code |
| Brief | Keyword, intent, questions to answer, the only clinic facts allowed (copied from `clinic.yaml`, with price conditions and safety sentences kept verbatim), internal links from the site's routes, and external sources from a short list of pages that were opened and load. | code |
| Draft | Title, description, FAQ and body. Slug, dates, author, reviewer, category and service are set by the pipeline, not the model. | Claude Sonnet, isolated `claude -p` |
| QA | The same gate as `demo/qa`: deterministic rules, then a model review. The pipeline first renders the JSON-LD and FAQ the theme will produce, so the gate checks what the site will serve. | rules + Claude Sonnet (Haiku in runs 1 to 4) |
| Fix | Only for CORREGIR. The model gets the exact findings and may not invent a source to fix a claim. Max 2 rounds. | Claude Sonnet |
| Out | `out/<run>/<clinic>--<service>/`: `brief.md`, `draft.md`, `qa-r*.json`, `changes.diff`, `final.md` or `needs-human.md`, `pr.md` (checklist for the person), `metrics.json` (cost, time, rounds). A published post is copied to the site and its `/blog/<slug>` route is added to `clinic.yaml` `pages`. | code |

## Run it

```bash
cd demo/pipeline                                   # Python 3.10+, needs the claude CLI logged in
python run_pipeline.py topics                      # candidate topics per clinic
python run_pipeline.py run --dry-run               # briefs only, no model calls, no cost
python run_pipeline.py run --pick "clinic-a=Teeth whitening;Root canal therapy"
python run_pipeline.py approve out/<run>/<post-dir> --by "Name"   # a person accepts a post that stopped on CORREGIR
python run_pipeline.py topics --explain            # every question title and why it was accepted or rejected
python run_pipeline.py sync-pages                  # add /blog/<slug> to clinic.yaml `pages` for posts that lack it
python -m pytest                                   # 108 tests, no network, no model calls
```

`--pick` is the editor's topic approval. Exit code 1 means at least one post needs a person.

## Results (real runs, 2026-10-30)

**Plainly: over all 17 attempts the pipeline published 8 without help (47%); the first 12 gave 3 (25%), and the last 5 gave 5
(4 under the final review prompt).** An earlier version of this README said 2 of 8; that count was wrong, because it
left out the 2 attempts of run 3. Each attempt is one topic going through the whole pipeline. The pipeline was changed
between runs, so the rows are a history, not repeated samples.

| Run | What changed before it | Published | Stopped for a person | Cost | Time |
|---|---|---|---|---|---|
| 1 | first version | 0 of 4 | 4 | $0.255 | 276 s |
| 2 | reviewer chosen from the dentists' bios; the post's own route counts as a page; model "block" opinions on wording become fixable warnings | 2 of 4 (clinic-a) | 2 | $0.436 | 426 s |
| 3 (clinic-b) | price conditions and the 911 sentence kept in the brief; the model is shown the site's page list | 0 of 2 | 2 | $0.268 | 240 s |
| 4 (one per clinic) | topic filter (below); routes registered in `clinic.yaml` | 1 of 2 | 1 | $0.154 | 140 s |
| 5 (five new topics, spread over both clinics) | improvements below: richer brief, error-vs-suggestion review, Sonnet as reviewer | **5 of 5** at the QA in force (**4 of 5** at the first QA pass under the final prompt, see below) | 0 | $0.425 | 192 s |
| **All** | | **8 of 17** (47%) | 9 | **$1.54** | 21 min |

## Run 5: what changed, and how far to trust the 5 of 5

The run used topics chosen by me, new for the pipeline: three on clinic-a (does a filling hurt, when should a child first
see a dentist, do aligners hurt) and two on clinic-b (how long does a crown last, how often should adults get a checkup).
Every post passed on the first draft with no fix round: **$0.085 and 38 s per published post** (draft $0.036, Sonnet
review $0.049). Rules, brief and review were all changed since run 4, so one batch cannot say which change mattered.

What I changed (each one generalises; none is tuned to a topic):

1. **The brief carries what the clinic itself says about the service**, word for word, with its conditions ("Often, yes",
   "for new patients paying without insurance"), and the writer may make claims about how the clinic works only from those lines.
2. **The writer may not use loose generalities** ("most people", "many patients", "usually"); it says "your dentist will ..."
   or links an authorized source. This was the second biggest cause of stops (8 of 12 attempts).
3. **The review separates error from suggestion.** An error (contradicts the ficha, drops a condition or a hedge, false or
   dangerous medical statement, omitted safety instruction, invented fact or source, guarantee, schema mismatch) still
   stops the post. A suggestion (wording, a harmless generality, filler) is logged in `qa-r*.json` and in `pr.md` and never
   blocks or triggers a fix. A finding with no `kind`, an unknown one, or "suggestion" with severity block counts as an error.
4. **The fix prompt shows the paragraph** that holds each problem next to the reviewer's exact words and suggested fix.
5. **The review model is Sonnet, not Haiku.** Under the new prompt Sonnet's precision is far higher (below), at about
   $0.05 per review instead of $0.004.
6. Topic picking by exact question, and more hand-written seed questions (one per service per intent).

### Did the bar stay where it was? QA recall on the three blind sets

Same files and method as `demo/qa/README.md`: model run alone, then combined with the rules as they were on their first blind run.

| Review prompt | Sonnet alone | Rules + Sonnet | Sonnet precision | Clean posts not PUBLICAR | Review cost |
|---|---|---|---|---|---|
| original | 32/32 | **32/32** | 50% (33 true / 33 false) | 2 of 4 | $0.033 per post |
| error vs suggestion | 29/32 | **32/32** | 83% (29 true / 6 false) | 0 of 4 | |
| **final** (adds: "stronger or less conditional than the ficha's wording is an error") | 29/32 | **32/32** | 58% (30 true / 22 false) | 1 of 4 | $0.049 per post ($0.79 for 16 posts) |

**Rules + Sonnet stays at 32/32.** The three Sonnet misses (the "In today's fast-paced world" opener twice, and a dead link)
are things the rules catch. With Haiku and the middle prompt the combination was 31/32: it missed "the tooth is no longer
alive and cannot feel anything afterward", which Sonnet catches, one more reason the default is now Sonnet.

The middle prompt was too lenient. Reading the 15 suggestions it logged on the run 5 posts, I judged at least two to be real
errors it had demoted: "Parents and children can book back to back" (the ficha says "often") and "Your dentist will numb the
area first". The final prompt adds one sentence to count that as an error. Re-reviewing the five published posts under it:

- 3 of 5 still PUBLICAR (both aligners and pediatric on clinic-a, fillings on clinic-a).
- **checkups (clinic-b): CORREGIR, in both reviews** (the dropped "often"). One fix round ($0.034) cleared it, the post was
  rewritten on the site and the old and new QA reports are in the run folder (`qa-strict-s0.json`, `qa-strict-s1.json`).
- **crowns (clinic-b): CORREGIR in one review (the emergency price quoted without "any treatment is quoted after the exam";
  an unverifiable description of what an ADA page covers) and PUBLICAR in a second.** The review is not deterministic. The
  post stays published; I have not asked a person to settle it.

So the honest figures for run 5 are **5 of 5 at the QA that ran, 4 of 5 on the first pass under the final prompt (after one
fix round, 5 of 5)**. Extra spend on those re-checks and the blind-set measurements was about $2 (60+ model calls), which is not
in the table.

### Caveats that matter

- The new topics are easier than the ones that failed before. The failures concentrated in decision and emergency topics
  (root canal or extraction, a gap after a new crown, cavities after a checkup). Run 5 has none of those, and pain and
  lifespan questions are mild clinical topics. **I would not quote 5 of 5 as the expected rate on hard topics.**
- One batch of five. The review gave different answers on the same crown post.
- A suggestion that is really an error is the new risk. The final prompt narrows it; nothing in the code can detect it.
  A person skimming `pr.md` sees the suggestion count for each post.

Cost is the CLI's `total_cost_usd` at API list prices, not subscription quota. Averages over all 52 model calls: draft
(Sonnet) $0.038 and 24 s; one auto-fix (Sonnet) $0.040 and 15 s; one QA model review (Haiku, runs 1 to 4) $0.004 and 22 s (Sonnet in run 5: $0.049 and 17 s); rules
cost nothing. A fix round is about $0.045 and 37 s. Published posts: $0.117 and 114 s, $0.118 and 118 s (both needed the
2 rounds), and $0.040 and 42 s (passed on the first draft). Counting the failed attempts, a published post cost about
**$0.37 and 6 minutes of model time**.

### Why posts did not publish, with numbers

First drafts: **1 PUBLICAR, 7 CORREGIR, 4 BLOQUEAR** (12 attempts). Only one first draft passed.

Of the 9 attempts that stopped, **8 stopped on the model's remarks alone: the rules were clean (PUBLICAR) at the last
round.** One stopped on a rule (`unsourced_stat`, see the gate defect below) plus a model BLOQUEAR. Remarks by the Haiku
reviewer (runs 1 to 4), counted as attempts in which the type appeared at least once:

| Remark type | Attempts (of 12) | What it was |
|---|---|---|
| `fact_vs_ficha` | 9 | the draft contradicted or dropped a condition in `clinic.yaml`: a price without "for new patients paying without insurance", a reviewer who is not the one the bio names, swelling advice without the 911 instruction, "accepted" where the ficha says "in network" |
| `unsourced_claim` | 8 | a plausible general statement with no source ("most teeth need a crown", a treatment-time range) |
| `other` | 6 | judgment calls: advice thought too thin ("ask your dentist about vaping") or a section that did not answer its heading |
| `false_medical_claim` | 3 (2 as BLOQUEAR) | emergency advice left out (2) and an oversimplification (1); none was a false statement |
| rules `unsourced_stat` | 3 | one real, two false alarms ("every age in one visit") |
| `ai_tell`, `schema_incoherent`, `broken_or_fake_source` | 1 each | the last two were pipeline bugs (own route missing; a pool URL it cannot open) |

The biggest cause was therefore **my brief withholding facts that the clinic's own file contains** (9 of 12 attempts).
Four of those gaps are fixed (price and insurance statements and the 911 sentence are now copied verbatim; the reviewer comes
from the bios; the insurance rule that contradicted the ficha is removed). The insurance fix came after run 4 and is
not yet tested on a new run.

### What I would change to raise the rate

1. **Stop the loop on the right signal.** Rules decide PUBLICAR. Model remarks go into `pr.md` for the person unless they are
   a hard type (chatbot residue, testimonial, guarantee, false medical claim). On these 12 attempts the rules were clean at
   the last round in 11, so this alone would publish up to 11 of 12. The cost is real: the model's remarks included true
   catches the rules cannot make (price conditions, missing 911 advice), so the person must read them. Decide how much
   review time per post is acceptable (the planning target was 15 minutes) before choosing.
2. **Pick topics that are not clinical triage.** The one post that passed on the first draft was a factual lifespan topic
   (how long fillings last). The ones that never converged were decision and emergency topics (root canal or extraction,
   a gap after a new crown, cavities after a checkup), where every draft invites a new caution.
3. **Give the writer more of the ficha, not less**: each missing fact cost a fix round, about $0.045.
4. **Fix the rule defect** below.
5. Measure with Sonnet instead of Haiku as reviewer only if a person finds Haiku's noise too costly; precision was similar
   in the gate evaluation (`demo/qa/README.md`).

### A defect in the QA gate, not fixed here (it lives in `demo/qa`)

The `unsourced_stat` rule added after the third blind set treats "every age in one visit" as a statistic (a universal
quantifier plus "one visit"). It flagged clean text on clinic-b twice. The auto-fix reworded it away at the cost of a round.
`visits?` should come out of that rule's units.

## Where topics come from

Documented in `topics/seed.yaml`; the filter is `dental_pipeline/intent.py`; every title considered is in
`topics/explain-2026-10-30.txt` with the reason it was accepted or rejected.

1. **Evidence of what worries patients:** question titles from r/askdentists, through the public Arctic Shift archive (no
   account). Only the title, comment count and post id are kept. These are Reddit users, not Austin patients.
2. **Topic filter, before the brief.** A title becomes a topic only if (a) it is about a service in the clinic's own
   `clinic.yaml`, not one the clinic does not list (wisdom teeth, veneers, sedation, braces, grafts ...), (b) it is a general
   question, not a personal story (first-person words and numbers reject it), and (c) its wording matches a search-style
   intent: cost, pain, safety, how long it lasts, how long it takes, what to expect after, how often, urgency, or whether you
   need it. The post is then written for the canonical query ("Is teeth whitening safe?"); the Reddit title is kept as "how a
   patient put it". The title behind the old whitening post ("as white as the whites in my eyes") is rejected twice
   over: it is first person and has no search intent.
3. **Result on the real data:** of 134 question titles considered, **0 were accepted**: 69 not phrased as a question, 27
   with fewer than 3 comments, 22 personal cases, 11 with no search-style intent, 5 about a service the clinic does not list,
   9 services skipped because they already have a post. So Reddit gave evidence, not topics.
4. **Fallback that did the work:** `topics/seed.yaml` holds hand-written canonical questions, one per service, in the
   shape people search. These are **[sin verificar]**: no search volume was consulted. A real client needs Search Console on
   the site, a keyword tool, or the front desk's questions (all documented in `seed.yaml`, none used here).
5. **Editor approval:** `--pick` is the approval step. It was done by the AI session, not a human.

## Fail-closed behaviour (code review 08)

- **The model's verdict is read, not just its findings.** Severity and verdict are normalised (BLOCK, Bloquear, critical, high
  all mean block); an unknown or missing severity counts as block and is never dropped. A model that says BLOQUEAR or
  CORREGIR but names nothing actionable stops the post for a person. An answer that is not valid JSON, has no usable verdict,
  or a model that did not run, also stops the post (`needs_person`) and skips the fix rounds. It is never PUBLICAR.
- **`--no-publish`** gives status `passed-not-published`, and `pr.md` says the post was not copied.
- **A crash in QA** makes that post BLOQUEAR (`qa-crashed`); a crash anywhere else in a topic is recorded as `crashed`. The
  run goes on with the next topic and `run.json` is rewritten after every post, so earlier results are never lost.
- **An empty slug** (a title with no usable words) is a draft error; nothing is written. `publish` also refuses any slug that
  is not kebab-case.
- **`pages` in `clinic.yaml`**: an unindented list is handled; a `pages` that exists in a form the tool cannot edit (inline
  list, no items) raises and the post is not published; the file is replaced atomically.
- **The text that is published is checked too**: the rules run once more on the exact bytes (footer included) before a copy.
- **A failed model call keeps its cost** in the totals. `approve` gives a clean error for a folder that is not a post.
- **QA gate (in `demo/qa`)**: raw HTML in a post, links with schemes other than http, https, mailto and tel, links to
  localhost or private addresses (never fetched), and malformed URLs are blocked. The `visits?` false alarm is fixed. Reddit
  titles shown to the writer as "other patient questions" go through the same filter as topics.

Not touched here: the tracker items of the review (`demo/tracker`) belong to that terminal.

## Routes in `clinic.yaml`

A site that lists `pages` in `clinic.yaml` (clinic-a) fails `npm run check` if a built route is missing from it. Publishing
now adds exactly one line, `- /blog/<slug>`, to that list (after the last `/blog/` entry, keeping the file's line endings),
checks that nothing else in the file changed, and undoes the post if that check fails. A site with no `pages` list
(clinic-b) is not touched. `python run_pipeline.py sync-pages` adds routes for posts that lack one; it added the two that
had been published before the change. The pipeline touches nothing else in `demo/web`. 9 tests cover it.

## What a person did, and has to do

Done in this session by the AI, not by a human editor: topic approval and reading the stop reports. No dentist reviewed
anything. Left for a person, from each `pr.md`:

- **The 9 stopped attempts** each leave a `needs-human.md` and the remaining remarks; most are model-only. Read them, edit, or
  accept with `approve ... --by`, which records who accepted what and also registers the route. Not done for any of them.
- **Dentist sign-off on clinical statements** for the three published posts (the QA passing is not a review).
- **Open every external link**: the check only fetches status codes.
- **Skim `changes.diff`** when rounds > 0.

## Website checks after publishing

`npm run build` and `npm run check` in `demo/web`: **ALL GATES PASS** (9 of 9 checks). clinic-a has 16 pages and clinic-b 15
(the fillings post was added to it). Posts on the site: clinic-a 5 (2 new), clinic-b 4 (1 new).

## Limits

- One fictional clinic pair and 12 attempts; the pipeline changed between runs.
- Topics: see above. The "primary keyword" is a heuristic (service plus city) with no volume data.
- The QA model review is now Sonnet with an error-vs-suggestion prompt; the runs 1 to 4 numbers are for Haiku, which was noisy (about half its remarks were cautions or mistakes, see `demo/qa/README.md`).
- Source list: 11 pages, all opened on 2026-10-30. A topic with no matching source gets no external link and no statistics.
- No Codex second opinion, no preview URL, no git PR, no deploy. "Local PR" is a folder.

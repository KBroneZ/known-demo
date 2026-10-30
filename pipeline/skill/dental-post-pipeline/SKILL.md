---
name: dental-post-pipeline
description: >
  Produce a dental clinic blog post end to end and leave it as a local "PR" folder: pick a topic from real patient
  questions, build a brief from clinic.yaml, draft with Claude, run the content-qa-gate (rules + model), auto-fix
  CORREGIR for at most 2 rounds, stop on BLOQUEAR, and copy to the website only when the verdict is PUBLICAR.
  Use for "write the next post for <clinic>", "run the blog pipeline", "generate posts for clinic-a / clinic-b".
version: 0.1.0
---

# dental-post-pipeline

Code: `demo/pipeline/` (`run_pipeline.py`, `dental_pipeline/`). Python 3.10+, standard library, needs the `claude` CLI
logged in and `demo/qa/` (the QA gate) next to it. It never commits, pushes or deploys.

## Stages

1. **Topic** `topics.py` + `intent.py`: question titles from r/askdentists (Arctic Shift archive, no account), cached.
   Filter: a service the clinic lists, a general question (no first person or numbers), and a search-style intent (cost,
   pain, safety, lifespan, duration, recovery, frequency, urgency, decision). Passing titles become the canonical query.
   On the real data 0 of 134 titles passed, so the hand-written `topics/seed.yaml` queries [sin verificar] did the work.
   `topics --explain` shows every decision. The editor approves the topics (`--pick`).
2. **Brief** `brief.py`: built from data, not by a model. Keyword, intent, questions to answer, the only clinic facts
   allowed (copied from `clinic.yaml`, hours worded like the theme), internal links from the site's routes, and
   external sources from `sources/authorized-sources.yaml` (pages that were opened and load).
3. **Draft** `draft.py`: `claude -p` on Sonnet, isolated (no user memory, tools, skills or MCP). The model writes
   title, description, FAQ and body. Slug, dates, author, reviewer, category and service are set by the pipeline.
4. **QA** `review.py`: renders the JSON-LD and FAQ section the theme will produce, then runs the gate: rules, then a
   model review on Haiku. Model remarks that only say "cannot verify this URL" for a pool URL are dropped.
5. **Fix** only for CORREGIR: the model gets the exact findings and must change only those, never invent a source.
   At most 2 rounds. **BLOQUEAR stops the run** for a human; nothing is copied.
6. **Out** `out/<run>/<clinic>--<service>/`: `brief.md`, `brief.json`, `draft.md`, `qa-r*.json`, `changes.diff`,
   `final.md` or `needs-human.md`, `pr.md` (checklist for the person), `metrics.json` (cost, time, rounds).
   A PUBLICAR post is copied to `web/sites/<clinic>/src/content/posts/<slug>.md` with the demo footer, never over an
   existing file.

## Run it

```bash
cd demo/pipeline
python run_pipeline.py topics                                   # candidate topics per clinic
python run_pipeline.py run --dry-run --pick "clinic-a=Teeth whitening"   # briefs only, no model calls
python run_pipeline.py run --pick "clinic-a=Teeth whitening;Root canal therapy" --pick "clinic-b=Crowns and bridges"
python run_pipeline.py run --no-publish --no-model-qa           # rules-only QA, copy nothing
python -m pytest
```

Exit code 1 when any post needs a person. `approve out/<run>/<post> --by "Name"` publishes a post that stopped on
CORREGIR after a person has read the remaining findings (never BLOQUEAR); it records who accepted what. After publishing,
run `npm run build` and `npm run check` in `demo/web`.

## Rules for whoever runs it

- Do not hand-edit a drafted post to make it pass; fix the brief, the rules or the source pool, and re-run.
- Publishing adds one line, `- /blog/<slug>`, to `pages` in the site's `clinic.yaml` (when the site has that list) and
  nothing else; `sync-pages` does it for posts published before. Without it `npm run check` fails on the route contract.
- The model's output is unverified. A person still signs off clinical statements and opens every external link.
- Cost, measured on 8 attempts: draft about $0.04 and 26 s, each fix round about $0.045 and 35 s, QA model review
  (Haiku) about $0.004 and 23 s. Two of the three published posts needed the full 2 rounds; 3 of 12 attempts published on their own (3 of 8 after the first run's bugs were fixed).
- The Haiku review keeps finding new nitpicks, so a post whose rules are clean can still stop after 2 rounds. Decide the
  stopping rule (rules only decide; model remarks go to the person) before running at scale.

---
name: content-qa-gate
description: >
  Run the two-layer QA gate on AI-written dental clinic blog posts before they are published.
  Deterministic checks (clinic facts vs clinic.yaml, links, forbidden claims, AI phrases, frontmatter
  and JSON-LD) plus an optional model review. Returns BLOQUEAR / CORREGIR / PUBLICAR per post and a
  JSON report. Use when a post .md is drafted, before opening a PR, or when asked to "QA this post",
  "check the post against the clinic data" or "run the content gate".
version: 0.1.0
---

# content-qa-gate

Gate for posts written by AI for a clinic site. It answers one question: is anything in this post
false, risky or off-brand compared with the clinic's own data (`clinic.yaml`)? It does not judge
whether the post is good SEO, and it does not publish anything.

Code lives in `demo/qa/` (`run_gate.py`, `qa_gate/`). Python 3.10+, standard library only
(pytest only for the tests).

## When to use

- A draft post exists as `.md` with frontmatter and a JSON-LD block.
- Before a PR with a new or refreshed post, and again after any edit (an approval expires when the text changes).
- Not for: non-dental content, posts without a `clinic.yaml`, or deciding clinical truth. Clinical claims
  that pass here still need the clinic dentist's sign-off (see "Limits").

## Run it

From `demo/qa/`:

```bash
# Deterministic layer, network on (HEAD requests, 10 s timeout). Exit 0/1/2 = PUBLICAR/CORREGIR/BLOQUEAR, 3 = gate error.
# Fail CI on any code >= 2. A post that crashes the gate is BLOQUEAR; zero posts is exit 3, never 0.
python run_gate.py path/to/post.md --clinic path/to/clinic.yaml

# Offline: external links come from fixtures/link-cache.json; a link not cached (or older than 30 days) is CORREGIR
python run_gate.py fixtures/posts/clean --offline

# Record fresh link results into the cache (online run)
python run_gate.py fixtures/posts/clean --update-cache

# Add the model review (opt-in; sends the post + ficha to the model CLI)
python run_gate.py post.md --llm claude --llm-model sonnet   # needs a logged-in claude CLI
python run_gate.py post.md --llm codex      # ChatGPT via the ask-chatgpt skill, slow
```

Outputs go to `reports/`: `<name>.json` per post, `SUMMARY.md` (verdict table),
`prompts/<name>.prompt.md` (the model prompt, always written), `llm/<name>.llm.txt` (raw model answer).

## Read the result

- **BLOQUEAR**: at least one `block` finding (wrong phone/address/hours/price/dentist, dead link, fake
  testimonial, guarantee, medical myth, chatbot residue, broken schema). Do not publish.
- **CORREGIR**: only `warn` findings (AI phrases, unsourced statistic, "best dentist", unverifiable link,
  missing schema). Fix or justify each, then re-run.
- **PUBLICAR**: no block/warn. Still goes to the human reviewer; the gate never publishes.
- `info` findings never change the verdict. An external link that is not verified (offline cache miss) is a `warn`, not `info`.

Each finding has `rule`, `severity`, `line` (file line), `evidence` and `message`. Fix the line, not the symptom:
never "repair" a claim by inventing a source. Remove the claim or mark it for the dentist.

## Model layer

`--llm none` (default) only writes the prompt, so the gate runs with no keys and no cost. `--llm claude` runs
`claude -p` isolated (no CLAUDE.md memory, skills, MCP or tools, empty cwd, English system prompt) and returns JSON
findings with an exact `quote`; `--llm codex` goes through `ask-chatgpt` and returns a readable Spanish review that
is kept but not merged. The model can raise the verdict, never lower it, and its output is unverified data: confirm
each finding against the post before acting.

- `--llm-independent` hides the rules' findings from the model; use it only when measuring the model alone.
- Measured on the fictional blind sets (see README): Sonnet found 32/32 injected errors (rules alone 17/32), Haiku 18/20
  on the first two sets; about half of the model's block/warn remarks are off-target. Sonnet costs about $0.033 per post, Haiku about $0.002.
- Practical use: rules decide the verdict; show the model's remarks to the human reviewer as notes. For R3 content
  (health claims, real people) also run the `prepublish-review` skill on the corrected draft.

## Adapting to a new clinic

1. Fill a `clinic.yaml` like `fixtures/clinic.yaml`: NAP, dentists, hours, services with aliases, the only
   allowed prices, accepted insurance, pages that exist, testimonials on file (empty list = none allowed).
2. The YAML subset is parsed by `qa_gate/miniyaml.py`: no anchors, no `|`/`>` blocks.
3. Run `pytest tests` and `python evaluate.py` before trusting a rule change.

## Travel profile

A `site.yaml` with `profile: travel` (see `fixtures/travel/site.yaml`) switches the gate to the travel rules; the dental
rules do not run. Every check is switched on by the key that configures it: `required_sections`, `banned_characters`,
`bylines`, `author_titles`, `evidence_headings`, `affiliate` (hosts, params, disclosure phrases), `review_max_age_days`,
`stamp_grace_days`, `pages` (internal page list from the sitemap). Pass the check date with `--today YYYY-MM-DD` for
reproducible runs. Rules: contradictions inside a post (same entity, two prices, distances, dates or weekdays; a weekday
that disagrees with its own date), staleness (past event date, past year in the title, review stamp equal to the publish
date, prices with no as-of date), first-hand claims with no evidence block, and the site ruleset. A 401/403/429/451 answer
is `link_blocked` (CORREGIR, never dead); a link that ends on another domain is `link_moved_domain`. The model prompt
checks entities, whether a source plausibly backs a figure, and seasonality. Numbers: `README.md`, section "Travel profile".

## Limits (say them out loud when reporting)

- Deterministic rules match patterns. A false medical statement is caught only if it is on the curated
  myth list or the model layer notices it; an invented statistic is flagged because it has no link, not
  because it was proven false; a link in the paragraph only means a source is claimed.
- Rules were written by the same people who wrote the first test set. Blind sets lose their value once the
  rules are fixed against them: `heldout`, `heldout2` and `heldout3` are used up (first blind runs: 7/10, 7/10,
  3/12), so write a new blind set, with an author who has not seen the rules, before quoting a new recall.
- Real-world scores need real posts. The numbers in `README.md` come from 4 fictional posts.

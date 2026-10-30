# Known demo: sites, posts, QA and AI-visibility measurement

Built by Andrew Rodrigo in October 2026, mostly with Claude Code agents, the way Known works. Every number below comes from a run in this repo; each folder's README says how to reproduce it. Where something did not work, it says so.

The clinics in `web/`, `qa/` and `pipeline/` are **fictional** (555 phone numbers, `.example` domains). The tracker measured **real** Austin practices from public directories, shown anonymised as Practice A–H. They are a sample, not clients and not a ranking.

## The four pieces

| Folder | What it does | Result |
|---|---|---|
| [`web/`](web/README.md) | One Astro repo, many clinic sites. A site is a `clinic.yaml`, a `theme.json` and Markdown posts. JSON-LD, sitemap and `llms.txt` are generated from the data. | 2 sites (19 and 17 pages). All local gates pass (JSON-LD, links, page weight ~4 KB gzip, axe on desktop and mobile with 0 violations, CLS 0). A footer change touched only the footer on 36 of 36 pages, with 0 content-text diffs; an edit outside the footer was caught on 32 pages (negative control). |
| [`qa/`](qa/README.md) | Pre-publish check for AI-written posts: rules against the clinic's own data, plus a model review. Verdict per post: block / fix / publish. | On 3 blind test sets (32 errors), the rules alone caught **17/32** on first sight. Rules plus model caught **all 32** in these sets, at about one false alarm per real error (model precision ~50%). The third set's posts and error list were written by a different model (ChatGPT) that never saw the rules; it declined to insert 11 of the 12 errors itself, so a script inserted them verbatim. A **travel-site profile** (driven by a `site.yaml` with the site's own editorial rules) adds checks for contradictory figures and weekdays, past event dates, undated prices, "we tested" claims with no method, and dead or moved links: on its blind set (14 errors) the frozen rules caught **6/14** first time and rules plus model **11/14**. |
| [`pipeline/`](pipeline/README.md) | Topic → brief → draft → QA → fix (max 2 rounds) → local "PR" folder → site. A person approves. | **8 of 17** attempts published unaided so far: 3 of the first 12, then 5 of 5 after the brief and the reviewer were fixed (4 of 5 on a re-check under the final reviewer prompt), with the QA still catching 32/32 on the blind sets. 8 of the first 9 stops came from the model reviewer's remarks while the rules were clean. The README has the history, costs and causes. |
| [`tracker/`](tracker/RESULTS.md) | Runs each patient-style prompt several times per engine and reports how often a practice is named or cited, with 95% intervals. | 80 real answers (an OpenAI model through Codex CLI, ×5; Claude Haiku through Claude Code CLI, ×3). Two repeats of the same prompt share only **~27% (Codex) and ~32% (Claude)** of the businesses they name (Jaccard, computed in code), so a single answer is not a result. |

## What I would bring to Known

- **Receipts with a rate.** The same prompt × engine × city, repeated, reported as "named in k of n answers [interval]" next to the raw answers.
- **QA before anything goes live.** Cheap deterministic rules first, a model review second, and a person reads only what was flagged. Every finding is logged.
- **Many sites from one repo.** Template changes ship to every client at once (tested here on 2 sites), with a snapshot test proving the content did not move.

## Checks and CI

Every push runs [`.github/workflows/ci.yml`](.github/workflows/ci.yml):

- **Python** (`qa/`, `tracker/`, `pipeline/`): `ruff check` and `ruff format --check` (settings in [`ruff.toml`](ruff.toml)), then each package's pytest suite on Python 3.10 and 3.13.
- **Web** (Node 22.18+): Prettier check, build both sites, compare the built HTML with the approved `golden/` snapshots, run the quality gates (JSON-LD, links, page weight, axe, CLS) in headless Chrome, then the tool tests.

To run the same checks locally:

```bash
ruff check . && ruff format --check .
cd qa && python -m pytest        # same in tracker/ and pipeline/
cd web && npm ci && npm run format:check && npm run build && npm run golden:diff && npm run check && npm test
```

No step needs an API key or the network, except the browser gate, which needs a local Chrome or Edge. Recorded run output (`pipeline/out/`, `qa/reports/`, `tracker/report/`, `web/golden/`, `web/reports/`) is kept as evidence for the numbers above and is marked as generated.

## Honest limits

- The engines in the tracker are vendor coding-agent CLIs, not the ChatGPT or Claude apps, and not the APIs. Location is a sentence in the prompt. Google AI Overviews and Perplexity have not run, because I had no keys.
- The samples are small: one city, one day, 10 prompts.
- The pipeline's publish rate rose after fixes measured on a small new batch (5 attempts). That needs a bigger sample before it means much.
- Nothing is deployed. Everything runs locally.

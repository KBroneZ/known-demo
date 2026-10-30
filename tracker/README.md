# AI visibility tracker (prototype)

Sends the same prompt to each AI engine several times, with the city set, stores every raw answer, and reports how often each practice is **named** and **cited**, with 95% intervals. One screenshot of one answer is not a measurement: the same prompt gives different practices on different runs.

## What each engine is (read this first)

None of these is the consumer app a patient would open.

| Key | What it really is | Needs |
|---|---|---|
| `codex_cli` | An OpenAI model with its native web search, run through OpenAI's **Codex coding-agent CLI** under a ChatGPT Plus login. Not ChatGPT, not the API. | `codex` on PATH, `codex login` |
| `claude_cli` | Claude Haiku with WebSearch/WebFetch, run through the **Claude Code CLI** under a Claude subscription, with memory files, settings, plugins and MCP switched off. Not claude.ai, not the API. | `claude` on PATH, `claude auth login` |
| `openai` | OpenAI Responses API + `web_search`, approximate Austin location | `OPENAI_API_KEY` |
| `anthropic` | Claude Messages API + `web_search`, approximate Austin location | `ANTHROPIC_API_KEY` |
| `perplexity` | Perplexity Agent API + `web_search`, Austin location | `PERPLEXITY_API_KEY` |
| `google_aio`, `google_ai_mode` | Google AI Overviews / AI Mode via DataForSEO (third-party search data), Austin | `DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD` |
| `app_<name>` | Answers **you paste by hand** from a consumer app (see Import) | nothing |

CLI engines get their location only from a sentence added to the prompt ("I'm in Austin, Texas."), and a coding agent may search and write differently from the product it shares a model with. The API engines pass a structured location. Official APIs, vendor CLIs or a SERP provider only: no scraping of any app. **Gemini is left out on purpose**: its grounding terms forbid storing and analysing results (see `research/04-ai-visibility-tracker.md`). An engine without its key or login is skipped and listed in the report.

## Status (30 Oct 2026)

- Built and tested: 7 engine adapters, SQLite storage, mention/citation extraction, optional LLM judge, Wilson intervals, HTML report, cost guard, manual import. 94 tests.
- **First real batch done** on 8 real Austin practices, shown here as Practice A to H: `codex_cli` 10 prompts × 5 reps = 50 answers, `claude_cli` 10 × 3 = 30, all 80 OK, no quota hit, $0. One-page summary for Mike: `RESULTS.md`; full numbers and intervals: `report/index.html` (anonymized). Raw data is in `runs/real.db` (git-ignored).
- The practice domains were checked by opening each site (two needed a fix, one practice shows a second trade name that is tracked as an alias). After a config fix, `python -m vistrack reextract` recomputes mentions and citations from stored answers without new queries.
- The API engines (`openai`, `anthropic`, `perplexity`, `google_*`) have not run live (no keys); their request/response shapes follow vendor docs and may need small fixes.
- `--mock` runs everything with synthetic answers about fictional practices (`config/mock_demo.yaml`). Mock reports carry a red banner: their numbers measure nothing.

## Real names stay local (anonymization)

Real practice names, aliases and domains live only in `config/austin_real.local.yaml` (git-ignored). `config/austin_real.yaml` is the shareable example: Practice A to H with reserved `.example` domains and the same structure (each real brand also carries `public_id`, `public_name`, `public_domain`). The default config is the local file when it exists. Everything that may leave the machine is generated with `--anonymize`: practices become Practice A to H, domains of tracked practices become `practice-x.example`, and the list of other businesses is dropped (only their count is shown). The git-ignored `gold/gold_real.local.jsonl` (real answers) and `runs/` hold the raw data.

```bash
python -m vistrack report --anonymize     # report/index.html          (shareable)
python -m vistrack numbers --anonymize    # report/numbers.json        (shareable)
python -m vistrack report                 # report/local/index.html    (real names, git-ignored)
```

Source domains that engines cite (directories, state board, practices' own sites) stay in the cited-sources table, since they are the sources; review them before sharing outside the team.

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env            # only for API engines; never commit .env
python -m vistrack status       # which engines are ready (secrets are never printed)
python -m vistrack estimate     # upper-bound API cost before spending anything
python -m vistrack run --engines codex_cli --confirm-spend
python -m vistrack report --anonymize    # writes report/index.html (without the flag: report/local/index.html)
python -m vistrack numbers --anonymize   # every figure quoted in RESULTS.md (report/numbers.json)
```

CLI engines run one call at a time with a pause between calls (`pause_seconds`, default 20) and **stop at the first quota or login error** (the run prints `STOPPED EARLY` with the reason), keeping everything stored so far; re-running the same command resumes. The CLI child process gets only an allowlist of environment variables (PATH, profile dirs, proxy settings, the CLI's own config dir), never the keys in `.env`, runs in an empty temporary directory that is deleted afterwards, and is killed with its whole process tree on timeout. Repetitions per engine are set in the config (`reps`): 5 for `codex_cli`, 3 for `claude_cli`. They use subscription quota, not dollars, so their cost shows as $0.00; API engines' cost is measured per call and capped by `budget_usd` (25 $).

Without any login or key: `python -m vistrack run --config config/mock_demo.yaml --mock`, then `report` with the same flags.

## Compare with the consumer apps (import)

Copy answers by hand from the apps (ChatGPT, Gemini, Perplexity, claude.ai...) into a JSONL file, one answer per line:

```json
{"prompt": "best dentist in Austin TX", "app": "chatgpt", "date": "2026-11-02", "text": "<the answer as shown>", "urls": ["https://..."], "location": "Austin, TX (device)"}
```

```bash
python -m vistrack import --file apps.jsonl
python -m vistrack report
```

Each app becomes its own column (`app_chatgpt`...) next to the other engines. `date` must be ISO (`2026-11-02`). `urls` and `location` are optional; URLs inside `text` are picked up. Paste different answers to the same prompt to get repetitions; importing the same file twice adds nothing (identical answers are skipped). With few pasted answers the intervals are very wide: read them as examples.

## What is measured

- **Mention**: the practice is named in the answer (alias match on normalised text; negative mentions are flagged). **Cited**: a URL in the answer (link or bare) is on the practice's domain. For the CLI engines, search results the answer does not use are kept as "consulted", not counted as cited. Rates are k of n answers with a Wilson 95% interval, plus a prompt-level bootstrap interval, since runs of one prompt are correlated.
- Errors, rate limits (including errors hidden inside HTTP 200) and "no AI Overview shown" are **not** counted as "not mentioned": they leave the denominator.
- The report shows how much repetitions disagree over **all** businesses named (needs the judge; two empty answers never count as agreement) and, separately, over the tracked practices only; it also shows the most cited domains, other businesses named (heuristic, from bold or linked names, unless the optional LLM judge ran), and a method box.
- The tracked list is a convenience sample of public directory listings, not a ranking. Engines often name other practices; a low rate means "not named in these prompts", nothing more.

## LLM judge (optional)

`python -m vistrack judge` sends each stored answer to Claude Haiku and records which tracked practices it names (plus other businesses), next to the regex result: `matched_by` is `regex`, `judge` or `both`. By default it runs through the Claude Code CLI (`--with claude_cli`, subscription, no API key, no tools, no memory files); `--with api` uses `ANTHROPIC_API_KEY`. It is serial with a pause and keeps going per answer. The report's headline rates stay on the regex layer; judge-only mentions are shown separately.

## Extractor accuracy

- **Real answers** (`gold/gold_real.local.jsonl`, git-ignored because it holds real answers): 40 of the 80 real answers (random, stratified by engine), read in full and labelled by a Claude model **before** looking at any extractor output; **not yet spot-checked by a human**. Only 12 true mentions, so every figure is rough. `python -m vistrack validate-real` writes an anonymized `report/validation_real.json`. Alias regex first scored precision 100%, recall 83% (it missed "Dr. H at Practice H Cosmetic Dentistry"); I added an alias for the doctor's name and re-measured on the same sample: 100%/100%, which is tuned on that sample. The judge scored 100%/100% from the start. Labels and judge are both Claude, so errors may be correlated. Over all 80 answers regex and judge agree on 26 mentions; 1 is regex-only (a practice named only in a sources list) and none judge-only after the alias fix.
- **Synthetic edge cases** (`gold/gold_set.jsonl`, 40 answers I wrote, with Practice A-H and `.example` domains): precision 94%, recall 94%, citations 100%; the 4 misses are generic wording that contains an alias, an indirect reference and a typo (plus one noun phrase). Not real answers.

## CLI-engine answer review

All 80 real answers were scanned (and 40 read in full) for coding-agent artefacts. Found: no sandbox, file or "I'll search" talk; no non-English text. Found: 3 of 50 Codex answers are a clarifying question or generic advice with no practice named; 4 Codex answers cite no URL; 2 of 50 Codex and 1 of 30 Claude answers state today's date; 20 of 30 Claude answers add meta-comments such as "I haven't verified these pages"; both engines often end by offering to narrow the search. None of this affects mention detection, but it shows these are agent-style answers, not app-style ones.

## Checklist for the next real run

1. Practice domains are verified (30 Oct 2026); recheck if the list changes.
2. Model ids for the API engines come from research 04; confirm them against the vendors' current docs.
3. Have a person spot-check a sample of the model-labelled answers in `gold/gold_real.local.jsonl`.
4. Before sharing anything, regenerate with `--anonymize` and grep the shared files for real names.

```bash
python -m pytest        # 94 tests: statistics, extraction, adapters, CLI engines, judge, runner, import
```

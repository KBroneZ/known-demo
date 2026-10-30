# First real batch: Austin dental practices (30 Oct 2026)

**What was measured.** 10 patient-style prompts ("best cosmetic dentist in Austin", "emergency dentist open today"...), each sent repeatedly to two AI engines with web search, location set to Austin: an OpenAI model through the Codex CLI (5 repetitions, 50 answers) and Claude Haiku through the Claude Code CLI (3 repetitions, 30 answers). 80 of 80 calls succeeded, no quota limit hit, cost $0 (subscription quota). We tracked 8 real Austin practices taken from public directories, shown here as Practice A to H; they are a convenience sample, not a ranking, and not clients.

**Headline: one answer is not a result.** Counting every business an answer names (tracked practices plus the names an LLM judge extracted), two repetitions of the same prompt share only about 27% (Codex) and 32% (Claude) of their names (Jaccard overlap, averaged over all pairs; per prompt it ranges 10–68% and 6–67%). Codex named 77 business-prompt pairs (67 distinct names): only 1 appeared in every repetition of its prompt, and 38 (49%) in just one. Claude named 114 pairs (97 distinct names): 19 (17%) in every repetition, 74 (65%) in one, with only 3 repetitions. Names are compared as written, so one business under two spellings overstates the gap a little. For the 8 tracked practices, every practice-prompt pair Codex named at least once was missing from some repetitions (6 of 6; Claude 2 of 6), so a single run would say "named" or "not named" by luck.

**Rates for the tracked practices** (share of answers naming them, 95% Wilson interval):

| | OpenAI model (Codex CLI, n=50) | Claude Haiku (CLI, n=30) |
|---|---|---|
| Any of the 8 named | 18% (9/50) [10–31] | 30% (9/30) [17–48] |
| Practice A | 8% [3–19] | 0% [0–11] |
| Practice H | 8% [3–19] | 20% [10–37] |
| Practice C | 2% [0–10] | 13% [5–30] |
| Practice E | 6% [2–16] | 10% [3–26] |
| Practice F | 0% [0–7] | 7% [2–21] |

Practices B, D and G were never named (0/80). The intervals overlap almost everywhere, so differences between practices or engines are not established. The engines mostly recommend other practices (the judge found over 130 other names, not listed here), so "rarely named" says nothing about quality.

**Most cited sources** (share of the 80 answers citing the domain): lantern.llc 21%, reviews.birdeye.com 16%, rankmydentist.com 10%, tsbde.texas.gov (state dental board) 9%, aidm.org 9%, zocdoc.com 9%. A tracked practice's own website was cited in 9 of 80 answers, all from the OpenAI model; Claude named practices without citing their sites.

**Limits, plainly.**
- Both engines are vendors' coding-agent CLIs, not the ChatGPT or Claude apps, and not the APIs. Location is only the sentence "I'm in Austin, Texas." in the prompt. A scan of all 80 answers found no coding-agent artefacts (sandbox or file talk, "I'll search"); 3 of 50 Codex answers asked a clarifying question or gave generic advice instead of recommending anyone.
- Small sample: 10 prompts, 3–5 repetitions, one day, one city. The name-overlap figure depends on a Claude judge reading Claude answers.
- Mention detection was checked on 40 real answers labelled by a Claude model (12 true mentions), not a human, so a person should spot-check. The alias matcher first missed 2 of 12 (engines write "Dr. H at Practice H Cosmetic Dentistry"); after adding an alias for the doctor's name it scores 100% on that same sample, which overstates accuracy on new answers. The LLM judge found all 12. Labels and judge are both Claude, so errors may correlate.
- Gemini is not measured (its terms forbid storing results); Google AI Overviews and API engines have not run (no keys).

Every figure above comes from `python -m vistrack numbers --anonymize` (written to `report/numbers.json`); details, per-prompt intervals and method: `report/index.html`.

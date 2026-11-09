# Offline version: LLM personas play the bargaining game

*Plan, 8 November 2026. Nothing has been built yet.*

## 1. Goal

Let a **local language model**, running on your own machine with no internet, play the Bargaining Simulation Tool many times. Each time, it plays in the role of a given **player profile**, for example "a 52-year-old female union delegate, blue-collar, foreign-born, working in Romania". All choices, game outcomes and the model's answers to the final questionnaire are exported to **CSV** for analysis in **Stata**.

The research question is whether the persona changes the play, and whether it does so in stereotyped ways. For example:
- Do "female" personas favour women and target the gender pay gap more than otherwise-identical "male" personas?
- Do "union delegate" personas protect the union premium?
- Do "blue-collar" personas prefer flat (absolute) increases?
- Do the priorities a persona *states* in the questionnaire match what it *did* in the game?
- Does any of this change with the model used, or with the language the game is played in?

## 2. Design principles

1. **The game logic is reused, never copied.** The offline runner drives the existing Flask app in-process, the same way the regression test already does (Flask's test client, no web server, no browser). The maths is therefore identical to the website by construction, and every future fix to the game automatically applies to the experiment.
2. **The same random draws for every persona.** Each game gets a *scenario seed*, which fixes the workforce, the company gains, inflation and the blue-/white-collar shares. Every profile plays the same set of scenarios, so differences between profiles come from their choices, not from luck.
3. **Attributes are controlled, not just described.** To detect bias, the persona attributes must vary independently (a factorial design), and the descriptions must differ only in those attributes. A free-text description that also changes writing style or tone would mix the effect of "female" with the effect of the text. See section 4.
4. **The model sees what a human sees.** Prompts are built from the same translation files as the website (`translations/*.xlsx`), so the model reads the same case description, instructions and indicator names as human players. Playing in other languages comes for free, and that is itself a variable to study.
5. **Everything is logged and resumable.** Every prompt and raw response is saved, so a run of many hours can stop and continue where it left off.
6. **Human and model data are comparable.** The exported variables use the same names and codes as `fdb.db` from the website, so real players can be added to the same Stata analysis as a benchmark.

## 3. How a game is played by the model

For each game (one profile, one scenario seed, one model, one language):

1. **Setup:** set the scenario seed, choose the number of rounds (for example 5) and the wage level (for example 2,000 in the country's currency), and start the game.
2. **Each round, one call to the model.** The prompt contains:
   - a **system message** with the persona ("You are …; play the game as this person would, according to their own views and interests") and the case description and instructions in the chosen language;
   - the **current state**: round x of N, the social dashboard (all nine indicators and their change since the last round), the company gains, the blue-/white-collar shares and inflation;
   - a **compact history table** of the earlier rounds (claim, method, promotions and resulting indicators). This avoids sending a growing conversation, keeps prompts short and makes each call reproducible on its own;
   - the **answer format**: a JSON object with
     `claim` (number, 0 to gains + 5), `method` (`percentual` | `absolute` | `lump`), the six promotions (`same` | the two named groups), and a short `reason` (one or two sentences).
3. **Validation:** the answer is checked against the rules. Out-of-range values are clamped or re-asked at most twice. Every correction is counted and exported (`n_retries`, `invalid_flag`).
4. **The choices are submitted** to the real game engine, and the next round follows.
5. **The questionnaire:** after the last round, the model answers the evaluation questions, in role: conviction (1–5), satisfaction (1–5), approach, and the 8 × 2 "targeted in this simulation / important in general" items. The "about you" fields are filled from the profile, not by the model.
6. **Manipulation check:** one final question, "In two sentences, who are you and what mattered most to you?", stored as text. It verifies that the persona was actually adopted.

**Controls:** each profile × seed is also played by a **no-persona baseline** ("You are a workers' representative"). This makes it possible to say whether personas shift play away from the model's default, and in which direction.

## 4. The profiles

`offline/profiles.xlsx`, one row per profile:

| column | example | used for |
|---|---|---|
| `profile_id` | P07 | key |
| `gender` | female / male | analysis + description |
| `age` | 26 / 52 | analysis + description |
| `origin` | native / foreign-born | analysis + description |
| `union` | member / delegate / not unionized | analysis + description |
| `jobstatus` | blue-collar / white-collar / manager | analysis + description |
| `paylevel` | below / average / above | analysis + description |
| `country` | RO | language, currency, description |
| `twin_of` | P06 | counterfactual pair (optional) |
| `description` | *generated or your own text* | prompt |

**Recommended design for 40 profiles:**
- A balanced (fractional factorial) design over the main attributes: 2 genders × 2 origins × 2 union statuses × 5 combinations of age and job, giving 40. Each attribute is then uncorrelated with the others, and plain regressions identify each effect.
- Descriptions **generated from one template**, for example: "You are a {age}-year-old {gender} {jobstatus} worker, born {origin}, {union}, earning {paylevel} the national average." Only the attributes change. Optionally, you add a free-text column with your own richer narrative and run it as a second condition. Comparing the two shows whether rich narratives add extra, unintended signal.
- **Counterfactual twins:** for gender (and optionally origin), every profile has a twin that differs *only* in that attribute. This gives the cleanest test of gender bias: a within-pair difference.

## 5. Experiment size and run time

| factor | suggested start |
|---|---|
| profiles | 40 + 1 no-persona baseline |
| scenario seeds (repetitions) | 10 |
| models | 2–3 (for example one ~8B and one larger model) |
| languages | English first; then 1–2 others (for example French, Romanian) |
| rounds per game | 5 |
| temperature | 0.7, the same for all; the call seed recorded |

This makes 41 × 10 = 410 games per model and language, with 5 + 2 = 7 model calls per game, so about 2,900 calls. A local ~8B model on a recent Mac answers in roughly 3–10 seconds, so a run takes about 3–8 hours per model and language. Larger models take proportionally longer. Runs can be resumed, and the script skips finished games.

With 400 games, a binary per-round outcome such as "promote women: yes/no" gives 2,000 decisions per model. That is enough to detect differences of about 6 to 8 percentage points between the two gender groups. Because decisions are clustered within 40 profiles, the real threshold is somewhat higher. The pilot (step 6) will show the actual variation, so the number of seeds can be adjusted before the full run.

## 6. Local model setup

- **Runtime:** [Ollama](https://ollama.com) (recommended: simplest on a Mac). The runner talks to the **OpenAI-compatible API** (`http://localhost:11434/v1`), so LM Studio, llama.cpp-server or vLLM also work without code changes.
- **Structured output:** request JSON matching a schema (Ollama `format` / `response_format`). Small models still sometimes produce invalid JSON, which is why validation and retries are counted (section 3).
- **Models:** any open-weight model you choose; the runner records the exact model name and version tag. Pick at least two families, because bias patterns often differ more between families than between sizes. A model with 30B+ parameters needs about 32–64 GB of memory.

## 7. Files and code

```
offline/
  profiles.xlsx          the personas (editable, section 4)
  experiment.xlsx        settings: models, seeds, languages, rounds, temperature
  run_experiment.py      plays all games, resumable
  llm.py                 small client for the local OpenAI-compatible API (standard library only)
  prompts.py             builds the prompts from translations/*.xlsx and the game state
  export.py              writes the CSV files (and optionally .dta)
  analysis.do            Stata: import, labels, standard analyses
  runs/<run_id>/         raw log (JSONL of every prompt and response), game databases, CSV output
```

Changes to the existing app are **none, or minimal**: the runner uses the same routes as a human player. The only additions are an optional `seed` field on `/instructions` (so it does not depend on Python's global random state) and a `player_type` column (`human` / `llm`) in `logtable`. This keeps the website and the experiment on one codebase.

## 8. Exported data (CSV, Stata-ready)

All variable names are lowercase, at most 32 characters, with numeric 0/1 dummies plus the original codes. Files can be joined on `game_id` and `profile_id`.

| file | one row per | main variables |
|---|---|---|
| `profiles.csv` | profile | attributes, `twin_of`, description |
| `games.csv` | game | ids, model, language, seed, temperature; final indicators and their change since the start (gpg, apg, epg, wnq, wd, up, nominal and real wage, employment); survey answers (`svy_*`, same names as the website); `n_retries`, `invalid_flag`; manipulation-check text |
| `rounds.csv` | game × round | dashboard before the decision; gains, shares, inflation; `claim`, `claim_minus_gains`, `method`; the six promotion choices as codes and dummies (`prom_women`, `prom_men`, `prom_young`, …); `reason` text |
| `calls.jsonl` | model call | full prompt, raw answer, latency, tokens (audit only, not for Stata) |

Optional: `export.py` also writes `.dta` files with value labels, so the `encode`/label step in Stata can be skipped.

## 9. Analysis in Stata (`analysis.do`)

**A. Do personas shape choices?** (round level)
```stata
logit prom_women i.female i.foreign i.union_member i.bluecollar c.age i.round ///
      i.seed i.model i.language, vce(cluster profile_id)
margins, dydx(female)
```
Apply the same model to every promotion choice, `method` (`mlogit`), and `claim_minus_gains` (`reg`).

**B. Counterfactual twins** (cleanest gender test): the share of rounds promoting women, compared within twin pairs.
```stata
xtset pair_id
xtreg share_prom_women i.female i.seed, fe vce(cluster pair_id)
```

**C. Outcomes** (game level): change in gender pay gap, employment and purchasing power, by persona.

**D. Stated versus revealed priorities:** for example, `svy_case_gender_pay_gap` (stated) against `share_prom_women` (revealed). Use `tab` / `kap` and logit, by persona.

**E. Deviation from the baseline:** each persona's choices minus the no-persona baseline on the same seed. This answers whether the model only reacts to the persona or also has a default lean of its own.

**F. Model and language effects:** interactions `i.female##i.model` and `i.female##i.language`.

**G. Human benchmark:** add the website data (`fdb.db` → CSV) with `player_type = human`. Real respondents' own gender, union status and so on are in the same `resp_*` variables.

Many hypotheses are tested at once, so report adjusted p-values or pre-register the main hypotheses (A for gender, union and origin; B; D).

## 10. Threats to validity and how the design handles them

| risk | handling |
|---|---|
| Wording of the persona changes more than one attribute | Template descriptions; free text only as a separate condition |
| Order of options in the prompt (position bias) | Randomise the order of the promotion options per call, record the order, add it as a control |
| The model ignores the persona | Manipulation check; comparison with the no-persona baseline |
| The model refuses or moralises ("I cannot role-play gender…") | Detect refusals and flag them; report refusal rates per persona, which is itself a bias finding |
| Run-to-run randomness | 10 seeds × fixed temperature; the call seed is recorded; standard errors clustered by profile |
| Invalid or out-of-range answers | Validation, at most 2 retries, counts exported |
| Model updates change results | Exact model tag and file hash stored with every game |

## 11. Work steps

| # | Step | Size |
|---|---|---|
| 1 | Add the `seed` field and `player_type` column to the app; regression check that the website maths is unchanged | S |
| 2 | `llm.py` + JSON schema + validation, tested against one local model | S |
| 3 | `prompts.py` from the translation files; review prompts in English with you | M |
| 4 | `run_experiment.py`: one game end to end, then resumable batch runs | M |
| 5 | `profiles.xlsx` generator (factorial design + twins + template descriptions) | S |
| 6 | Pilot: 5 profiles × 2 seeds × 1 model; check answer validity, persona adoption, timing | S |
| 7 | `export.py` (CSV, optional .dta) + `analysis.do` | M |
| 8 | Full run(s), then the analysis | run time |

## 12. Decisions I need from you

| # | Question | Recommendation |
|---|---|---|
| E1 | Local runtime | Ollama |
| E2 | Which models (and is your Mac's memory enough for a ~30–70B model)? | Two families, one small and one large |
| E3 | Profiles: factorial template design, your own 40 descriptions, or both as two conditions? | Both, with the template version as the main analysis |
| E4 | Languages in the first run | English only for the pilot; then add one or two |
| E5 | Should the model also answer the "about you" fields itself, as a check that it stays in role? | No; fill them from the profile and use the manipulation check instead |

## 13. Which model to use for building this

The code is moderate in size and mostly plumbing, so **Sonnet 5.5 at high effort** is sufficient for steps 1, 2, 4, 5 and 7. For **prompt design (step 3), the profile design and the Stata analysis plan (steps 5 and 9)**, use **Opus 5.5 at medium effort**: these choices decide whether the bias estimates are valid.

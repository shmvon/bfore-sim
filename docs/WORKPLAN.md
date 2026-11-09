# Bargaining Simulation Tool: workplan

*Version 1, 8 November 2026. Covers the four requested tasks: external data volume, social dashboard layout, translation, and language-independent form handling.*

## Status (8 November 2026)

Approved with the recommended answers: D1 Excel, D2 cookie + `prefs.db` plus country/language in the research data, D3 the model calculates in EUR and only displays local currency, D4 EU-27 + NO + UK + Non-EU, D5 bugs fixed.

| Phase | State |
|---|---|
| 0 Safety net | Done. Git repository created; seeded reference run recorded. The final code gives identical numbers on every logtable row and workforce wage column. |
| 1 Volume | Code done (`config.py`, `DATA_DIR`, `.dockerignore`, startup log line). **Still to do on the server:** check the CaaS mount at `/app/data`, back up the live `fdb.db`, and run the redeploy test. |
| 2 Button codes | Done |
| 3 Templates + dashboard | Done. `base.html`, `_dashboard.html`, single 3×6 table with fixed proportions. Checked at desktop and narrow widths. |
| 4 i18n core | Done. `i18n.py`, `i18n_tools.py`, `translations/en.xlsx`, `translations/countries.xlsx`. |
| 5 Switch + persistence | Done. Includes the progress-preserving GET, the one-time `/thanks` transfer, and automatic `fdb.db` column migration. |
| 6 Batch 1 | Done. fr, de, nl, it, sv, es, ro, all marked `draft`. |
| 7 Test | Done locally. Every page in every language renders with no missing texts. Survey, maths fix and migration verified. Not yet deployed. |
| 8 Batch 2 | Done. pl, da, fi, lt, lv, et, pt, hr, marked `draft`. |
| 9 Batch 3 | Done. bg, cs, el, hu, sk, sl, mt, nb (Norwegian Bokmål), is (Icelandic), marked `draft`. Iceland (is) and Switzerland (fr, de) were added as countries. Every country in the list now has its main national language(s). **Partner review is still needed for all 23 translated languages**, batches 2 and 3 most of all. |

Also fixed, from `IMPROVEMENTS.md`: 1.1 (survey answers), 1.2 (blue-collar promotion maths), 1.3 (duplicate submissions), 1.5 (`fdb.db` schema), the "no game" crash on `/page/n` and `/results`, and tooltips that now open on tap or keyboard focus. Item 2.2 is partly done: the download code now comes from the `DOWNLOAD_CODE` environment variable (locally from a `.env` file, see `.env.example`), and downloading is switched off when it is not set.

**Translator workflow:** send `translations/xx.xlsx` to the partner. They edit the *Translation* column and set *Status* to `reviewed`. Put the returned file back in `translations/` and run `python3 i18n_tools.py check`. The site picks up changed files within seconds, without a restart. To add a new text: add it to `en.xlsx`, then run `python3 i18n_tools.py sync`.

---

## Part A: The game and how it is built

### A.1 Concept

The Bargaining Simulation Tool (BFORE, "Bargaining For Equality", EU-funded, HIVA KU Leuven) is a serious game for training trade unionists, workers' representatives, policymakers and students. The player is the **workers' representative at "Li-Ion"**, a fictitious battery maker with 194 employees: 144 permanent staff, half blue-collar and half white-collar, plus 50 temporary agency workers. The workforce is balanced by gender, age, origin and union membership.

The game runs over 5 to 10 **bargaining rounds** (one round is one year). In each round the player:

1. **Reads the social dashboard.** It has nine indicators: nominal wage + bonus, purchasing power (deflated), net hirings/layoffs, the gender, age and ethnic pay gaps, residual wage inequality (high vs low pay within the same job), pay differentials (white- vs blue-collar), and the union premium. Arrows show the change since the previous round.
2. **Makes a wage claim** after seeing the company's gains (1–8%), split into blue- and white-collar contributions, and inflation (1–3%). If the claim exceeds the gains, one temporary worker is laid off per 0.5 percentage point. A claim below the gains leads to hirings.
3. **Chooses a method:** a percentage increase, a flat (absolute) increase per worker, or a one-off bonus. A bonus doesn't compound and isn't offered in the last round.
4. **Sets promotions:** for each of six dimensions (gender, age, origin, pay level, job category, union membership), the player can treat groups the same or favour one group. The favoured group gets ×1.2 of the increase and the others ×0.8. Age and pay level have three groups: there only the opposite extreme gets ×0.8 and the middle group ×1, so every promotion keeps the total increase equal to the claim.

There is no preset target. Success depends on the player's own idea of fairness. The game ends with the final dashboard (compared with the initial state) and a short evaluation and background questionnaire, which feeds the research database.

### A.2 Implementation

| Part | What it does |
|---|---|
| `app.py` | Creates the Flask app, registers the blueprint, starts the cleanup thread, runs on `::` with `debug=True`. |
| `website.py` | All routes and the model (1,400 lines). |
| `cleanup.py` | Every 10 minutes, deletes `data/*-user.db` files older than 3 hours. |
| `templates/*.html` | 7 standalone pages (no shared base template). All text is hard-coded English. |
| `static/css/styles.css` | One small stylesheet. |
| `Dockerfile` | `ubuntu:latest` with python3, `COPY . /app`, `CMD python3 app.py`. |

**Page flow:** `/` (intro) → `/instructions` (settings: rounds and average wage) → POST creates `data/<uuid>-user.db` → `/page/1 … /page/N` (rounds) → `/page/N+1` redirects to `/results` (dashboard + survey) → POST → `/thanks` (copies `logtable` + `evaluation` into `data/fdb.db`) → `/download` (password-protected download of `fdb.db`). `/case` (case description) is not linked from the flow.

**Data model, one SQLite file per player:**
- `workforce`: 1,440 synthetic workers, made of the 144 combinations of 2 genders × 3 ages × 2 origins × 3 pay levels × 2 union statuses × 2 job categories, each repeated 10 times with its own random residual ε. One `logwageN` and one `bonusN` column are added per round. Agency workers are not modelled as individuals; they appear only as the employment counter.
- `logtable`: one row per round plus two result rows. It holds the dashboard values, random draws (gains, inflation, shares), choices and employment state.
- `evaluation`: one row with the survey answers.

**Maths (unchanged by this workplan):**
- Starting wage: `logwage0 = ln(0.4·W + ε) + gpg·[man] + apg·[old] + apg_mid·[mid] + epg·[native] + pay_hi·[high] + pay_mid·[mid] + up·[member] + wd·[white-collar]`, where ε ~ N(600, 200) and the gap parameters are drawn at random.
- Gaps: `100 · (ln(e^m₁ + e^b₁) − ln(e^m₂ + e^b₂))`, where m and b are group means of log wage and log bonus.
- Increases: percentage `w·(1 + r·Π mᵢ)`, absolute `w + a·Π mᵢ` with `a = r·mean_wage`, or bonus `2.5·a·Π mᵢ` per month. Here mᵢ ∈ {1, 1.2, 0.8} is the promotion multiplier per dimension. The bonus is not available in the last round, because it would not count in the final results.
- Employment: `shift = ±ceil(|gains − claim| / 0.5)`. Deflator: `×(1 + inflation/100)` per round.

---

## Part B: The tasks

### Task 1: Is the data on an external volume?

**Finding: this can't be confirmed from the code, and two signs suggest it isn't working.**

- Nothing in the repository sets up a volume. The Dockerfile has no `VOLUME`, and there is no compose file or CaaS config. All paths are relative (`data/fdb.db`, `data/<uuid>-user.db`), so they resolve to **`/app/data`** inside the container. A volume only exists if it was configured in the CaaS console with mount path `/app/data`.
- **The live site currently reports "0 entries"** (`https://sim.bfore.be/download`, checked 8 Nov 2026). That means one of three things: nobody has finished a game since the last deploy, the data is lost on each redeploy (no volume, or a volume mounted at the wrong path), or saving fails silently (`thanks()` catches every exception and only prints it).
- `COPY . /app` also copies the local `data/saved/*.db` files into the image, including files named after people. If a volume is mounted at `/app/data`, it hides them. If not, they ship with the image.

**Actions**
1. In the CaaS console, check that a persistent volume is mounted at exactly `/app/data`.
2. Make the location explicit: `DATA_DIR = os.environ.get("DATA_DIR", "data")` in one place, with every path built from it. Log the resolved absolute path and whether it is writable at startup.
3. Add a `.dockerignore` (`data/`, `_junk/`, `simenv/`, `__pycache__/`, `*.db`, `.DS_Store`).
4. Test end to end: play a 1-round test game and submit, check that `/download` shows 1, redeploy, and check that it still shows 1.
5. Download and back up the current `fdb.db` before any deploy.

### Task 2: Social dashboard alignment

**Cause.** The dashboard (`round.html` and, identically, `results.html`) is an outer table whose three cells each hold a separate nested 3-row table. Each nested table sizes its rows to its own content, and `style="height: 33%"` has no effect without a fixed table height. When a label wraps in one column and not in another, the bottom edges drift apart. (The outer table also has no `<tr>`.)

**Fix.** Use one table with 3 rows × 6 columns (label | value, three times):
- `table-layout: fixed` with a `<colgroup>`, for example label 21% and value 12.33% per pair, so the proportions hold at every width.
- Every row spans all columns, so rows line up by construction.
- Long words wrap with `overflow-wrap: anywhere; hyphens: auto;` and `<html lang="…">`. This matters for German and Finnish compound words, such as *Geschlechtsspezifisches Lohngefälle*.
- Put the dashboard in one partial `templates/_dashboard.html` used by both pages, with a flag for the "arrows" variant (rounds) and the "delta" variant (results).
- Apply the same treatment to the two-column promotions table.
- Test at 375 px, 768 px and desktop widths, in English and German.

### Task 3: Translation

#### 3.1 Principles
- **Plain Flask, no new framework.** A ~100-line `i18n.py` module provides a `t(key, **values)` function, registered as a Jinja global. Only one new dependency is needed: `openpyxl`, to read Excel.
- **Non-coders edit the texts.** There is one Excel file per language, which partners can send back by email.
- **English is the fallback.** An empty cell shows English, so a partial translation never breaks a page.

#### 3.2 Translation files (`translations/`)

`translations/fr.xlsx`, sheet **Texts**:

| key | English | Translation | Notes for translator | Status |
|---|---|---|---|---|
| `round.title` | Bargaining Round {round} | Cycle de négociation {round} | {round} = round number | draft |
| `round.claim.context` | Over the last year, the company's gains were {gains}%. In the blue-collar departments, this was {bc}%, and in the white-collar departments {wc}%. Inflation has been {inflation}%. | … | Gains = gross value added per employee | draft |
| `dash.gpg.label` | Gender pay gap | Écart salarial entre hommes et femmes | Standard EU term (Eurostat) | reviewed |

The workbook also has:
- sheet **Glossary**: the fixed jargon (pay gap, union premium, pay differentials, purchasing power, agency worker, blue-/white-collar…) with the agreed term per language, so it stays consistent across pages.
- sheet **Format**: decimal separator, thousands separator, currency position (`{amount} {symbol}` or `{symbol} {amount}`).

Rules for editors, printed at the top of each sheet:
- Leave `{curly}` words exactly as they are. You may move them within the sentence.
- `**word**` makes a word bold. No HTML.
- Don't change the `key` column.

Why Excel and not CSV: European Excel opens CSV files with `;` as the separator and often a non-UTF-8 encoding, which breaks accented characters and commas inside sentences. `.xlsx` avoids both problems. If you prefer plain text, the same structure works as `fr.txt` with `key = text` lines. This is decision D1.

**Tool script** `i18n_tools.py` (command line, used by the maintainer):
- `extract`: scans the templates for `t('…')` keys and updates `en.xlsx`.
- `sync`: adds new or removed keys to every language file without touching existing translations.
- `check`: reports missing translations and changed or missing `{placeholders}`, and flags translations that are much longer than the English, which can matter for layout.

#### 3.3 Dynamic game data in text
- Every sentence with game data uses **named placeholders**, so translators can reorder: `{gains}`, `{claim}`, `{aclaim}`, `{bonus}`, `{round}`, `{rounds}`.
- Numbers are formatted per language before they are inserted: `3,5 %` in French, `3.5%` in English, `2 000 €` in French, `€ 2,000` in Irish English. The rounding stays as it is now.
- Some current sentences glue fragments together, for example `Bonus (€ {{ bonus }} this year)`. Each of these becomes one whole sentence with placeholders. Slight rephrasing is allowed here.
- Plurals ("1 layoff" / "3 layoffs"): avoided by phrasing ("Hirings / layoffs: +3"). Where needed, use two keys (`…one`, `…many`).

#### 3.4 Country and language switch
- **Header on every page** (a new `base.html` that all pages extend): `[Country ▾]` and then `[Language ▾]`. The language list only appears after a country is chosen. It shows that country's official languages that are available, plus English. For **Non-EU**, every language is offered.
- Plain form: `POST /locale` stores the choice and redirects back to the same page. A one-line `onchange="this.form.submit()"` handles it, and a `<noscript>` button covers browsers without JavaScript.
- **A `countries.xlsx` table** defines per country: code, languages, currency symbol, default and maximum wage for the slider. For example: BE → nl, fr, de, en, €, 2000/6000. SE → sv, en, kr. FI → fi, sv, en. Country names are translated in the language files (`country.BE`).
- The selected country pre-fills "Country" in the final questionnaire.

| Language | Batch | Countries where it is offered |
|---|---|---|
| English | 1 | all (always), IE, MT, CY, Non-EU |
| French | 1 | FR, BE, LU |
| German | 1 | DE, AT, BE, LU |
| Dutch | 1 | NL, BE |
| Italian | 1 | IT |
| Swedish | 1 | SE, FI |
| Spanish | 1 | ES |
| Romanian | 1 | RO |
| Polish, Danish, Finnish, Lithuanian, Latvian, Estonian, Portuguese, Croatian | 2 | PL, DK, FI, LT, LV, EE, PT, HR |

BG, CZ, GR, HU, SK, SI, CY and MT fall back to English until a language is added. Adding a language later means adding one Excel file and one column in `countries.xlsx`, with no code change.

#### 3.5 Saving the last-used setting in the database
- A long-lived cookie (1 year) holds only a random `visitor_id`. A persistent table `visitor_prefs(visitor_id, country, language, updated_at)` in `DATA_DIR/prefs.db` stores the last choice and is read back on the next visit. This is a functional cookie requested by the user, and the privacy text will mention it.
- **`logtable` and `evaluation` get `country` and `language` columns**, so research data shows which version was played.
- **Migration needed:** `fdb.db` was created as a copy of the first player's database, and rows are copied in by column name. New columns must be added to `fdb.db` at startup (`ALTER TABLE … ADD COLUMN` if missing). Without this, every submission fails silently.

#### 3.6 Switching language mid-game must not lose progress
- Today, every GET of `/page/n` resets that round's three form states (`website.py:779-784`, where both branches set everything to `False`). A language switch, which redirects with a GET, would therefore throw the player back to "submit claim". The fix is to initialise the states only when they are absent.
- `/thanks` copies the data on every GET, so a reload or a language switch on that page duplicates the submission. The fix is a "transferred" flag in the user database.

#### 3.7 Generating the translations
1. Extract all strings into `en.xlsx`: about 350 fragments, about 1,500 words, including the survey.
2. Draft the batch 1 languages (fr, de, nl, it, sv, es, ro) with Claude, with the Glossary filled first using established EU and Eurofound terminology. Mark every row `draft`.
3. Send each file to a local partner (trade union or research contact) for review. They set `reviewed` and return the file.
4. Batch 2 (pl, da, fi, lt, lv, et, pt, hr) is the same mechanical step and is straightforward once batch 1 works. Do it right after batch 1 if you approve.
5. Other assets: the EU "Funded by the EU" logo exists officially in every EU language, so swap in the image per language. The YouTube video stays English, with subtitles per language as an option.

### Task 4: English labels sent to the backend

**Found:** `website.py:793`, `:807` and `:821` decide which form was submitted by comparing the button's visible text:

```python
if pressed_button == 'submit claim':      # value="submit claim" in round.html
elif pressed_button == 'submit method':
elif pressed_button == 'submit promotions':
```

As soon as the button text is translated, none of the three branches matches, so no claim, method or promotion would ever be saved and the round could not be finished.

**Fix:** separate the code from the label:

```html
<button type="submit" name="submit_button" value="claim">{{ t('round.claim.submit') }}</button>
```

```python
if pressed_button == 'claim': …
```

Other form values were checked and are already language-independent: `mchoice` (`lump`/`percentual`/`absolute`), promotions (`choice1-3`), survey options (codes such as `male`, `blue-collar`), and round counts. They stay as stable codes, so research data from every language stays comparable.

---

## Part C: Order of work

| # | Phase | Contents | Size |
|---|---|---|---|
| 0 | Safety net | `git init` (the folder is named "-git" but is not a repository). Back up the live `fdb.db`. Record a **reference run with a fixed random seed** so the maths can be shown unchanged after refactoring. | S |
| 1 | Volume (Task 1) | `DATA_DIR`, `.dockerignore`, CaaS mount check, end-to-end test | S |
| 2 | Button codes (Task 4) | 3 buttons, 3 comparisons | XS |
| 3 | Templates + dashboard (Task 2) | `base.html`, `_dashboard.html`, CSS fix | M |
| 4 | i18n core | `i18n.py`, `t()` in all templates, number formatting, `en.xlsx`, `i18n_tools.py` | M–L |
| 5 | Switch + persistence | header switch, `countries.xlsx`, `visitor_prefs`, new columns + `fdb` migration, progress-preserving GET, idempotent `/thanks` | M |
| 6 | Batch 1 translations | glossary, 7 drafts, `check` passes | M |
| 7 | Test + deploy | seeded run gives identical numbers to phase 0. Play through in each language at mobile and desktop width. Redeploy and check persistence. | M |
| 8 | Batch 2 + partner review | 8 drafts. Partner corrections are only file swaps. | M |

## Part D: Decisions I need from you

| # | Question | Recommendation |
|---|---|---|
| D1 | Translator file format: Excel (`.xlsx`) or plain text (`key = text`)? | Excel |
| D2 | "Saved in the database": cookie visitor id + `prefs.db` table, plus country/language in research data? | Yes, both |
| D3 | Currency per country (SEK, RON, PLN, DKK…)? This interacts with the maths. The random wage component ε ~ N(600, 200) is a fixed amount, so with a wage level in SEK or HUF it becomes negligible and the inequality indicators behave differently. Options: (a) the model works in EUR internally and only displays the local currency, or (b) scale ε with the average wage, which is a change to the maths. | (a), which keeps the maths |
| D4 | Country list: EU-27 + "Non-EU" only, or also Norway, UK, Switzerland and Iceland separately? The survey already lists NO and UK. | EU-27 + NO + UK + Non-EU |
| D5 | Fix the maths bug and the survey data-loss bug found during the review (see `IMPROVEMENTS.md`, items 1–2) in the same release? | Yes |

## Part E: Which model to use

| Work | Model | Effort |
|---|---|---|
| Phases 0–5 (code: refactor, CSS, i18n plumbing, persistence) | Sonnet 5.5 | high |
| Phases 6 and 8 (translating labour-relations jargon into 15 languages, glossary consistency) | Opus 5.5 | high |
| Decisions on the maths (D3, D5) and final review | Opus 5.5 | medium |

If you'd rather run it all in one session: **Opus 5.5, medium effort**. The code is small enough that higher effort mainly adds cost. The quality gains of Opus matter most for the translations, which still need review by native-speaking practitioners.

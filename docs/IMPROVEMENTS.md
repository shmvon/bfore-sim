# Bargaining Simulation Tool: suggested improvements

*Found while reviewing the code on 8 November 2026. None of these were part of the request. They are ordered by importance. Items marked **(maths)** would change game outcomes and need your decision.*

---

## 1. Data integrity: fix first

### 1.1 Survey answers are mostly lost
`website.py:1240`
```python
form_values = {field: 1 if request.form.get(field, 'off') == 'on' else 0 for field in field_names}
```
This treats **every** field as a checkbox. The two 1–5 sliders, the "approach" choice, gender, age, country, origin, union status and job status are therefore **all stored as 0**. Only the checkboxes and `resp_paylevel`, which is patched on the next line, survive. Every survey response collected so far is missing these answers.
**Fix:** read checkboxes as 0/1 and store the other fields with their real value (age as a number, the rest as text codes).

### 1.2 **(maths)** Promoting blue-collar workers is wrong for percentage and absolute increases
`website.py:430` and `:468`, compared with the correct version at `:395`:
```sql
+ ({pjobcat} = 2)*(jobcat=1)*{less}     -- should be (jobcat!=1)
```
With "Promote blue-collar workers" under a percentage or absolute increase, blue-collar workers get ×(1.2 + 0.8) = **×2.0** and white-collar workers get **×0**. The bonus method is coded correctly. This looks like a copy-paste slip, and fixing it restores the intended maths.

### 1.3 Reloading `/thanks` stores the submission twice
`thanks()` copies `logtable` and `evaluation` into `fdb.db` on every visit. A reload, the back button, or (once added) a language switch duplicates the entry. **Fix:** mark the user database as transferred and skip it after the first time.

### 1.4 Saving errors are invisible
`thanks()` wraps everything in `except Exception: print(...)`. The player always sees "Thank you", even when nothing was saved. Combined with 1.5, this would hide every failure. **Fix:** log to a file in `DATA_DIR` and keep a simple counter on `/download` ("last successful save: …").

### 1.5 `fdb.db` schema is inherited from the first player
`fdb.db` is created by copying the first submitter's database, and rows are inserted by column name. Any future column (country, language, seed) makes every insert fail, silently because of 1.4. **Fix:** create `fdb.db` from an explicit schema and add missing columns at startup.

### 1.6 The live site shows "0 entries"
See Task 1 in the workplan. Either no one has finished a game since the last deploy, or the data is not persisting. Back up the live `fdb.db` before the next deploy.

## 2. Security and privacy

| # | Issue | Suggestion |
|---|---|---|
| 2.1 | `app.run(debug=True)` in production. The Werkzeug debugger and reloader are meant for local use only. | `debug=False`. Serve with `gunicorn` (1 worker, several threads, which suits SQLite and the cleanup thread). |
| 2.2 | The download password was in the source code (now the `DOWNLOAD_CODE` environment variable), and the attempt limit is stored in the session cookie, so clearing cookies resets it. | Read a hashed password from an environment variable, and rate-limit by IP in a small table. |
| 2.3 | The `/download` page publicly shows the number of entries. | Show it only after login. |
| 2.4 | `secret_key = secrets.token_hex(16)` is regenerated at every restart, so every running game breaks at each redeploy. | Read `SECRET_KEY` from an environment variable. |
| 2.5 | The Docker image contains `data/saved/*.db` (files named after people), `_junk/` and the local `simenv/`. | Add a `.dockerignore`. Remove the personal files from the image (GDPR). |
| 2.6 | `FROM ubuntu:latest`, and Flask is unpinned. | `FROM python:3.12-slim` and pinned versions in `requirements.txt` for reproducible builds. |
| 2.7 | The privacy text refers to "our Privacy Policy", but there is no link. | Add a privacy page, also translated, covering the language cookie. |

## 3. Robustness

- **Visiting `/page/3` or `/results` without a game crashes** (`sqlite3.connect(None)`). This happens with an old bookmark, after a restart, or after cleanup. Redirect to the start page with a short message instead.
- **An invalid wage on `/instructions` crashes**, because `averagewage_float` is never assigned. Validate the input and show the form again.
- **Games idle for more than 3 hours** are deleted mid-play (cleanup goes by file age). This is acceptable, but the player should see a friendly "session expired" page instead of an error.
- `if page - 1 in session['button_states']` compares an integer with string keys, so old states are never removed. This is harmless but should be tidied.
- `get_fdb()` points to `data/fdb` (no `.db`) and is unused. Remove it, together with the commented-out code (about 40% of `app.py` and parts of `website.py`).
- A little reorganisation without changing logic would make maintenance easier: `model.py` for wages, gaps and increases, `routes.py`, and `db.py`. The three nearly identical 40-line SQL blocks in `wageincrease()` could be generated by one function, which would also have prevented bug 1.2.

## 4. Front end

- `results.html` loads the Tooltipster jQuery plugin **without jQuery**, so it throws a JavaScript error and the slider tooltips never work. It also has a duplicate `<!DOCTYPE>`. Remove the plugin, since the value is already shown next to each slider.
- `round.html` and `results.html` contain an "info-sign" script that runs before the page exists and targets elements that don't exist. Remove it.
- Tooltips only open on mouse hover, so **on phones and tablets the definitions of the indicators can't be read**. Make them open on tap or focus (CSS `:focus-within` with `tabindex="0"`), which also helps keyboard users.
- `thanks.html` has no `<body>`. Every page repeats its own `<head>`. The `base.html` from the workplan solves this.
- Many inline `style=` attributes should move into the stylesheet. Also add a `<meta name="viewport">` tag; without it, phones render the desktop layout zoomed out.
- `/case` (case description) isn't reachable from the flow. Either link it between the intro and the instructions, or merge it into the instructions page.

## 5. Game design and maths: suggestions only

- **(maths) Promotions are not budget-neutral for age and pay level.** Gender, origin, job category and union membership have two groups, so ×1.2 / ×0.8 averages to 1. Age and pay level have three groups, so promoting one gives an average of (1.2 + 0.8 + 0.8) / 3 = **0.933**, and the total increase falls about 7% below the claim. Since the dimensions multiply, this compounds when both are used. You could normalise the multipliers so they average 1 within the workforce, or explain this to players as a deliberate cost.
- **(maths) The random wage component is a fixed amount** (ε ~ N(600, 200), as the comment in the code already notes). Wage inequality therefore depends on the chosen wage level: it is large at €1,000 and small at €6,000. This becomes more visible with national wage levels and currencies (decision D3 in the workplan). Scaling ε with the average wage would make countries comparable.
- **Store the random seed** of each game in `logtable`. Any game can then be replayed exactly for teaching, debugging, or showing that a code change didn't alter the maths.
- **Results page:** add a small per-round chart of the main indicators. The data already exists in `logtable`.
- **Workshop mode:** a facilitator creates a session code, participants join with it, and the facilitator sees an anonymous comparison of strategies and outcomes. This fits the training use and needs one extra table.
- **Data export:** besides the raw `fdb.db`, offer an Excel/CSV export with readable column names and labels, which is easier for researchers.
- **National wage defaults** in `countries.xlsx`, for example the median monthly gross wage from Eurostat, so the slider starts at a realistic value per country.
- **EU logo per language:** the official "Funded by the European Union" logo exists in every EU language.
- **Subtitles** for the YouTube instruction video in the batch 1 languages.

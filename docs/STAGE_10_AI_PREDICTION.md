# Stage 10 — AI Weather-Aware Turf Prediction (for WAICY, due Nov 29, 2026)

> Put this file in `D:\Lavi\SpectralTurf\docs\`. Claude Code: read this file and CLAUDE.md
> first. Work ONE step at a time unless Lavi says otherwise. After each step: run tests,
> commit, tell Lavi what changed, the exact command to test it, and what success looks like.
> Keep code beginner-readable. Never touch `backend/.env` except to read keys through config.

## The idea
A person looking at a dry field can't tell whether it's dry because of the weather (normal)
or because something is broken (fix it). They also can't see stress before it shows.
This stage trains a machine-learning model on years of real satellite + weather history to
learn **how green each field should be, given recent weather**. Then the app can say:

1. **"Weather doesn't explain this."** Actual NDVI is much lower than the model expected →
   likely an on-the-ground problem (irrigation, traffic) → inspect first.
2. **"At risk next week."** Using the 7-day weather forecast, predict which fields are likely
   to decline before damage is visible.

This is AI because the model learns the patterns from data; we do not hand-write them.

## ADD-ON ONLY — do not replace anything
This stage is an **add-on**. Everything SpectralTurf already does must keep working exactly
the same: place search, drawing, Exclude tool, NDVI/NDMI analysis, the 0.20 / 5% inspection
flag, map layers, data-quality panel, and all existing tests.
- Put all new code in **new files** (`ml/`, `backend/predict.py`, a new React component).
- Only change existing files to **add** things: register the new endpoint in `main.py`, and
  add the new "AI Weather Check" panel **below** the current results in the results panel.
  Do not rename, rewrite, move, or delete any existing function, endpoint, component, or test.
- The existing analysis must still run and show results even if the AI part fails or is
  off-season; the AI panel just shows its own message in that case.
- The optional accounts system (login, sessions, saved history, `spectralturf.db`, and
  `test_accounts.py`) must keep working unchanged. New features may only READ saved fields.
- Before each step: make a git commit. After each step: run the existing tests
  (`python test_indices.py`, `python test_accounts.py`, and any others) **plus** the new tests, and confirm the original
  app still works before committing.
- If a step seems to require changing existing behavior, stop and ask Lavi first.

## Non-negotiable rules for this stage (add to CLAUDE.md)
- Every number shown to users or in slides must come from real data and `evaluate.py` output.
  Never invent accuracy or example results.
- Test the model on a **year it never saw** (time split), and separately on **fields it never
  saw** (group split). Report both honestly, even if results are weak.
- The model's output is a **prioritization signal**, not a diagnosis or watering instruction.
- Growing season only (April–October). Outside it, show "Off-season — grass may be dormant."
- Respect API limits: cache all downloaded data to disk, never re-download what's cached,
  and stop and report if the Copernicus processing quota is getting low.
- Weather data credit: "Weather data by Open-Meteo.com". Field outlines: "© OpenStreetMap contributors".

---

## Step 1 — Collect field outlines
**Files:** `ml/get_fields.py`, `ml/data/fields.geojson`
- Use the Overpass API (OpenStreetMap) to get `leisure=pitch` polygons in the Denver metro area.
- Keep grass fields only (drop `surface=artificial_turf` / `surface=artificial` and similar),
  area ≥ 8,000 m² (2 acres).
- Start with **25 fields**. Save id, name (if any), sport, area, centroid, polygon.
- Be polite to Overpass: one query, cached to disk.
- **Success:** `python ml/get_fields.py` saves ~25 fields; print a summary table.

## Step 2 — Satellite history per field (NDVI time series)
**Files:** `ml/get_ndvi_history.py`, `ml/data/ndvi/<field_id>.csv`
- Use the Sentinel Hub **Statistical API** on CDSE (verify the exact endpoint in the CDSE docs;
  reuse the existing OAuth code in `sentinel.py`). It returns summary stats per date for a
  polygon — much cheaper than downloading images.
- Evalscript: NDVI from B04/B08, mask with SCL (same rejected classes as the app) and dataMask.
- Date range: April–October, 2019–2025. Output per date: mean NDVI, clear-pixel fraction.
- Keep only dates with ≥ 80% clear pixels.
- First test with **1 field**, print processing units used, then run the rest.
- **Success:** one CSV per field with dated NDVI values; print how many usable dates per field.

## Step 3 — Weather history per field
**Files:** `ml/get_weather.py`, `ml/data/weather/<field_id>.csv`
- Open-Meteo Historical Weather API (free, no key): daily `precipitation_sum`,
  `temperature_2m_max`, `et0_fao_evapotranspiration` for each field's centroid, 2019–2025.
- **Success:** one weather CSV per field, no missing days (or missing days reported).

## Step 4 — Build the training dataset
**Files:** `ml/build_dataset.py`, `ml/data/dataset.csv`
- One row per (field, satellite date). **Target:** NDVI on that date.
- **Features** (only information available *before* that date):
  - previous clear NDVI for that field, and days since it
  - rain in last 7 / 14 / 30 days
  - ET0 (water demand) in last 7 / 14 / 30 days
  - water balance = rain − ET0 over 14 and 30 days
  - average max temperature over last 7 / 14 days
  - day of year (season), field area
- Print row count and a few example rows. Explain each feature in comments.
- **Success:** a clean dataset with a few thousand rows.

## Step 5 — Train and evaluate the model (main AI result)
**Files:** `ml/train.py`, `ml/evaluate.py`, `ml/model/ndvi_model.joblib`, `ml/results.md`
- Model: scikit-learn `HistGradientBoostingRegressor` (no new installs needed beyond scikit-learn).
- Splits:
  - **Time split:** train 2019–2023, validate 2024, **test 2025**.
  - **Field split:** hold out ~20% of fields entirely.
- Compare against simple baselines:
  - "Same as last time" (previous NDVI)
  - "Seasonal average" (that field's average NDVI for that time of year)
- Report mean absolute error (MAE) for model vs. baselines on both splits.
- Show feature importance (which weather factors matter most) as a simple chart.
- From validation errors, set the "weather doesn't explain this" cutoff
  (e.g., actual is more than 2× typical error below predicted).
- Save everything to `ml/results.md` with the date.
- **Success:** a results table; honest statement of whether the model beats the baselines.

## Step 6 — Backend endpoint
**Files:** `backend/predict.py`, update `backend/main.py`, `backend/test_predict.py`
- `POST /api/ai/weather-check` with the field polygon (same format as the existing analysis).
- Fetches that field's recent NDVI (Statistical API) and weather (Open-Meteo history +
  7-day forecast), then returns:
  `{expected_ndvi, actual_ndvi, difference, weather_explains: bool, risk_next_week,
    top_factors, last_image_date, note}`
- Off-season → returns an off-season note instead of a result.
- Tests with saved sample data (no network in unit tests).
- **Success:** works from http://localhost:8000/docs for Village Greens.

## Step 7 — Frontend "AI Weather Check" panel
- New section in the results panel:
  - Expected vs. actual greenness (small chart of the last ~60 days with the model's expected line)
  - Clear message: "Weather explains this" or "Weather does NOT explain this — inspect irrigation first"
  - Next-week risk: Low / Medium / High, with the forecast reason (e.g., "hot and dry forecast")
  - Text: "AI estimate based on satellite + weather history. Confirm in person."
- **Success:** run the analysis on a field and see the AI panel fill in.

## Step 8 — "My Fields" ranking (uses existing accounts)
**Files:** new endpoint in `backend/predict.py`, new React component
- The app already has optional accounts with saved analyses (`backend/spectralturf.db`,
  table `saved_analyses`). Do NOT change the account system; only read from it.
- For a logged-in user, take their distinct saved fields (outline + exclusions) and run the
  weather check on each. Return a list ranked by risk: "Check these first this week."
- A user can only ever see their own fields (check the session token, same as saved history).
- Not logged in → panel says "Log in and analyze fields to see your ranked list."
- **Success:** log in, analyze 3 fields, open "My Fields" and see them ranked.

## Step 9 — "What if?" weather simulator (interactive use of the trained model)
**Files:** new endpoint `POST /api/ai/what-if`, new React component
- Sliders: days without rain (0–21), average high temperature, and rain amount.
- Runs the trained Stage 10 model with the user's scenario instead of the real forecast and
  shows the predicted greenness change and risk level for the current field (and for
  "My Fields" if logged in).
- Clear label: "Scenario estimate from the AI model, not a forecast."
- Only allow slider values inside the range the model saw in training; show a warning outside it.
- **Success:** move the sliders and watch the predicted risk update.

## Step 10 — "Ask SpectralTurf" assistant (AI agent with tools)
**Files:** `backend/assistant.py`, new endpoint `POST /api/ai/ask`, new React chat panel
- Uses an LLM API (Lavi chooses: Claude API or Gemini). The API key goes ONLY in
  `backend/.env`, read on the backend; never in the frontend, logs, or git.
- The LLM can call these tools (each is an existing or Stage 10 backend function):
  - `list_my_fields` (logged-in user's saved fields only)
  - `get_saved_analysis(field)` (latest saved result for that field)
  - `weather_check(field)` (Stage 10 expected vs. actual + next-week risk)
  - `rank_my_fields()` (Step 8)
  - `what_if(field, scenario)` (Step 9)
- Rules for the assistant (put in its system prompt AND enforce in code):
  - Answer only from tool results; always mention the image date and data quality.
  - If data is missing or cloudy, say so instead of guessing.
  - Never prescribe watering amounts or diagnose a cause; suggest what to inspect.
  - Only access the current user's data; not logged in → only the field on screen.
- Limit message length and number of messages per minute per user (cost and abuse control).
- Tests: tool calls return only the user's own data; missing API key gives a friendly message
  and the rest of the app still works.
- **Success:** ask "Which of my fields should I check first?" and get an answer that matches
  the "My Fields" ranking, with dates and numbers.

## Step 11 — Wrap-up for WAICY
- README section: data sources, dataset size, model, splits, results from `ml/results.md`,
  the assistant's tools and safety rules, limitations.
- Slides: how the model learns, results vs. baselines, the assistant + what-if demo.
- Demo video: analyze a field → AI weather check → what-if sliders → ask the assistant.

---

## Schedule
| Dates | Steps |
|---|---|
| Nov 1 – Nov 5 | 1, 2 (start with 1 field, then 25) |
| Nov 6 – Nov 9 | 3, 4 |
| Nov 10 – Nov 13 | 5 (most important — leave time to fix problems) |
| Nov 14 – Nov 17 | 6, 7 |
| Nov 18 – Nov 20 | 8, 9 |
| Nov 21 – Nov 25 | 10 |
| Nov 26 – Nov 29 | 11, buffer + submit |

## Known limits (say these to judges)
- 10 m pixels: the model works at field/zone level, not individual sprinkler heads.
- Irrigation schedules are unknown; the model learns *typical* irrigated-field behavior.
- Weather forecasts are only reliable ~7 days ahead.
- Only Denver-area grass fields, growing season only.

## What Lavi should be able to explain
1. What the model learns (how greenness responds to rain, heat and water demand).
2. Why we test on 2025 and on unseen fields (to prove it works on new data).
3. What MAE means, and how the model compares with the simple baselines.
4. Why "weather doesn't explain this" is useful to a grounds crew.

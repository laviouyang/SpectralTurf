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
- Before each step: make a git commit. After each step: run the existing tests
  (`python test_indices.py` and any others) **plus** the new tests, and confirm the original
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

## Step 8 — Multi-field ranking (if time)
- Endpoint + page that runs the weather check on all saved fields and ranks them by risk.
- This is the "which fields should my crew check first this week" view.

## Step 9 — Wrap-up for WAICY
- README section: data sources, dataset size, model, splits, results from `ml/results.md`, limitations.
- 2–3 slides: how the model learns, results vs. baselines, a real example from the app.
- Demo video: analyze a field → AI weather check → ranked list.

---

## Schedule
| Dates | Steps |
|---|---|
| Nov 1 – Nov 5 | 1, 2 (start with 1 field, then 25) |
| Nov 6 – Nov 9 | 3, 4 |
| Nov 10 – Nov 15 | 5 (most important — leave time to fix problems) |
| Nov 16 – Nov 21 | 6, 7 |
| Nov 22 – Nov 26 | 8 if time, then 9 |
| Nov 27 – Nov 29 | Buffer + submit |

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

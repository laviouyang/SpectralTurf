# SpectralTurf AI — status report (2026-11-25)

Written for another AI assistant to catch up. The full, detailed project log is `CLAUDE.md`
(root); the original requirements are `docs/PROJECT_SPEC.md`. No secrets, keys, `.env` contents
or database contents are included here.

Project: high-school project by Yuanzhi (Lavi) Ouyang. First for the Congressional App Challenge
(deadline passed), now for **WAICY, due November 29, 2026**. The student must be able to explain
everything, so code stays simple and claims stay honest (no invented numbers; the app never
diagnoses disease or gives watering instructions).

---

## 1. Branches

| Branch | Where | Latest commit | Notes |
|---|---|---|---|
| `main` | local + GitHub (`origin/main`), in sync | `30bc53c` (2026-11-25) CLAUDE.md notes | Old single-sidebar UI. Everything up to Render deploy prep (`71840e5`) + one CLAUDE.md notes commit. |
| `version-2` (local name) | local; **tracks `origin/ui-redesign`** on GitHub | `c7a4e74` (2026-11-25) | = the former `ui-redesign` branch, renamed locally at the student's request. Redesigned website + all "Version 2" changes. |
| `origin/ui-redesign` | GitHub | was `7777089` before this report | GitHub name of the same branch. Updated to `version-2`'s commits when this report was pushed (see the end). |
| `us-expansion` | — | — | **Does not exist** (not local, not on GitHub). The homepage only has a "coming soon" state picker. |

Current branch: **`version-2`**.

**What `version-2` has that `main` doesn't** (7 commits, 35 files, ~4,300 lines added): new
homepage, /about page, separate /login page, router, redesigned map app with a tabbed floating
panel, and the Version 2 feature changes (sections 2 and 3). Backend additions on `version-2` only:
`saved_fields.py`, `POST /api/fields`, optional `save` in `POST /api/analyze`, optional `field` in
`POST /api/ai/ask` (+ `assistant.Context(focus=...)`), and 3 new test files.

**What `main` has that `version-2` doesn't:** only `30bc53c`, a CLAUDE.md-only notes commit
(`version-2` has its own, newer CLAUDE.md). No code differences in that direction.

**Not merged:** `version-2` is NOT merged into `main`. The student must approve the merge;
no assistant should merge without being asked.

**Not renamed on GitHub:** the GitHub branch is still called `ui-redesign`. Renaming it to
`version-2` on GitHub (and deleting the old name) was offered but not approved yet.

---

## 2. Features (one line each)

"Both" = on `main` and `version-2`. "V2" = only on `version-2`.

**Website and accounts**
- V2 — Homepage with a real Sentinel-2 example (Village Greens, image 2026-08-05), sourced water stats, model results, credits.
- V2 — Homepage shows "Logged in as <name>" in the top right when logged in.
- V2 — Homepage "Which state are your fields in?" picker: Colorado selectable; other 49 states "coming soon", with a disclaimer.
- V2 — Footer data credits are links (Copernicus, Open-Meteo, OpenStreetMap, Nominatim, Esri).
- V2 — /about methodology page.
- V2 — Separate /login page (log in / sign up / "Continue without an account") between home and app.
- Both — Accounts: username + password only (scrypt hashing), 30-day sessions, logout.

**Map and analysis**
- Both — Place search (OpenStreetMap Nominatim, 1 request/s). V2: it sits at the top of the Analyze tab, searches any address (Colorado preferred), and pops up a warning outside Colorado.
- V2 — Map starts on the OpenStreetMap street map; the Esri satellite photo is in the layer switcher.
- V2 — Map note (bottom right): background map is for drawing only; Esri photo about June 1, 2025 (checked at one field, can differ).
- Both — Draw a polygon or rectangle; Edit shape / Save shape / Clear area; size checks (2,000 m² minimum, 5 km maximum side).
- Both — Exclude tool (✂): cut non-turf areas (infields, tracks) out of the analysis.
- Both — Analyze: real Sentinel-2 L2A data, least-cloudy image in the date range, SCL cloud/shadow masking, NDVI (10 m) and NDMI (20 m), data-quality panel, limitations.
- V2 — Default dates: To = yesterday, From = 14 days before; To can never be before From (auto-corrects).
- Both — Inspection flag: within-field rule (0.20 below median, ≥5% and ≥5 px), healthy-turf baseline (NDVI < 0.5 or NDMI < 0), color check (NGRDI < 0.15); "may warrant inspection" / "no area stands out" / "insufficient evidence". All cutoffs are project choices.
- Both — Map layers: NDVI, NDMI, true color, inspection, none.
- V2 — Analyze never saves. Optional "Save this field" (name box + "Save to My Fields") under the Analyze button; it saves only the outline, excluded areas and name (no numbers). Same name → "Replace it / Don't replace" pop-up.
- V2 — "Show on map" from My Fields reloads the outline + name, keeps the current dates, opens the Analyze tab.
- Both (main: analyses are saved automatically when logged in) — Saved history list with Show on map / Delete.

**AI (Stage 10)**
- Both — AI Weather Check: expected vs actual NDVI for the latest clear image, next-week risk, chart, cloudy-day estimate. V2: in the "AI Check" tab as "1.", with a field drop-down (map field or any saved field).
- Both — What if? weather scenario sliders (limits from training data and the month). V2: "2." in the AI Check tab, with a field drop-down.
- Both — My Fields AI ranking ("check these first").
- Both — Ask SpectralTurf (Gemini) with photo upload, voice typing, read aloud. V2: you must pick ONE field first; all answers are about that field.
- V2 — My Fields, AI Check and Ask AI tabs need an account (🔒 shown for visitors). This lock is in the website only; the backend AI endpoints still accept visitors.
- Both — Off-season message outside April–October.

---

## 3. Recent changes (last 15 commits across all branches, newest first)

| Date | Commit | Branch | What changed |
|---|---|---|---|
| 2026-11-25 | c7a4e74 | version-2 | Saving made clearly optional: name box + Save button moved under the Analyze button. |
| 2026-11-25 | 7ee369e | version-2 | Separate "Save to My Fields" (no analysis, new `POST /api/fields`) and "Analyze" (never saves); Show on map keeps the dates. |
| 2026-11-25 | 00b70f5 | version-2 | Place search moved from the top bar into the Analyze tab. |
| 2026-11-25 | d588e84 | version-2 | Login page, save-vs-analyze, same-name replace pop-up, any-address search + outside-Colorado warning, map date note, AI Check numbering, footer links, homepage state picker. |
| 2026-11-25 | 39bce94 | version-2 | "Logged in as" on homepage, street map default, account-only AI tabs, date defaults, field drop-downs, Ask AI "pick one field first". |
| 2026-11-25 | 30bc53c | main | CLAUDE.md notes only. |
| 2026-11-25 | 7777089 | version-2 | CLAUDE.md: status, test commands, working rules. |
| 2026-11-23 | 37b050d | version-2 | UI redesign: homepage, about page, tabbed map app. |
| 2026-11-22 | 71840e5 | both | Render deploy prep: render.yaml, env-var paths, usage limits, deploy guide. |
| 2026-11-22 | 971f8f5 | both | Progress notes: collapsible sidebar, photo + speech. |
| 2026-11-22 | 7ca43a3 | both | Ask SpectralTurf: photo upload, voice typing, read aloud. |
| 2026-11-22 | 8ba1d70 | both | Sidebar sections became collapsible panels. |
| 2026-11-15 | c56c352 | both | Assistant tests (fake Gemini, no internet). |
| 2026-11-15 | 8700b08 | both | Ask SpectralTurf chat panel. |
| 2026-11-15 | 8ee416e | both | Ask SpectralTurf agent (Gemini function calling, read-only tools). |

---

## 4. AI model

- **Current version: 3** (`ml/model/ndvi_model_v3.joblib`, made 2026-11-07; the app loads v3).
  Predicts a field's mean NDVI 7–20 days after a clear satellite image. Model =
  HistGradientBoostingRegressor (learning rate 0.05, 200 iterations, depth 3), chosen on 2024.
- **Dataset:** `ml/data/dataset_v3.csv`, **38,342** start→target pairs from **22 fields**
  (Denver area; 25 collected, 3 likely artificial-turf fields removed), target years 2019–2025.
- **Inputs (input set "B"):** start image NDVI, recent trend, average of recent images, start
  image pixel spread and clear fraction, season (day of year), days ahead, rain / ET0 / rain−ET0 /
  average high temperature over 7–30 days, and weather compared with the Denver 2019–2024 normal.
  By far the most important input is the start image NDVI; weather inputs matter very little.
- **Real results (`ml/results_v3.md`), MAE in NDVI units, lower is better:**
  - 2025 (a year it never saw, tested once): model **0.0577** vs "same as last time" 0.0686
    (16% better, reliable), recent average 0.0686, seasonal average 0.0859.
  - Unseen fields (5 rounds, ~20% of fields held out): model **0.0600** vs "same as last time"
    0.0694 (14% better, reliable); vs recent average 0.0664 → **no clear difference**.
  - "Weather doesn't explain this" cutoff = 2 × 0.0611 (2024 error) = 0.1222.
  - Honesty note in the file: v3's ideas came after seeing the v1/v2 test results, so the
    numbers are still slightly optimistic. v1 did not beat "same as last time"; v2 tied it.
- **Leakage audit:** I found **no record of a formal leakage audit** in the repo (no file or
  notes mention one). What does exist: tests check that features use only data from before the
  image date (`ml/test_dataset_and_model.py`) and that no field is in both training and testing
  in the field split (test 12). Note: the weather inputs are the real weather of the 30 days
  before the TARGET day, so the evaluation uses actual weather where the live app would use a
  forecast for future days; this is a design choice, but it makes the test slightly kinder.
- **Wording fixes:** I found **no record** of a separate "wording fixes" task. Deliberate
  wording notes in CLAUDE.md cover the homepage statistics and "may warrant inspection" language.
  If another assistant did these, they are not recorded in this repo.

---

## 5. Ask SpectralTurf agent (`backend/assistant.py`, `POST /api/ai/ask`)

- **LLM:** Google Gemini via REST function calling; default model `gemini-3.5-flash`
  (`GEMINI_MODEL` can override); key only in the backend environment, sent in a header, never to the browser.
- **Tools (all read-only):** `get_my_fields`, `get_latest_analysis`, `get_expected_vs_observed`,
  `get_ranking`, `get_field_history`. Fields are "screen" (the map field) or "field-1"…
  (the logged-in user's own saved outlines). V2: with a picked field, every other field and the
  ranking are refused; fields saved without an analysis are reported as "not analyzed" (no numbers).
- **Safety checks (in code, on every answer):** every number and date must appear in a tool
  result (rounding/percent allowed); no watering amounts/schedules; no cause claims; no
  disease/pest diagnosis (also from photos). One retry, then the answer is blocked.
  Gemini never receives usernames, field names or coordinates. Answers carry
  "AI-generated explanation based on SpectralTurf data. Confirm in person."
- **Limits:** questions ≤ 500 characters; 5 per minute per user (or address); 300 per day for
  the whole server; at most 6 tool rounds; 90 s timeout. With usage limits on (Render): chat
  40/day per user, 15 per visitor, 300 total. No chat memory (each question stands alone).
- **Photo feature: ON.** One JPEG/PNG/WebP per question, max 8 MB; the server re-saves it at
  ≤ 1024 px (removes EXIF/GPS) and never stores it. Voice typing (browser speech recognition)
  and read-aloud are also on.

---

## 6. Tests (run 2026-11-25 on `version-2`)

| Test file | Result |
|---|---|
| backend/test_indices.py | 30/30 pass |
| backend/test_accounts.py | 16/16 pass |
| backend/test_predict.py | 58/58 pass |
| backend/test_assistant.py | 48/48 pass |
| backend/test_limits.py | 23/23 pass |
| backend/test_ask_focus.py (V2) | 15/15 pass |
| backend/test_analyze_save.py (V2) | 4/4 pass |
| backend/test_save_field.py (V2) | 8/8 pass |
| ml/test_get_fields.py | 20/20 pass |
| ml/test_get_ndvi_history.py | 11/11 pass |
| ml/test_get_weather.py | 6/6 pass |
| ml/test_dataset_and_model.py | 15/15 pass |
| ml/test_dataset_v3.py | 13/13 pass |
| **Total** | **267 pass, 0 fail** |

Frontend: `npm.cmd run build` **succeeds**. How to run everything: see "How to run all tests" in CLAUDE.md.

---

## 7. Deployment (`render.yaml`)

- **spectralturf-backend:** Python web service, rootDir `backend`, `pip install -r requirements.txt`,
  `uvicorn main:app --host 0.0.0.0 --port $PORT`, health check `/api/health`, 1 GB persistent disk at
  `/var/data` (needs a paid plan). Env: PYTHON_VERSION 3.13.14; secrets CDSE_CLIENT_ID,
  CDSE_CLIENT_SECRET, GEMINI_API_KEY set on Render (not in the file); GEMINI_MODEL, DATABASE_PATH
  `/var/data/spectralturf.db`, AI_CACHE_DIR `/var/data/ai_cache`, USAGE_LIMITS on, TRUST_PROXY_HEADERS 1.
- **spectralturf-frontend:** static site, rootDir `frontend`, `npm install && npm run build`,
  publish `dist`; rewrites `/api/*` → `https://spectralturf-backend.onrender.com/api/*` and `/*` → `/index.html`.
- **What Render is deploying:** the student says they deployed it themselves (2026-11-25).
  render.yaml does not name a branch, so Render uses the branch picked when the Blueprint was
  created, **most likely `main`** (the old UI). **Not verified** — no assistant can see the Render
  dashboard. If so, none of the `version-2` changes are live until `version-2` is merged into
  `main` (student approval needed) or Render is pointed at the other branch.

---

## 8. Open issues / unsure

- `version-2` is not merged into `main`, and is still named `ui-redesign` on GitHub.
- Unknown which branch Render deploys, and whether the live backend URL matches the rewrite in render.yaml.
- The "account needed" lock for the AI tabs is only in the website; the backend AI endpoints still accept visitors.
- "No duplicate names" is only checked in the website, not in the backend.
- A field saved without an analysis has no stored numbers; Ask AI can still use the weather check / satellite history for it.
- When searching a place, the map centers on the whole screen, so part of the field can sit under the floating panel.
- Not tested in a browser: the What-if field drop-down, the "Don't replace" button, the photo picker and microphone (need a person).
- No real phone test; the phone layout was only checked in a 390 px frame (before the latest changes).
- Esri basemap terms for a public website not checked; the Esri photo date (about June 1, 2025) was only checked at one field.
- No formal leakage audit record (see section 4); model results are slightly optimistic by the project's own note.
- Gemini free tier: Google may use what is sent to improve its products (the chat panel warns).
- Still to do for WAICY: Stage 10 Step 11 — README update, slides, demo video.
- `docs/HANDOFF.md` is older and may be out of date; CLAUDE.md is the up-to-date record.

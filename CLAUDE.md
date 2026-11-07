# SpectralTurf AI — project context for Claude Code

High school project for the **Congressional App Challenge**, deadline **October 26, 2026**.
The student must be able to explain every major part to judges, so keep code simple,
beginner-readable, and scientifically honest. Do not overengineer.

Full original requirements: `docs/PROJECT_SPEC.md` — read it before starting new stages.

## What the app does
User searches a place in Colorado → draws a polygon around sports-field turf → backend
fetches real Sentinel-2 L2A data → computes NDVI and NDMI → shows results, observation
date, data quality, and limitations. It prioritizes areas that "may warrant inspection".
It must NOT claim to diagnose disease, prove drought, prescribe watering, or control irrigation.

## Non-negotiable rules
- Never fabricate imagery, dates, index values, or weather. On failure, show an honest
  error or "Insufficient evidence" — never hardcoded/fallback numbers.
- Secrets (CDSE client ID/secret) live only in `backend/.env`; never in frontend, logs, or git.
- NDMI uses 20 m bands (B8A, B11) — never imply 10 m detail. Resampling adds no detail.
- Thresholds (e.g. MIN_VALID_PIXELS = 20) are project choices, not published standards; say so.
- Work in small stages. For each: list files, give complete code, explain simply,
  give exact commands, say what success looks like, and list what is still unverified.

## Environment
- Windows, PowerShell. Project at `D:\Lavi\SpectralTurf`.
- Backend venv: `backend\venv`. Each new terminal needs:
  `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` then `venv\Scripts\activate`
- Run server: `cd backend` → `uvicorn main:app --reload` → http://localhost:8000/docs
- Test area: **Village Greens** sports complex (Greenwood Village, CO area).

## Architecture
- `backend/` — Python FastAPI
  - `sentinel.py` — CDSE auth (cached OAuth token), Catalog search, Process API calls.
    Token URL: identity.dataspace.copernicus.eu/.../CDSE/protocol/openid-connect/token
    Process: https://sh.dataspace.copernicus.eu/process/v1
    Catalog: https://sh.dataspace.copernicus.eu/catalog/v1/search
    Output size is computed for 10 m pixels from the bbox (cos(latitude) correction), max 500 px/side.
  - `indices.py` — pure numpy math: NDVI, NDMI, SCL cloud/shadow masking, stats,
    insufficient-evidence rule. No network. Tested by `test_indices.py`.
  - `main.py` — endpoints:
    - `GET /api/health`
    - `POST /api/analyze` {geometry (GeoJSON Polygon), start, end, max_cloud} → same JSON stats,
      for the drawn polygon only. Used by the website.
    - `GET /api/test/truecolor?west&south&east&north&start&end&max_cloud` → PNG (2.5x display gain only)
    - `GET /api/test/indices?...` → picks least-cloudy scene via Catalog (real date),
      fetches raw FLOAT32 TIFF of B04,B08,B8A,B11,SCL,dataMask for that day, returns JSON stats
- `frontend/` — Vite + React 18 + Leaflet + leaflet-draw. Run: `cd frontend` → `npm.cmd run dev`
  → http://localhost:5173 (use `npm.cmd`, or set the execution policy, since `npm` is a blocked .ps1).
  Files: App.jsx, MapView.jsx, SearchBox.jsx, polygonCheck.js, api.js, Results.jsx, leafletSetup.js.

## Science decisions already made
- NDVI = (B08−B04)/(B08+B04); NDMI = (B8A−B11)/(B8A+B11); |denominator| < 1e-6 → NaN.
- Rejected SCL classes: 0 no data, 1 saturated, 2 dark/shadow, 3 cloud shadow,
  8/9 cloud, 10 cirrus, 11 snow. Kept: 4 veg, 5 non-veg, 6 water, 7 unclassified.
- Upsampling NEAREST (keeps honest pixels; SCL codes must never be blended).
- Catalog eo:cloud_cover is tile-level, so per-pixel SCL masking is still required.
- Brightness gain is display-only; index math always uses raw reflectance.

## Progress (stages from the spec)
- [x] Stage 1 — Diagnosed Request Builder issue; true color at 10 m verified at Village Greens.
- [x] Stage 2 — Backend fetches true color itself. **Verified by student** (image matched Request Builder).
- [x] Stage 3 — Verified against the real API on 2026-10-12 (scene 2026-08-05, 0% tile cloud).
      **Student reproduced the grass and parking numbers.** Unit tests pass (7/7). Results:
      grass_A `-104.8790,39.6337,-104.8784,39.6344` NDVI 0.628 / NDMI 0.134 (40 px);
      grass_B `-104.8790,39.6355,-104.8784,39.6360` NDVI 0.754 / NDMI 0.239 (30 px);
      parking `-104.8848,39.6247,-104.8837,39.6258` NDVI 0.096 / NDMI -0.033 (108 px);
      9-px box → insufficient_evidence. Reflectance 0.06–0.46 (units correct); TIFF parsed fine.
      Village Greens Park confirmed by student: ~39.635, -104.880 is the middle of its west
      (left) side; ball fields with dirt infields extend east. NOTE: the Stage 2 default box (-104.90,39.61,-104.89,39.62) is the I-25
      corridor, NOT the field.
- [x] Stage 4 — Code written 2026-10-12 in `frontend/` (Vite + React 18, plain Leaflet + leaflet-draw,
      no react-leaflet). Files: MapView.jsx (map, draw/edit/delete), SearchBox.jsx (Nominatim, bounded
      to Colorado, submit-only, 1 req/s), polygonCheck.js (2,000 m² min, 5 km max side — mirror backend),
      leafletSetup.js (sets window.L for leaflet-draw). Basemaps: Esri World Imagery (drawing only) + OSM.
      showArea:false avoids leaflet-draw "type is not defined" bug. Node 24.20 installed via winget.
      Vite upgraded 5→7.3 (+ plugin-react 5) to clear npm audit dev-server advisories; audit clean.
      Run: `cd frontend` → `npm install` → `npm run dev` → http://localhost:5173
      Tested by Claude in Chrome: page loads at Colorado; search finds "Village Greens North Park"
      (Nominatim's name for the open space N of the ball fields) and zooms; polygon draw → 40,582 m²
      (cross-checked 40,569 from GeoJSON); tiny shape → "too small"; redraw replaces; Clear works;
      rectangle works. Leaflet.draw ignores clicks <~0.5 s apart (automation only; humans fine).
      Student verified by hand: draw, rectangle, edit, delete, crossing-edges block all work.
      UX change (student request): Leaflet.draw's edit/trash toolbar removed. Sidebar now has
      "Edit shape" → "Save shape" (uses layer.editing.enable/disable) + "Clear area". Starting a new
      drawing ends editing. Corner-crossing during edit isn't blocked live, but checkPolygon flags it
      after Save. Claude tested Edit/Save toggle in Chrome; corner-drag + area update awaits student.
      Unverified: Esri tile terms for public deploy. Student verified all map features by hand.
- [x] Stage 5 — Done 2026-10-12; student verified 2026-10-13 (grass high; a parking lot with
      trees/cars gave mean NDVI ~0.3 — mixed pixels, good limitations example). `POST /api/analyze` {geometry, start, end,
      max_cloud}; `clean_polygon()` validates (400s); `run_analysis()` shared with /api/test/indices
      (box → polygon). fetch_bands uses `input.bounds.geometry`; outside-polygon pixels come back
      dataMask=0 (VERIFIED: triangle half of a 476-px rect → 259 px inside). valid_fraction now
      = valid / inside-area pixels. CORS: FRONTEND_ORIGINS env, default localhost/127.0.0.1:5173
      (other origins rejected). Frontend: api.js (VITE_API_URL, default :8000), Results.jsx (basic;
      hides means when insufficient_evidence), App: date inputs (default 2026-06-01..08-31), Analyze
      with loading; results cleared when polygon changes; stale responses ignored (request counter).
      Tests: 8/8 unit; grass_B via POST = 0.754/0.239 (matches Stage 3); in Chrome: North Park
      meadow NDVI 0.164 (dry open space), reservoir NDVI −0.691; backend-down message works.
- [x] Stage 6 — Done 2026-10-13; student verified (ball fields map, NDMI/true color, 08-13 cloudy case). New `backend/render.py` (Pillow) colors the
      SAME pixel arrays used for stats → PNG data URLs in `images` {ndvi, ndmi, true_color}; outside
      polygon transparent, rejected = gray; fixed display color scales sent as `color_scales` (legend
      uses them). Bands evalscript now 8 bands (B02,B03 added for true color). `quality_warnings()` in
      indices.py (project-choice levels: <80% clear, tile >10% cloud, <20 NDMI 20 m measurements;
      all-rejected → "no usable data"). Frontend: imageOverlay in pane 'analysis' (z 350, under
      outline) with `image-rendering: pixelated`; layer radio NDVI/NDMI/True color/None; Results.jsx
      has legend, stats, meaning, data quality, limitations, raw JSON (images stripped). Decision: backend
      keeps stats when insufficient_evidence; UI hides them. Tests 11/11.
      Verified: picture orientation (diamonds at known coords; NDVI turf green, infields brown);
      overlay aligned with basemap in Chrome (Fiddler's Green lawn arc); real CLOUDY case: 2026-08-13,
      09-07, 08-08 fully clouded field → all rejected, insufficient_evidence, all-gray map;
      08-15 (52% tile) field clear, NDVI 0.454 vs 0.432 on 08-05.
- [~] Stage 7 — Done 2026-10-13, awaiting student run. Within-field rule (no history): in indices.py
      `interior_mask` (skip outer pixel ring), `inspection_masks` (shared by stats + picture),
      `inspection_indicator` → `inspection` {status may_warrant_inspection | no_area_stands_out |
      insufficient_evidence, headline, reason, rule, median, cutoff, low_pixels/fraction/area}.
      Project choices: LOW_NDVI_MARGIN 0.20 below field median (healthy turf std measured 0.05–0.08
      on 2026-08-05 → ~3x), flag if ≥5% AND ≥5 px. NDVI only (10 m). render.py `inspection` image:
      pink low, faint white checked, gray rejected. Frontend: InspectionCard at top of Results
      (preliminary label, "How this rule works", "What to check when you visit" checklist → CSU
      Extension; observations only, no diagnosis/watering advice), Inspection map layer + legend.
      Tests 16/16. Real data: turf-only box → no area stands out (median 0.687); same box reaching
      road edge → flagged bottom rows; ball fields incl. diamonds → pink exactly on 4 infields
      (15%, NDVI 0.26 vs 0.69); dry meadow → no area stands out (whole-field-low limitation).
      Student asked "which stage tells people what to do": answer = none by design (spec forbids);
      app says where to look; checklist suggests what to observe.
- [~] Stage 8 — 2026-10-13. Stage 7 follow-up: student chose ONLY a "Your next step" line on the
      inspection card (NEXT_STEP in Results.jsx); declined the "if you find X → do Y" table.
      Field tests done (all summer 2026, real API): Village Greens turf 0.70; DSG Park Commerce City
      0.84 / 0.75 (2026-08-20); Memorial Park Colorado Springs 0.88 / 0.90; Cherry Creek HS stadium
      0.17 = ARTIFICIAL TURF (green in true color, low NDVI) → added WARN_BELOW_MEDIAN_NDVI = 0.3
      warning. No false inspection flags on real turf (0–2% low). Cloudy case done in Stage 6.
      Tests 17/17. README.md written at root (install, env vars, run, science, project-choice table,
      limitations, test results, code map, data sources). Root .gitignore added (.env safety net).
      Weather skipped (optional). Deploy NOT done: needs student's GitHub + hosting accounts.
      EXCLUDE TOOL (student found infields flagged as false alarm): user draws exclusion shapes
      (sidebar "Exclude a rectangle/polygon" → MapView excludeRequest → L.Draw.Rectangle/Polygon with
      EXCLUDE_STYLE tagged `exclusion: true`). POST /api/analyze `exclude: [Polygon]` (max 30,
      clean_polygon each). Backend: indices.excluded_pixel_mask (pixel-center ray casting on the
      CRS84 output grid) → apply_exclusions sets dataMask=0; response `excluded` {areas, pixels}.
      Edge ring around excluded areas is skipped by the inspection rule automatically. New outline
      clears exclusions. Rejected auto-excluding dirt: dead grass looks the same. Tests 19/19.
      Real: ball fields 16% low → with 4 infields excluded 3.7% → "No area stands out"; browser
      verified (175 px excluded, 4%). Student will do the demo video later; wants GitHub steps.
      Git was NOT installed (2026-10-13).
      FOLLOW-UP: student said exclusions "just remove the first shape" — they used the map's
      outline tools. Added ✂▭/✂⬠ exclude buttons ON THE MAP (custom leaflet-bar control under the
      draw toolbar; works only once an outline exists) + L.drawLocal hover titles "Draw turf
      outline… (replaces the current outline)". Found + fixed real bug: polygon clicks INSIDE an
      existing shape were swallowed (0 vertices) → SHAPE_STYLE/EXCLUDE_STYLE `interactive: false`.
      Verified in Chrome: ✂ polygon + ✂ rectangle inside outline → 2 exclusions kept; new outline
      clears exclusions; Edit/Save still works with exclusions kept.
      HEALTHY-TURF BASELINE (2026-10-14, student request: "it always says 0%... comparing to itself"):
      within-field rule could never flag an evenly dry field, or a mostly-dry field with green spots
      (median is dry). Added absolute check in indices.py: pixel below baseline if NDVI < 0.5 OR
      NDMI < 0.0 (BASELINE_NDVI/NDMI, project choices from real data: healthy turf p5 NDVI 0.57-0.86,
      NDMI 0.10-0.28 at 6 fields; dry meadow 0.18/-0.14). >=50% below (WHOLE_FIELD_FRACTION) →
      scope "whole_field", headline "Most of this field may warrant inspection"; else either check
      >=5% & >=5 px → scope "some_areas". inspection.baseline {...} added. Map: orange = below
      baseline, pink on top. Season warning outside May-Oct (BASELINE_MONTHS; April turf 0.53 →
      33% below). Frontend NEXT_STEP keyed by scope. Tests 25/25. Real API: healthy fields unchanged
      (No area stands out); meadow → whole field; meadow+turf → 77%, turf stays unflagged.
      Awaiting student hand-test.
      GATES NORTH / COLOR CHECK (2026-10-14): student saw obvious yellow spots at Gates North
      (Aurora, turf W of 6743 S Chambers Way, ~-104.8146,39.5913,-104.8121,39.5931) that passed.
      Found: Esri photo dated 2025-06-01 (Esri identify service); Sentinel same day NDVI 0.78-0.82
      (healthy); 39-date averaging found no persistent low spots in turf (first "signal" was a path).
      Sentinel true color DID show the pale east side: NGRDI east 0.14 vs west 0.27. Added check 1
      "color": NGRDI=(B03-B04)/(B03+B04) (Tucker 1979), compute_ngrdi; YELLOW_NGRDI = 0.15 —
      STUDENT CHOSE this strict line ("only deep green is good") after seeing a cutoff table
      (0/0.05/0.10/0.15). Effects: Memorial 1-5% (NW = 5.4% → "Some areas"), DSG south 20%,
      Gates 36% (2025, yellow on east side matching photo) / 52% (2026), DSG east 64%, VG 96%
      → many growing fields now flagged by color; NDVI checks still pass for them. Whole-field =
      ≥50% fail color OR baseline. Map yellow (under orange, under pink). analyze_bands(b03=None)
      optional; response adds `ngrdi` stats and inspection.color {...}. Tests 29/29.
      STUDENT VERIFIED 2026-10-14: at first thought yellow was "on the greener parts" — they were
      comparing the 2026-08-05 analysis with the 2025-06-01 Esri photo (pattern had moved). With
      dates set to 2025-06-01..2025-06-01 it matched: "everything works as normal now".
      Idea offered, not built: show the Esri photo date next to the satellite date.
- [~] Stage 9 — ACCOUNTS + SAVED HISTORY (2026-10-31, student request; after the CAC deadline).
      Optional; visitors can still analyze. `backend/accounts.py`: SQLite (stdlib) file
      `backend/spectralturf.db` (git-ignored, *.db). Username + password only (no email: least
      personal data for minors; no password reset). Passwords: hashlib.scrypt (n=2^14,r=8,p=1) +
      16-byte salt, hmac.compare_digest; same error for unknown user / wrong password. Sessions:
      secrets.token_urlsafe(32), only SHA-256 stored, 30 days, logout deletes. Project choices:
      username 3-30 [A-Za-z0-9_], password 8-200 chars, max 500 saved per user.
      main.py: /api/auth/signup|login|logout (POST), /api/auth/me, /api/history (GET),
      /api/history/{id} (DELETE); Authorization: Bearer; CORS adds DELETE + Authorization.
      /api/analyze saves a SUMMARY server-side when logged in (numbers from the backend's own
      result, never from the browser; images not stored), optional `name`; returns saved_id
      (or save_error, analysis still shown). Frontend: api.js token in localStorage;
      AccountPanel.jsx (login/signup form, history list: Show on map / Delete); App "Your account"
      section + "Field name" input; MapView `loadRequest` redraws saved outline + exclusions.
      Tests: test_accounts.py 16/16; test_indices 29/29. Claude verified via API + Chrome:
      signup, stays logged in after reload, analyze saves (Gates 2025-06-01 NDVI 0.819 / NDMI
      0.332, "Some areas"), Show on map redraws outline, re-analyze adds entry, delete, logout.
      Test DB deleted afterwards. NOT for public deploy as-is: no login rate limit, no HTTPS
      locally, localStorage token. Awaiting student hand-test.

- SHARE LINK (2026-10-31): student wants "a website" for a few people, NOT public/hosted.
      Chose Cloudflare quick tunnel from own PC. api.js API_URL default '' (same origin);
      vite.config.js proxies /api -> localhost:8000 (dev + preview); preview port 4173,
      allowedHosts ['.trycloudflare.com'] (others 403). `npm.cmd run share` = build + preview.
      Verified locally: page 200, /api/health + login 401 through 4173, unknown Host 403.
      cloudflared NOT installed or tested yet (student runs winget). README "Sharing a link".
      PHONE ON WI-FI: `npm.cmd run phone` = `vite --host`. Verified page 200 at the PC's Wi-Fi
      IP (10.0.0.118 on 2026-10-31); backend :8000 not reachable from Wi-Fi (good). Wi-Fi profile
      was Public + no Node firewall rule → student must set Private / allow Node. Phone untested.

## Stage 10 — AI weather-aware turf prediction (plan: `docs/STAGE_10_AI_PREDICTION.md`, WAICY, due Nov 29, 2026)
Work ONE step at a time unless the student says otherwise. Before each step: git commit.
After each step: run existing + new tests, confirm the original app still works, commit, then
tell the student what changed, the exact test command, and what success looks like.
(A photo-AI "Stage 9" was built and then fully removed on 2026-11-01 at the student's request.)

ADD-ON ONLY — do not replace anything:
- Everything SpectralTurf already does must keep working exactly the same: place search,
  drawing, Exclude tool, NDVI/NDMI analysis, the 0.20 / 5% inspection flag, map layers,
  data-quality panel, and all existing tests.
- All new code goes in **new files** (`ml/`, `backend/predict.py`, a new React component).
- Existing files may only be changed to **add** things: register the new endpoint in `main.py`,
  and add the "AI Weather Check" panel **below** the current results. Never rename, rewrite,
  move, or delete an existing function, endpoint, component, or test.
- The existing analysis must still run and show results even if the AI part fails or is
  off-season; the AI panel just shows its own message.
- The optional accounts system (login, sessions, saved history, `spectralturf.db`, and
  `test_accounts.py`) must keep working unchanged. New features may only READ saved fields.
- Tests to run after every step: `cd backend` → `python test_indices.py`,
  `python test_accounts.py`, plus every new Stage 10 test (so far: `python ml/test_get_fields.py`
  from the project folder).
- If a step seems to require changing existing behavior, stop and ask the student first.

Non-negotiable rules for this stage:
- Every number shown to users or in slides must come from real data and `evaluate.py` output.
  Never invent accuracy or example results.
- Test the model on a **year it never saw** (time split), and separately on **fields it never
  saw** (group split). Report both honestly, even if results are weak.
- The model's output is a **prioritization signal**, not a diagnosis or watering instruction.
- Growing season only (April–October). Outside it, show "Off-season — grass may be dormant."
- Respect API limits: cache all downloaded data to disk, never re-download what's cached,
  and stop and report if the Copernicus processing quota is getting low.
- Weather data credit: "Weather data by Open-Meteo.com". Field outlines: "© OpenStreetMap contributors".

Steps (details in the plan doc):
  1 field outlines (OSM Overpass) · 2 NDVI history per field (CDSE Statistical API, Apr–Oct
  2019–2025, ≥80% clear) · 3 weather history (Open-Meteo, daily rain / max temp / ET0) ·
  4 training dataset (features only from BEFORE each date) · 5 train + evaluate
  (HistGradientBoostingRegressor; time split train 2019–23 / val 2024 / test 2025, plus ~20%
  fields held out; MAE vs "same as last time" and "seasonal average"; results → ml/results.md) ·
  6 POST /api/ai/weather-check (backend/predict.py) · 7 "AI Weather Check" panel below results ·
  8 "My Fields" ranking from the user's saved fields (READ ONLY from accounts; own fields only) ·
  9 "What if?" sliders, POST /api/ai/what-if ("Scenario estimate, not a forecast"; only values
  inside the training range) · 10 "Ask SpectralTurf" assistant, POST /api/ai/ask (LLM key ONLY
  in backend/.env; tools = list_my_fields, get_saved_analysis, weather_check, rank_my_fields,
  what_if; answers only from tool results, mention image date + data quality, never prescribe
  watering or diagnose, own data only, rate limits) · 11 README, slides, demo.
  Student said: STOP before building Steps 8–10 and wait for their go-ahead.

Progress:
- [x] Step 1 — Field outlines (2026-11-01). STUDENT DECISION: AI must work on ANY grass field,
      incl. parks → mix 10 "sports" / 5 "baseball" / 10 "park" (FIELDS_PER_KIND). ml/get_fields.py:
      2 Overpass queries cached in ml/data/cache/ (git-ignored): pitches (4,494) and landuse=grass
      inside leisure=park (628; map_to_area returns far-away parks → centroid must be in Denver box
      39.55,-105.15,39.95,-104.70). Rules (project choices): closed; drop non-grass surface tags,
      never-grass sports, golf/shooting/model airfield; 8,000–100,000 m²; average width
      (2·area/perimeter) >= 30 m (drops greenway strips); >= 1 km apart (300 m let 3 fields of one
      complex in); seed 2026; VISUAL_REVIEW_EXCLUDE (9 ids with reasons, from Esri photo check).
      Retries with 30/90 s backoff (Overpass returned 502 "at capacity" once).
      Overpass was blocked by Cloudflare WARP on this PC; student turned WARP off for downloads.
      Output ml/data/fields.geojson (25). Visual check: #1–#3 (sports) may be artificial turf —
      left for Step 2's rule. tests ml/test_get_fields.py 20/20.
- [x] Step 2 — ml/get_ndvi_history.py: CDSE Statistical API https://sh.dataspace.copernicus.eu/api/v1/statistics
      (P1D, resx/resy = 10 m in degrees, NDVI NaN for SCL-rejected px, "clear" output = clear
      fraction). VERIFIED: grass_B 2026-08-05 = 0.754 (same as Stage 3). PU from header
      x-processingunits-spent: 12.1 PU per field (7 seasons), 302.5 total; PU_BUDGET_PER_RUN 1000.
      Cache ml/data/cache/stats/. 405–442 usable dates/field (>= 80% clear). All 25 kept by
      p90 >= 0.3 rule. FLAGGED (kept, per rule): sports #1 osm_way_1288554499, #2 osm_way_544154803,
      #3 osm_way_337232615 = flat seasonal NDVI 0.3–0.5, likely artificial turf (edge pixels mix
      in grass so p90 > 0.3); park #19 osm_way_1256470760 jumped 0.10→0.62 in 2024 (renovation?).
      Haze can pass SCL (e.g. a 0.578 day among ~0.8s) — a noise source.
- [x] Step 3 — ml/get_weather.py: Open-Meteo archive, 2,557 days/field, 0 missing, 17 grid points.
- [x] Step 4 — ml/build_dataset.py → ml/data/dataset.csv: 10,443 rows, 25 fields; features only
      from before the image day; MAX_GAP_DAYS 45; field kind NOT a feature.
- [x] Step 5 — ml/train.py + ml/evaluate.py → ml/results.md, feature_importance.png,
      ml/model/ndvi_model.joblib. v1 (results_v1.md) did NOT beat "same as last time" (field size
      was #2 input = field fingerprint). v2 (made AFTER seeing v1 test → slightly optimistic):
      ChangeModel = prev NDVI + HistGBR-predicted change, no area_m2. Settings chosen on 2024
      (lr 0.1, 100 iters, depth 3; val MAE 0.0578). Cutoff 2 x 0.0578 = 0.1156 (6.4% of 2024 dates).
      RESULTS (bootstrap over fields, 1000x): 2025 model 0.0507 vs last 0.0513 → NO CLEAR
      DIFFERENCE; unseen fields 0.0542 vs 0.0542 → NO CLEAR DIFFERENCE; unseen fields with prev
      image 8+ days old (662 rows) → model reliably 13% better (0.0088, 95% +0.0019..+0.0145);
      2025 8+ days (102 rows) +4%, inconclusive. Weather inputs have tiny importance (fields are
      watered). STOPPED after Step 5 to let the student decide how to proceed (2026-11-01).
- [ ] Steps 6–7 — NOT built (no /api/ai/weather-check endpoint, no AI Weather Check panel).
      The weather-check ENGINE exists in backend/predict.py (built for Step 8).
- [x] Step 8 — My Fields ranking (2026-11-02, student asked for Steps 8+9). backend/predict.py:
      weather_check(geometry, exclusions, as_of) = Statistical API last 60 days (same evalscript,
      80% clear; exclusions become holes if valid, else not used + note) + Open-Meteo (archive up
      to today-6, forecast service after) → expected vs actual for the latest clear image
      (cutoff 0.1156) + next-week risk (target as_of+7; High drop>=cutoff, Medium>=0.0578, else
      Low; project choices). Any input outside training feature_ranges → no number ("Unknown").
      NOTE training days_since_prev range is only 1–20 days. Cache backend/ai_cache/
      (git-ignored); DAILY_PU_BUDGET 100; ~0.5 PU per field. rank_my_fields: distinct saved
      fields (READ ONLY via accounts.list_analyses), max 10, ranked by not-explained → risk →
      difference. POST /api/ai/my-fields {as_of} (401 if logged out). Frontend MyFields.jsx,
      sidebar section "5. My Fields — AI ranking" ("Check as of" + "Rank my fields", "Show on
      map"). train.py now runs main() as module `train` so the model pickles as train.ChangeModel
      (retrained: identical settings/MAE). Tests backend/test_predict.py. Verified live as of
      2026-08-15 (3 fields, all "Weather explains this", Low) and off-season message in Chrome.
- [x] Step 9 — What-if simulator (2026-11-02). predict.what_if: scenario = the 14 days after the
      latest clear image (WHAT_IF_DAYS; model saw gaps 1–20 only, so 0–14 dry days, not 0–21);
      weather before the image stays real. Sliders: dry_days (last X days no rain), rain_mm
      (spread over the other days), avg_high_c (every day). ET0 = 0.179 x high + 0.55 mm/day,
      fitted to real Apr–Oct 2019–2025 training weather (R² 0.71). Slider limits from training
      ranges (GET /api/ai/what-if/limits: rain 0–145, high 6–35 °C); any feature still outside →
      "outside_training", no number. POST /api/ai/what-if {geometry?, exclude, as_of, dry_days,
      rain_mm, avg_high_c, include_my_fields}. WhatIf.jsx = sidebar "6. What if? — AI weather
      scenario" ("Run scenario", then auto-updates 0.6 s after a slider stops). REAL BEHAVIOR:
      changes are small (14 dry days at 34 °C ≈ −0.02 NDVI); cool scenarios (15–20 °C) show
      ≈ −0.05 because cool = autumn in training (pattern, not cause) → PATTERN_NOTE shown.
      Nothing reached Medium/High on 3 real fields. Test account deleted after E2E check.
- [x] MODEL VERSION 3 (2026-11-07, student asked for improvements 1+2 + drop artificial turf; no new
      fields). NEW files ml/build_dataset_v3.py (pair_features shared with the app), train_v3.py,
      evaluate_v3.py, test_dataset_v3.py (13/13); outputs dataset_v3.csv (38,342 start->target pairs
      7-20 days apart, 22 fields), model/ndvi_model_v3.joblib, results_v3.md, feature_importance_v3.png.
      v2 files untouched (results_v2.md = copy of v2 results). Removed #1-#3 (EXCLUDED_FIELDS): Esri
      photos Sep/Nov 2025 bright green + painted lines among dormant grass; S2 July 2025 NDVI 0.31-0.42
      vs 0.74 real grass; flat Apr-Oct. Chosen on 2024: input set B (recent avg, trend, image quality,
      weather vs Denver 2019-2024 normal), start = start image, lr 0.05/200/depth 3; val MAE 0.0611,
      cutoff 0.1222. Own-usual-NDVI set C lost on 2024 (app needs no earlier-year downloads).
      2025 TEST (run once): model 0.0577 vs last time 0.0686 (16% better, reliable), recent avg 0.0686,
      seasonal 0.0859. Unseen fields: 0.0600 vs last 0.0694 (14%, reliable, 95% +0.0007..+0.0150),
      vs recent average 0.0664 NOT clearly better. Beats v2 design on same question by 6% (reliable).
      Still slightly optimistic (v3 ideas came after seeing v1/v2 tests). predict.py loads v3 if present
      (v2 path kept; tests 33-38 added, 38/38): weather check compares latest image with newest image
      7-20 days earlier. WHAT-IF RE-TEST (Aug 15 2026, 3 real fields): more dry days -> bigger drop
      (Gates 25 °C: 0 dry -0.059, 14 dry -0.080); 26-34 °C nearly flat; scenarios far cooler than
      normal (15-22 °C in Aug) now get NO number (outside training); ~6 °C below normal (23-25 °C) still
      shows a larger drop (learned from 198 rows / ~5 cool spells) -> PATTERN_NOTE updated.
      MONTH LIMIT FIX (2026-11-07, student): What-if temperature only allowed if a real 14-day spell
      ENDING in that month (as_of's month) averaged that high, 2019-2025 (predict.month_high_ranges,
      ml/data/weather). Apr 6-20, May 12-27, Jun 14-33, Jul 25-34, Aug 26-35, Sep 22-33, Oct 6-28 °C
      (also capped by training range). GET /api/ai/what-if/limits?as_of= adds month + month_note +
      heat_note; what_if refuses others (no download). WhatIf.jsx reloads limits when the date
      changes, clamps the slider, shows "allowed X–Y °C in <Month>" + HEAT_NOTE. Tests 39-45 (45/45).
- STEP 2 DECISION (student): drop fields whose NDVI never rises above 0.3 during the season
  (use the field's high percentile, e.g. 90th, over all clear dates — NOT a summer median, since
  unwatered park grass can be < 0.3 all August yet greens up in spring) and REPORT them.
  If too few sports fields remain, add replacements.

## Known gaps / TODO
- Overlay drawn as lon/lat-grid image on Web Mercator map: fine for field-sized areas, slight
  stretch possible near the 5 km max.
- GitHub: https://github.com/laviouyang/SpectralTurf (pushed 2026-10-14). Handoff summary: `docs/HANDOFF.md`.

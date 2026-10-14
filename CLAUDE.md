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

## Known gaps / TODO
- Overlay drawn as lon/lat-grid image on Web Mercator map: fine for field-sized areas, slight
  stretch possible near the 5 km max.
- README not written yet (required: install, env vars, run, data sources, limitations, components).

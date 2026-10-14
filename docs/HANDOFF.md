# SpectralTurf AI: handoff for the next Claude session

Written 2026-10-14. Read this first, then `CLAUDE.md` (rules and per-stage detail),
`docs/PROJECT_SPEC.md` (original requirements) and `README.md` (user-facing docs).

## Who and what
- **Student project** for the **Congressional App Challenge**, deadline **2026-10-26**.
- The student must explain every part to judges. Keep code simple, explain in plain language,
  and work in small stages: list the files, give complete code, explain it, give exact
  commands, describe what success looks like, and list what is unverified.
- **App:** search a place in Colorado → draw a turf outline (and optionally cut out non-turf
  parts) → backend fetches real Sentinel-2 L2A data → NDVI/NDMI, cloud masking, stats,
  data-quality warnings, and a "may warrant inspection" indicator with color maps.

## Rules that must never be broken
- Never fabricate imagery, dates, index values, or weather. On failure, show an honest
  error or "Insufficient evidence", never fallback numbers.
- CDSE secrets live **only** in `backend/.env`. That file is git-ignored and must never be
  opened, printed, committed, or put in the frontend.
- NDMI is 20 m data (B8A, B11). Never imply 10 m detail.
- Thresholds are **project choices**, not published standards. Say so.
- Never claim to diagnose disease, prove drought, prescribe watering, or control irrigation.
  The student declined an "if you find X → do Y" table. The app only says *where to look*,
  plus a "Your next step" line and a "what to observe" checklist that links to CSU Extension.

## Environment (Windows, PowerShell)
- Project: `D:\Lavi\SpectralTurf`. GitHub: **https://github.com/laviouyang/SpectralTurf**
  (public, branch `main`, pushed and in sync as of 2026-10-14; first commit `1e79f20`).
- Git 2.55 and Node 24.20 were installed via winget. A shell opened before an install needs
  its PATH refreshed:
  `$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')`
- Backend: `cd backend` → `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` →
  `venv\Scripts\activate` → `uvicorn main:app --reload` (port 8000, Python 3.13).
- Frontend: `cd frontend` → `npm.cmd run dev` (port 5173). Use `npm.cmd`, because the `npm` .ps1
  script is blocked. Vite 7.3, `npm audit` clean.
- Tests: `cd backend` → `python test_indices.py` → **29/29 pass** (offline, no login).
- The student usually runs both servers themselves and runs commands by hand when asked.
- PowerShell quirk: negative numbers as positional arguments become strings. Use Python for API tests.

## Architecture (short; see CLAUDE.md and README "Code map")
**Backend (FastAPI)**
- `sentinel.py`: OAuth token (cached), Catalog search for the least-cloudy scene, and Process API
  calls returning an 8-band FLOAT32 TIFF (B02, B03, B04, B08, B8A, B11, SCL, dataMask) clipped
  to the polygon. Uses NEAREST resampling, 10 m pixels, max 500 px/side.
- `indices.py`: pure numpy.
  - NDVI, NDMI, and the SCL mask (rejects classes 0, 1, 2, 3, 8, 9, 10, 11), plus stats.
  - `MIN_VALID_PIXELS` = 20 → insufficient_evidence.
  - Warnings: <80% clear, tile >10% cloud, <20 NDMI measurements, and median NDVI <0.3 (possible artificial turf).
  - Exclusions: ray casting at pixel centers sets dataMask = 0.
  - Inspection rule (skips the edge ring). Besides the checks below, there is a **color check**
    (2026-10-14): NGRDI = (B03−B04)/(B03+B04) < 0.15 is yellow on the map.
    - The student chose this strict line. It flags pale fields like Gates North, Village Greens,
      and DSG east.
    - "Whole field" = ≥50% of the field fails the color OR the baseline check.
    - See CLAUDE.md Stage 8 for the cutoff table.
  - The other two checks:
    - (1) Healthy-turf baseline, added 2026-10-14: NDVI < 0.5 or NDMI < 0.0 is orange on the map.
      If ≥50% of the field is below it, the result is "Most of this field may warrant inspection".
    - (2) Within-field: NDVI more than 0.20 below the field median is pink.
    - Either check reports an area if it is ≥5% of the field and ≥5 px. There is a season
      warning outside May–Oct.
    - This was added because the student found the within-field rule alone always said 0% on an
      evenly dry field.
- `render.py`: PNG data URLs (ndvi, ndmi, true_color, inspection) made from the same arrays as the stats.
- `main.py`: `POST /api/analyze` {geometry, start, end, max_cloud, exclude[]}. Also `/api/health`
  and `/api/test/indices` and `/api/test/truecolor`. CORS is set by the `FRONTEND_ORIGINS` env var.

**Frontend (Vite + React 18 + plain Leaflet + leaflet-draw)**
- `App.jsx`: state, sidebar, dates (default 2026-06-01..08-31), Analyze. Results are cleared
  when shapes change, and stale responses are ignored.
- `MapView.jsx`
  - Esri/OSM basemaps, draw toolbar (new outline replaces the old one and clears exclusions),
    ✂▭/✂⬠ exclude buttons on the map, Edit/Save through the sidebar, and an analysis overlay
    in pane z 350.
  - Shapes use `interactive:false` so clicks inside an outline reach the map. This fixed a
    real bug.
- `Results.jsx`: inspection card + next step + checklist, layer radio buttons
  (Inspection/NDVI/NDMI/True color/None), legends, stats, data quality, limitations, raw JSON.
- `SearchBox.jsx` (Nominatim, Colorado only, 1 req/s), `polygonCheck.js` (2,000 m² min,
  5 km max side), `api.js` (`VITE_API_URL`, default :8000).

## Stage status
- Stages 1–6: done and **verified by the student**.
- Stage 7 (inspection indicator): done. The student used it and raised the infield false
  alarm, which led to the exclude tool. CLAUDE.md still shows `[~]`; mark it `[x]` once the
  student confirms.
- Stage 8 (polish, testing, docs, exclusions, GitHub)
  - Done: field tests at 4 Colorado sites, artificial-turf warning, cloudy cases,
    the exclude tool, README, `.gitignore`, and the GitHub push.
  - The ✂ exclude buttons and the interactive:false fix were verified in Chrome by Claude.
    The student has not explicitly confirmed testing them by hand, so ask.
  - Key results are in README "Testing results". For example, the ball fields read 16% low
    → 3.7% with the 4 infields excluded → "No area stands out".

## Still open / unverified
1. **Demo video**: the student will make it later (CAC requires one). Offer a script or shot list if asked.
2. **Deployment**: not done. It needs the student's hosting accounts. Risks: the public could
   use up the CDSE free quota, and the Esri tile terms need checking. Only recommended if the
   CAC rules require a live site.
3. **Phone layout**: CSS exists (`@media max-width 800px`) but has not been tested.
4. **Very large areas near 5 km**: the overlay may stretch slightly (lon/lat image on a Web Mercator map).
5. **The 0.20 NDVI cutoff** was only checked on summer 2026 Colorado turf. Other grass types
   and seasons (dormant cool-season turf) are untested.
6. Weather data was skipped (it was optional in the spec).

## Saving future changes to GitHub
```powershell
cd D:\Lavi\SpectralTurf
git add .
git status          # make sure backend/.env is NOT listed
git commit -m "What changed"
git push
```
If `.env` is ever pushed, the student must delete and recreate the OAuth client in the
Copernicus dashboard. Deleting the file from GitHub is not enough.

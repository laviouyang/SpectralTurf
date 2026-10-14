# SpectralTurf AI

**Find the parts of a sports field that may need a closer look, using real Sentinel-2 satellite data.**

A Congressional App Challenge 2026 project. You search for a park or school in Colorado, draw an
outline around the turf, and the app downloads real satellite measurements for that exact area.
It calculates two vegetation indices (NDVI and NDMI), shows them as color maps over the field, and
points out spots that are notably less green than the rest of the field, so a person knows **where to
go and look**.

> **What it does not do:** it does not diagnose plant disease, prove drought, say how much to water,
> or control sprinklers. A satellite can show *that* a spot is less green, not *why*.

---

## How it works

```
Browser (React + Leaflet)                 Backend (Python FastAPI)                 Copernicus Data Space
------------------------------            --------------------------------         ----------------------
1. Search a place  ──► OpenStreetMap
                       Nominatim
2. Draw an outline (GeoJSON polygon)
3. Click Analyze  ─────────────────────►  4. Check the polygon
                                          5. Catalog API: find least-cloudy  ───►   Sentinel-2 L2A
                                             image in the date range               scene list
                                          6. Process API: download raw bands ───►   B02 B03 B04 B08
                                             for that day, inside the polygon       B8A B11 SCL
                                          7. Remove cloud/shadow pixels (SCL)
                                          8. NDVI, NDMI, statistics, warnings,
                                             inspection rule, map pictures
9. Show results, color maps, legend ◄────
```

The secret login for Copernicus lives **only in the backend** (`backend/.env`). The website never
sees it.

---

## Installation

You need **Python 3.11+** and **Node.js 20+** (the project was built with Python 3.13 and Node 24 on
Windows). The commands below are for Windows PowerShell.

### 1. Backend

```powershell
cd backend
python -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass   # lets PowerShell run the venv script
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment variables (Copernicus login)

1. Create a free account at the [Copernicus Data Space Ecosystem](https://dataspace.copernicus.eu/).
2. Open the [Sentinel Hub dashboard](https://shapps.dataspace.copernicus.eu/dashboard/) →
   **User settings** → **OAuth clients** → **Create**.
3. Copy `backend/.env.example` to `backend/.env` and fill in your values:

| Variable | Required | Meaning |
|---|---|---|
| `CDSE_CLIENT_ID` | yes | OAuth client ID from the dashboard |
| `CDSE_CLIENT_SECRET` | yes | OAuth client secret (keep private) |
| `FRONTEND_ORIGINS` | no | Website addresses allowed to call the backend. Default: `http://localhost:5173,http://127.0.0.1:5173` |

`.env` is listed in `.gitignore`, so it is never uploaded to GitHub.

The frontend has one optional setting, `VITE_API_URL` (where the backend runs). The default is
`http://localhost:8000`.

### 3. Frontend

```powershell
cd frontend
npm.cmd install
```

(`npm.cmd` instead of `npm` avoids Windows' "running scripts is disabled" error.)

---

## Running the app

Use two PowerShell windows.

**Window 1, backend:**
```powershell
cd backend
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
venv\Scripts\activate
uvicorn main:app --reload
```
API documentation: http://localhost:8000/docs

**Window 2, website:**
```powershell
cd frontend
npm.cmd run dev
```
Open **http://localhost:5173**.

**Using it:** search for a place → zoom to the field → draw a polygon or rectangle around the
turf → use **Exclude a rectangle / polygon** to cut out anything inside that is not supposed to be
grass (dirt infields, tracks, paths) → choose dates → **Analyze**.

**Why exclusions are drawn by the user:** to the satellite, a dirt infield and a patch of dead grass
look almost the same. If the app ignored "dirt-looking" pixels automatically, it would also hide dead
grass, which is exactly what it is meant to find. So the user says what *should* be turf, and the
satellite measures how green it *is*. Excluded pixels are treated exactly like pixels outside the
outline (a pixel is excluded if its center falls inside an excluded shape).

### Tests

```powershell
cd backend
python test_indices.py
```
These tests need no internet or login. They check the index math, cloud masking, the
insufficient-evidence rule, pixels outside the outline, data-quality warnings, map colors, and the
inspection rule.

---

## The science

| Index | Formula | Bands (resolution) | What it measures |
|---|---|---|---|
| **NDVI** | (B08 − B04) / (B08 + B04) | near-infrared, red (10 m) | Greenness: living leaves reflect much more near-infrared than red |
| **NDMI** | (B8A − B11) / (B8A + B11) | narrow near-infrared, shortwave infrared (20 m) | Leaf water: water in leaves absorbs shortwave infrared |

* **Cloud masking:** Sentinel-2 L2A includes a Scene Classification Layer (SCL) for every pixel.
  Pixels classed as no data, saturated, dark/shadow, cloud shadow, cloud (medium/high), thin cirrus,
  or snow are removed. The scene's overall cloud percentage is for a whole ~110 km tile, so this
  per-pixel step is still needed.
* **Only real values:** if a calculation is impossible (for example, dividing by zero), the pixel is
  marked "no value", never filled in with a guess.
* **Resolution:** the 20 m bands are copied into 2×2 blocks on the 10 m grid (nearest neighbor).
  This adds no detail, and the map shows NDMI as blocks so it doesn't look sharper than it is.
* **Map pictures** are made from exactly the same pixels as the statistics, and are drawn as sharp
  squares (no smoothing).

### "May warrant inspection" indicator

A preliminary, rule-based comparison of each part of a field with the rest of the **same field on
the same day**:

1. Skip the outer ring of pixels (they mix turf with whatever is outside the outline).
2. Find the field's median NDVI.
3. A pixel is **notably low** if its NDVI is more than **0.20** below that median.
4. The field is flagged if notably low pixels are at least **5%** of the checked turf and at
   least **5 pixels** (500 m²).

**Why 0.20:** on turf that looked uniformly healthy at Village Greens (2026-08-05), NDVI varied
from pixel to pixel by about 0.05–0.08 (standard deviation), so 0.20 is roughly three times
normal variation.

### Project choices (not published standards)

| Setting | Value | Where |
|---|---|---|
| Minimum clear pixels for results | 20 (2,000 m²) | `indices.py` `MIN_VALID_PIXELS` |
| Largest area | 5 km per side | `sentinel.py` `MAX_PIXELS_PER_SIDE` |
| Notably low NDVI | 0.20 below field median | `indices.py` `LOW_NDVI_MARGIN` |
| Flag a field | ≥5% and ≥5 pixels | `indices.py` `FLAG_MIN_FRACTION`, `FLAG_MIN_PIXELS` |
| Warnings | <80% clear, tile >10% cloudy, <20 NDMI measurements, median NDVI <0.3 | `indices.py` `WARN_*` |
| Map color scales | NDVI 0→0.8, NDMI −0.4→0.4 | `render.py` |

---

## Limitations

* **Resolution:** NDVI pixels are 10 m × 10 m and NDMI pixels are 20 m × 20 m. Small dry patches
  can be missed.
* **Mixed pixels:** a pixel can contain turf plus dirt, pavement, trees, or cars. A parking lot
  with trees measured NDVI ≈ 0.3, a bare one ≈ 0.1.
* **One snapshot:** each analysis uses one satellite image. It is not a trend over time.
* **Cloud masking is imperfect:** thin haze or small shadows can slip through. Check the
  true-color layer.
* **Within-field comparison only:** a problem affecting the **whole** field evenly will not stand
  out (a uniformly dry meadow returned "No area stands out").
* **Artificial turf** looks green in photos but has low NDVI (Cherry Creek HS stadium: 0.17). The
  app warns about this but cannot evaluate artificial turf.
* **Not a diagnosis:** dormancy, mowing, wear, disease, and irrigation problems can look the same
  from space. The app shows where to look; a person decides what is wrong.
* **Map alignment:** the analysis picture is placed using longitude/latitude. This is accurate for
  field-sized areas, but may stretch slightly near the 5 km maximum.

---

## Testing results

Real data, summer 2026 (June 1 – August 31; the app picks the least-cloudy image):

| Field | Image date | Clear pixels | NDVI | NDMI | Indicator |
|---|---|---|---|---|---|
| Village Greens Park, Greenwood Village (turf only) | 2026-08-05 | 112/112 | 0.70 | 0.20 | No area stands out |
| Village Greens, ball fields **including** dirt infields | 2026-08-05 | n/a | 0.69 median | n/a | May warrant inspection: pink exactly on the 4 infields |
| Same ball fields, 4 infields **excluded** | 2026-08-05 | 561/561 (175 excluded) | n/a | n/a | No area stands out (4% low, was 15–16%) |
| Dick's Sporting Goods Park, Commerce City (south fields) | 2026-08-20 | 306/306 | 0.84 | 0.26 | No area stands out |
| Dick's Sporting Goods Park (east fields) | 2026-08-20 | 289/289 | 0.75 | 0.27 | No area stands out |
| Memorial Park, Colorado Springs (NW field) | 2026-08-05 | 160/160 | 0.88 | 0.29 | No area stands out |
| Memorial Park (middle field) | 2026-08-05 | 208/208 | 0.90 | 0.33 | No area stands out |
| Cherry Creek HS stadium (artificial turf) | 2026-08-05 | 65/65 | 0.17 | −0.09 | Artificial-turf warning |
| Parking lot (Stage 3 check) | 2026-08-05 | 108/108 | 0.10 | −0.03 | n/a |
| Cherry Creek Reservoir (water) | 2026-08-05 | 360/360 | −0.69 | −0.55 | n/a |

**Cloudy case:** on 2026-08-13, 2026-09-07 and 2026-08-08 a cloud covered Village Greens. Every
pixel was rejected, the app reported **Insufficient evidence**, showed no averages, and drew an
all-gray map. The true-color picture showed solid white cloud.

**Polygon check:** a triangle that is half of a rectangle gave 259 pixels inside, compared with 476
for the rectangle, so only pixels inside the drawn outline are analyzed.

---

## Code map

| File | What it does |
|---|---|
| `backend/main.py` | Web server: `/api/analyze`, test endpoints, polygon checks, CORS |
| `backend/sentinel.py` | Copernicus login (cached token), Catalog search, Process API downloads |
| `backend/indices.py` | The science: NDVI, NDMI, cloud mask, excluded areas, statistics, warnings, inspection rule (no internet) |
| `backend/render.py` | Turns index values into the map pictures (display only) |
| `backend/test_indices.py` | Offline tests |
| `frontend/src/App.jsx` | Page layout, state, Analyze button |
| `frontend/src/MapView.jsx` | Leaflet map, drawing tools, analysis picture overlay |
| `frontend/src/SearchBox.jsx` | Place search (Nominatim) |
| `frontend/src/polygonCheck.js` | Area size checks before sending |
| `frontend/src/api.js` | The only file that talks to the backend |
| `frontend/src/Results.jsx` | Inspection card, legends, numbers, data quality, limitations |
| `frontend/src/leafletSetup.js` | Makes Leaflet available to the Leaflet.draw plugin |

---

## Data sources and credits

* **Satellite data:** Copernicus Sentinel-2 Level-2A, accessed through the
  [Copernicus Data Space Ecosystem](https://dataspace.copernicus.eu/) Sentinel Hub APIs.
  Contains modified Copernicus Sentinel data 2026.
* **Place search:** [OpenStreetMap Nominatim](https://nominatim.openstreetmap.org/), © OpenStreetMap
  contributors (ODbL). The app searches only when the user presses Search (at most one request per
  second), as its [usage policy](https://operations.osmfoundation.org/policies/nominatim/) requires.
* **Background maps (for drawing only, not analyzed):** Esri World Imagery (© Esri, Maxar,
  Earthstar Geographics, and the GIS User Community) and OpenStreetMap tiles.
* **Libraries:** FastAPI, NumPy, tifffile, Pillow, Requests, React, Vite, Leaflet, Leaflet.draw.
* **Further turf advice:** [Colorado State University Extension](https://extension.colostate.edu/).

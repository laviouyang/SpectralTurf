"""
main.py - The FastAPI web server for SpectralTurf AI.

Endpoints:
  GET  /api/health            -> quick "is the server running?" check
  POST /api/analyze           -> real NDVI/NDMI for a polygon drawn on the website
  GET  /api/test/truecolor    -> real Sentinel-2 true-color image for a box you choose
  GET  /api/test/indices      -> same analysis as /api/analyze, but for a box (easy to test)

Run it with:   uvicorn main:app --reload
Then open:     http://localhost:8000/docs
"""

import math
import os
from datetime import date

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

import indices
import render
import sentinel

# Load CDSE_CLIENT_ID and CDSE_CLIENT_SECRET from the .env file.
load_dotenv()

app = FastAPI(title="SpectralTurf AI backend")

# CORS: browsers block a web page from calling a different address (our page is
# on port 5173, this server is on 8000) unless the server says it's allowed.
# We allow ONLY our own frontend, not every website.
FRONTEND_ORIGINS = os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in FRONTEND_ORIGINS],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# A drawn field needs only a handful of corners; this stops absurd requests.
MAX_POLYGON_POINTS = 500
# Enough for every infield, track and path on a big sports complex.
MAX_EXCLUDED_AREAS = 30


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# The shared analysis steps (used by /api/analyze and /api/test/indices)
# ---------------------------------------------------------------------------

def run_analysis(geometry, start, end, max_cloud, exclusions=()):
    """
    1. Find the least-cloudy scene in the date range (gives a real date).
    2. Download raw B04, B08, B8A, B11, SCL for that date, inside the polygon only.
    3. Drop pixels in areas the user excluded (e.g. dirt infields).
    4. Mask clouds/shadows, compute NDVI and NDMI, and report statistics.
    5. Add data-quality warnings and map pictures made from the same pixels.
    """
    if start > end:
        raise HTTPException(status_code=400, detail="Start date must be before end date.")

    west, south, east, north = sentinel.geometry_bbox(geometry)
    try:
        # Size problems are the user's input, so they get 400 ("bad request").
        sentinel.check_box(west, south, east, north)
    except sentinel.SentinelError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        scene = sentinel.find_clearest_scene(west, south, east, north, start, end, max_cloud)
        bands = sentinel.fetch_bands(geometry, scene["date"])
    except sentinel.SentinelError as e:
        # 502 = "the server we depend on had a problem" - honest, not fake numbers.
        raise HTTPException(status_code=502, detail=str(e))

    n_excluded = indices.apply_exclusions(bands, exclusions, (west, south, east, north))

    results = indices.analyze_bands(
        bands["B04"], bands["B08"], bands["B8A"], bands["B11"], bands["SCL"], bands["dataMask"],
        b03=bands["B03"],
    )
    return {
        "observation": scene,
        # The pictures below cover exactly this box (row 0 = north edge).
        "box": {"west": west, "south": south, "east": east, "north": north},
        **results,
        "excluded": {"areas": len(exclusions), "pixels": n_excluded},
        "warnings": indices.quality_warnings(
            results, scene["tile_cloud_cover"], int(scene["date"][5:7])  # month from "YYYY-MM-DD"
        ),
        "images": render.make_images(bands),
        "color_scales": render.color_scales(),
        "source": "Copernicus Sentinel-2 Level-2A via Copernicus Data Space Ecosystem (Sentinel Hub)",
    }


def clean_polygon(geometry: dict):
    """
    Check that the website sent a sensible GeoJSON Polygon, and return a clean copy.
    Never trust input from a browser - anyone can send anything to an API.
    """
    def bad(reason):
        raise HTTPException(status_code=400, detail=f"Invalid area: {reason}")

    if geometry.get("type") != "Polygon":
        bad("it must be a GeoJSON Polygon.")
    rings = geometry.get("coordinates")
    if not isinstance(rings, list) or len(rings) != 1:
        bad("it must be one outline with no holes.")
    ring = rings[0]
    if not isinstance(ring, list) or not (4 <= len(ring) <= MAX_POLYGON_POINTS):
        bad(f"it must have between 3 and {MAX_POLYGON_POINTS - 1} corners.")

    points = []
    for point in ring:
        if (
            not isinstance(point, list)
            or len(point) != 2
            or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in point)
        ):
            bad("every corner must be [longitude, latitude].")
        lon, lat = float(point[0]), float(point[1])
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            bad("a corner is outside valid longitude/latitude ranges.")
        points.append([lon, lat])

    if points[0] != points[-1]:
        bad("the outline is not closed (first and last corner must match).")
    return {"type": "Polygon", "coordinates": [points]}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    geometry: dict = Field(..., description="GeoJSON Polygon; corners are [longitude, latitude]")
    start: date = Field(date(2026, 6, 1), description="Start date (YYYY-MM-DD)")
    end: date = Field(date(2026, 8, 31), description="End date (YYYY-MM-DD)")
    max_cloud: int = Field(30, ge=0, le=100, description="Max tile cloud cover, %")
    exclude: list[dict] = Field(
        default_factory=list,
        description="GeoJSON Polygons inside the outline that are not turf (e.g. dirt infields)",
    )


@app.post("/api/analyze")
def analyze(request: AnalyzeRequest):
    geometry = clean_polygon(request.geometry)
    if len(request.exclude) > MAX_EXCLUDED_AREAS:
        raise HTTPException(status_code=400, detail=f"At most {MAX_EXCLUDED_AREAS} excluded areas.")
    exclusions = [clean_polygon(shape) for shape in request.exclude]
    return run_analysis(geometry, request.start, request.end, request.max_cloud, exclusions)


@app.get("/api/test/truecolor")
def test_true_color(
    west: float = Query(..., description="Western longitude, e.g. -104.90"),
    south: float = Query(..., description="Southern latitude, e.g. 39.61"),
    east: float = Query(..., description="Eastern longitude, e.g. -104.89"),
    north: float = Query(..., description="Northern latitude, e.g. 39.62"),
    start: date = Query(date(2026, 6, 1), description="Start date (YYYY-MM-DD)"),
    end: date = Query(date(2026, 8, 31), description="End date (YYYY-MM-DD)"),
    max_cloud: int = Query(30, ge=0, le=100, description="Max scene cloud cover, %"),
):
    if start > end:
        raise HTTPException(status_code=400, detail="Start date must be before end date.")

    try:
        png = sentinel.fetch_true_color(west, south, east, north, start, end, max_cloud)
    except sentinel.SentinelError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return Response(content=png, media_type="image/png")


@app.get("/api/test/indices")
def test_indices(
    west: float = Query(..., description="Western longitude"),
    south: float = Query(..., description="Southern latitude"),
    east: float = Query(..., description="Eastern longitude"),
    north: float = Query(..., description="Northern latitude"),
    start: date = Query(date(2026, 6, 1), description="Start date (YYYY-MM-DD)"),
    end: date = Query(date(2026, 8, 31), description="End date (YYYY-MM-DD)"),
    max_cloud: int = Query(30, ge=0, le=100, description="Max tile cloud cover, %"),
):
    """Same analysis as /api/analyze, using a box turned into a polygon."""
    if not (west < east and south < north):
        raise HTTPException(status_code=400, detail="West must be less than east, and south less than north.")
    geometry = sentinel.box_polygon(west, south, east, north)
    return run_analysis(geometry, start, end, max_cloud)

"""
main.py - The FastAPI web server for SpectralTurf AI.

Endpoints:
  GET  /api/health            -> quick "is the server running?" check
  POST /api/analyze           -> real NDVI/NDMI for a polygon drawn on the website
  GET  /api/test/truecolor    -> real Sentinel-2 true-color image for a box you choose
  GET  /api/test/indices      -> same analysis as /api/analyze, but for a box (easy to test)
  POST /api/auth/signup, /api/auth/login, /api/auth/logout, GET /api/auth/me -> accounts
  GET  /api/history, DELETE /api/history/{id} -> a logged-in user's saved analyses
  POST /api/ai/my-fields      -> Stage 10 Step 8: the user's saved fields ranked by the AI check

Run it with:   uvicorn main:app --reload
Then open:     http://localhost:8000/docs
"""

import math
import os
from datetime import date

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

import accounts
import indices
import predict
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
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
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
# Accounts: who is making this request?
# ---------------------------------------------------------------------------

def get_db():
    """Open the accounts database for one request, and always close it afterwards."""
    db = accounts.connect()
    try:
        yield db
    finally:
        db.close()


def token_from(authorization):
    """The browser sends "Authorization: Bearer <token>" when someone is logged in."""
    if authorization and authorization.startswith("Bearer "):
        return authorization[len("Bearer "):].strip()
    return None


def current_user(authorization: str | None = Header(None), db=Depends(get_db)):
    """The logged-in user, or None for a visitor. Analyzing works either way."""
    return accounts.user_for_token(db, token_from(authorization))


def required_user(user=Depends(current_user)):
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in first.")
    return user


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
    name: str = Field("", max_length=200, description="Field name for the history (logged-in users)")


@app.post("/api/analyze")
def analyze(request: AnalyzeRequest, user=Depends(current_user), db=Depends(get_db)):
    geometry = clean_polygon(request.geometry)
    if len(request.exclude) > MAX_EXCLUDED_AREAS:
        raise HTTPException(status_code=400, detail=f"At most {MAX_EXCLUDED_AREAS} excluded areas.")
    exclusions = [clean_polygon(shape) for shape in request.exclude]
    result = run_analysis(geometry, request.start, request.end, request.max_cloud, exclusions)

    # Logged in? Save a summary of this real result to the user's history.
    # Saving problems never hide the analysis itself.
    if user:
        try:
            result["saved_id"] = accounts.save_analysis(
                db, user["id"], request.name, geometry, exclusions, request.start, request.end, result
            )
        except accounts.AccountError as e:
            result["save_error"] = str(e)
    return result


class Credentials(BaseModel):
    username: str = Field(..., max_length=100)
    password: str = Field(..., max_length=1000)


@app.post("/api/auth/signup")
def sign_up(body: Credentials, db=Depends(get_db)):
    try:
        token = accounts.sign_up(db, body.username.strip(), body.password)
    except accounts.AccountError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"token": token, "user": accounts.user_for_token(db, token)}


@app.post("/api/auth/login")
def log_in(body: Credentials, db=Depends(get_db)):
    try:
        token = accounts.log_in(db, body.username.strip(), body.password)
    except accounts.AccountError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return {"token": token, "user": accounts.user_for_token(db, token)}


@app.post("/api/auth/logout")
def log_out(authorization: str | None = Header(None), db=Depends(get_db)):
    token = token_from(authorization)
    if token:
        accounts.log_out(db, token)
    return {"status": "logged out"}


@app.get("/api/auth/me")
def me(user=Depends(required_user)):
    return {"user": user}


@app.get("/api/history")
def history(user=Depends(required_user), db=Depends(get_db)):
    return {"analyses": accounts.list_analyses(db, user["id"])}


@app.delete("/api/history/{analysis_id}")
def delete_history_item(analysis_id: int, user=Depends(required_user), db=Depends(get_db)):
    if not accounts.delete_analysis(db, user["id"], analysis_id):
        raise HTTPException(status_code=404, detail="That saved analysis was not found.")
    return {"status": "deleted"}


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


# ---------------------------------------------------------------------------
# Stage 10: AI weather-aware checks (backend/predict.py). Added on; nothing above changed.
# ---------------------------------------------------------------------------

def check_as_of(as_of):
    """The AI checks use real data up to "as of", so it can't be in the future."""
    if as_of > date.today():
        raise HTTPException(status_code=400, detail="'As of' can't be in the future.")
    if as_of < date(2019, 1, 1):
        raise HTTPException(status_code=400, detail="'As of' must be 2019 or later.")


class MyFieldsRequest(BaseModel):
    as_of: date = Field(default_factory=date.today, description="Check the fields as of this day")


@app.post("/api/ai/my-fields")
def my_fields(body: MyFieldsRequest, user=Depends(current_user), db=Depends(get_db)):
    """Step 8: rank the logged-in user's OWN saved fields. Only READS the accounts database."""
    if user is None:
        raise HTTPException(status_code=401, detail="Log in and analyze fields to see your ranked list.")
    check_as_of(body.as_of)
    saved = accounts.list_analyses(db, user["id"])  # only this user's rows
    try:
        return predict.rank_my_fields(saved, body.as_of)
    except predict.PredictError as e:
        raise HTTPException(status_code=502, detail=str(e))

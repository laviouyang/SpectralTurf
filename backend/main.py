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
  GET  /api/ai/what-if/limits, POST /api/ai/what-if -> Step 9: "What if?" weather scenarios (POST: login)
  POST /api/ai/weather-check  -> Steps 6-7: AI Weather Check for the field on the map (login)
  POST /api/ai/ask            -> Step 10: "Ask SpectralTurf" AI assistant (Gemini + read-only tools) (login)
  POST /api/fields            -> Version 2: save a field to My Fields WITHOUT analyzing it (login)
  POST /api/photo/classify    -> Stage 11: "Check a photo" - which photo category it LOOKS MOST LIKE,
                                 not a diagnosis (login; photo_classifier.py; photo never stored)

Public-website safety limits (login lockout, daily caps) are at the end of this file
(backend/limits.py); they are only on when deployed (Render) or with USAGE_LIMITS=on.

Run it with:   uvicorn main:app --reload
On Render:     uvicorn main:app --host 0.0.0.0 --port $PORT   (see docs/DEPLOY_RENDER.md)
Then open:     http://localhost:8000/docs
"""

import math
import os
from datetime import date

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

import accounts
import assistant
import photo_classifier  # added 2026-11-26 (Stage 11 "Check a photo"; model loads on first photo)
import indices
import field_shape  # 2026-11-27: a field can be several separate pieces
import predict
import regions
import render
import saved_fields
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


def clean_field(geometry: dict):
    """
    Added 2026-11-27 (student request): a FIELD may be one outline (Polygon, checked by
    clean_polygon exactly as before) or several separate pieces (MultiPolygon), e.g. park fields
    with walkways between them. Rules are in field_shape.py. Excluded areas stay single Polygons.
    """
    def bad(reason):
        raise HTTPException(status_code=400, detail=f"Invalid area: {reason}")

    return field_shape.clean_field(geometry, clean_polygon, bad)


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
    geometry: dict = Field(..., description="GeoJSON Polygon, or MultiPolygon = a field in several pieces; corners are [longitude, latitude]")
    start: date = Field(date(2026, 6, 1), description="Start date (YYYY-MM-DD)")
    end: date = Field(date(2026, 8, 31), description="End date (YYYY-MM-DD)")
    max_cloud: int = Field(30, ge=0, le=100, description="Max tile cloud cover, %")
    exclude: list[dict] = Field(
        default_factory=list,
        description="GeoJSON Polygons inside the outline that are not turf (e.g. dirt infields)",
    )
    name: str = Field("", max_length=200, description="Field name for the history (logged-in users)")
    # Added 2026-11-25 (Version 2): saving is now a separate choice ("Save & analyze" vs
    # "Analyze"). The website always sends it; leaving it out keeps the old behavior (save).
    save: bool = Field(True, description="Logged in: save a summary of this result to your history")
    # Added 2026-11-25: the field's grass region (1-7, detected on the map or changed by the user).
    # Only a LABEL on the result: the analysis math is exactly the same in every region.
    region: int | None = Field(None, ge=1, le=7, description="Grass region 1-7 (optional; detected if left out)")


@app.post("/api/analyze")
def analyze(request: AnalyzeRequest, user=Depends(current_user), db=Depends(get_db)):
    geometry = clean_field(request.geometry)
    if len(request.exclude) > MAX_EXCLUDED_AREAS:
        raise HTTPException(status_code=400, detail=f"At most {MAX_EXCLUDED_AREAS} excluded areas.")
    exclusions = [clean_polygon(shape) for shape in request.exclude]
    result = run_analysis(geometry, request.start, request.end, request.max_cloud, exclusions)
    # Grass region label + "validated or not" (regions.py). Numbers above are unchanged.
    result["grass_region"] = regions.resolve(request.region, geometry)

    # Logged in and asked to save ("Save & analyze")? Save a summary of this real result.
    # Saving problems never hide the analysis itself.
    if user and request.save:
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


# Version 2 (2026-11-25): "Save" and "Analyze" are separate buttons. Saving keeps only the
# outline, excluded areas and name (no satellite numbers - nothing was measured).
class SaveFieldRequest(BaseModel):
    name: str = Field(..., max_length=200, description="The field's name in My Fields")
    geometry: dict = Field(..., description="GeoJSON Polygon or MultiPolygon, same rules as /api/analyze")
    exclude: list[dict] = Field(default_factory=list, description="Excluded areas inside the outline")


@app.post("/api/fields")
def save_field(body: SaveFieldRequest, user=Depends(required_user), db=Depends(get_db)):
    geometry = clean_field(body.geometry)
    if len(body.exclude) > MAX_EXCLUDED_AREAS:
        raise HTTPException(status_code=400, detail=f"At most {MAX_EXCLUDED_AREAS} excluded areas.")
    exclusions = [clean_polygon(shape) for shape in body.exclude]
    try:
        saved_id = saved_fields.save_field(db, user["id"], body.name, geometry, exclusions)
    except accounts.AccountError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "saved", "saved_id": saved_id}


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


@app.get("/api/ai/what-if/limits")
def what_if_limits(as_of: date | None = None):
    """Step 9: slider ranges, from what the AI saw in training. With as_of (added 2026-11-07),
    the temperature range is limited to what actually happened in that month in 2019-2025."""
    try:
        return predict.what_if_limits(month=as_of.month if as_of else None)
    except predict.PredictError as e:
        raise HTTPException(status_code=503, detail=str(e))


class WhatIfRequest(BaseModel):
    geometry: dict | None = Field(None, description="The field on screen (GeoJSON Polygon or MultiPolygon), optional")
    exclude: list[dict] = Field(default_factory=list)
    as_of: date = Field(default_factory=date.today)
    dry_days: int = Field(..., ge=0, le=predict.WHAT_IF_DAYS, description="Last X of the 14 days have no rain")
    rain_mm: float = Field(..., ge=0, le=500, description="Total rain over the other days, mm")
    avg_high_c: float = Field(..., ge=-20, le=50, description="High temperature every day, °C")
    include_my_fields: bool = Field(False, description="Also run it for my saved fields (logged in)")


@app.post("/api/ai/what-if")
def what_if(body: WhatIfRequest, user=Depends(required_user), db=Depends(get_db)):
    """Step 9: run the trained model with the user's made-up weather. Only READS saved fields.
    Login required since 2026-11-25 (Version 2), like the website's AI Check tab."""
    check_as_of(body.as_of)
    if body.dry_days >= predict.WHAT_IF_DAYS and body.rain_mm > 0:
        raise HTTPException(status_code=400, detail=f"With {predict.WHAT_IF_DAYS} days without rain, "
                                                    "the rain amount must be 0.")
    try:
        limits = predict.what_if_limits(month=body.as_of.month)
        scenario = {"dry_days": body.dry_days, "rain_mm": body.rain_mm, "avg_high_c": body.avg_high_c}
        answer = {"limits": limits, "label": predict.WHAT_IF_LABEL, "pattern_note": predict.PATTERN_NOTE,
                  "accuracy_note": predict.ACCURACY_NOTE, "credits": predict.CREDITS}
        if body.geometry is not None:
            geometry = clean_field(body.geometry)
            if len(body.exclude) > MAX_EXCLUDED_AREAS:
                raise HTTPException(status_code=400, detail=f"At most {MAX_EXCLUDED_AREAS} excluded areas.")
            exclusions = [clean_polygon(shape) for shape in body.exclude]
            try:
                sentinel.check_box(*sentinel.geometry_bbox(geometry))
            except sentinel.SentinelError as e:
                raise HTTPException(status_code=400, detail=str(e))
            answer["current_field"] = predict.what_if(geometry, exclusions, body.as_of, scenario)
        if body.include_my_fields:
            if user is None:
                raise HTTPException(status_code=401, detail="Log in to include My Fields.")
            answer["my_fields"] = predict.what_if_my_fields(
                accounts.list_analyses(db, user["id"]), body.as_of, scenario)
        return answer
    except predict.PredictError as e:
        raise HTTPException(status_code=502, detail=str(e))


# Stage 10 Steps 6-7 (2026-11-07): AI Weather Check for the field on the map.
class WeatherCheckRequest(BaseModel):
    geometry: dict = Field(..., description="The field outline (GeoJSON Polygon or MultiPolygon), same as /api/analyze")
    exclude: list[dict] = Field(default_factory=list, description="Excluded areas (become holes)")
    as_of: date = Field(default_factory=date.today, description="Check the field as of this day")


@app.post("/api/ai/weather-check")
def weather_check(body: WeatherCheckRequest, user=Depends(required_user)):
    """Expected vs actual NDVI for the latest clear image, next-week risk, and (when there has
    been no clear image for 7+ days) the AI's cloudy-day estimate. Uses no account data.
    Login required since 2026-11-25 (Version 2), like the website's AI Check tab."""
    check_as_of(body.as_of)
    geometry = clean_field(body.geometry)
    if len(body.exclude) > MAX_EXCLUDED_AREAS:
        raise HTTPException(status_code=400, detail=f"At most {MAX_EXCLUDED_AREAS} excluded areas.")
    exclusions = [clean_polygon(shape) for shape in body.exclude]
    try:
        sentinel.check_box(*sentinel.geometry_bbox(geometry))
    except sentinel.SentinelError as e:
        raise HTTPException(status_code=400, detail=str(e))
    try:
        return predict.weather_check(geometry, exclusions, body.as_of)
    except predict.PredictError as e:
        raise HTTPException(status_code=502, detail=str(e))


# Stage 10 Step 10 (2026-11-15): "Ask SpectralTurf" AI assistant (backend/assistant.py).
class AskRequest(BaseModel):
    question: str = Field(..., max_length=5000, description="The user's question")
    geometry: dict | None = Field(None, description="The field on screen (GeoJSON Polygon or MultiPolygon), optional")
    exclude: list[dict] = Field(default_factory=list)
    start: date | None = Field(None, description="Date range of the analysis on screen")
    end: date | None = None
    max_cloud: int = Field(30, ge=0, le=100)
    as_of: date = Field(default_factory=date.today)
    # Added 2026-11-22: one optional photo (base64 JPEG/PNG/WebP). Re-saved without metadata, never stored.
    photo: str | None = Field(None, max_length=12_000_000, description="Optional photo, base64")
    # Added 2026-11-25 (Version 2): the ONE field the questions are about: "screen" (the field
    # on the map) or the id of one of your saved analyses. Optional, so old requests still work.
    field: str | None = Field(None, max_length=40, description="'screen' or a saved analysis id")
    # Added 2026-11-25: the picked field's grass region (1-7); detected from its outline if left out.
    region: int | None = Field(None, ge=1, le=7, description="Grass region 1-7 of the picked field")


@app.post("/api/ai/ask")
def ask(body: AskRequest, request: Request, user=Depends(required_user), db=Depends(get_db)):
    """Answer a question with Gemini + read-only tools: the user's OWN saved fields (read only)
    + the field on screen. Login required since 2026-11-25 (Version 2), like the website's Ask AI
    tab (visitors get 401). Gemini never gets the username or the field names. Problems give a
    friendly 503; the rest of the app is unaffected."""
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Please type a question.")
    if len(question) > assistant.MAX_QUESTION_CHARS:
        raise HTTPException(status_code=400,
                            detail=f"Questions can be at most {assistant.MAX_QUESTION_CHARS} characters.")
    check_as_of(body.as_of)
    # Changed 2026-11-26 (student request): the photo is NO LONGER sent to Gemini. Our own photo
    # classifier runs on it here, and Gemini only gets the result (percentages, top class,
    # Uncertain) through the classify_photo tool. The photo itself is never stored.
    photo_result = None
    if body.photo:
        try:
            raw = assistant.photo_bytes(body.photo)
            photo_result = photo_classifier.classify(raw)
        except assistant.AssistantError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except photo_classifier.PhotoError as e:
            raise HTTPException(status_code=e.status, detail=str(e))
    screen, analyze_screen = None, None
    if body.geometry is not None:
        geometry = clean_field(body.geometry)
        if len(body.exclude) > MAX_EXCLUDED_AREAS:
            raise HTTPException(status_code=400, detail=f"At most {MAX_EXCLUDED_AREAS} excluded areas.")
        exclusions = [clean_polygon(shape) for shape in body.exclude]
        try:
            sentinel.check_box(*sentinel.geometry_bbox(geometry))
        except sentinel.SentinelError as e:
            raise HTTPException(status_code=400, detail=str(e))
        screen = {"geometry": geometry, "exclusions": exclusions, "start": body.start, "end": body.end,
                  "max_cloud": body.max_cloud}
        if body.start and body.end:
            def analyze_screen():
                try:  # the same analysis as the Analyze button (real data, nothing saved)
                    return run_analysis(geometry, body.start, body.end, body.max_cloud, exclusions)
                except HTTPException as e:
                    raise assistant.ToolDataError(f"The analysis failed: {e.detail}")

    who = f"user:{user['id']}" if user else f"ip:{request.client.host if request.client else 'unknown'}"
    try:
        assistant.limiter.check(who)
    except assistant.AssistantError as e:
        raise HTTPException(status_code=429, detail=str(e))
    saved = accounts.list_analyses(db, user["id"]) if user else []  # only this user's rows (read only)
    ctx = assistant.Context(user is not None, saved, screen, analyze_screen, body.as_of)
    ctx.photo_result = photo_result
    if body.field is not None:  # Version 2: answer only about the field the user picked
        picked = body.field.strip().lower()
        if picked == "screen":
            if screen is None:
                raise HTTPException(status_code=400, detail="Draw a field on the map first.")
        else:
            if user is None:
                raise HTTPException(status_code=401, detail="Log in to ask about your saved fields.")
            label = ctx.label_for_saved_id(int(picked)) if picked.isdigit() else None
            if label is None:
                raise HTTPException(status_code=404, detail="That field is not in your saved fields.")
            picked = label
        ctx.focus = picked
    # The grass region of the field the questions are about (tools then include it).
    if ctx.focus == "screen" or (ctx.focus is None and screen is not None):
        ctx.grass_region = regions.resolve(body.region, screen["geometry"])
    elif ctx.focus:
        ctx.grass_region = regions.resolve(body.region, ctx.fields[ctx.focus]["geometry"])
    try:
        return assistant.ask(question, ctx)
    except assistant.AssistantError as e:
        raise HTTPException(status_code=503, detail=str(e))


# Stage 11 on the website (2026-11-26): "Check a photo" (backend/photo_classifier.py).
# The photo is sent as the request body itself (Content-Type image/jpeg, image/png or image/webp),
# so no extra upload library is needed. It is re-saved without metadata, classified, and dropped.
photo_limiter = assistant.RateLimiter(per_minute=10, per_day=10**9)  # per minute, like Ask; daily caps in limits.py


@app.post("/api/photo/classify")
async def classify_photo(request: Request, user=Depends(required_user)):
    """Which of our 6 photo categories the photo LOOKS MOST LIKE, with a percentage for each,
    or "Uncertain — inspect in person" below the cutoff. Not a diagnosis. Login required."""
    size = request.headers.get("content-length")
    if size and size.isdigit() and int(size) > photo_classifier.MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail=f"The photo is too big "
                            f"(max {photo_classifier.MAX_PHOTO_BYTES // (1024 * 1024)} MB).")
    raw = await request.body()
    try:
        photo_limiter.check(f"user:{user['id']}")
    except assistant.AssistantError as e:
        raise HTTPException(status_code=429, detail=str(e).replace("questions", "photo checks"))
    try:
        # Runs in a worker thread so the server keeps answering other requests meanwhile.
        return await run_in_threadpool(photo_classifier.classify, raw)
    except photo_classifier.PhotoError as e:
        raise HTTPException(status_code=e.status, detail=str(e))


# ---------------------------------------------------------------------------
# Public-website safety limits (added 2026-11-22, backend/limits.py). Added on; nothing above
# changed. Only active on Render or with USAGE_LIMITS=on, so running locally is unchanged.
# Limits reached -> HTTP 429 with a friendly message (the website shows "detail" as-is).
# ---------------------------------------------------------------------------

from fastapi.responses import JSONResponse  # noqa: E402

import limits  # noqa: E402


def limits_user_id(request):
    """The logged-in user's id (READ ONLY lookup of the session token), or None for a visitor."""
    token = token_from(request.headers.get("authorization"))
    if not token:
        return None
    db = accounts.connect()
    try:
        user = accounts.user_for_token(db, token)
    finally:
        db.close()
    return user["id"] if user else None


@app.middleware("http")
async def usage_limits(request: Request, call_next):
    if not limits.enabled() or request.method == "OPTIONS":
        return await call_next(request)
    path = request.url.path.rstrip("/")
    address = limits.client_address(request)

    if path == "/api/auth/login" and request.method == "POST":
        username = limits.username_from(await request.body())
        message = limits.login_lock_message(username, address)
        if message:
            return JSONResponse({"detail": message}, status_code=429)
        response = await call_next(request)
        if response.status_code == 401:
            limits.login_failed(username, address)
        elif response.status_code == 200:
            limits.login_succeeded(username)
        return response

    kind = limits.KIND_OF_PATH.get(path)
    if kind is None:
        return await call_next(request)
    user_id = None if kind == "signup" else limits_user_id(request)
    who = f"user:{user_id}" if user_id else f"ip:{address}"
    try:
        limits.check(kind, who, logged_in=user_id is not None)
    except limits.LimitReached as e:
        return JSONResponse({"detail": str(e)}, status_code=429)
    response = await call_next(request)
    # Count it unless the request was turned down (bad input, not logged in, ...), since those
    # never reach Copernicus or Gemini.
    if response.status_code < 400 or response.status_code >= 500:
        limits.record(kind, who)
    return response

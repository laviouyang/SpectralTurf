"""
predict.py - Stage 10: use the trained AI model (ml/model/ndvi_model.joblib) inside the app.

  weather_check(field, as_of)  -> "Did the weather explain the latest change?" + next-week risk
  rank_my_fields(db, user)     -> Step 8: a logged-in user's saved fields, ranked by priority
  what_if(field, scenario)     -> Step 9: the model run with made-up weather the user chooses

How the weather check works, for one field on one day ("as of"):
  1. Real NDVI history for the field: the Copernicus Statistical API (same evalscript and
     80%-clear rule as the training data in ml/get_ndvi_history.py), last 60 days.
  2. Real weather: Open-Meteo. Past dates use the same historical archive as the training data;
     recent dates (and the next 7 days) use Open-Meteo's forecast service.
  3. "Expected NDVI": the model predicts the latest clear image from the one before it plus the
     weather in between. Actual more than the cutoff (2 x the model's typical error) below
     expected -> "Weather does NOT explain this".
  4. "Next-week risk": the model predicts NDVI 7 days after "as of" from the latest image and
     the weather forecast. Predicted drop >= cutoff -> High, >= typical error -> Medium, else Low.
     These levels are PROJECT CHOICES tied to the model's own error, not published standards.

Honesty rules (CLAUDE.md, Stage 10):
  - Outside April-October: "Off-season - grass may be dormant." and no numbers.
  - If any model input is outside what the model saw in training (e.g. a 30-day-old image,
    or a heat wave hotter than any in 2019-2025), we say so and give NO prediction.
  - Missing data -> "Insufficient evidence", never filled in.
  - The output is a prioritization signal, not a diagnosis or a watering instruction.

Respecting limits: every download is cached in backend/ai_cache/ and never repeated; processing
units (PU) are counted per day and requests stop at DAILY_PU_BUDGET.
"""

import hashlib
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import joblib
import numpy as np
import requests

import sentinel

BACKEND_DIR = Path(__file__).resolve().parent
ML_DIR = BACKEND_DIR.parent / "ml"
sys.path.insert(0, str(ML_DIR))
import train  # noqa: E402,F401  (the model file refers to train.ChangeModel)
from build_dataset import weather_features  # noqa: E402
from get_ndvi_history import (  # noqa: E402  (same science as the training data)
    EVALSCRIPT, MIN_CLEAR_FRACTION, STATISTICS_URL, rows_from_answer, ten_meters_in_degrees,
)

MODEL_FILE = ML_DIR / "model" / "ndvi_model.joblib"
WEATHER_HISTORY_DIR = ML_DIR / "data" / "weather"
CACHE_DIR = BACKEND_DIR / "ai_cache"

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_VARIABLES = ["precipitation_sum", "temperature_2m_max", "et0_fao_evapotranspiration"]

# Project choices (not published standards):
GROWING_MONTHS = range(4, 11)  # April-October
LOOKBACK_DAYS = 60             # how far back we look for clear satellite images
DAYS_AHEAD = 7                 # "next week"
ARCHIVE_DELAY_DAYS = 6         # the Open-Meteo archive is a few days behind; newer -> forecast service
MAX_RANKED_FIELDS = 10         # My Fields: cost limit (each field = 1 small Copernicus request)
DAILY_PU_BUDGET = 100          # Copernicus processing units this server may spend per day
WHAT_IF_DAYS = 14              # what-if scenarios cover 14 days (the model saw gaps of 1-20 days)

OFF_SEASON = "Off-season — grass may be dormant."
LABEL = "AI estimate based on satellite + weather history. Confirm in person."
CREDITS = ["Weather data by Open-Meteo.com",
           "Satellite data: Copernicus Sentinel-2 (Copernicus Data Space Ecosystem)"]
# Real results from ml/results.md (evaluate.py, 2026-11-01). Update if the model is retrained.
ACCURACY_NOTE = ("Tested on 2025 (a year it never saw) and on fields it never saw: overall it was "
                 "about as accurate as simply assuming 'same as last time' (typical error about "
                 "0.05 NDVI). On unseen fields it was reliably better (about 13%) when the last "
                 "clear image was 8 or more days old. See ml/results.md.")


class PredictError(Exception):
    """A problem we explain to the user honestly (never replaced by made-up numbers)."""


# ---------------------------------------------------------------------------
# The trained model
# ---------------------------------------------------------------------------

_bundle = None


def load_model():
    """The saved model plus its settings (typical error, cutoff, training ranges)."""
    global _bundle
    if _bundle is None:
        if not MODEL_FILE.exists():
            raise PredictError("The AI model has not been trained yet (run: python ml/train.py).")
        _bundle = joblib.load(MODEL_FILE)
    return _bundle


# Plain-language names for the model inputs (used in "outside the training range" messages).
READABLE = {"prev_ndvi": "starting NDVI", "days_since_prev": "days since the last clear image",
            "rain_7": "rain", "rain_14": "rain", "rain_30": "rain",
            "et0_7": "water demand (ET0)", "et0_14": "water demand (ET0)", "et0_30": "water demand (ET0)",
            "balance_14": "rain minus water demand", "balance_30": "rain minus water demand",
            "tmax_7": "temperature", "tmax_14": "temperature", "day_of_year": "time of year"}


def outside_training(bundle, features):
    """Names of inputs outside the range the model saw in training (empty list = all fine)."""
    ranges = bundle["feature_ranges"]
    return [name for name in bundle["features"]
            if not ranges[name][0] <= features[name] <= ranges[name][1]]


def readable(names):
    return ", ".join(dict.fromkeys(READABLE.get(n, n) for n in names))


def predict_one(bundle, features):
    X = np.array([[features[name] for name in bundle["features"]]])
    return float(bundle["model"].predict(X)[0])


def risk_level(change, bundle):
    """Predicted change in NDVI -> Low / Medium / High (project choice, tied to model error)."""
    if change <= -bundle["weather_cutoff"]:
        return "High"
    if change <= -bundle["typical_error"]:
        return "Medium"
    return "Low"


def in_season(day):
    return day.month in GROWING_MONTHS


# ---------------------------------------------------------------------------
# Geometry helpers: excluded areas become holes in the outline
# ---------------------------------------------------------------------------

def point_in_ring(point, ring):
    x, y = point
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def segments_cross(a, b, c, d):
    def side(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return side(a, b, c) * side(a, b, d) < 0 and side(c, d, a) * side(c, d, b) < 0


def rings_cross(r1, r2):
    return any(segments_cross(a, b, c, d) for a, b in zip(r1, r1[1:]) for c, d in zip(r2, r2[1:]))


def field_geometry(geometry, exclusions):
    """The outline with excluded areas cut out as holes, plus a note if that wasn't possible.
    Holes are only valid if they lie fully inside the outline and don't touch each other."""
    outline = geometry["coordinates"][0]
    holes = [shape["coordinates"][0] for shape in exclusions]
    ok = all(
        all(point_in_ring(p, outline) for p in hole) and not rings_cross(hole, outline)
        for hole in holes
    ) and not any(
        rings_cross(h1, h2) or point_in_ring(h1[0], h2) or point_in_ring(h2[0], h1)
        for i, h1 in enumerate(holes) for h2 in holes[i + 1:]
    )
    if holes and not ok:
        return geometry, ("Excluded areas were NOT used for the AI check because some overlap "
                          "each other or reach outside the outline.")
    return {"type": "Polygon", "coordinates": [outline] + holes}, None


def centroid(geometry):
    ring = geometry["coordinates"][0][:-1]
    return sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring)


# ---------------------------------------------------------------------------
# Downloads (always cached)
# ---------------------------------------------------------------------------

def cache_path(kind, key_data):
    key = hashlib.sha256(json.dumps(key_data, sort_keys=True).encode()).hexdigest()[:32]
    return CACHE_DIR / kind / f"{key}.json"


def pu_spent_today():
    path = CACHE_DIR / "processing_units.json"
    spent = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return spent, path


def record_pu(pu):
    spent, path = pu_spent_today()
    today = date.today().isoformat()
    spent[today] = round(spent.get(today, 0.0) + pu, 3)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(spent), encoding="utf-8")


def fetch_ndvi(geometry, start, end):
    """Clear dates (>= 80% clear) with mean NDVI for the field, oldest first. Cached."""
    cache = cache_path("ndvi", [geometry, str(start), str(end)])
    if cache.exists():
        saved = json.loads(cache.read_text(encoding="utf-8"))
    else:
        spent, _ = pu_spent_today()
        if spent.get(date.today().isoformat(), 0.0) >= DAILY_PU_BUDGET:
            raise PredictError(f"Today's Copernicus budget for the AI check ({DAILY_PU_BUDGET} "
                               "processing units) is used up. Try again tomorrow.")
        resx, resy = ten_meters_in_degrees(centroid(geometry)[1])
        body = {
            "input": {
                "bounds": {"geometry": geometry, "properties": {"crs": sentinel.CRS84}},
                "data": [{"type": "sentinel-2-l2a", "dataFilter": {"mosaickingOrder": "leastCC"}}],
            },
            "aggregation": {
                "timeRange": {"from": f"{start}T00:00:00Z", "to": f"{end}T23:59:59Z"},
                "aggregationInterval": {"of": "P1D"},
                "evalscript": EVALSCRIPT, "resx": resx, "resy": resy,
            },
        }
        try:
            response = requests.post(STATISTICS_URL, json=body, timeout=120,
                                     headers={"Authorization": f"Bearer {sentinel.get_token()}"})
        except (requests.RequestException, sentinel.SentinelError) as e:
            raise PredictError(f"Could not reach Copernicus: {e}")
        if response.status_code in (402, 403, 429):
            raise PredictError(f"Copernicus refused the request (HTTP {response.status_code}); "
                               "the processing quota may be low. Check the Copernicus dashboard.")
        if response.status_code != 200:
            raise PredictError(f"Copernicus answered HTTP {response.status_code}.")
        pu = float(response.headers.get("x-processingunits-spent", 0))
        record_pu(pu)
        saved = {"processing_units": pu, "answer": response.json()}
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(saved), encoding="utf-8")
    rows = rows_from_answer(saved)
    return [r for r in rows if r["clear_fraction"] >= MIN_CLEAR_FRACTION and r["ndvi_mean"] is not None]


def open_meteo(url, lon, lat, start, end):
    """One cached Open-Meteo request -> {date: (rain, tmax, et0)}. Missing values stay None."""
    today = date.today()
    # Forecasts change every day, so a forecast answer is only reused on the same day.
    key = [round(lon, 3), round(lat, 3), str(start), str(end), url,
           None if url == ARCHIVE_URL else str(today)]
    cache = cache_path("weather", key)
    if cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
    else:
        params = {"latitude": lat, "longitude": lon, "start_date": str(start), "end_date": str(end),
                  "daily": ",".join(WEATHER_VARIABLES), "timezone": "America/Denver"}
        try:
            response = requests.get(url, params=params, timeout=60)
        except requests.RequestException as e:
            raise PredictError(f"Could not reach Open-Meteo: {e}")
        if response.status_code != 200:
            raise PredictError(f"Open-Meteo answered HTTP {response.status_code}.")
        data = response.json()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(data), encoding="utf-8")
    daily = data["daily"]
    return {day: tuple(daily[v][i] for v in WEATHER_VARIABLES) for i, day in enumerate(daily["time"])}


def fetch_weather(lon, lat, start, end):
    """Daily weather from start to end plus a description of the sources. Older days come from
    the historical archive (same source as the training data); the archive is a few days
    behind, so the most recent days and the future come from the forecast service."""
    archive_end = min(end, date.today() - timedelta(days=ARCHIVE_DELAY_DAYS))
    weather, sources = {}, []
    if start <= archive_end:
        weather.update(open_meteo(ARCHIVE_URL, lon, lat, start, archive_end))
        sources.append(f"Open-Meteo historical archive up to {archive_end} (same source as the training data)")
    if end > archive_end:
        first = max(start, archive_end + timedelta(days=1))
        weather.update(open_meteo(FORECAST_URL, lon, lat, first, end))
        sources.append(f"Open-Meteo forecast service from {first} (recent days are model estimates; "
                       "days after today are a forecast)")
    return weather, "; ".join(sources)


# ---------------------------------------------------------------------------
# One field: real data around "as of"
# ---------------------------------------------------------------------------

def field_snapshot(geometry, exclusions, as_of):
    """Everything the model needs for one field: its clear NDVI dates and the weather."""
    shape, note = field_geometry(geometry, exclusions)
    season_start = date(as_of.year, 4, 1)  # training images were April-October only
    clear = fetch_ndvi(shape, max(as_of - timedelta(days=LOOKBACK_DAYS), season_start), as_of)
    lon, lat = centroid(geometry)
    weather, source = fetch_weather(lon, lat, as_of - timedelta(days=LOOKBACK_DAYS + 31),
                                    as_of + timedelta(days=DAYS_AHEAD))
    return {"clear": clear, "weather": weather, "weather_source": source, "geometry_note": note}


def model_inputs(prev_ndvi, prev_day, target_day, weather):
    """The same inputs as one training row (ml/build_dataset.py), or None if weather is missing."""
    part = weather_features(weather, target_day)
    if part is None:
        return None
    return {"prev_ndvi": prev_ndvi, "days_since_prev": (target_day - prev_day).days, **part,
            "day_of_year": target_day.timetuple().tm_yday}


def weather_summary(weather, first_day, days):
    window = [weather.get((first_day + timedelta(days=k)).isoformat()) for k in range(days)]
    if any(w is None or None in w for w in window):
        return None
    return {"days": days, "from": first_day.isoformat(),
            "rain_mm": round(sum(w[0] for w in window), 1),
            "avg_high_c": round(sum(w[1] for w in window) / days, 1),
            "et0_mm": round(sum(w[2] for w in window), 1)}


def weather_check(geometry, exclusions, as_of):
    """Expected vs actual NDVI for the latest clear image, and next-week risk."""
    base = {"as_of": as_of.isoformat(), "label": LABEL, "accuracy_note": ACCURACY_NOTE, "credits": CREDITS}
    if not in_season(as_of):
        return {**base, "status": "off_season", "message": OFF_SEASON}
    bundle = load_model()
    snap = field_snapshot(geometry, exclusions, as_of)
    clear, weather = snap["clear"], snap["weather"]
    base.update({"weather_source": snap["weather_source"], "geometry_note": snap["geometry_note"],
                 "clear_dates_found": len(clear),
                 "typical_error": bundle["typical_error"], "cutoff": bundle["weather_cutoff"]})
    if len(clear) < 2:
        return {**base, "status": "insufficient_evidence",
                "message": f"Insufficient evidence: fewer than 2 clear satellite images in the "
                           f"{LOOKBACK_DAYS} days before {as_of} (clouds or early season)."}

    latest, previous = clear[-1], clear[-2]
    latest_day, previous_day = date.fromisoformat(latest["date"]), date.fromisoformat(previous["date"])
    result = {**base, "status": "ok", "last_image_date": latest["date"],
              "previous_image_date": previous["date"], "actual_ndvi": latest["ndvi_mean"],
              "latest_clear_fraction": latest["clear_fraction"],
              "weather_last_14_days": weather_summary(weather, latest_day - timedelta(days=14), 14)}

    # 1. Does the weather explain the latest image?
    inputs = model_inputs(previous["ndvi_mean"], previous_day, latest_day, weather)
    unusual = outside_training(bundle, inputs) if inputs else None
    if inputs is None:
        result["check"] = {"status": "insufficient_evidence", "message": "Weather data is missing for this period."}
    elif unusual:
        result["check"] = {"status": "outside_training", "outside": unusual,
                           "message": "Not checked: these inputs are outside what the AI saw in "
                                      f"training ({readable(unusual)})."}
    else:
        expected = predict_one(bundle, inputs)
        difference = latest["ndvi_mean"] - expected
        explains = difference >= -bundle["weather_cutoff"]
        result["check"] = {
            "status": "ok", "expected_ndvi": round(expected, 3), "difference": round(difference, 3),
            "weather_explains": explains,
            "message": ("Weather explains this." if explains else
                        "Weather does NOT explain this — inspect irrigation first."),
        }

    # 2. Next-week risk
    target = as_of + timedelta(days=DAYS_AHEAD)
    inputs = model_inputs(latest["ndvi_mean"], latest_day, target, weather)
    unusual = outside_training(bundle, inputs) if inputs else None
    risk = {"target_date": target.isoformat(),
            "weather_next_7_days": weather_summary(weather, as_of + timedelta(days=1), DAYS_AHEAD)}
    if target <= date.today():
        risk["note"] = ("This is a past date: the 'next 7 days' weather is what actually happened "
                        "(old forecasts are not archived).")
    elif as_of < date.today():
        risk["note"] = "The 'next 7 days' weather is partly what already happened, partly a forecast."
    if inputs is None:
        risk.update(level="Unknown", message="Weather (or the forecast) is missing for the next week.")
    elif unusual:
        risk.update(level="Unknown", outside=unusual,
                    message=f"Unknown: outside what the AI saw in training ({readable(unusual)}).")
    else:
        predicted = predict_one(bundle, inputs)
        change = predicted - latest["ndvi_mean"]
        risk.update(level=risk_level(change, bundle), predicted_ndvi=round(predicted, 3),
                    predicted_change=round(change, 3))
    result["risk_next_week"] = risk
    return result


# ---------------------------------------------------------------------------
# Step 8: My Fields ranking (READS the accounts database; never writes to it)
# ---------------------------------------------------------------------------

def distinct_saved_fields(saved):
    """One entry per distinct outline (+ exclusions), newest save first. `saved` is the
    output of accounts.list_analyses for ONE user, so only their own fields are included."""
    seen, fields = set(), []
    for item in saved:  # list_analyses is newest first
        key = json.dumps([item["geometry"], item["exclusions"]], sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        fields.append({k: item[k] for k in ("id", "name", "geometry", "exclusions", "start", "end",
                                            "observation_date")})
    return fields


RISK_ORDER = {"High": 0, "Medium": 1, "Low": 2, "Unknown": 3}


def priority_key(entry):
    """Sort order: 1) weather does NOT explain the latest image, 2) next-week risk,
    3) how far below expected. Fields we couldn't check go last."""
    check = entry.get("result") or {}
    if check.get("status") != "ok":
        return (2, 0, 0, 0)
    c, risk = check.get("check", {}), check.get("risk_next_week", {})
    not_explained = c.get("status") == "ok" and not c["weather_explains"]
    return (0 if c.get("status") == "ok" else 1, 0 if not_explained else 1,
            RISK_ORDER.get(risk.get("level"), 3), c.get("difference", 0))


def rank_my_fields(saved, as_of, check=weather_check):
    base = {"as_of": as_of.isoformat(), "label": LABEL, "accuracy_note": ACCURACY_NOTE,
            "credits": CREDITS,
            "rule": "Ranked by: 1) weather does NOT explain the latest image, 2) next-week risk, "
                    "3) how far the field is below what the AI expected. A project choice."}
    fields = distinct_saved_fields(saved)
    if not fields:
        return {**base, "status": "no_fields", "fields": [],
                "message": "Analyze a field while logged in to add it to My Fields."}
    if not in_season(as_of):
        return {**base, "status": "off_season", "message": OFF_SEASON, "fields": []}
    skipped = max(0, len(fields) - MAX_RANKED_FIELDS)
    entries = []
    for field in fields[:MAX_RANKED_FIELDS]:
        entry = {"field": field}
        try:
            entry["result"] = check(field["geometry"], field["exclusions"], as_of)
        except PredictError as e:
            entry["result"] = {"status": "error", "message": str(e)}
        entries.append(entry)
    entries.sort(key=priority_key)
    for rank, entry in enumerate(entries, 1):
        entry["rank"] = rank
    return {**base, "status": "ok", "fields": entries,
            "skipped": (f"Only your {MAX_RANKED_FIELDS} most recently saved fields are ranked "
                        f"({skipped} older ones left out to limit Copernicus use).") if skipped else None}

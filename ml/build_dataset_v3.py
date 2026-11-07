"""
build_dataset_v3.py - Stage 10, version 3 of the training table (2026-11-07).

Why version 3? Versions 1 and 2 learned from BACK-TO-BACK clear images (73% only 1-3 days
apart). Grass can't change in 2 days, so "same as last time" is almost perfect there and the
weather can't matter. But the app asks about NEXT WEEK and the What-if covers 14 DAYS.
So version 3 (student decision, 2026-11-07):

  1. "Jump" rows: one row = a START image and a TARGET image 7-20 days later (every such pair).
     The images in between are skipped. The model predicts the target NDVI from what was
     known on the start day plus the weather before the target day.
  2. Better inputs (all known on the start day, or weather before the target day):
       recent_mean      average NDVI of the last (up to) 3 clear images in the 20 days up to
                        the start day -> smooths out haze / sun-angle noise of one image
       trend_per_day    NDVI change per day over those recent images (NaN if only one image)
       start_clear      clear fraction of the start image (image quality)
       start_std        pixel spread (standard deviation) of NDVI in the start image
       *_vs_normal      rain / heat / rain-minus-ET0 compared with the Denver-area NORMAL for
                        the same days of the year (2019-2024 average of the training weather).
                        "Dry for August" instead of just "August": this separates weather
                        from season, which versions 1-2 mixed up.
       own_gap          start NDVI minus this field's OWN usual NDVI for that time of year
       own_step         this field's own usual change from the start day to the target day
                        (both from up to 3 EARLIER years only; NaN if there are none)
  3. Three fields removed: likely artificial turf (EXCLUDED_FIELDS below, checked on aerial
     photos and Sentinel-2 true color on 2026-11-07).

Which inputs are actually used is chosen on 2024 only (ml/train_v3.py), never on the test year.
The SAME functions are used by the app (backend/predict.py), so app inputs = training inputs.

Run from the project folder:   python ml/build_dataset_v3.py   -> ml/data/dataset_v3.csv
"""

import csv
import json
import math
import sys
from datetime import date, timedelta
from pathlib import Path

ML_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ML_DIR))
from build_dataset import (FIELDS_FILE, NDVI_DIR, WEATHER_DIR, load_weather, read_csv,  # noqa: E402
                           weather_features)

DATASET_V3_FILE = ML_DIR / "data" / "dataset_v3.csv"

# Project choices (not published standards):
MIN_DAYS_AHEAD, MAX_DAYS_AHEAD = 7, 20  # "next week" up to ~3 weeks
RECENT_DAYS, RECENT_IMAGES = 20, 3      # smoothing: last 3 clear images within 20 days
OWN_YEARS, OWN_WINDOW_DAYS = 3, 15      # own normal: up to 3 earlier years, +-15 days
NORMAL_YEARS = range(2019, 2025)        # weather normal: 2019-2024 (never the 2025 test year)
NORMAL_SMOOTH_DAYS = 3                  # weather normal averaged over +-3 calendar days

# Likely artificial turf (student decision 2026-11-07). Evidence for each one:
#  - Esri aerial photos (Sept/Nov 2025): evenly bright green with painted multi-sport lines
#    while the grass around it is brown/dormant
#  - Sentinel-2 true color July 2025 looks green, but NDVI only 0.31-0.42 (real watered grass
#    nearby: 0.74); NDVI stays flat April-October (no spring green-up)
EXCLUDED_FIELDS = {
    "osm_way_1288554499": "sports #1: likely artificial turf (NDVI ~0.31 all season, green in photos)",
    "osm_way_544154803": "sports #2: likely artificial turf (NDVI ~0.45 flat, red-track complex)",
    "osm_way_337232615": "sports #3: likely artificial turf (NDVI ~0.42 flat, green in Nov photo)",
}

START_FEATURES = ["start_ndvi", "recent_mean", "trend_per_day", "start_clear", "start_std"]
WEATHER = ["rain_7", "rain_14", "rain_30", "et0_7", "et0_14", "et0_30", "balance_14",
           "balance_30", "tmax_7", "tmax_14"]
VS_NORMAL = ["rain_14_vs_normal", "tmax_7_vs_normal", "tmax_14_vs_normal", "balance_14_vs_normal"]
OWN = ["own_gap", "own_step"]
ALL_FEATURES = START_FEATURES + ["days_ahead"] + WEATHER + VS_NORMAL + ["day_of_year"] + OWN
COLUMNS = ["field_id", "kind", "start_date", "date", "year", "ndvi"] + ALL_FEATURES


def doy(day):
    return day.timetuple().tm_yday


# ---------------------------------------------------------------------------
# Weather normal (Denver area)
# ---------------------------------------------------------------------------

def weather_normal(weather_by_field, years=NORMAL_YEARS):
    """{day of year: (rain, tmax, et0)} = average over all fields and the given years,
    smoothed over +-NORMAL_SMOOTH_DAYS calendar days. Uses real weather only."""
    sums = {d: [0.0, 0.0, 0.0, 0] for d in range(1, 367)}
    for weather in weather_by_field:
        for day_text, values in weather.items():
            day = date.fromisoformat(day_text)
            if day.year in years and None not in values:
                s = sums[doy(day)]
                s[0] += values[0]
                s[1] += values[1]
                s[2] += values[2]
                s[3] += 1
    normal = {}
    for d in range(1, 367):
        near = [sums[(d - 1 + k) % 366 + 1] for k in range(-NORMAL_SMOOTH_DAYS, NORMAL_SMOOTH_DAYS + 1)]
        n = sum(s[3] for s in near)
        if n:
            normal[d] = tuple(round(sum(s[i] for s in near) / n, 3) for i in range(3))
    return normal


def vs_normal(features, normal, target_day):
    """Weather before the target day minus the normal for the same days of the year."""
    def window(days):
        return [normal[doy(target_day - timedelta(days=k))] for k in range(1, days + 1)]
    n7, n14 = window(7), window(14)
    rain_14 = sum(w[0] for w in n14)
    balance_14 = rain_14 - sum(w[2] for w in n14)
    return {
        "rain_14_vs_normal": round(features["rain_14"] - rain_14, 2),
        "tmax_7_vs_normal": round(features["tmax_7"] - sum(w[1] for w in n7) / 7, 2),
        "tmax_14_vs_normal": round(features["tmax_14"] - sum(w[1] for w in n14) / 14, 2),
        "balance_14_vs_normal": round(features["balance_14"] - balance_14, 2),
    }


# ---------------------------------------------------------------------------
# The field's own usual NDVI (from earlier years only)
# ---------------------------------------------------------------------------

def own_normal(history, year, day_of_year):
    """Average NDVI of this field within +-15 days of the same day of year, in the up to 3
    years BEFORE `year`. `history` = [(date, ndvi), ...]. None if there is no such image."""
    values = [v for d, v in history
              if year - OWN_YEARS <= d.year < year and abs(doy(d) - day_of_year) <= OWN_WINDOW_DAYS]
    return sum(values) / len(values) if values else None


# ---------------------------------------------------------------------------
# One (start image -> target day) example: used for training AND by the app
# ---------------------------------------------------------------------------

def pair_features(recent, target_day, weather, normal, history):
    """All inputs for predicting NDVI on target_day.
    recent  = the field's clear images up to and including the START image, oldest first
              (dicts with date, ndvi_mean, ndvi_std, clear_fraction); only the last 20 days used
    weather = {date: (rain, tmax, et0)} real (or scenario) weather
    normal  = weather_normal(...) table
    history = [(date, ndvi), ...] clear images of EARLIER years (for own_gap / own_step)
    Returns a dict, or None if weather is missing (never filled in)."""
    start = recent[-1]
    start_day = date.fromisoformat(start["date"])
    w = weather_features(weather, target_day)
    if w is None:
        return None
    last = [r for r in recent if (start_day - date.fromisoformat(r["date"])).days < RECENT_DAYS]
    last = last[-RECENT_IMAGES:]
    first_day = date.fromisoformat(last[0]["date"])
    span = (start_day - first_day).days
    own_start = own_normal(history, start_day.year, doy(start_day))
    own_target = own_normal(history, target_day.year, doy(target_day))
    nan = float("nan")
    return {
        "start_ndvi": float(start["ndvi_mean"]),
        "recent_mean": round(sum(float(r["ndvi_mean"]) for r in last) / len(last), 4),
        "trend_per_day": round((float(start["ndvi_mean"]) - float(last[0]["ndvi_mean"])) / span, 5) if span else nan,
        "start_clear": float(start["clear_fraction"]),
        "start_std": float(start["ndvi_std"]) if start.get("ndvi_std") not in (None, "") else nan,
        "days_ahead": (target_day - start_day).days,
        **w,
        **vs_normal(w, normal, target_day),
        "day_of_year": doy(target_day),
        "own_gap": round(float(start["ndvi_mean"]) - own_start, 4) if own_start is not None else nan,
        "own_step": round(own_target - own_start, 4) if own_start is not None and own_target is not None else nan,
    }


def rows_for_field(field, ndvi_rows, weather, normal, counts):
    """One row for every pair of clear images 7-20 days apart."""
    ndvi_rows = sorted(ndvi_rows, key=lambda r: r["date"])
    days = [date.fromisoformat(r["date"]) for r in ndvi_rows]
    out = []
    for j, target_day in enumerate(days):
        for i in range(j):
            gap = (target_day - days[i]).days
            if not MIN_DAYS_AHEAD <= gap <= MAX_DAYS_AHEAD:
                continue
            history = [(d, float(r["ndvi_mean"])) for d, r in zip(days, ndvi_rows) if d.year < days[i].year]
            features = pair_features(ndvi_rows[: i + 1], target_day, weather, normal, history)
            if features is None:
                counts["missing weather"] += 1
                continue
            out.append({"field_id": field["id"], "kind": field["kind"], "start_date": ndvi_rows[i]["date"],
                        "date": ndvi_rows[j]["date"], "year": target_day.year,
                        "ndvi": float(ndvi_rows[j]["ndvi_mean"]), **features})
    return out


def load_normal(fields):
    return weather_normal([load_weather(f["id"]) for f in fields])


def used_fields():
    """Fields kept in Step 2, minus the artificial-turf fields."""
    fields = [f["properties"] for f in json.loads(FIELDS_FILE.read_text(encoding="utf-8"))["features"]]
    status = {row["id"]: row["status"] for row in read_csv(NDVI_DIR / "summary.csv")}
    return [f for f in fields if status.get(f["id"]) == "kept" and f["id"] not in EXCLUDED_FIELDS]


def main():
    fields = used_fields()
    normal = load_normal(fields)
    counts = {"missing weather": 0}
    rows = []
    for field in fields:
        rows += rows_for_field(field, read_csv(NDVI_DIR / f"{field['id']}.csv"),
                               load_weather(field["id"]), normal, counts)
    with open(DATASET_V3_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows({k: ("" if isinstance(v, float) and math.isnan(v) else v) for k, v in r.items()}
                         for r in rows)
    print(f"Version 3 rows: {len(rows)} (start -> target image pairs {MIN_DAYS_AHEAD}-{MAX_DAYS_AHEAD} days apart) "
          f"from {len(fields)} fields ({', '.join(f'{k} {sum(f['kind'] == k for f in fields)}' for k in ('sports', 'baseball', 'park'))})")
    print("Rows per year: " + ", ".join(f"{y} {sum(r['year'] == y for r in rows)}" for y in sorted({r['year'] for r in rows})))
    print(f"Skipped pairs: missing weather {counts['missing weather']}")
    for field_id, reason in EXCLUDED_FIELDS.items():
        print(f"Field removed: {field_id} ({reason})")
    print(f"Saved {DATASET_V3_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

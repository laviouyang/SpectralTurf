"""
get_ndvi_history.py - Stage 10, Step 2: how green was each field on every clear day, 2019-2025?

For each field in ml/data/fields.geojson, we ask the Copernicus Sentinel Hub STATISTICAL API
for one summary per satellite date: mean NDVI of the clear pixels, and what fraction of the
field was clear. This is much cheaper than downloading pictures: Copernicus does the math and
sends back only the numbers.

Same science as the app:
  - NDVI = (B08 - B04) / (B08 + B04), 10 m pixels
  - pixels with SCL classes 0,1,2,3,8,9,10,11 (no data, saturated, shadows, clouds, cirrus,
    snow) are left out, exactly like backend/indices.py
Checked against the app: the Stage 3 test box grass_B gave NDVI 0.754 on 2026-08-05 here too.

What we keep (project choices, not standards):
  - growing season only: April 1 - October 31, years 2019-2025
  - only dates where at least MIN_CLEAR_FRACTION (80%) of the field is clear
  - a field is DROPPED if its NDVI never gets above 0.3 (its 90th-percentile NDVI over all
    clear dates is below 0.3): real grass greens up at least in spring, plastic turf never
    does. Dropped fields are listed with the reason, not hidden.

Respecting Copernicus limits:
  - every answer is saved in ml/data/cache/stats/ and never downloaded again
  - the cost of each request (processing units, PU) is read from Copernicus' reply and added up
  - the run stops if it spends more than PU_BUDGET_PER_RUN, or if Copernicus says a limit
    was reached, and says so

Run from the project folder (backend venv active):
    python ml/get_ndvi_history.py --fields 1     (test with the first field only)
    python ml/get_ndvi_history.py                (all fields)
"""

import argparse
import csv
import json
import math
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np
import requests
from dotenv import load_dotenv

ML_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ML_DIR.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")  # the Copernicus keys are only read, never printed or copied
import sentinel  # noqa: E402  (reuses the app's login code)

FIELDS_FILE = ML_DIR / "data" / "fields.geojson"
CACHE_DIR = ML_DIR / "data" / "cache" / "stats"
NDVI_DIR = ML_DIR / "data" / "ndvi"
SUMMARY_FILE = NDVI_DIR / "summary.csv"

STATISTICS_URL = "https://sh.dataspace.copernicus.eu/api/v1/statistics"
YEARS = range(2019, 2026)
SEASON = ("04-01", "10-31")
MIN_CLEAR_FRACTION = 0.80
ARTIFICIAL_NDVI = 0.30  # same level as the app's artificial-turf warning (WARN_BELOW_MEDIAN_NDVI)
PU_BUDGET_PER_RUN = 1000
SECONDS_BETWEEN_REQUESTS = 0.5

# Runs on Copernicus' servers, once per pixel per date. "ndvi" is NaN for rejected pixels, so
# they are left out of the NDVI statistics; "clear" (1/0) tells us what fraction was clear.
EVALSCRIPT = """//VERSION=3
function setup() {
  return {input: [{bands: ["B04", "B08", "SCL", "dataMask"]}],
          output: [{id: "ndvi", bands: 1, sampleType: "FLOAT32"},
                   {id: "clear", bands: 1, sampleType: "FLOAT32"},
                   {id: "dataMask", bands: 1}]};
}
const REJECTED = [0, 1, 2, 3, 8, 9, 10, 11];
function evaluatePixel(s) {
  const ok = s.dataMask == 1 && REJECTED.indexOf(s.SCL) < 0;
  return {ndvi: [ok ? (s.B08 - s.B04) / (s.B08 + s.B04) : NaN],
          clear: [ok ? 1 : 0],
          dataMask: [s.dataMask]};
}"""


class QuotaStop(Exception):
    """Stop downloading: the budget or a Copernicus limit was reached."""


def ten_meters_in_degrees(latitude):
    """Pixel size for the request: 10 m, written in degrees (the polygon is in lon/lat)."""
    return 10 / (111_320 * math.cos(math.radians(latitude))), 10 / 111_320


def download_year(field, year, spent):
    """One field, one growing season. Returns (Copernicus answer, PU spent). Uses the cache."""
    cache = CACHE_DIR / f"{field['id']}_{year}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8")), 0.0
    if spent >= PU_BUDGET_PER_RUN:
        raise QuotaStop(f"spent {spent:.1f} PU this run (budget {PU_BUDGET_PER_RUN})")

    resx, resy = ten_meters_in_degrees(field["centroid"][1])
    body = {
        "input": {
            "bounds": {"geometry": field["geometry"], "properties": {"crs": sentinel.CRS84}},
            "data": [{"type": "sentinel-2-l2a", "dataFilter": {"mosaickingOrder": "leastCC"}}],
        },
        "aggregation": {
            "timeRange": {"from": f"{year}-{SEASON[0]}T00:00:00Z", "to": f"{year}-{SEASON[1]}T23:59:59Z"},
            "aggregationInterval": {"of": "P1D"},  # one summary per day that has an image
            "evalscript": EVALSCRIPT,
            "resx": resx,
            "resy": resy,
        },
    }
    for attempt in range(4):
        response = requests.post(STATISTICS_URL, json=body, timeout=180,
                                 headers={"Authorization": f"Bearer {sentinel.get_token()}"})
        if response.status_code == 429:  # too many requests right now: wait and retry
            time.sleep(10 * (attempt + 1))
            continue
        break
    if response.status_code in (402, 403, 429):
        raise QuotaStop(f"Copernicus answered HTTP {response.status_code}: {response.text[:200]}")
    if response.status_code != 200:
        raise RuntimeError(f"{field['id']} {year}: HTTP {response.status_code}: {response.text[:300]}")

    answer = response.json()
    pu = float(response.headers.get("x-processingunits-spent", 0))
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"processing_units": pu, "answer": answer}), encoding="utf-8")
    time.sleep(SECONDS_BETWEEN_REQUESTS)
    return {"processing_units": pu, "answer": answer}, pu


def rows_from_answer(saved):
    """Turn Copernicus' answer into one row per date: date, mean NDVI, clear fraction, pixels."""
    rows = []
    for item in saved["answer"].get("data", []):
        if "error" in item:
            continue  # a date Copernicus couldn't compute: skip, never guess
        outputs = item["outputs"]
        ndvi = outputs["ndvi"]["bands"]["B0"]["stats"]
        clear = outputs["clear"]["bands"]["B0"]["stats"]
        mean = ndvi.get("mean")
        rows.append({
            "date": item["interval"]["from"][:10],
            "ndvi_mean": None if mean in (None, "NaN") else round(float(mean), 4),
            "ndvi_std": None if ndvi.get("stDev") in (None, "NaN") else round(float(ndvi["stDev"]), 4),
            "clear_fraction": round(float(clear["mean"]), 3),
            "pixels": int(clear["sampleCount"]) - int(clear["noDataCount"]),
        })
    return rows


def field_status(usable):
    """Keep the field, or drop it with a reason."""
    if len(usable) < 10:
        return "dropped: fewer than 10 clear dates"
    p90 = float(np.percentile([r["ndvi_mean"] for r in usable], 90))
    if p90 < ARTIFICIAL_NDVI:
        return f"dropped: NDVI never above {ARTIFICIAL_NDVI} (90th percentile {p90:.2f}), likely artificial turf"
    return "kept"


def load_fields(limit=None):
    features = json.loads(FIELDS_FILE.read_text(encoding="utf-8"))["features"]
    fields = [{**f["properties"], "geometry": f["geometry"]} for f in features]
    return fields[:limit] if limit else fields


def main(limit=None):
    fields = load_fields(limit)
    NDVI_DIR.mkdir(parents=True, exist_ok=True)
    spent, summary, stopped = 0.0, [], None

    for field in fields:
        all_rows, cost = [], 0.0
        try:
            for year in YEARS:
                saved, pu = download_year(field, year, spent)
                spent += pu
                cost += saved["processing_units"]
                all_rows += rows_from_answer(saved)
        except QuotaStop as e:
            stopped = str(e)
            break

        usable = [r for r in all_rows if r["clear_fraction"] >= MIN_CLEAR_FRACTION and r["ndvi_mean"] is not None]
        with open(NDVI_DIR / f"{field['id']}.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["date", "ndvi_mean", "ndvi_std", "clear_fraction", "pixels"])
            writer.writeheader()
            writer.writerows(usable)
        ndvi = [r["ndvi_mean"] for r in usable]
        summary.append({
            "id": field["id"], "kind": field["kind"], "satellite_dates": len(all_rows),
            "usable_dates": len(usable),
            "ndvi_median": round(float(np.median(ndvi)), 3) if ndvi else None,
            "ndvi_p90": round(float(np.percentile(ndvi, 90)), 3) if ndvi else None,
            "processing_units": round(cost, 2), "status": field_status(usable),
        })

    with open(SUMMARY_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0]) if summary else ["id"])
        writer.writeheader()
        writer.writerows(summary)

    print(f"\n{'#':>3}  {'field':<20}{'kind':<10}{'dates':>6}{'usable':>7}{'median':>8}{'p90':>6}{'PU':>7}  status")
    print("-" * 100)
    for i, s in enumerate(summary, 1):
        median = f"{s['ndvi_median']:.2f}" if s["ndvi_median"] is not None else "-"
        p90 = f"{s['ndvi_p90']:.2f}" if s["ndvi_p90"] is not None else "-"
        print(f"{i:>3}  {s['id']:<20}{s['kind']:<10}{s['satellite_dates']:>6}{s['usable_dates']:>7}"
              f"{median:>8}{p90:>6}{s['processing_units']:>7.2f}  {s['status']}")
    kept = [s for s in summary if s["status"] == "kept"]
    print(f"\nKept {len(kept)} of {len(summary)} fields: "
          + ", ".join(f"{k} {sum(s['kind'] == k for s in kept)}" for k in ("sports", "baseball", "park")))
    print(f"Processing units spent by this run: {spent:.2f} (fields already cached cost nothing).")
    print(f"Total PU for these fields (incl. earlier runs): {sum(s['processing_units'] for s in summary):.2f}")
    print(f"Saved one CSV per field in {NDVI_DIR}, plus summary.csv")
    if stopped:
        print(f"\nSTOPPED EARLY: {stopped}\nNothing more was downloaded. Check the Copernicus dashboard "
              "(https://shapps.dataspace.copernicus.eu/dashboard/) before running again.")
        return 2
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download NDVI history for the training fields.")
    parser.add_argument("--fields", type=int, help="only the first N fields (test with 1 first)")
    sys.exit(main(parser.parse_args().fields))

"""
get_weather.py - Stage 10, Step 3: daily weather history for every training field, 2019-2025.

Source: the Open-Meteo Historical Weather API (free, no key). Weather data by Open-Meteo.com.
For each field's centroid we download, per day:
  - precipitation_sum           rain + melted snow, mm
  - temperature_2m_max          highest air temperature, °C
  - et0_fao_evapotranspiration  "ET0": how much water a reference grass would lose to the air
                                that day, mm (the standard FAO-56 measure of water demand)

Things to know:
  - Open-Meteo's history is a weather MODEL grid (several km per cell), not a rain gauge at
    the field, and it snaps each request to the nearest grid point. Fields close together can
    share the same weather. We record which grid point was used.
  - We download whole years (January-December), so Step 4 can look back 30 days before the
    first April image.
  - Every answer is saved in ml/data/cache/weather/ and never downloaded again.
  - Missing days are reported, never filled in with made-up values.

Run from the project folder (backend venv active):
    python ml/get_weather.py
"""

import csv
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests

ML_DIR = Path(__file__).resolve().parent
FIELDS_FILE = ML_DIR / "data" / "fields.geojson"
CACHE_DIR = ML_DIR / "data" / "cache" / "weather"
WEATHER_DIR = ML_DIR / "data" / "weather"

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
START, END = "2019-01-01", "2025-12-31"
VARIABLES = ["precipitation_sum", "temperature_2m_max", "et0_fao_evapotranspiration"]
SECONDS_BETWEEN_REQUESTS = 1.0  # be polite to a free service
CREDIT = "Weather data by Open-Meteo.com"


def download(field):
    """The whole 2019-2025 daily history for one field's centroid. Uses the cache."""
    cache = CACHE_DIR / f"{field['id']}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8")), False
    lon, lat = field["centroid"]
    params = {"latitude": lat, "longitude": lon, "start_date": START, "end_date": END,
              "daily": ",".join(VARIABLES), "timezone": "America/Denver"}
    response = requests.get(ARCHIVE_URL, params=params, timeout=60)
    if response.status_code != 200:
        raise RuntimeError(f"{field['id']}: Open-Meteo answered HTTP {response.status_code}: {response.text[:200]}")
    data = response.json()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data), encoding="utf-8")
    time.sleep(SECONDS_BETWEEN_REQUESTS)
    return data, True


def days_between(start, end):
    day, last = date.fromisoformat(start), date.fromisoformat(end)
    while day <= last:
        yield day.isoformat()
        day += timedelta(days=1)


def to_rows(data):
    """One row per day. Returns (rows, list of days with a missing value)."""
    daily = data["daily"]
    rows, missing = [], []
    by_day = {d: i for i, d in enumerate(daily["time"])}
    for day in days_between(START, END):
        i = by_day.get(day)
        values = {v: (daily[v][i] if i is not None else None) for v in VARIABLES}
        if any(value is None for value in values.values()):
            missing.append(day)
        rows.append({"date": day, **values})
    return rows, missing


def main():
    features = json.loads(FIELDS_FILE.read_text(encoding="utf-8"))["features"]
    WEATHER_DIR.mkdir(parents=True, exist_ok=True)
    print(f"{'field':<20}{'kind':<10}{'grid point':<22}{'days':>6}{'missing':>8}  source")
    print("-" * 80)
    grid_points = set()
    for feature in features:
        field = feature["properties"]
        data, downloaded = download(field)
        rows, missing = to_rows(data)
        with open(WEATHER_DIR / f"{field['id']}.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["date"] + VARIABLES)
            writer.writeheader()
            writer.writerows(rows)
        grid = f"{data['latitude']:.3f}, {data['longitude']:.3f}"
        grid_points.add(grid)
        print(f"{field['id']:<20}{field['kind']:<10}{grid:<22}{len(rows):>6}{len(missing):>8}  "
              f"{'downloaded' if downloaded else 'cache'}")
        if missing:
            print(f"   missing days (left empty, never filled in): {', '.join(missing[:10])}"
                  f"{' ...' if len(missing) > 10 else ''}")
    print(f"\n{len(features)} fields use {len(grid_points)} different weather grid points.")
    print(f"Saved one CSV per field in {WEATHER_DIR}")
    print(CREDIT)
    return 0


if __name__ == "__main__":
    sys.exit(main())

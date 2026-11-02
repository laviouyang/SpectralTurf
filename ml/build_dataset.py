"""
build_dataset.py - Stage 10, Step 4: turn the NDVI and weather histories into a training table.

One row = one field on one clear satellite date.
  TARGET (what the AI learns to predict): ndvi, the field's mean NDVI on that date.
  FEATURES (what the AI may look at): only things known BEFORE that date, so the model can
  never "peek" at the answer. Weather on the image day itself is NOT used (the image is taken
  around 10:30 am; most of that day's rain or heat comes later).

Features, explained:
  prev_ndvi        the field's NDVI on its previous clear date: "how green was it last time?"
  days_since_prev  how many days ago that was (a 2-day-old number is more useful than a 40-day-old one)
  rain_7/14/30     total rain + melted snow in the last 7 / 14 / 30 days, mm
  et0_7/14/30      total ET0 (water demand: how much water grass loses to the air) in the
                   last 7 / 14 / 30 days, mm
  balance_14/30    rain minus ET0 over 14 / 30 days, mm. Negative = the air took more water
                   than the rain gave (dry). Watering isn't known, so it can't be included.
  tmax_7/14        average daily high temperature over the last 7 / 14 days, °C
  day_of_year      the season (1 = Jan 1)
  area_m2          field size
We deliberately do NOT give the model the field's "kind" (sports/baseball/park): when someone
draws a field in the app we don't know its kind, so the model must work without it.

Rows are skipped (and counted) when:
  - it is the field's first clear date (no previous NDVI), or the previous clear date is more
    than MAX_GAP_DAYS ago (e.g. the first April image after winter): too old to be "last time"
  - any weather day in the 30-day window is missing (never filled in with made-up values)
  - the field was dropped in Step 2 (see ml/data/ndvi/summary.csv)

Run from the project folder:   python ml/build_dataset.py
"""

import csv
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ML_DIR = Path(__file__).resolve().parent
FIELDS_FILE = ML_DIR / "data" / "fields.geojson"
NDVI_DIR = ML_DIR / "data" / "ndvi"
WEATHER_DIR = ML_DIR / "data" / "weather"
DATASET_FILE = ML_DIR / "data" / "dataset.csv"

MAX_GAP_DAYS = 45  # a project choice
FEATURES = ["prev_ndvi", "days_since_prev", "rain_7", "rain_14", "rain_30", "et0_7", "et0_14",
            "et0_30", "balance_14", "balance_30", "tmax_7", "tmax_14", "day_of_year", "area_m2"]
COLUMNS = ["field_id", "kind", "date", "year", "ndvi"] + FEATURES


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def number(value):
    return None if value in (None, "") else float(value)


def load_weather(field_id):
    """{date: (rain, tmax, et0)} for one field; missing values stay None."""
    return {row["date"]: (number(row["precipitation_sum"]), number(row["temperature_2m_max"]),
                          number(row["et0_fao_evapotranspiration"]))
            for row in read_csv(WEATHER_DIR / f"{field_id}.csv")}


def weather_features(weather, day):
    """Rain, ET0, balance and temperature for the days BEFORE `day`. None if any day is missing."""
    window = [weather.get((day - timedelta(days=k)).isoformat()) for k in range(1, 31)]  # yesterday back 30 days
    if any(w is None or None in w for w in window):
        return None
    rain = [w[0] for w in window]
    tmax = [w[1] for w in window]
    et0 = [w[2] for w in window]
    features = {}
    for n in (7, 14, 30):
        features[f"rain_{n}"] = round(sum(rain[:n]), 2)
        features[f"et0_{n}"] = round(sum(et0[:n]), 2)
    for n in (14, 30):
        features[f"balance_{n}"] = round(features[f"rain_{n}"] - features[f"et0_{n}"], 2)
    for n in (7, 14):
        features[f"tmax_{n}"] = round(sum(tmax[:n]) / n, 2)
    return features


def rows_for_field(field, ndvi_rows, weather, counts):
    """One training row per clear date that has a recent previous clear date."""
    out = []
    ndvi_rows = sorted(ndvi_rows, key=lambda r: r["date"])
    for previous, current in zip(ndvi_rows, ndvi_rows[1:]):
        day, prev_day = date.fromisoformat(current["date"]), date.fromisoformat(previous["date"])
        gap = (day - prev_day).days
        if gap > MAX_GAP_DAYS:
            counts["previous clear date too old"] += 1
            continue
        weather_part = weather_features(weather, day)
        if weather_part is None:
            counts["missing weather"] += 1
            continue
        out.append({
            "field_id": field["id"], "kind": field["kind"], "date": current["date"], "year": day.year,
            "ndvi": float(current["ndvi_mean"]),
            "prev_ndvi": float(previous["ndvi_mean"]), "days_since_prev": gap,
            **weather_part,
            "day_of_year": day.timetuple().tm_yday, "area_m2": field["area_m2"],
        })
    counts["first clear date of the field"] += 1 if ndvi_rows else 0
    return out


def main():
    fields = [f["properties"] for f in json.loads(FIELDS_FILE.read_text(encoding="utf-8"))["features"]]
    status = {row["id"]: row["status"] for row in read_csv(NDVI_DIR / "summary.csv")}
    counts = {"first clear date of the field": 0, "previous clear date too old": 0, "missing weather": 0}
    rows, used, dropped = [], [], []
    for field in fields:
        if status.get(field["id"]) != "kept":
            dropped.append((field["id"], status.get(field["id"], "no NDVI history")))
            continue
        field_rows = rows_for_field(field, read_csv(NDVI_DIR / f"{field['id']}.csv"),
                                    load_weather(field["id"]), counts)
        rows += field_rows
        used.append(field)

    with open(DATASET_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Training rows: {len(rows)} from {len(used)} fields "
          f"({', '.join(f'{k} {sum(f['kind'] == k for f in used)}' for k in ('sports', 'baseball', 'park'))})")
    print("Rows per year: " + ", ".join(f"{y} {sum(r['year'] == y for r in rows)}"
                                        for y in sorted({r['year'] for r in rows})))
    print("Skipped dates: " + ", ".join(f"{reason} {n}" for reason, n in counts.items()))
    for field_id, reason in dropped:
        print(f"Field not used: {field_id} ({reason})")
    print("\nA few example rows:")
    shown = ["field_id", "date", "ndvi", "prev_ndvi", "days_since_prev", "rain_14", "et0_14",
             "balance_14", "tmax_7", "day_of_year"]
    print("  ".join(f"{c:>15}" if c != "field_id" else f"{c:<20}" for c in shown))
    for row in rows[:: max(1, len(rows) // 5)][:5]:
        print("  ".join(f"{row[c]:<20}" if c == "field_id" else f"{row[c]:>15}" for c in shown))
    print(f"\nSaved {DATASET_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

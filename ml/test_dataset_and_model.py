"""
test_dataset_and_model.py - Offline checks for build_dataset.py, train.py and evaluate.py.

Uses small MADE-UP inputs only to check the rules (no peeking at the answer, splits, baselines).
Any error numbers from made-up data mean nothing and are never reported.

Run from the project folder:   python ml/test_dataset_and_model.py
"""

import csv
import tempfile
from datetime import date, timedelta
from pathlib import Path

import numpy as np

import build_dataset as b
import evaluate as ev
import train as t

passed = 0


def check(name, condition):
    global passed
    assert condition, name
    passed += 1
    print("PASS", name)


# ---- Step 4: features only from BEFORE the image date ----
image_day = date(2024, 7, 31)
weather = {}
for k in range(0, 40):
    d = image_day - timedelta(days=k)
    # 1 mm of rain on each earlier day, but a huge 100 mm storm ON the image day
    weather[d.isoformat()] = (100.0 if k == 0 else 1.0, 30.0, 5.0)
features = b.weather_features(weather, image_day)
check("1. rain on the image day itself is NOT used (no peeking)", features["rain_7"] == 7.0)
check("2. 7/14/30-day sums are correct", features["rain_14"] == 14.0 and features["et0_30"] == 150.0)
check("3. water balance = rain - ET0", features["balance_14"] == 14.0 - 70.0)
check("4. average high temperature", features["tmax_7"] == 30.0)
del weather[(image_day - timedelta(days=20)).isoformat()]
check("5. a missing weather day inside the window -> row skipped (None), never filled in",
      b.weather_features(weather, image_day) is None)

full_weather = {(date(2024, 1, 1) + timedelta(days=k)).isoformat(): (1.0, 25.0, 4.0) for k in range(366)}
ndvi_rows = [{"date": "2024-05-01", "ndvi_mean": "0.50"}, {"date": "2024-05-06", "ndvi_mean": "0.55"},
             {"date": "2024-07-01", "ndvi_mean": "0.70"}, {"date": "2024-07-04", "ndvi_mean": "0.72"}]
counts = {"first clear date of the field": 0, "previous clear date too old": 0, "missing weather": 0}
rows = b.rows_for_field({"id": "f", "kind": "park", "area_m2": 10000}, ndvi_rows, full_weather, counts)
check("6. first date and a 56-day gap are skipped; others become rows",
      [r["date"] for r in rows] == ["2024-05-06", "2024-07-04"] and counts["previous clear date too old"] == 1)
check("7. prev_ndvi and days_since_prev come from the previous clear date",
      rows[1]["prev_ndvi"] == 0.70 and rows[1]["days_since_prev"] == 3 and rows[1]["ndvi"] == 0.72)
check("8. the field's kind is NOT a model input (the app can't know it)", "kind" not in b.FEATURES)

# ---- Step 5: made-up dataset to check splits and baselines ----
rng = np.random.default_rng(0)
with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "dataset.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=b.COLUMNS)
        writer.writeheader()
        for field in range(10):
            for year in range(2019, 2026):
                prev = 0.6
                for doy in range(110, 300, 6):
                    rain = rng.uniform(0, 40)
                    ndvi = float(np.clip(0.5 * prev + 0.3 + 0.004 * rain - 0.1 + rng.normal(0, 0.02), 0, 1))
                    row = {c: 0 for c in b.FEATURES}
                    row.update({"field_id": f"field{field}", "kind": ["sports", "baseball", "park"][field % 3],
                                "date": f"{year}-01-01", "year": year, "ndvi": round(ndvi, 4),
                                "prev_ndvi": round(prev, 4), "days_since_prev": 6, "rain_14": round(rain, 2),
                                "day_of_year": doy, "area_m2": 10000})
                    writer.writerow(row)
                    prev = ndvi
    X, y, info = t.load_dataset(path)
    chosen = t.choose_settings(X, y, info)
    check("9. settings are chosen by 2024 error; the model never trains on 2024 or 2025",
          chosen["model_2019_2023"].n_features_in_ == len(t.MODEL_FEATURES)
          and len(chosen["validation_residuals"]) == int((info["year"] == 2024).sum()))

    test_rows = np.where(info["year"] == 2025)[0]
    season, _ = ev.seasonal_baseline(y, info, test_rows[:1], range(2019, 2024))
    i = test_rows[0]
    same = ((info["field_id"] == info["field_id"][i]) & np.isin(info["year"], list(range(2019, 2024)))
            & (np.abs(info["day_of_year"] - info["day_of_year"][i]) <= 15))
    check("10. seasonal average uses only the same field, other (allowed) years, +-15 days",
          abs(season[0] - y[same].mean()) < 1e-12)

    scores = ev.score_table(np.array([0.5, 0.6, 0.7]), np.array([0.5, 0.6, 0.8]),
                            np.array([0.4, 0.6, 0.7]), np.array([np.nan, 0.6, 0.7]))
    check("11. all methods are scored on the same rows (rows without a seasonal value left out)",
          scores["rows"] == 2 and abs(scores["model"] - 0.05) < 1e-12 and scores["same as last time"] == 0)

    from sklearn.model_selection import GroupKFold
    leaks = [set(info["field_id"][a]) & set(info["field_id"][c])
             for a, c in GroupKFold(n_splits=5).split(X, y, info["field_id"])]
    check("12. field split: no field is ever in both training and testing", all(not s for s in leaks))

check("12b. field size is not a model input (v1 used it to recognize fields)", "area_m2" not in t.MODEL_FEATURES)
fake_X = np.zeros((3, len(t.MODEL_FEATURES)))
fake_X[:, t.PREV] = [0.3, 0.5, 0.7]
m = t.make_model({"max_iter": 20}).fit(fake_X, fake_X[:, t.PREV] + 0.05)
check("12c. the model predicts previous NDVI + a learned change", np.allclose(m.predict(fake_X) - fake_X[:, t.PREV],
      m.trees.predict(fake_X)))
check("13. MAE is the average absolute difference", abs(t.mae([0.5, 0.7], [0.6, 0.4]) - 0.2) < 1e-12)
print(f"\nAll {passed} dataset/model tests passed.")

"""
test_dataset_v3.py - Offline checks for version 3 (build_dataset_v3.py, train_v3.py).

Uses small MADE-UP inputs only to check the rules (7-20-day pairs, no peeking, smoothing,
normals, removed fields). Numbers from made-up data mean nothing and are never reported.

Run from the project folder:   python ml/test_dataset_v3.py
"""

import math
from datetime import date, timedelta

import numpy as np

import build_dataset_v3 as b3
import train_v3 as t3

passed = 0


def check(name, condition):
    global passed
    assert condition, name
    passed += 1
    print("PASS", name)


weather = {(date(2024, 1, 1) + timedelta(days=k)).isoformat(): (1.0, 25.0, 4.0) for k in range(366)}
normal = {d: (1.0, 25.0, 4.0) for d in range(1, 367)}


def image(day, ndvi, std=0.05, clear=1.0):
    return {"date": day, "ndvi_mean": ndvi, "ndvi_std": std, "clear_fraction": clear}


images = [image("2024-06-01", 0.60), image("2024-06-05", 0.62), image("2024-06-09", 0.64),
          image("2024-06-12", 0.70), image("2024-06-20", 0.50), image("2024-07-15", 0.80)]
counts = {"missing weather": 0}
rows = b3.rows_for_field({"id": "f", "kind": "park"}, images, weather, normal, counts)
pairs = [(r["start_date"], r["date"]) for r in rows]
check("1. only pairs 7-20 days apart become rows",
      all(7 <= (date.fromisoformat(t) - date.fromisoformat(s)).days <= 20 for s, t in pairs)
      and ("2024-06-01", "2024-06-12") in pairs and ("2024-06-09", "2024-06-12") not in pairs
      and not any(t == "2024-07-15" for _, t in pairs))
row = next(r for r in rows if (r["start_date"], r["date"]) == ("2024-06-09", "2024-06-20"))
check("2. target = the later image; start = the earlier one; days ahead counted",
      row["ndvi"] == 0.50 and row["start_ndvi"] == 0.64 and row["days_ahead"] == 11)
check("3. recent average = last 3 clear images up to the start day", abs(row["recent_mean"] - 0.62) < 1e-9)
check("4. trend per day over those images: (0.64 - 0.60) / 8 days", abs(row["trend_per_day"] - 0.005) < 1e-9)

changed = [dict(r) for r in images]
changed[3]["ndvi_mean"] = 0.10  # an image BETWEEN start (06-09) and target (06-20)
row2 = next(r for r in b3.rows_for_field({"id": "f", "kind": "park"}, changed, weather, normal, counts)
            if (r["start_date"], r["date"]) == ("2024-06-09", "2024-06-20"))
check("5. no peeking: images after the start day don't change the inputs",
      all(row2[k] == row[k] or (isinstance(row[k], float) and math.isnan(row[k]))
          for k in b3.ALL_FEATURES))
first = next(r for r in rows if r["start_date"] == "2024-06-01")
check("6. only one recent image -> trend is missing (NaN), never made up", math.isnan(first["trend_per_day"]))
check("7. weather equal to the normal -> 'vs normal' inputs are 0",
      row["rain_14_vs_normal"] == 0 and row["tmax_7_vs_normal"] == 0 and row["balance_14_vs_normal"] == 0)

w2025 = {(date(2025, 1, 1) + timedelta(days=k)).isoformat(): (99.0, 40.0, 9.0) for k in range(365)}
n = b3.weather_normal([{**weather, **w2025}])
check("8. the weather normal never uses the 2025 test year", n[180] == (1.0, 25.0, 4.0))

history = [(date(2020, 6, 1), 0.2), (date(2021, 6, 1), 0.6), (date(2023, 6, 1), 0.8), (date(2024, 6, 1), 0.9)]
check("9. the field's own usual NDVI uses only the 3 years BEFORE (not the same year)",
      abs(b3.own_normal(history, 2024, date(2024, 6, 5).timetuple().tm_yday) - 0.7) < 1e-9
      and b3.own_normal(history, 2020, 152) is None)
check("10. no earlier years -> own inputs missing (NaN)", math.isnan(row["own_gap"]))

check("11. the three likely artificial-turf fields are not used",
      not {f["id"] for f in b3.used_fields()} & set(b3.EXCLUDED_FIELDS) and len(b3.EXCLUDED_FIELDS) == 3)

X = np.random.default_rng(0).uniform(0.3, 0.8, size=(60, len(b3.ALL_FEATURES)))
y = X[:, t3.col("start_ndvi")] + 0.02
m = t3.ChangeModelV3({"max_iter": 20}, t3.SET_A, "start_ndvi").fit(X, y)
X2 = X.copy()
X2[:, t3.col("recent_mean")] = 0.0  # not one of set A's inputs
check("12. the model = starting point + learned change, and uses only its chosen inputs",
      np.allclose(m.predict(X), X[:, t3.col("start_ndvi")] + m.trees.predict(X[:, [t3.col(c) for c in t3.SET_A]]))
      and np.allclose(m.predict(X), m.predict(X2)))
check("13. input sets grow A < B < C and C adds only the field's own usual NDVI",
      set(t3.SET_A) < set(t3.SET_B) < set(t3.SET_C) and set(t3.SET_C) - set(t3.SET_B) == set(b3.OWN))
print(f"\nAll {passed} version 3 dataset/model tests passed.")

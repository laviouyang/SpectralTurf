"""
train_v3.py - Stage 10, version 3 of the AI (2026-11-07). See build_dataset_v3.py for why.

Same kind of model as version 2 (gradient boosting that predicts the CHANGE from a starting
NDVI), but trained on 7-20-day jumps and with more inputs. Everything below is CHOSEN ON 2024
ONLY (train 2019-2023, score 2024); the 2025 test year is touched once, by evaluate_v3.py.

What is chosen on 2024:
  - input set   A = the version 2 inputs (start NDVI, days ahead, weather, season)
                B = A + smoothing, trend, image quality, weather compared with normal
                C = B + the field's own usual NDVI for the time of year (earlier years)
  - starting point for "change": the start image, or the average of the recent images
  - tree settings (the same 4 as version 2)
If a smaller input set wins on 2024, we use it and say so (more inputs are not always better).

Run from the project folder:   python ml/train_v3.py   -> ml/model/ndvi_model_v3.joblib
"""

import csv
import sys
from datetime import date
from pathlib import Path

import joblib
import numpy as np
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.ensemble import HistGradientBoostingRegressor

ML_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ML_DIR))
from build_dataset_v3 import (ALL_FEATURES, DATASET_V3_FILE, EXCLUDED_FIELDS, OWN,  # noqa: E402
                              START_FEATURES, VS_NORMAL, WEATHER, load_normal, used_fields)
from train import CANDIDATE_SETTINGS, CUTOFF_TIMES, TEST_YEAR, TRAIN_YEARS, VALIDATION_YEAR, mae  # noqa: E402

MODEL_V3_FILE = ML_DIR / "model" / "ndvi_model_v3.joblib"

SET_A = ["start_ndvi", "days_ahead"] + WEATHER + ["day_of_year"]
SET_B = SET_A + [f for f in START_FEATURES if f != "start_ndvi"] + VS_NORMAL
SET_C = SET_B + OWN
INPUT_SETS = {"A (version 2 inputs)": SET_A,
              "B (+ smoothing, trend, image quality, weather vs normal)": SET_B,
              "C (B + field's own usual NDVI)": SET_C}
BASES = ["start_ndvi", "recent_mean"]
BASE_TEXT = {"start_ndvi": "start image", "recent_mean": "average of recent images"}


def load_dataset_v3(path=DATASET_V3_FILE):
    """X has ALL_FEATURES columns (missing = NaN); the model picks the columns it uses."""
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    X = np.array([[float(r[c]) if r[c] != "" else np.nan for c in ALL_FEATURES] for r in rows])
    y = np.array([float(r["ndvi"]) for r in rows])
    info = {
        "field_id": np.array([r["field_id"] for r in rows]),
        "kind": np.array([r["kind"] for r in rows]),
        "year": np.array([int(r["year"]) for r in rows]),
        "day_of_year": np.array([int(float(r["day_of_year"])) for r in rows]),
    }
    return X, y, info


def col(name):
    return ALL_FEATURES.index(name)


class ChangeModelV3(RegressorMixin, BaseEstimator):
    """NDVI = starting point (start image or recent average) + the change the trees expect.
    Takes the full ALL_FEATURES table and uses only its chosen inputs."""

    def __init__(self, settings, inputs, base):
        self.settings = settings
        self.inputs = inputs
        self.base = base
        self.trees = HistGradientBoostingRegressor(random_state=0, **settings)

    def _x(self, X):
        return X[:, [col(n) for n in self.inputs]]

    def fit(self, X, y):
        self.trees.fit(self._x(X), y - X[:, col(self.base)])
        self.n_features_in_ = X.shape[1]
        return self

    def predict(self, X):
        return X[:, col(self.base)] + self.trees.predict(self._x(X))


def candidates():
    for set_name, inputs in INPUT_SETS.items():
        for base in BASES:
            for settings in CANDIDATE_SETTINGS:
                yield set_name, inputs, base, settings


def choose_v3(X, y, info):
    """Train every candidate on 2019-2023 and score it on 2024; keep the best."""
    train = np.isin(info["year"], list(TRAIN_YEARS))
    val = info["year"] == VALIDATION_YEAR
    if not train.any() or not val.any():
        raise ValueError("The dataset needs rows from 2019-2023 and from 2024.")
    results = []
    for set_name, inputs, base, settings in candidates():
        model = ChangeModelV3(settings, inputs, base).fit(X[train], y[train])
        predicted = model.predict(X[val])
        results.append({"mae": mae(y[val], predicted), "set": set_name, "inputs": inputs, "base": base,
                        "settings": settings, "model": model, "predicted": predicted})
    best = min(results, key=lambda r: r["mae"])
    return {**best, "validation_mae": best["mae"], "model_2019_2023": best["model"],
            "validation_residuals": y[val] - best["predicted"], "all": results}


def main():
    X, y, info = load_dataset_v3()
    chosen = choose_v3(X, y, info)
    typical_error = chosen["validation_mae"]
    cutoff = CUTOFF_TIMES * typical_error
    final = ChangeModelV3(chosen["settings"], chosen["inputs"], chosen["base"]).fit(X, y)
    checked = list(dict.fromkeys(chosen["inputs"] + [chosen["base"]]))
    MODEL_V3_FILE.parent.mkdir(exist_ok=True)
    joblib.dump({
        "version": 3,
        "model": final,
        "features": ALL_FEATURES,          # the app computes all of these
        "used_features": checked,          # ... the model uses these
        "input_set": chosen["set"],
        "base": chosen["base"],
        "predicts": f"{BASE_TEXT[chosen['base']]} NDVI + predicted change, 7-20 days ahead",
        "settings": chosen["settings"],
        "typical_error": round(typical_error, 4),
        "weather_cutoff": round(cutoff, 4),
        "cutoff_rule": f"actual NDVI more than {CUTOFF_TIMES} x typical error below expected",
        "trained_on_years": sorted({int(v) for v in info["year"]}),
        "rows": int(len(y)),
        "fields": int(len(set(info["field_id"]))),
        "excluded_fields": EXCLUDED_FIELDS,
        "feature_ranges": {n: [float(np.nanmin(X[:, col(n)])), float(np.nanmax(X[:, col(n)]))] for n in checked},
        "weather_normal": load_normal(used_fields()),
        "created": date.today().isoformat(),
    }, MODEL_V3_FILE)

    print(f"Candidates tried (trained 2019-2023, scored on {VALIDATION_YEAR}); best per input set + start:")
    for set_name in INPUT_SETS:
        for base in BASES:
            best = min((r for r in chosen["all"] if r["set"] == set_name and r["base"] == base), key=lambda r: r["mae"])
            mark = "  <- chosen" if best["model"] is chosen["model"] else ""
            print(f"  {set_name:<58} start = {BASE_TEXT[base]:<25} MAE {best['mae']:.4f}{mark}")
    print(f"\nChosen: {chosen['set']}, start = {BASE_TEXT[chosen['base']]}, settings {chosen['settings']}")
    print(f"Typical {VALIDATION_YEAR} error (MAE): {typical_error:.4f}; cutoff {cutoff:.4f}")
    print(f"Final model trained on {len(y)} rows from {len(set(info['field_id']))} fields. Saved {MODEL_V3_FILE}")
    print(f"The {TEST_YEAR} test is run once by: python ml/evaluate_v3.py")
    return 0


if __name__ == "__main__":
    # Run as module "train_v3" so the saved file refers to train_v3.ChangeModelV3 (backend can load it).
    import train_v3
    sys.exit(train_v3.main())

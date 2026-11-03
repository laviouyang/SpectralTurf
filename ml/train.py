"""
train.py - Stage 10, Step 5: train the AI that predicts how green a field should be.

The model: scikit-learn's HistGradientBoostingRegressor ("gradient boosting"). It builds many
small decision trees one after another; each new tree learns to fix the mistakes of the trees
before it. It learns from the training table (ml/data/dataset.csv) how NDVI depends on the
previous NDVI, recent rain, water demand (ET0), heat and the season. We don't write those rules.

Version 2 (2026-11-01). Version 1 did NOT beat "same as last time" (ml/results_v1.md). Two
design fixes, chosen by reasoning and checked only on the 2024 validation year:
  - the model predicts the CHANGE since the previous image (prediction = previous NDVI +
    predicted change), so it starts from "same as last time" and only learns what the weather adds
  - field size is no longer an input: v1 used it to recognize individual fields (it was the
    #2 input), which can't help on a field the model has never seen

How the data is used (no peeking at the test year):
  - 2019-2023: training      - 2024: validation      - 2025: test (only used by evaluate.py)
  1. A few model settings are each trained on 2019-2023 and scored on 2024; the best is kept.
  2. "Weather doesn't explain this" cutoff = CUTOFF_TIMES x the typical 2024 error (mean
     absolute error, MAE). A field more than that far BELOW its prediction gets the message.
  3. The final model for the app is trained on ALL years with the chosen settings, so it
     knows the most recent behavior. Its accuracy is measured by evaluate.py (which trains
     separate test models that never see the test year or the test fields).

Run from the project folder:   python ml/train.py
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
from build_dataset import DATASET_FILE, FEATURES  # noqa: E402

# The inputs the model actually uses (field size removed, see above).
MODEL_FEATURES = [f for f in FEATURES if f != "area_m2"]
PREV = MODEL_FEATURES.index("prev_ndvi")

MODEL_FILE = ML_DIR / "model" / "ndvi_model.joblib"
TRAIN_YEARS, VALIDATION_YEAR, TEST_YEAR = range(2019, 2024), 2024, 2025
CUTOFF_TIMES = 2  # "more than 2x the typical error below the prediction" (a project choice)

# The settings we try. Small trees and a slow learning rate are less likely to memorize noise.
CANDIDATE_SETTINGS = [
    {"learning_rate": 0.05, "max_iter": 200, "max_depth": 3},
    {"learning_rate": 0.05, "max_iter": 400, "max_depth": 3},
    {"learning_rate": 0.05, "max_iter": 200, "max_depth": None},
    {"learning_rate": 0.1, "max_iter": 100, "max_depth": 3},
]


def load_dataset(path=DATASET_FILE):
    """The training table as numpy arrays: X (features), y (NDVI), and the row details."""
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    X = np.array([[float(r[c]) for c in MODEL_FEATURES] for r in rows])
    y = np.array([float(r["ndvi"]) for r in rows])
    info = {
        "field_id": np.array([r["field_id"] for r in rows]),
        "kind": np.array([r["kind"] for r in rows]),
        "year": np.array([int(r["year"]) for r in rows]),
        "day_of_year": np.array([int(float(r["day_of_year"])) for r in rows]),
    }
    return X, y, info


class ChangeModel(RegressorMixin, BaseEstimator):
    """Predicts NDVI as: previous NDVI + the change the trees expect from weather and season."""

    def __init__(self, settings):
        self.settings = settings
        # random_state: the same data always gives the same model (repeatable results).
        self.trees = HistGradientBoostingRegressor(random_state=0, **settings)

    def fit(self, X, y):
        self.trees.fit(X, y - X[:, PREV])  # learn the change, not the level
        self.n_features_in_ = X.shape[1]
        return self

    def predict(self, X):
        return X[:, PREV] + self.trees.predict(X)


def make_model(settings):
    return ChangeModel(settings)


def mae(actual, predicted):
    """Mean absolute error: on average, how far off the predictions are (in NDVI units)."""
    return float(np.mean(np.abs(np.asarray(actual) - np.asarray(predicted))))


def choose_settings(X, y, info):
    """Train each candidate on 2019-2023, score it on 2024, keep the best. Also returns the
    2024 errors, which set the 'weather doesn't explain this' cutoff."""
    train = np.isin(info["year"], list(TRAIN_YEARS))
    val = info["year"] == VALIDATION_YEAR
    if not train.any() or not val.any():
        raise ValueError("The dataset needs rows from 2019-2023 and from 2024.")
    results = []
    for settings in CANDIDATE_SETTINGS:
        model = make_model(settings).fit(X[train], y[train])
        predicted = model.predict(X[val])
        results.append((mae(y[val], predicted), settings, model, predicted))
    best_mae, best_settings, best_model, val_predicted = min(results, key=lambda r: r[0])
    return {
        "settings": best_settings, "validation_mae": best_mae, "model_2019_2023": best_model,
        "validation_residuals": y[val] - val_predicted,  # actual minus predicted
        "all_candidates": [(r[1], r[0]) for r in results],
    }


def main():
    X, y, info = load_dataset()
    chosen = choose_settings(X, y, info)
    typical_error = chosen["validation_mae"]
    cutoff = CUTOFF_TIMES * typical_error

    final = make_model(chosen["settings"]).fit(X, y)  # all years, for the app
    MODEL_FILE.parent.mkdir(exist_ok=True)
    joblib.dump({
        "model": final,
        "features": MODEL_FEATURES,
        "predicts": "previous NDVI + predicted change",
        "settings": chosen["settings"],
        "typical_error": round(typical_error, 4),
        "weather_cutoff": round(cutoff, 4),
        "cutoff_rule": f"actual NDVI more than {CUTOFF_TIMES} x typical error below expected",
        "trained_on_years": sorted({int(v) for v in info["year"]}),
        "rows": int(len(y)),
        "fields": int(len(set(info["field_id"]))),
        "feature_ranges": {name: [float(X[:, i].min()), float(X[:, i].max())]
                           for i, name in enumerate(MODEL_FEATURES)},
        "created": date.today().isoformat(),
    }, MODEL_FILE)

    print("Settings tried (trained 2019-2023, scored on 2024):")
    for settings, score in chosen["all_candidates"]:
        mark = "  <- chosen" if settings == chosen["settings"] else ""
        print(f"  {settings}: MAE {score:.4f}{mark}")
    print(f"\nTypical 2024 error (MAE): {typical_error:.4f} NDVI")
    print(f"'Weather doesn't explain this' cutoff: actual more than {cutoff:.4f} below expected")
    print(f"Final model trained on {len(y)} rows from {len(set(info['field_id']))} fields, "
          f"years {min(info['year'])}-{max(info['year'])}.")
    print(f"Saved {MODEL_FILE}")
    print("Run python ml/evaluate.py for the honest test on 2025 and on unseen fields.")
    return 0


if __name__ == "__main__":
    # Run main() from the module "train" (not "__main__"), so the saved model file refers to
    # train.ChangeModel and the backend (backend/predict.py) can load it.
    import train
    sys.exit(train.main())

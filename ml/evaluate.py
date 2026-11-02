"""
evaluate.py - Stage 10, Step 5: how good is the AI, honestly?

Two separate tests, both on data the model never saw:
  1. TIME SPLIT  - train on 2019-2023 (settings chosen on 2024), then predict every 2025 date.
                   "Does it work on a new year?"
  2. FIELD SPLIT - the fields are split into 5 groups (~20% each). Five times, a model is trained
                   on the other 80% of fields and predicts the held-out 20%, all years.
                   "Does it work on fields it has never seen?" Every field is tested once.

Both are compared with two simple baselines (no AI):
  - "same as last time":  predict the previous clear NDVI
  - "seasonal average":   that field's average NDVI within 15 days of the same day of the
                          year, in OTHER years (time split: only 2019-2023)
Score: MAE, mean absolute error = on average how far off, in NDVI units. Lower is better.

Also: which inputs matter most (permutation importance, as a chart), and how often the
"weather doesn't explain this" cutoff would fire.
Everything is printed and saved to ml/results.md (with the date) and ml/feature_importance.png.
Only numbers from this file may be reported (see CLAUDE.md).

Run from the project folder (after build_dataset.py):   python ml/evaluate.py
"""

import sys
from datetime import date
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from sklearn.inspection import permutation_importance
from sklearn.model_selection import GroupKFold

ML_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ML_DIR))
from train import MODEL_FEATURES as FEATURES  # noqa: E402
from train import (CUTOFF_TIMES, TEST_YEAR, TRAIN_YEARS, VALIDATION_YEAR, choose_settings,  # noqa: E402
                   load_dataset, mae, make_model)

RESULTS_FILE = ML_DIR / "results.md"
BOOTSTRAP_ROUNDS = 1000
CHART_FILE = ML_DIR / "feature_importance.png"
SEASON_WINDOW_DAYS = 15
FIELD_GROUPS = 5

# Plain-language names for the chart and table.
FEATURE_TEXT = {
    "prev_ndvi": "previous NDVI", "days_since_prev": "days since previous image",
    "rain_7": "rain, last 7 days", "rain_14": "rain, last 14 days", "rain_30": "rain, last 30 days",
    "et0_7": "water demand (ET0), 7 days", "et0_14": "water demand (ET0), 14 days",
    "et0_30": "water demand (ET0), 30 days", "balance_14": "rain minus ET0, 14 days",
    "balance_30": "rain minus ET0, 30 days", "tmax_7": "avg high temp, 7 days",
    "tmax_14": "avg high temp, 14 days", "day_of_year": "season (day of year)", "area_m2": "field size",
}


def seasonal_baseline(y, info, rows, allowed_years):
    """For each row: the same field's average NDVI within 15 days of the same day of year, in
    other allowed years. Returns (predictions, how many rows had no such history)."""
    predictions, no_history = np.full(len(rows), np.nan), 0
    for k, i in enumerate(rows):
        same = ((info["field_id"] == info["field_id"][i])
                & (info["year"] != info["year"][i])
                & np.isin(info["year"], list(allowed_years))
                & (np.abs(info["day_of_year"] - info["day_of_year"][i]) <= SEASON_WINDOW_DAYS))
        if same.any():
            predictions[k] = y[same].mean()
        else:
            no_history += 1
    return predictions, no_history


def score_table(actual, model_pred, last_pred, season_pred):
    """MAE for the model and both baselines, on the rows where the seasonal baseline exists
    (so all three are compared on exactly the same rows)."""
    ok = ~np.isnan(season_pred)
    return {"rows": int(ok.sum()),
            "model": mae(actual[ok], model_pred[ok]),
            "same as last time": mae(actual[ok], last_pred[ok]),
            "seasonal average": mae(actual[ok], season_pred[ok])}


def bootstrap_gain(actual, model_pred, base_pred, fields, rounds=BOOTSTRAP_ROUNDS):
    """Is the model's advantage real or luck? Re-draw the FIELDS at random (with replacement)
    many times and recompute (baseline MAE - model MAE) each time. If the middle 95% of those
    results is entirely above 0, the model is reliably better; if it includes 0, the difference
    could be luck. Whole fields are re-drawn because dates of one field are not independent."""
    rng = np.random.default_rng(0)
    names = np.unique(fields)
    rows_of = {name: np.where(fields == name)[0] for name in names}
    gains = []
    for _ in range(rounds):
        rows = np.concatenate([rows_of[n] for n in rng.choice(names, size=len(names), replace=True)])
        gains.append(mae(actual[rows], base_pred[rows]) - mae(actual[rows], model_pred[rows]))
    low, high = np.percentile(gains, [2.5, 97.5])
    return mae(actual, base_pred) - mae(actual, model_pred), float(low), float(high)


def verdict(gain, low, high, base_mae):
    if low > 0:
        return f"YES, reliably: {gain:.4f} lower error ({gain / base_mae:.0%} better); 95% range {low:+.4f} to {high:+.4f}"
    if high < 0:
        return f"NO, reliably worse by {-gain:.4f}; 95% range {low:+.4f} to {high:+.4f}"
    return (f"NO CLEAR DIFFERENCE: {gain:+.4f} ({gain / base_mae:+.0%}); the 95% range {low:+.4f} to "
            f"{high:+.4f} includes 0, so it could be luck")


def draw_chart(names, values, path):
    """A simple horizontal bar chart with Pillow (no extra installs)."""
    width, row, left = 760, 30, 260
    img = Image.new("RGB", (width, 60 + row * len(names)), "white")
    d = ImageDraw.Draw(img)
    d.text((10, 10), "Which inputs matter most (permutation importance on 2024)", fill="black")
    top = max(max(values), 1e-9)
    for k, (name, value) in enumerate(zip(names, values)):
        y = 40 + k * row
        d.text((10, y + 6), name, fill="black")
        length = int((width - left - 80) * max(value, 0) / top)
        d.rectangle([left, y + 4, left + length, y + row - 6], fill=(31, 94, 59))
        d.text((left + length + 6, y + 6), f"{value:.4f}", fill="black")
    img.save(path)


def main():
    X, y, info = load_dataset()
    out = []

    def say(line=""):
        print(line)
        out.append(line)

    n_fields = len(set(info["field_id"]))
    say(f"# Stage 10 AI results, version 2 ({date.today().isoformat()})")
    say()
    say("Version 2 predicts the change since the previous image and no longer uses field size "
        "(version 1 did not beat 'same as last time'; its results are kept in results_v1.md). "
        "These changes were made AFTER seeing version 1's test results, so version 2's test numbers "
        "are slightly optimistic.")
    say()
    say(f"Dataset: {len(y)} rows from {n_fields} fields, years {info['year'].min()}-{info['year'].max()}. "
        "Target: mean NDVI of the field on a clear satellite date.")
    say("MAE = mean absolute error in NDVI units (lower is better). Baselines use no AI.")

    # ---- 1. Time split ----
    chosen = choose_settings(X, y, info)
    model = chosen["model_2019_2023"]
    test = np.where(info["year"] == TEST_YEAR)[0]
    if len(test) == 0:
        say(f"No {TEST_YEAR} rows: the time-split test can't run.")
        return 1
    season_pred, no_hist = seasonal_baseline(y, info, test, TRAIN_YEARS)
    time_scores = score_table(y[test], model.predict(X[test]), X[test, FEATURES.index("prev_ndvi")], season_pred)

    say()
    say(f"## 1. Time split: train 2019-2023, settings chosen on {VALIDATION_YEAR}, test {TEST_YEAR}")
    say(f"Chosen settings: {chosen['settings']} (validation MAE {chosen['validation_mae']:.4f})")
    say(f"Test rows compared: {time_scores['rows']} ({no_hist} rows with no seasonal history left out "
        "so all three methods are scored on the same rows)")
    say("```")
    for name in ("model", "same as last time", "seasonal average"):
        say(f"{name:<20}MAE {time_scores[name]:.4f}")
    say("```")

    # ---- 2. Field split ----
    field_pred = np.full(len(y), np.nan)
    for train_idx, test_idx in GroupKFold(n_splits=min(FIELD_GROUPS, n_fields)).split(X, y, info["field_id"]):
        fold_model = make_model(chosen["settings"]).fit(X[train_idx], y[train_idx])
        field_pred[test_idx] = fold_model.predict(X[test_idx])
    every = np.arange(len(y))
    season_all, no_hist_all = seasonal_baseline(y, info, every, range(2019, TEST_YEAR + 1))
    field_scores = score_table(y, field_pred, X[:, FEATURES.index("prev_ndvi")], season_all)

    say()
    say(f"## 2. Field split: {FIELD_GROUPS} rounds, each holding out ~20% of the fields (all years)")
    say("Every field is predicted once, by a model that never saw that field. (The seasonal "
        "baseline uses the field's own other years, which the model never sees.)")
    say(f"Rows compared: {field_scores['rows']} ({no_hist_all} rows with no seasonal history left out)")
    say("```")
    for name in ("model", "same as last time", "seasonal average"):
        say(f"{name:<20}MAE {field_scores[name]:.4f}")
    say("```")
    say("By field type (field split, model vs. same as last time):")
    say("```")
    for kind in ("sports", "baseball", "park"):
        rows = info["kind"] == kind
        if rows.any():
            say(f"{kind:<10}{int(rows.sum()):>6} rows   model {mae(y[rows], field_pred[rows]):.4f}   "
                f"same as last time {mae(y[rows], X[rows, FEATURES.index('prev_ndvi')]):.4f}")
    say("```")

    say()
    say("How far ahead the prediction is (field split): weather can only matter when there is time")
    say("for the grass to change, so errors are shown by days since the previous image.")
    say("```")
    gap = X[:, FEATURES.index("days_since_prev")]
    for low, high in ((1, 3), (4, 7), (8, 14), (15, 45)):
        rows = (gap >= low) & (gap <= high)
        if rows.any():
            say(f"{low:>2}-{high:<2} days {int(rows.sum()):>6} rows   model {mae(y[rows], field_pred[rows]):.4f}   "
                f"same as last time {mae(y[rows], X[rows, FEATURES.index('prev_ndvi')]):.4f}")
    say("```")

    # ---- Honest verdict ----
    say()
    say("## Does the model beat the best baseline ('same as last time')?")
    say(f"Checked by re-drawing the fields at random {BOOTSTRAP_ROUNDS} times (bootstrap). "
        "Positive = model better.")
    prev_col = FEATURES.index("prev_ndvi")
    time_pred = model.predict(X[test])
    checks = [
        ("Time split, 2025, all rows", y[test], time_pred, X[test, prev_col], info["field_id"][test]),
        ("Field split, unseen fields, all rows", y, field_pred, X[:, prev_col], info["field_id"]),
    ]
    week = gap >= 8
    checks.append(("Field split, previous image 8+ days old", y[week], field_pred[week], X[week, prev_col],
                   info["field_id"][week]))
    t_gap = X[test, FEATURES.index("days_since_prev")] >= 8
    checks.append(("Time split, previous image 8+ days old", y[test][t_gap], time_pred[t_gap],
                   X[test, prev_col][t_gap], info["field_id"][test][t_gap]))
    for name, actual, pred, base, fields in checks:
        gain, low, high = bootstrap_gain(actual, pred, base, fields)
        say(f"- {name} ({len(actual)} rows): {verdict(gain, low, high, mae(actual, base))}")

    # ---- Cutoff ----
    residuals = chosen["validation_residuals"]
    cutoff = CUTOFF_TIMES * chosen["validation_mae"]
    flagged = np.mean(residuals < -cutoff)
    say()
    say("## 'Weather doesn't explain this' cutoff")
    say(f"Typical {VALIDATION_YEAR} error (MAE) {chosen['validation_mae']:.4f}; cutoff = {CUTOFF_TIMES} x "
        f"that = {cutoff:.4f}. In {VALIDATION_YEAR}, {flagged:.1%} of clear dates were more than this "
        "far below the model's expectation (the message would have shown).")

    # ---- Feature importance ----
    val = info["year"] == VALIDATION_YEAR
    importance = permutation_importance(model, X[val], y[val], scoring="neg_mean_absolute_error",
                                        n_repeats=10, random_state=0).importances_mean
    order = np.argsort(importance)[::-1]
    names = [FEATURE_TEXT[FEATURES[i]] for i in order]
    draw_chart(names, importance[order], CHART_FILE)
    say()
    say("## Which inputs matter most")
    say(f"How much worse the {VALIDATION_YEAR} MAE gets when one input is shuffled (bigger = more important). "
        f"Chart: {CHART_FILE.name}")
    say("```")
    top = max(importance.max(), 1e-9)
    for i in order:
        bar = "#" * int(30 * max(importance[i], 0) / top)
        say(f"{FEATURE_TEXT[FEATURES[i]]:<30}{importance[i]:>8.4f}  {bar}")
    say("```")

    RESULTS_FILE.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"\nSaved {RESULTS_FILE} and {CHART_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
evaluate_v3.py - Stage 10, version 3: the honest test (run ONCE on 2025, 2026-11-07).

Same two tests as version 2 (evaluate.py), on version 3's question "NDVI 7-20 days after a
clear image":
  1. TIME SPLIT  - train 2019-2023 (inputs + settings chosen on 2024), predict every 2025 pair.
  2. FIELD SPLIT - 5 rounds, each holding out ~20% of the fields; every field predicted once
                   by a model that never saw it.
Baselines (no AI), scored on exactly the same rows:
  - "same as last time":  the start image's NDVI
  - "recent average":     the average of the last (up to) 3 clear images up to the start day.
                          Added in version 3: version 3 itself uses this smoothing, so we must
                          show the AI beats the smoothing alone, not only one noisy image.
  - "seasonal average":   the field's average NDVI within 15 days of the same day of year in
                          OTHER years (time split: only 2019-2023)
Luck check: 1,000 re-draws of the fields (bootstrap), as in version 2.
Also: version 2's design asked the same 7-20-day question (to see what the jumps and the new
inputs add), the version 1 / 2 / 3 table, the cutoff, and which inputs matter.

Writes ml/results_v3.md and ml/feature_importance_v3.png. Only these numbers may be reported.

Run from the project folder (after build_dataset_v3.py and train_v3.py):   python ml/evaluate_v3.py
"""

import csv
import re
import sys
from datetime import date
from pathlib import Path

import numpy as np
from sklearn.inspection import permutation_importance
from sklearn.model_selection import GroupKFold

ML_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ML_DIR))
import train as v2  # noqa: E402
from build_dataset import DATASET_FILE  # noqa: E402
from build_dataset_v3 import ALL_FEATURES, EXCLUDED_FIELDS, MAX_DAYS_AHEAD, MIN_DAYS_AHEAD  # noqa: E402
from evaluate import (BOOTSTRAP_ROUNDS, FEATURE_TEXT, FIELD_GROUPS, bootstrap_gain, draw_chart,  # noqa: E402
                      seasonal_baseline, verdict)
from train_v3 import (BASE_TEXT, BASES, INPUT_SETS, ChangeModelV3, choose_v3, col,  # noqa: E402
                      load_dataset_v3)
from train import CUTOFF_TIMES, TEST_YEAR, TRAIN_YEARS, VALIDATION_YEAR, mae  # noqa: E402

RESULTS_V3_FILE = ML_DIR / "results_v3.md"
CHART_V3_FILE = ML_DIR / "feature_importance_v3.png"
TEXT = {**FEATURE_TEXT, "start_ndvi": "start image NDVI", "recent_mean": "average of recent images",
        "trend_per_day": "recent trend (per day)", "start_clear": "start image clear fraction",
        "start_std": "start image pixel spread", "days_ahead": "days ahead",
        "rain_14_vs_normal": "rain 14 days vs normal", "tmax_7_vs_normal": "high temp 7 days vs normal",
        "tmax_14_vs_normal": "high temp 14 days vs normal",
        "balance_14_vs_normal": "rain minus ET0 14 days vs normal",
        "own_gap": "start vs field's usual", "own_step": "field's usual change"}
METHODS = ("model", "same as last time", "recent average", "seasonal average")


def old_results(path):
    """(time-split MAEs, field-split MAEs) as printed by evaluate.py for versions 1 and 2."""
    text = path.read_text(encoding="utf-8")
    parts = re.split(r"## 2\. ", text)
    def grab(part):
        return {name: float(re.search(rf"{name}\s+MAE ([0-9.]+)", part).group(1))
                for name in ("model", "same as last time", "seasonal average")}
    return grab(parts[0]), grab(parts[1])


def v2_design_on_v3_question(X):
    """Version 2's model (back-to-back images, v2 inputs, v2's chosen settings), trained on
    2019-2023 from the same 22 fields, asked the version 3 question (7-20 days ahead)."""
    with open(DATASET_FILE, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["field_id"] not in EXCLUDED_FIELDS
                and int(r["year"]) in TRAIN_YEARS]
    X2 = np.array([[float(r[c]) for c in v2.MODEL_FEATURES] for r in rows])
    y2 = np.array([float(r["ndvi"]) for r in rows])
    model = v2.make_model({"learning_rate": 0.1, "max_iter": 100, "max_depth": 3}).fit(X2, y2)
    same_names = {"prev_ndvi": "start_ndvi", "days_since_prev": "days_ahead"}
    Xq = np.column_stack([X[:, col(same_names.get(c, c))] for c in v2.MODEL_FEATURES])
    return model.predict(Xq)


def main():
    X, y, info = load_dataset_v3()
    out = []

    def say(line=""):
        print(line)
        out.append(line)

    start = X[:, col("start_ndvi")]
    recent = X[:, col("recent_mean")]
    n_fields = len(set(info["field_id"]))
    say(f"# Stage 10 AI results, VERSION 3 ({date.today().isoformat()})")
    say()
    say("What changed from version 2 (student decision 2026-11-07):")
    say(f"1. The model predicts NDVI {MIN_DAYS_AHEAD}-{MAX_DAYS_AHEAD} days after a clear image (every pair of clear "
        "images that far apart), not the next back-to-back image. This is what the app asks (next week, 14-day What-if).")
    say("2. New inputs: average of recent images, recent trend, image quality, weather compared with the "
        "Denver-area normal (2019-2024), and the field's own usual NDVI (earlier years).")
    say("3. Three likely artificial-turf fields removed: " + "; ".join(EXCLUDED_FIELDS.values()) + ".")
    say()
    say("Honesty notes: which inputs, starting point and settings to use was chosen on 2024 only; 2025 was "
        "tested once, by this file. But the version 3 IDEAS came after seeing the version 1 and 2 test "
        "results, so these test numbers are still slightly optimistic. Version 3 answers a different "
        "(harder) question than versions 1-2 (7-20 days ahead instead of the next image, usually 1-3 days), "
        "so compare each version with its own baselines, not the raw MAEs across versions.")
    say()
    say(f"Dataset: {len(y)} rows (start -> target pairs) from {n_fields} fields, target years "
        f"{info['year'].min()}-{info['year'].max()}. Target: mean NDVI of the field on the target date.")
    say("MAE = mean absolute error in NDVI units (lower is better). Baselines use no AI.")

    # ---- Choice on 2024 ----
    chosen = choose_v3(X, y, info)
    say()
    say(f"## 0. Chosen on {VALIDATION_YEAR} only (trained 2019-2023)")
    say("```")
    for set_name in INPUT_SETS:
        for base in BASES:
            best = min((r for r in chosen["all"] if r["set"] == set_name and r["base"] == base), key=lambda r: r["mae"])
            mark = "  <- chosen" if best["model"] is chosen["model"] else ""
            say(f"{set_name:<58} start = {BASE_TEXT[base]:<25} MAE {best['mae']:.4f}{mark}")
    say("```")
    say(f"Chosen: input set {chosen['set']}, start = {BASE_TEXT[chosen['base']]}, settings {chosen['settings']}.")
    model = chosen["model_2019_2023"]

    # ---- 1. Time split ----
    test = np.where(info["year"] == TEST_YEAR)[0]
    season_t, no_hist = seasonal_baseline(y, info, test, TRAIN_YEARS)
    time_pred = model.predict(X[test])
    ok_t = ~np.isnan(season_t)
    preds_t = {"model": time_pred, "same as last time": start[test], "recent average": recent[test],
               "seasonal average": season_t}
    time_scores = {m: mae(y[test][ok_t], p[ok_t]) for m, p in preds_t.items()}
    say()
    say(f"## 1. Time split: train 2019-2023, chosen on {VALIDATION_YEAR}, test {TEST_YEAR} (run once)")
    say(f"Test rows compared: {int(ok_t.sum())} ({no_hist} rows with no seasonal history left out)")
    say("```")
    for m in METHODS:
        say(f"{m:<20}MAE {time_scores[m]:.4f}")
    v2q = v2_design_on_v3_question(X[test])
    say(f"{'version 2 design':<20}MAE {mae(y[test][ok_t], v2q[ok_t]):.4f}   (same rows; trained on back-to-back "
        "images, same 22 fields)")
    say("```")

    # ---- 2. Field split ----
    field_pred = np.full(len(y), np.nan)
    for tr, te in GroupKFold(n_splits=min(FIELD_GROUPS, n_fields)).split(X, y, info["field_id"]):
        fold = ChangeModelV3(chosen["settings"], chosen["inputs"], chosen["base"]).fit(X[tr], y[tr])
        field_pred[te] = fold.predict(X[te])
    every = np.arange(len(y))
    season_f, no_hist_f = seasonal_baseline(y, info, every, range(2019, TEST_YEAR + 1))
    ok_f = ~np.isnan(season_f)
    preds_f = {"model": field_pred, "same as last time": start, "recent average": recent,
               "seasonal average": season_f}
    field_scores = {m: mae(y[ok_f], p[ok_f]) for m, p in preds_f.items()}
    say()
    say(f"## 2. Field split: {FIELD_GROUPS} rounds, each holding out ~20% of the fields (all years)")
    say(f"Rows compared: {int(ok_f.sum())} ({no_hist_f} rows with no seasonal history left out)")
    say("```")
    for m in METHODS:
        say(f"{m:<20}MAE {field_scores[m]:.4f}")
    say("```")
    say("By field type (field split):")
    say("```")
    for kind in ("sports", "baseball", "park"):
        r = info["kind"] == kind
        if r.any():
            say(f"{kind:<10}{int(r.sum()):>6} rows   model {mae(y[r], field_pred[r]):.4f}   same as last time "
                f"{mae(y[r], start[r]):.4f}   recent average {mae(y[r], recent[r]):.4f}")
    say("```")
    say("By days ahead (field split):")
    say("```")
    ahead = X[:, col("days_ahead")]
    for low, high in ((7, 10), (11, 14), (15, 20)):
        r = (ahead >= low) & (ahead <= high)
        say(f"{low:>2}-{high:<2} days {int(r.sum()):>6} rows   model {mae(y[r], field_pred[r]):.4f}   same as last time "
            f"{mae(y[r], start[r]):.4f}   recent average {mae(y[r], recent[r]):.4f}")
    say("```")

    # ---- Luck check ----
    say()
    say(f"## Does version 3 beat the baselines? ({BOOTSTRAP_ROUNDS:,} re-draws of the fields)")
    say("Positive = model better. 'Reliably' = the middle 95% of the re-draws is entirely above 0.")
    fields_t, fields_f = info["field_id"][test], info["field_id"]
    for name in ("same as last time", "recent average", "seasonal average"):
        gain, low, high = bootstrap_gain(y[test][ok_t], time_pred[ok_t], preds_t[name][ok_t], fields_t[ok_t])
        say(f"- 2025 vs {name} ({int(ok_t.sum())} rows): {verdict(gain, low, high, time_scores[name])}")
    for name in ("same as last time", "recent average", "seasonal average"):
        gain, low, high = bootstrap_gain(y[ok_f], field_pred[ok_f], preds_f[name][ok_f], fields_f[ok_f])
        say(f"- Unseen fields vs {name} ({int(ok_f.sum())} rows): {verdict(gain, low, high, field_scores[name])}")
    gain, low, high = bootstrap_gain(y[test][ok_t], time_pred[ok_t], v2q[ok_t], fields_t[ok_t])
    say(f"- 2025 vs version 2 design on the same question: {verdict(gain, low, high, mae(y[test][ok_t], v2q[ok_t]))}")

    # ---- Versions side by side ----
    v1_t, v1_f = old_results(ML_DIR / "results_v1.md")
    v2_t, v2_f = old_results(ML_DIR / "results_v2.md")
    say()
    say("## Versions 1, 2 and 3 side by side (each with its own baselines)")
    say("v1/v2: next back-to-back image, 25 fields (results_v1.md, results_v2.md). "
        f"v3: {MIN_DAYS_AHEAD}-{MAX_DAYS_AHEAD} days ahead, 22 fields. 'vs last time' = how much lower the "
        "model's error is than 'same as last time' (positive = better).")
    say("```")
    say(f"{'':<10}{'2025 model':>11}{'last time':>11}{'seasonal':>10}{'vs last':>9}   "
        f"{'unseen model':>13}{'last time':>11}{'seasonal':>10}{'vs last':>9}")
    for label, t, f in (("v1", v1_t, v1_f), ("v2", v2_t, v2_f),
                        ("v3", time_scores, field_scores)):
        say(f"{label:<10}{t['model']:>11.4f}{t['same as last time']:>11.4f}{t['seasonal average']:>10.4f}"
            f"{(t['same as last time'] - t['model']) / t['same as last time']:>+9.0%}   "
            f"{f['model']:>13.4f}{f['same as last time']:>11.4f}{f['seasonal average']:>10.4f}"
            f"{(f['same as last time'] - f['model']) / f['same as last time']:>+9.0%}")
    say("```")

    # ---- Cutoff ----
    cutoff = CUTOFF_TIMES * chosen["validation_mae"]
    flagged = np.mean(chosen["validation_residuals"] < -cutoff)
    say()
    say("## 'Weather doesn't explain this' cutoff")
    say(f"Typical {VALIDATION_YEAR} error (MAE) {chosen['validation_mae']:.4f}; cutoff = {CUTOFF_TIMES} x that = "
        f"{cutoff:.4f}. In {VALIDATION_YEAR}, {flagged:.1%} of pairs were more than this far below the "
        "model's expectation.")

    # ---- Importance ----
    val = info["year"] == VALIDATION_YEAR
    imp = permutation_importance(model, X[val], y[val], scoring="neg_mean_absolute_error",
                                 n_repeats=5, random_state=0).importances_mean
    used = [col(n) for n in chosen["inputs"]]
    order = sorted(used, key=lambda i: -imp[i])
    draw_chart([TEXT[ALL_FEATURES[i]] for i in order], [imp[i] for i in order], CHART_V3_FILE)
    say()
    say("## Which inputs matter most")
    say(f"How much worse the {VALIDATION_YEAR} MAE gets when one input is shuffled. Chart: {CHART_V3_FILE.name}")
    say("```")
    top = max(max(imp[i] for i in order), 1e-9)
    for i in order:
        say(f"{TEXT[ALL_FEATURES[i]]:<34}{imp[i]:>8.4f}  {'#' * int(30 * max(imp[i], 0) / top)}")
    say("```")

    RESULTS_V3_FILE.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"\nSaved {RESULTS_V3_FILE} and {CHART_V3_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

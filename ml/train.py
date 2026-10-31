"""
train.py - Step 3: train OUR OWN classifier on Lavi's labeled photos, and save it for the app.

How it works:
  1. CLIP turns every photo into 512 numbers (its embedding). CLIP itself is not changed.
  2. Logistic regression (a simple, well-known classifier) learns which patterns in those
     numbers go with which label. It outputs a probability for each of the 4 labels.
  3. The trained classifier is saved to ml/model/turf_photo_clf.joblib. The backend uses it
     instead of zero-shot as soon as this file exists.

This uses ALL photos, so the saved model is as good as it can be. To MEASURE how good it is
on fields it has never seen, run evaluate.py (it trains separate test models with whole
sites held out). Accuracy on the photos a model was trained on would be meaningless.

Run from the project folder:
    python ml/train.py                 (uses the 0.60 "uncertain" cutoff)
    python ml/train.py --cutoff 0.7    (after choosing a cutoff from evaluate.py's table)
"""

import argparse
import sys
from datetime import date
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import clip_model
from dataset import LABELS, ML_DIR, check

MODEL_FILE = Path("model") / "turf_photo_clf.joblib"

# How strongly the classifier is held back from trusting tiny details (logistic regression's
# "C"; smaller = more careful). 1.0 is scikit-learn's default and a project choice. If
# evaluate.py shows the model very sure (above 0.9) yet often wrong on unseen sites, try 0.1.
REGULARIZATION_C = 1.0


def make_classifier():
    """
    The classifier settings, shared with evaluate.py so both train the same way.
    StandardScaler: CLIP's 512 numbers are all tiny (about +-0.05). Rescaling each one to a
      similar range first lets logistic regression learn properly; without it, every
      probability stayed near 25% and every photo came out "Uncertain".
    class_weight="balanced": a label with fewer photos still counts as much as the others.
    max_iter=2000: enough steps for the math to finish (converge).
    """
    return make_pipeline(StandardScaler(), LogisticRegression(C=REGULARIZATION_C, class_weight="balanced",
                                                            max_iter=2000))


def probabilities_in_label_order(classifier, embeddings):
    """predict_proba only has columns for labels it was trained on; put them in LABELS order
    (a label it never saw gets probability 0)."""
    raw = classifier.predict_proba(embeddings)
    out = np.zeros((len(embeddings), len(LABELS)))
    for column, label in enumerate(classifier.classes_):
        out[:, LABELS.index(label)] = raw[:, column]
    return out


def main(root=ML_DIR, cutoff=clip_model.DEFAULT_CUTOFF):
    root = Path(root)
    rows, problems, _ = check(root)
    if problems:
        print(f"Note: {len(problems)} photo problem(s); those photos are left out. "
              "Run python ml/check_dataset.py to see them.\n")

    missing = [label for label in LABELS if not any(r["label"] == label for r in rows)]
    if missing:
        print(f"Can't train yet: no usable photos for {', '.join(missing)}.")
        print("Every label needs photos, or the model could never suggest it.")
        return 1
    if not 0 < cutoff < 1:
        print("The cutoff must be between 0 and 1.")
        return 1

    embeddings = clip_model.embed_dataset(rows, root / "embeddings.npz")
    labels = [row["label"] for row in rows]
    classifier = make_classifier().fit(embeddings, labels)

    model_path = root / MODEL_FILE
    model_path.parent.mkdir(exist_ok=True)
    joblib.dump(
        {
            "classifier": classifier,
            "labels": LABELS,
            "cutoff": cutoff,
            "clip_model": clip_model.MODEL_NAME,
            "trained_on": date.today().isoformat(),
            "photos": len(rows),
            "sites": len({r["site_key"] for r in rows}),
            "photos_per_label": {label: labels.count(label) for label in LABELS},
        },
        model_path,
    )
    print(f"Trained on {len(rows)} photos from {len({r['site_key'] for r in rows})} sites.")
    for label in LABELS:
        print(f"  {label:<14}{labels.count(label):>4} photos")
    print(f"Uncertain cutoff: {cutoff:.2f}")
    print(f"Saved {model_path}")
    print("The backend uses this model after it restarts. Run python ml/evaluate.py to measure it.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train the turf photo classifier.")
    parser.add_argument("--cutoff", type=float, default=clip_model.DEFAULT_CUTOFF,
                        help="confidence below which the app says 'Uncertain' (default 0.60)")
    parser.add_argument("--root", default=ML_DIR, help=argparse.SUPPRESS)  # used by the tests
    args = parser.parse_args()
    sys.exit(main(args.root, args.cutoff))

"""
zero_shot.py - Step 2: how well does CLIP do with NO training on our photos?

For each labeled photo, CLIP compares it to one sentence per class (see PROMPTS in
clip_model.py) and picks the closest. We compare that to Lavi's label.
This "baseline" is the number the trained classifier (Step 3) has to beat.

Run from the project folder:   python ml/zero_shot.py
"""

import sys
from pathlib import Path

import numpy as np

import clip_model
from dataset import LABELS, ML_DIR, check
from report import accuracy, print_confusion


def main(root=ML_DIR):
    root = Path(root)
    rows, problems, _ = check(root)
    if problems:
        print(f"Note: {len(problems)} photo problem(s); those photos are left out. "
              "Run python ml/check_dataset.py to see them.\n")
    if not rows:
        print("No usable labeled photos yet, so there is nothing to measure.")
        print("Add photos to ml/data/<label>/ and ml/photos.csv first (see ml/README.md).")
        return 0

    embeddings = clip_model.embed_dataset(rows, root / "embeddings.npz")
    probabilities = clip_model.zero_shot_probabilities(embeddings)
    true = [row["label"] for row in rows]
    predicted = [LABELS[i] for i in probabilities.argmax(axis=1)]
    confidence = probabilities.max(axis=1)
    cutoff = clip_model.DEFAULT_CUTOFF

    print(f"Zero-shot CLIP ({clip_model.MODEL_NAME}), no training")
    print(f"Photos: {len(rows)} from {len({r['site_key'] for r in rows})} site(s)\n")
    print(f"Accuracy: {accuracy(true, predicted):.1%}  ({sum(t == p for t, p in zip(true, predicted))} of {len(rows)} correct)")
    print(f"Below the {cutoff:.2f} confidence cutoff ('Uncertain'): {int(np.sum(confidence < cutoff))} photo(s)\n")
    print("Confusion matrix (rows = your label, columns = CLIP's answer):")
    print_confusion(true, predicted)
    print("\nSentences used:")
    for label in LABELS:
        print(f"  {label:<14}\"{clip_model.PROMPTS[label]}\"")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ML_DIR))

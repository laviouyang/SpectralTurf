"""
evaluate.py - Step 3: how accurate is the photo AI on FIELDS IT HAS NEVER SEEN?

Why "by site": photos of the same field look alike (same grass, light, soil). If some photos
of a field were used for training and others for testing, the test would be too easy and the
accuracy would look better than it really is. So we always hold out WHOLE sites:

  - The sites are split into groups ("folds"). With 5 or fewer sites, each site is its own
    fold (leave-one-site-out); with more, sites are split into 5 groups.
  - For each fold, a fresh classifier is trained on the OTHER sites only, then predicts the
    held-out site's photos.
  - So every photo gets exactly one prediction, from a model that never saw its field.

It prints, and saves to ml/results.md (with today's date):
  - accuracy of the trained classifier vs. zero-shot CLIP on the same photos
  - precision and recall for each label, and confusion matrices
  - accuracy per held-out site
  - how many photos fall below each possible "uncertain" cutoff, to help choose one

Only numbers printed by this script may be reported (see CLAUDE.md).

Run from the project folder:   python ml/evaluate.py
"""

import sys
from datetime import date
from pathlib import Path

import numpy as np
from sklearn.metrics import classification_report
from sklearn.model_selection import GroupKFold, LeaveOneGroupOut

import clip_model
from dataset import LABELS, ML_DIR, check
from report import accuracy, confusion_table
from train import make_classifier, probabilities_in_label_order

MAX_FOLDS = 5
CUTOFFS_TO_COMPARE = [0.40, 0.50, 0.60, 0.70, 0.80, 0.90]


def held_out_site_predictions(embeddings, labels, sites):
    """Train on all sites but one group, predict that group; repeat for every group."""
    n_sites = len(set(sites))
    splitter = LeaveOneGroupOut() if n_sites <= MAX_FOLDS else GroupKFold(n_splits=MAX_FOLDS)
    probabilities = np.full((len(labels), len(LABELS)), np.nan)
    skipped = []
    labels = np.asarray(labels)
    for train_index, test_index in splitter.split(embeddings, labels, groups=sites):
        held_out = sorted(set(np.asarray(sites)[test_index]))
        if len(set(labels[train_index])) < 2:
            skipped.append(held_out)  # the other sites only have one label: can't train
            continue
        classifier = make_classifier().fit(embeddings[train_index], labels[train_index])
        probabilities[test_index] = probabilities_in_label_order(classifier, embeddings[test_index])
    return probabilities, skipped, splitter


def cutoff_lines(true, probabilities):
    """For each cutoff: how many photos would be 'Uncertain', and how accurate the rest are."""
    predicted = np.array([LABELS[i] for i in probabilities.argmax(axis=1)])
    confidence = probabilities.max(axis=1)
    true = np.asarray(true)
    lines = [f"{'cutoff':>8}{'uncertain':>12}{'accuracy of the rest':>24}"]
    for cutoff in CUTOFFS_TO_COMPARE:
        sure = confidence >= cutoff
        rest = f"{accuracy(true[sure], predicted[sure]):.1%} of {sure.sum()}" if sure.any() else "(none left)"
        lines.append(f"{cutoff:>8.2f}{f'{(~sure).sum()} ({(~sure).mean():.0%})':>12}{rest:>24}")
    return lines


def main(root=ML_DIR):
    root = Path(root)
    rows, problems, warnings = check(root)
    out = []  # every line printed here also goes into results.md

    def say(line=""):
        print(line)
        out.append(line)

    if problems:
        say(f"Note: {len(problems)} photo problem(s); those photos are left out "
            "(see python ml/check_dataset.py).")
    sites = [r["site_key"] for r in rows]
    present = sorted({r["label"] for r in rows}, key=LABELS.index)
    if len(set(sites)) < 2 or len(present) < 2:
        say("Not enough photos to evaluate yet: need at least 2 sites and 2 labels.")
        say("Add photos (see ml/README.md), then run this again.")
        return 1

    embeddings = clip_model.embed_dataset(rows, root / "embeddings.npz")
    true = [r["label"] for r in rows]
    trained_probabilities, skipped, splitter = held_out_site_predictions(embeddings, true, sites)
    zero_shot_probabilities = clip_model.zero_shot_probabilities(embeddings)

    done = ~np.isnan(trained_probabilities).any(axis=1)
    if not done.any():
        say("Every held-out site left only one label to train on, so nothing could be tested.")
        return 1
    true_done = np.asarray(true)[done]
    trained_predicted = [LABELS[i] for i in trained_probabilities[done].argmax(axis=1)]
    zero_predicted = [LABELS[i] for i in zero_shot_probabilities[done].argmax(axis=1)]

    say(f"# Photo AI results ({date.today().isoformat()})")
    say()
    say(f"Photos: {len(rows)} from {len(set(sites))} sites. Labels present: {', '.join(present)}.")
    method = ("leave-one-site-out" if isinstance(splitter, LeaveOneGroupOut)
              else f"sites split into {MAX_FOLDS} groups")
    say(f"Test method: {method}. Every photo was predicted by a model that never saw its site.")
    if skipped:
        say(f"Not tested (the remaining sites had only one label to learn from): "
            f"{'; '.join(', '.join(group) for group in skipped)} -> {int((~done).sum())} photo(s) left out.")
    for label in LABELS:
        label_sites = {r["site_key"] for r in rows if r["label"] == label}
        if len(label_sites) == 1:
            say(f"Warning: all '{label}' photos come from one site, so when that site is held out "
                f"the model has never seen a '{label}' photo and can't get those right.")
    say()
    say("## Accuracy on unseen sites")
    say(f"Zero-shot CLIP (no training): {accuracy(true_done, zero_predicted):.1%}")
    say(f"Trained classifier:           {accuracy(true_done, trained_predicted):.1%}")
    say(f"(both on the same {int(done.sum())} photos)")
    say()
    say("## Trained classifier: precision and recall per label")
    say("precision = when it says this label, how often it's right; recall = of the photos")
    say("that really are this label, how many it found.")
    say("```")
    for line in classification_report(true_done, trained_predicted, labels=LABELS,
                                      zero_division=0).rstrip().splitlines():
        say(line)
    say("```")
    say()
    say("## Confusion matrices (rows = true label, columns = AI's answer)")
    say("Trained classifier:")
    say("```")
    for line in confusion_table(true_done, trained_predicted):
        say(line)
    say("```")
    say("Zero-shot CLIP:")
    say("```")
    for line in confusion_table(true_done, zero_predicted):
        say(line)
    say("```")
    say()
    say("## Trained classifier accuracy per held-out site")
    say("```")
    site_names = {}
    for r in rows:
        site_names.setdefault(r["site_key"], r["site"])
    site_array = np.asarray(sites)[done]
    for key in sorted(set(site_array)):
        mask = site_array == key
        say(f"{site_names[key][:30]:<32}{accuracy(true_done[mask], np.asarray(trained_predicted)[mask]):>7.1%}"
            f"  ({int(mask.sum())} photos)")
    say("```")
    say()
    say("## Choosing the 'uncertain' cutoff (trained classifier)")
    say("Photos below the cutoff are shown as 'Uncertain - inspect in person'.")
    say("```")
    for line in cutoff_lines(true_done, trained_probabilities[done]):
        say(line)
    say("```")
    say("Zero-shot CLIP, same table:")
    say("```")
    for line in cutoff_lines(true_done, zero_shot_probabilities[done]):
        say(line)
    say("```")
    say("Note: the cutoff is chosen by looking at these same photos, so it fits them a little")
    say("better than it will fit new ones. To use a cutoff: python ml/train.py --cutoff 0.70")
    if warnings:
        say()
        say("## Dataset warnings")
        for w in warnings:
            say(f"- {w}")

    (root / "results.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"\nSaved {root / 'results.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ML_DIR))

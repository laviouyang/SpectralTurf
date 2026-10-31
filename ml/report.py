"""
report.py - Prints accuracy and a confusion matrix the same way in every script.

A confusion matrix is a table: each ROW is the true label, each COLUMN is what the AI said.
Numbers on the diagonal are correct answers; everything else is a mix-up, and shows WHICH
labels get confused (e.g. dry_stressed photos called worn_bare).
"""

import numpy as np
from sklearn.metrics import confusion_matrix

from dataset import LABELS


def accuracy(true, predicted):
    return float(np.mean(np.asarray(true) == np.asarray(predicted))) if len(true) else float("nan")


def confusion_table(true, predicted):
    """The confusion matrix as text lines (used for printing and for results.md)."""
    matrix = confusion_matrix(true, predicted, labels=LABELS)
    width = max(len(label) for label in LABELS) + 2
    corner = "true / AI said"
    lines = [f"{corner:<{width + 2}}" + "".join(f"{label[:12]:>13}" for label in LABELS)]
    for label, counts in zip(LABELS, matrix):
        lines.append(f"{label:<{width + 2}}" + "".join(f"{n:>13}" for n in counts))
    return lines


def print_confusion(true, predicted):
    for line in confusion_table(true, predicted):
        print(line)

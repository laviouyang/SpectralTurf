"""
check_dataset.py - Is the photo dataset ready? Counts photos per label and per site,
and lists anything that needs fixing.

Run from the project folder (with the backend venv active):
    python ml/check_dataset.py

Exit code 0 = no problems, 1 = something must be fixed (warnings don't count).
"""

import sys
from collections import Counter
from pathlib import Path

from dataset import (GOAL_PHOTOS_PER_LABEL, GOAL_SITES_PER_LABEL, LABELS, ML_DIR,
                     MIN_SITES_PER_LABEL, check)


def main(root=ML_DIR):
    rows, problems, warnings = check(root)

    print(f"Photo dataset in {Path(root)}")
    print(f"Usable photos: {len(rows)}\n")

    # Table 1: per label.
    print(f"{'Label':<14}{'Photos':>8}{'Sites':>7}   Goal ({GOAL_PHOTOS_PER_LABEL}+ photos, "
          f"{GOAL_SITES_PER_LABEL}+ sites)")
    print("-" * 60)
    for label in LABELS:
        photos = [r for r in rows if r["label"] == label]
        n_sites = len({r["site_key"] for r in photos})
        if len(photos) >= GOAL_PHOTOS_PER_LABEL and n_sites >= GOAL_SITES_PER_LABEL:
            status = "OK"
        elif n_sites < MIN_SITES_PER_LABEL:
            status = "needs more sites"
        else:
            status = "keep going"
        print(f"{label:<14}{len(photos):>8}{n_sites:>7}   {status}")

    # Table 2: per site (how many photos of each label at each field).
    if rows:
        names = {}
        for r in rows:
            names.setdefault(r["site_key"], r["site"])
        counts = Counter((r["site_key"], r["label"]) for r in rows)
        print(f"\n{'Site':<26}" + "".join(f"{label[:12]:>13}" for label in LABELS) + f"{'Total':>7}")
        print("-" * (26 + 13 * len(LABELS) + 7))
        for key in sorted(names):
            per_label = [counts[(key, label)] for label in LABELS]
            print(f"{names[key][:25]:<26}" + "".join(f"{n:>13}" for n in per_label) + f"{sum(per_label):>7}")

        dates = sorted(r["date"] for r in rows)
        print(f"\nPhoto dates: {dates[0]} to {dates[-1]}")
        winter = sum(r["date"].month in (11, 12, 1, 2, 3) for r in rows)
        if winter:
            print(f"{winter} photo(s) were taken Nov-Mar, when brown turf may be normal dormancy.")
    else:
        print("\nNo photos yet. Put photos in ml/data/<label>/ and add one row per photo")
        print("to ml/photos.csv (see ml/README.md).")

    if warnings:
        print("\nWarnings (worth knowing, nothing is blocked):")
        for w in warnings:
            print(f"  - {w}")
    if problems:
        print(f"\nProblems to fix ({len(problems)}). These photos are left out until fixed:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\nNo problems found.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ML_DIR))

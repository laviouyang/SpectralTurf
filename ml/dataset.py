"""
dataset.py - Reads the labeled turf photos (ml/data/ + ml/photos.csv) and checks them.

Shared by check_dataset.py, zero_shot.py, train.py and evaluate.py, so every script
uses exactly the same photos and the same rules.

Folder layout:
    ml/data/healthy/       photos of green, dense turf
    ml/data/dry_stressed/  thin, straw/yellow, dry-looking turf (still grass)
    ml/data/worn_bare/     grass worn away, bare soil from traffic
    ml/data/non_turf/      dirt infield, track, pavement, artificial turf
    ml/photos.csv          one row per photo: filename,label,site,date,notes
"""

import csv
from datetime import date
from pathlib import Path

from PIL import Image

ML_DIR = Path(__file__).resolve().parent

# The 4 classes. The order here is the order used everywhere (tables, probabilities).
LABELS = ["healthy", "dry_stressed", "worn_bare", "non_turf"]
LABEL_TEXT = {
    "healthy": "Healthy turf",
    "dry_stressed": "Dry / stressed turf",
    "worn_bare": "Worn / bare turf",
    "non_turf": "Not turf",
}

CSV_COLUMNS = ["filename", "label", "site", "date", "notes"]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Goals from docs/STAGE_9_PHOTO_AI.md (project goals, not scientific standards).
GOAL_PHOTOS_PER_LABEL = 30
GOAL_SITES_PER_LABEL = 3
MIN_SITES_PER_LABEL = 2  # fewer than this and a by-site test is impossible for that label

# EXIF tag numbers (a standard list of photo metadata fields).
EXIF_GPS_INFO = 34853


def site_key(site):
    """'Village Greens ' and 'village greens' must count as the SAME site, otherwise
    the by-site train/test split could put one field on both sides."""
    return " ".join(site.lower().split())


def open_image(path):
    """Open a photo the way every script should: fully decoded, upright, RGB."""
    from PIL import ImageOps

    with Image.open(path) as img:
        img.load()  # actually decode it, so broken files fail here
        img = ImageOps.exif_transpose(img)  # phones store "rotate me" in EXIF
        return img.convert("RGB")


def has_gps(path):
    try:
        with Image.open(path) as img:
            return bool(img.getexif().get(EXIF_GPS_INFO))
    except Exception:
        return False


def check(root=ML_DIR):
    """
    Read photos.csv and look at every photo.
    Returns (rows, problems, warnings):
      rows     - the usable photos: dicts with filename, label, site, site_key, date, notes, path
      problems - things that must be fixed (the photo is left out until then)
      warnings - things worth knowing that don't block anything
    """
    root = Path(root)
    data_dir = root / "data"
    csv_path = root / "photos.csv"
    rows, problems, warnings = [], [], []

    if not csv_path.exists():
        return [], [f"{csv_path} is missing. It needs the header: {','.join(CSV_COLUMNS)}"], []

    with open(csv_path, newline="", encoding="utf-8-sig") as f:  # -sig: Excel adds a BOM
        reader = csv.DictReader(f)
        if reader.fieldnames != CSV_COLUMNS:
            return [], [f"photos.csv header must be exactly: {','.join(CSV_COLUMNS)} "
                        f"(found: {','.join(reader.fieldnames or [])})"], []
        csv_rows = list(reader)

    seen = set()
    listed_files = set()
    for line_number, raw in enumerate(csv_rows, start=2):  # line 1 is the header
        row = {k: (raw.get(k) or "").strip() for k in CSV_COLUMNS}
        where = f"photos.csv line {line_number} ({row['filename'] or 'no filename'})"

        if not any(row.values()):
            continue  # blank line
        if not row["filename"]:
            problems.append(f"{where}: filename is empty.")
            continue
        if row["label"] not in LABELS:
            problems.append(f"{where}: label '{row['label']}' must be one of {', '.join(LABELS)}.")
            continue
        listed_files.add((row["label"], row["filename"].lower()))
        if (row["label"], row["filename"].lower()) in seen:
            problems.append(f"{where}: this photo is listed twice.")
            continue
        seen.add((row["label"], row["filename"].lower()))

        if not row["site"]:
            problems.append(f"{where}: site is empty (needed to test on unseen fields).")
            continue
        try:
            taken = date.fromisoformat(row["date"])
        except ValueError:
            problems.append(f"{where}: date '{row['date']}' must look like 2026-11-02.")
            continue

        path = data_dir / row["label"] / row["filename"]
        if not path.exists():
            elsewhere = [lab for lab in LABELS if (data_dir / lab / row["filename"]).exists()]
            if elsewhere:
                problems.append(f"{where}: labeled '{row['label']}' but the file is in "
                                f"data/{elsewhere[0]}/. Move it or fix the label.")
            else:
                problems.append(f"{where}: file not found at data/{row['label']}/{row['filename']}.")
            continue
        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            hint = " iPhone HEIC photos: export or share them as JPG." if path.suffix.lower() in {".heic", ".heif"} else ""
            problems.append(f"{where}: only .jpg, .png, .webp are supported.{hint}")
            continue
        try:
            open_image(path)
        except Exception as e:
            problems.append(f"{where}: the image can't be opened ({type(e).__name__}).")
            continue

        rows.append({**row, "site_key": site_key(row["site"]), "date": taken, "path": path})

    # Photos in the folders that have no row in photos.csv.
    for label in LABELS:
        folder = data_dir / label
        if not folder.exists():
            problems.append(f"Folder data/{label}/ is missing.")
            continue
        for path in sorted(folder.iterdir()):
            if path.name.startswith(".") or path.is_dir():
                continue  # .gitkeep and similar
            if (label, path.name.lower()) not in listed_files:
                problems.append(f"data/{label}/{path.name} has no row in photos.csv.")

    # Same site typed differently ("Memorial Park" vs "memorial park") is fine, but say so.
    spellings = {}
    for row in rows:
        spellings.setdefault(row["site_key"], set()).add(row["site"])
    for variants in spellings.values():
        if len(variants) > 1:
            warnings.append(f"These site names are treated as ONE site: {', '.join(sorted(variants))}.")

    # Sites per label: the by-site test needs each label at more than one field.
    for label in LABELS:
        n_sites = len({r["site_key"] for r in rows if r["label"] == label})
        if n_sites < MIN_SITES_PER_LABEL:
            warnings.append(f"'{label}' has photos from {n_sites} site(s); need at least "
                            f"{MIN_SITES_PER_LABEL} (goal {GOAL_SITES_PER_LABEL}).")

    n_gps = sum(has_gps(r["path"]) for r in rows)
    if n_gps:
        warnings.append(f"{n_gps} photo(s) contain GPS location data. That's fine here (the photo "
                        "files are git-ignored), but don't share the originals publicly.")

    return rows, problems, warnings

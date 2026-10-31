"""
photo_ai.py - The "Check a spot with a photo" AI, used by POST /api/photo/analyze.

A photo goes in; a SUGGESTION comes out: healthy, dry/stressed, worn/bare, or not turf,
with a confidence. It is never a diagnosis.

Which method is used:
  - If ml/model/turf_photo_clf.joblib exists (made by ml/train.py from Lavi's labeled
    photos), the trained classifier is used.
  - Until then, zero-shot CLIP is used, and every answer says "zero-shot (not yet trained)".

Privacy: the photo is checked in memory and then forgotten. It is only saved if the user
ticked "Allow this photo to improve the model", and then only after GPS and all other
photo metadata (EXIF) are removed.

The AI code lives in the ml/ folder; this file borrows it so both use exactly the same model.
"""

import io
import secrets
import sys
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageOps

ML_DIR = Path(__file__).resolve().parent.parent / "ml"
sys.path.insert(0, str(ML_DIR))  # lets us "import clip_model" from the ml/ folder

import clip_model  # noqa: E402  (must come after the line above)
from dataset import LABEL_TEXT, LABELS  # noqa: E402

MODEL_PATH = ML_DIR / "model" / "turf_photo_clf.joblib"
INBOX_DIR = ML_DIR / "inbox"  # photos users allowed us to keep, waiting to be labeled

MAX_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
OFF_SEASON_MONTHS = {11, 12, 1, 2, 3}  # Nov-Mar: Colorado turf may be dormant (brown)

# EXIF tag numbers for "when was this photo taken"
EXIF_IFD = 0x8769
EXIF_DATE_TAKEN = 0x9003  # DateTimeOriginal
EXIF_DATE = 0x0132  # DateTime


class PhotoError(Exception):
    """Something wrong with the uploaded file (the user can fix it)."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class ModelUnavailable(Exception):
    """The AI libraries or model can't be loaded on this computer."""


def read_photo(data):
    """Check the upload really is a jpg/png/webp under 10 MB. Returns (upright RGB image, date taken or None)."""
    if len(data) == 0:
        raise PhotoError("The file is empty.")
    if len(data) > MAX_BYTES:
        raise PhotoError("The photo is larger than 10 MB. Try a smaller one.", status=413)
    try:
        img = Image.open(io.BytesIO(data))
        file_format = img.format
        img.load()  # really decode it, so broken files fail here
    except Exception:
        # Don't trust the file name or what the browser says: only the contents count.
        raise PhotoError("That file isn't a readable image. Please upload a JPG, PNG, or WEBP photo.")
    if file_format not in ALLOWED_FORMATS:
        raise PhotoError(f"{file_format} files aren't supported. Please upload a JPG, PNG, or WEBP photo.")

    taken = None
    exif = img.getexif()
    for raw in (exif.get_ifd(EXIF_IFD).get(EXIF_DATE_TAKEN), exif.get(EXIF_DATE)):
        try:
            taken = datetime.strptime(str(raw).strip(), "%Y:%m:%d %H:%M:%S").date()
            break
        except (TypeError, ValueError):
            continue
    upright = ImageOps.exif_transpose(img).convert("RGB")  # phones store "rotate me" in EXIF
    return upright, taken


@lru_cache(maxsize=1)
def model():
    """Load the AI once and keep it. The first photo takes a few extra seconds."""
    try:
        clip_model.load()
        if not MODEL_PATH.exists():
            return {"trained": None, "cutoff": clip_model.DEFAULT_CUTOFF,
                    "method": "zero-shot (not yet trained)"}
        import joblib

        saved = joblib.load(MODEL_PATH)
    except ImportError as e:
        raise ModelUnavailable(f"The photo AI libraries aren't installed ({e.name}). "
                               "See ml/README.md for the install command.")
    except Exception as e:
        raise ModelUnavailable(f"The photo AI model couldn't be loaded ({type(e).__name__}).")
    return {
        "trained": saved,
        "cutoff": saved["cutoff"],
        "method": (f"trained classifier ({saved['photos']} labeled photos from {saved['sites']} "
                   f"sites, trained {saved['trained_on']})"),
    }


def save_for_training(img, taken):
    """Keep a photo the user allowed us to keep, with ALL metadata removed (GPS, camera, time).
    Copying only the pixels into a brand-new image leaves the EXIF behind."""
    clean = Image.frombytes("RGB", img.size, img.tobytes())
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{taken.isoformat()}_{datetime.now():%H%M%S}_{secrets.token_hex(3)}.jpg"
    clean.save(INBOX_DIR / name, "JPEG", quality=92)
    return name


def analyze(data, allow_training=False, today=None):
    """The whole photo check. Returns the JSON the website shows."""
    img, taken = read_photo(data)
    ai = model()

    embedding = clip_model.embed_images([img])
    if ai["trained"]:
        from train import probabilities_in_label_order

        probabilities = probabilities_in_label_order(ai["trained"]["classifier"], embedding)[0]
    else:
        probabilities = clip_model.zero_shot_probabilities(embedding)[0]

    best = int(probabilities.argmax())
    label = LABELS[best]
    confidence = float(probabilities[best])
    uncertain = confidence < ai["cutoff"]

    photo_date = taken or today or date.today()
    off_season = photo_date.month in OFF_SEASON_MONTHS
    notes = ["AI suggestion, not a diagnosis. Confirm in person."]
    if uncertain:
        notes.append("Uncertain - inspect in person.")
    if off_season:
        notes.append("Taken in the off-season (Nov-Mar): brown turf may be normal winter "
                     "dormancy, not a problem.")

    saved_as = save_for_training(img, photo_date) if allow_training else None
    return {
        "label": label,
        "label_text": LABEL_TEXT[label],
        "confidence": round(confidence, 3),
        "probabilities": {lab: round(float(p), 3) for lab, p in zip(LABELS, probabilities)},
        "uncertain": uncertain,
        "cutoff": ai["cutoff"],
        "method": ai["method"],
        "photo_date": photo_date.isoformat(),
        "date_source": "photo" if taken else "today (the photo has no date inside it)",
        "off_season": off_season,
        "note": " ".join(notes),
        "saved_for_training": saved_as is not None,
    }

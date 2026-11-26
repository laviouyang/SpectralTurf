"""
photo_classifier.py - Stage 11 on the website: "Check a photo" (added 2026-11-26).

Answers which of our 6 photo categories a turf photo LOOKS MOST LIKE. It is NOT a diagnosis
(rule approved by the student on 2026-11-26: always say "not a diagnosis - confirm with an expert").

How it works (no PyTorch on the server):
  1. The photo is checked (JPEG/PNG/WebP, at most 10 MB) and re-saved as a new PNG in memory.
     Re-saving drops hidden data (EXIF: GPS location, camera, time). Nothing is ever stored.
  2. It is resized + center-cropped to 224 x 224 and normalized, like CLIP's own image processor.
  3. CLIP's image part (int8 ONNX file, made by ml_photo/export_onnx.py) turns it into 512 numbers.
  4. A logistic regression (6 x 512 weights in photo_classifier_v1.json) turns those into a
     percentage per class. If the top percentage is below the Uncertain cutoff (chosen on training
     photos only), the answer is "Uncertain — inspect in person".

Files (committed): photo_model/clip_image_int8.onnx, photo_model/photo_classifier_v1.json.
The model is loaded on the first photo only (saves memory until someone uses it).
"""

import io
import json
import threading
from datetime import date
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

MODEL_DIR = Path(__file__).resolve().parent / "photo_model"
ONNX_FILE = MODEL_DIR / "clip_image_int8.onnx"
JSON_FILE = MODEL_DIR / "photo_classifier_v1.json"

MAX_PHOTO_BYTES = 10 * 1024 * 1024   # student's limit for "Check a photo"
MAX_PHOTO_PIXELS = 50_000_000        # JPEG: refuses absurd "image bombs" (JPEGs are decoded at reduced size)
# PNG and WebP can't be decoded at reduced size, and a 49-megapixel WebP needed ~1 GB of memory
# (measured 2026-11-26), so they are limited to 4 megapixels (e.g. 2300 x 1730) to stay well under
# Render's 512 MB. The website shrinks photos to 1600 px before sending, so this only stops misuse.
MAX_PNG_WEBP_PIXELS = 4_000_000
RESAVE_SIDE = 1024                   # the re-saved copy is at most 1024 px (CLIP only uses 224 px)
PHOTO_FORMATS = {"JPEG", "PNG", "WEBP"}

# Plain-language names shown to people (the JSON keeps the folder names).
CLASS_NAMES = {
    "healthy": "Healthy-looking grass",
    "drought": "Drought stress",
    "fungal_disease": "Fungal disease",
    "insect_damage": "Insect damage",
    "wear": "Wear (foot traffic)",
    "dormant": "Dormant grass",
}
NOT_A_DIAGNOSIS = "Not a diagnosis — confirm with an expert."
DORMANCY_NOTE = "Brown grass may be normal winter dormancy."
DORMANCY_MONTHS = {11, 12, 1, 2, 3}  # November to March (student's choice)
LABEL = "Photo check (AI): looks most like… — not a diagnosis"


class PhotoError(Exception):
    """A problem with the uploaded photo, shown to the user as a friendly message."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


_model = None
_lock = threading.Lock()


def load_model():
    """Load the ONNX session + weights once (thread-safe). Raises PhotoError if files are missing."""
    global _model
    with _lock:
        if _model is None:
            if not ONNX_FILE.exists() or not JSON_FILE.exists():
                raise PhotoError("The photo check is not set up on this server.", status=503)
            import onnxruntime as ort  # only imported when someone checks a photo
            options = ort.SessionOptions()
            options.intra_op_num_threads = 1      # small server: one core is enough, uses less memory
            options.enable_cpu_mem_arena = False  # give memory back after each photo
            session = ort.InferenceSession(str(ONNX_FILE), options, providers=["CPUExecutionProvider"])
            info = json.loads(JSON_FILE.read_text(encoding="utf-8"))
            _model = {"session": session, "info": info,
                      "coef": np.array(info["coef"], dtype=np.float64),
                      "intercept": np.array(info["intercept"], dtype=np.float64)}
        return _model


def clean_photo(raw):
    """Check the uploaded bytes and return a NEW image without any metadata (never stored)."""
    if not raw:
        raise PhotoError("No photo was received.")
    if len(raw) > MAX_PHOTO_BYTES:
        raise PhotoError(f"The photo is too big (max {MAX_PHOTO_BYTES // (1024 * 1024)} MB).", status=413)
    try:
        image = Image.open(io.BytesIO(raw))
        if image.format not in PHOTO_FORMATS:
            raise PhotoError("Please choose a JPEG, PNG or WebP photo.")
        limit = MAX_PHOTO_PIXELS if image.format == "JPEG" else MAX_PNG_WEBP_PIXELS
        if image.width * image.height > limit:
            raise PhotoError(f"The photo has too many pixels (max {limit // 1_000_000} megapixels"
                             f"{'' if image.format == 'JPEG' else ' for PNG/WebP'}).", status=413)
        if image.format == "JPEG":
            # Big phone JPEGs are decoded at 1/2, 1/4 or 1/8 size (never smaller than 1024 px), so a
            # 48-megapixel photo does not need ~150 MB of memory on the small server.
            image.draft("RGB", (RESAVE_SIDE, RESAVE_SIDE))
        image = ImageOps.exif_transpose(image)  # right way up before the metadata is dropped
        image = image.convert("RGB")
        image.thumbnail((RESAVE_SIDE, RESAVE_SIDE))
        out = io.BytesIO()
        # Lossless PNG, no exif= argument -> the new copy has the same pixels but no metadata.
        # (A JPEG re-save changed CLIP's answer on many test photos - checked 2026-11-26.)
        image.save(out, "PNG")
        out.seek(0)
        return Image.open(out).convert("RGB")
    except PhotoError:
        raise
    except Exception:
        raise PhotoError("The photo could not be read. Please choose a JPEG, PNG or WebP photo.")


def preprocess(image, model):
    """CLIP's image preparation: shortest side -> 224 (bicubic), center crop 224 x 224,
    pixel values 0-1, then minus the mean and divided by the std of each color."""
    info = model["info"]
    size = info["image_size"]
    w, h = image.size
    scale = size / min(w, h)
    new_w, new_h = max(size, round(w * scale)), max(size, round(h * scale))
    image = image.resize((new_w, new_h), Image.BICUBIC)
    left, top = (new_w - size) // 2, (new_h - size) // 2
    image = image.crop((left, top, left + size, top + size))
    x = np.asarray(image, dtype=np.float32) / 255.0
    x = (x - np.array(info["mean"], dtype=np.float32)) / np.array(info["std"], dtype=np.float32)
    return x.transpose(2, 0, 1)[None].astype(np.float32)  # shape (1, 3, 224, 224)


def probabilities(embedding, model):
    """Logistic regression on the (length-1) CLIP features -> one probability per class (sums to 1)."""
    e = embedding / np.linalg.norm(embedding)
    scores = model["coef"] @ e + model["intercept"]
    scores = np.exp(scores - scores.max())
    return scores / scores.sum()


def percentages(probs):
    """Whole-number percentages that add up to EXACTLY 100 (largest-remainder rounding)."""
    raw = np.asarray(probs, dtype=np.float64) * 100
    out = np.floor(raw).astype(int)
    for i in np.argsort(-(raw - out))[: 100 - out.sum()]:
        out[i] += 1
    return out.tolist()


def result_from_probabilities(probs, info, today=None):
    """The answer shown to the user (also given to Ask SpectralTurf)."""
    classes = info["classes"]
    pct = percentages(probs)
    top = int(np.argmax(probs))
    uncertain = float(probs[top]) < info["uncertain_cutoff"]
    month = (today or date.today()).month
    notes = [NOT_A_DIAGNOSIS]
    if month in DORMANCY_MONTHS:
        notes.append(DORMANCY_NOTE)
    return {
        "status": "ok",
        "label": LABEL,
        "classes": [{"id": c, "name": CLASS_NAMES.get(c, c), "percent": p}
                    for c, p in sorted(zip(classes, pct), key=lambda cp: -cp[1])],
        "top_class": {"id": classes[top], "name": CLASS_NAMES.get(classes[top], classes[top]),
                      "percent": pct[top]},
        "uncertain": uncertain,
        "answer": (info["uncertain_label"] if uncertain
                   else f"Looks most like: {CLASS_NAMES.get(classes[top], classes[top])} ({pct[top]}%)"),
        "uncertain_cutoff_percent": round(info["uncertain_cutoff"] * 100),
        "notes": notes,
        "accuracy": accuracy_facts(info),
    }


def accuracy_facts(info):
    """The REAL test results of the website model (from ml_photo/export_onnx.py), for 'How accurate is this?'."""
    r = (info.get("test_results") or {}).get("int8")
    if not r:
        return None
    t = info["test_results"]
    return {"test_photos": t["test_photos"],
            "accuracy_percent": round(r["accuracy"] * 100, 1),
            "balanced_accuracy_percent": round(r["balanced_accuracy"] * 100, 1),
            "uncertain_percent": round(r["uncertain_rate"] * 100, 1),
            "answered_accuracy_percent": round(r["answered_accuracy"] * 100, 1),
            "per_class_test_photos": t["per_class_test_photos"],
            "limitation": "Most training photos came from public datasets and published articles, not from "
                          "real sports fields, and each category came mostly from one source, so real-world "
                          "accuracy may be lower. Wear and dormant had only 2 test photos each."}


def classify(raw, today=None):
    """Uploaded bytes -> result dict. The photo is only kept in memory during this call."""
    image = clean_photo(raw)
    model = load_model()
    x = preprocess(image, model)
    embedding = model["session"].run(None, {"pixel_values": x})[0][0]
    return result_from_probabilities(probabilities(embedding, model), model["info"], today)

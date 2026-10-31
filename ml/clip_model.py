"""
clip_model.py - The CLIP image model, shared by the ml/ scripts and the backend.

What CLIP does (in one line for judges): it turns a photo into a list of 512 numbers, an
"embedding", that captures what the photo looks like. It can do the same for a sentence,
and a photo's numbers end up close to the numbers of sentences that describe it.

Two ways we use it:
  1. Zero-shot (no training): compare the photo to one sentence per class and pick the
     closest. CLIP has never seen our labels; it only knows the sentences.
  2. Trained (Step 3): give the embeddings of Lavi's labeled photos to a small classifier
     (logistic regression) that learns which numbers go with which label.

Model: openai/clip-vit-base-patch32 (open source). The first run downloads it once
(about 600 MB) into the Hugging Face cache. It runs on the CPU; no API key.
"""

import os
from functools import lru_cache
from pathlib import Path

import numpy as np

from dataset import LABELS, open_image

MODEL_NAME = "openai/clip-vit-base-patch32"

# Windows can't make the shortcut links the model download cache prefers; it works fine
# without them, so hide that long warning.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

# One sentence per class for the zero-shot method (from docs/STAGE_9_PHOTO_AI.md).
PROMPTS = {
    "healthy": "a photo of healthy green grass",
    "dry_stressed": "a photo of dry yellow stressed grass",
    "worn_bare": "a photo of worn grass with bare soil",
    "non_turf": "a photo of a dirt infield, running track, pavement, or artificial turf",
}

# Below this confidence, the app says "Uncertain - inspect in person".
# A project choice (0.60 to start); Step 3 shows how many photos fall below each cutoff.
DEFAULT_CUTOFF = 0.60

EMBEDDING_BATCH = 16  # photos per batch; small enough for any computer's memory


@lru_cache(maxsize=1)
def load():
    """Load CLIP once (later calls reuse it). Takes a few seconds."""
    import torch
    from transformers import CLIPModel, CLIPProcessor

    torch.set_grad_enabled(False)  # we only use the model, we never change it
    model = CLIPModel.from_pretrained(MODEL_NAME).eval()
    processor = CLIPProcessor.from_pretrained(MODEL_NAME)
    return model, processor


def _as_tensor(output):
    # Newer versions of the transformers library wrap the result in an object.
    return output if hasattr(output, "shape") else output.pooler_output


def _unit_length(vectors):
    """Scale each embedding to length 1, so comparing two is just a dot product."""
    vectors = np.asarray(vectors, dtype=np.float32)
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


def embed_images(images):
    """List of PIL images -> array (n, 512) of unit-length embeddings."""
    model, processor = load()
    chunks = []
    for start in range(0, len(images), EMBEDDING_BATCH):
        batch = processor(images=images[start:start + EMBEDDING_BATCH], return_tensors="pt")
        chunks.append(_as_tensor(model.get_image_features(**batch)).numpy())
    return _unit_length(np.concatenate(chunks)) if chunks else np.zeros((0, 512), np.float32)


@lru_cache(maxsize=1)
def text_embeddings():
    """The 4 class sentences -> array (4, 512), in LABELS order."""
    model, processor = load()
    batch = processor(text=[PROMPTS[label] for label in LABELS], return_tensors="pt", padding=True)
    return _unit_length(_as_tensor(model.get_text_features(**batch)).numpy())


def zero_shot_probabilities(image_embeddings):
    """
    How close is each photo to each class sentence? CLIP's own scale (about 100) turns the
    closeness into scores, and softmax turns scores into probabilities that add up to 1.
    """
    model, _ = load()
    scale = float(model.logit_scale.exp())
    scores = scale * (np.asarray(image_embeddings) @ text_embeddings().T)
    scores -= scores.max(axis=1, keepdims=True)  # keeps exp() from overflowing
    probabilities = np.exp(scores)
    return probabilities / probabilities.sum(axis=1, keepdims=True)


def embed_dataset(rows, cache_path):
    """
    Embeddings for every photo in rows (same order). Saved in cache_path, so each photo
    is only processed once. A photo is re-done if its file changes (size or time).
    """
    cache_path = Path(cache_path)
    cache = {}
    if cache_path.exists():
        saved = np.load(cache_path)
        cache = dict(zip(saved["keys"].tolist(), saved["vectors"]))

    def key(row):
        stat = row["path"].stat()
        return f"{row['label']}/{row['filename']}|{stat.st_size}|{int(stat.st_mtime)}"

    keys = [key(row) for row in rows]
    todo = [i for i, k in enumerate(keys) if k not in cache]
    if todo:
        print(f"Computing CLIP embeddings for {len(todo)} photo(s) (cached: {len(rows) - len(todo)})...")
        new = embed_images([open_image(rows[i]["path"]) for i in todo])
        for i, vector in zip(todo, new):
            cache[keys[i]] = vector
        np.savez(cache_path, keys=np.array(list(cache)), vectors=np.array(list(cache.values())))
    if not rows:
        return np.zeros((0, 512), np.float32)
    return np.array([cache[k] for k in keys])

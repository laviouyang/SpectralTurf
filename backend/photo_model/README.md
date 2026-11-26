# photo_model — files for "Check a photo" (used by backend/photo_classifier.py)

Made by `ml_photo/export_onnx.py` (2026-11-26). Comparison with the original model: `ml_photo/results_onnx.md`.

- `clip_image_int8.onnx` — the image part of OpenAI's CLIP ViT-B/32 (`openai/clip-vit-base-patch32`),
  exported to ONNX with its weights stored as int8 (weight-only). CLIP is © OpenAI, released under the
  MIT License (https://github.com/openai/CLIP/blob/main/LICENSE). We did not change its weights except
  for this rounding.
- `photo_classifier_v1.json` — our logistic regression (6 categories × 512 weights), the Uncertain
  cutoff (0.75, chosen on training photos only), the image preparation settings and the real test results.

No photos are in this folder or in git. The result is "looks most like", not a diagnosis.

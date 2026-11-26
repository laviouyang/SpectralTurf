# Stage 11 photo classifier — shrunken (int8 ONNX) model vs original

Date: 2026-11-26. Made by `ml_photo/export_onnx.py` (numbers copied from `results_onnx.json`).
Same 379 test photos as `results_v1.md`. Uncertain below 75%.

- Same top class as the original: **99.7%**
- Same final answer (including "Uncertain"): **98.9%** (4 photos differ)
- Largest change in any class percentage: 17.3%
- Image features vs original (cosine similarity, 1 = identical): fp32 ONNX min 0.9893; int8 min 0.9902, mean 0.9997
- File size: fp32 351.6 MB -> int8 98.3 MB

| | Accuracy | Balanced accuracy | Uncertain rate | Accuracy on answered photos |
|---|---|---|---|---|
| Original (PyTorch) | 90.0% | 69.3% | 27.4% (104) | 97.1% |
| Shrunken (int8 ONNX, website) | 90.0% | 69.3% | 27.4% (104) | 96.7% |

Per-class recall of the website model (without Uncertain): healthy 80.4% (158 photos), drought 99.0% (194 photos), fungal_disease 100.0% (8 photos), insect_damage 86.7% (15 photos), wear 0.0% (2 photos), dormant 50.0% (2 photos)

## Photos where the answer changed

| Photo | True label | Original | Int8 |
|---|---|---|---|
| drought/grassland_dry_center_recording_2022_10_18_14_08_38_0_zed2i_0_rgb_raw_image_raw_color00038.png | drought | drought | Uncertain |
| drought/ref_drought-stressed-lawn_061.jpg | drought | Uncertain | wear |
| fungal_disease/ref_powdery-mildew_029.jpg | fungal_disease | Uncertain | fungal_disease |
| healthy/grassland_grass_center_recording_2022_10_18_12_14_41_0_zed2i_0_rgb_raw_image_raw_color00000.png | healthy | healthy | Uncertain |

Limitations (same as v1): each class came mostly from ONE kind of source (robot-camera video frames for
healthy/drought, figures from articles for fungal/insect, a few web photos for wear/dormant), so the
model may partly recognize the source instead of the turf problem. Wear and dormant have 2 test photos each.

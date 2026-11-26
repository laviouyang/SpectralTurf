"""
export_onnx.py - Stage 11: shrink the v1 photo model so it can run on the website's small
backend (Render, 512 MB) WITHOUT PyTorch.

Run from the project folder (after ml_photo/train_v1.py):
    backend\\venv\\Scripts\\python.exe ml_photo\\export_onnx.py

What it does:
  1. Exports CLIP's IMAGE part (openai/clip-vit-base-patch32) to ONNX, a file format that the small
     "onnxruntime" library can run (needs torch + transformers + onnx here, NOT on the server).
  2. Quantizes its weights to int8: each weight is stored as an 8-bit number (plus one scale per
     128 weights) instead of a 32-bit number, so the file is ~3.5x smaller. This can change answers
     slightly - step 4 checks.
  3. Writes the logistic regression (6 classes x 512 weights + 6 intercepts), the Uncertain cutoff and
     the image preprocessing settings to a small JSON file.
  4. Compares the shrunken model with the ORIGINAL (PyTorch CLIP + the saved scikit-learn model) on
     the same test photos used in results_v1.md, and writes ml_photo/results_onnx.md + .json:
     how often they give the same answer, and the new accuracy.

Output (used by the website at runtime, committed to git):
    backend/photo_model/clip_image_int8.onnx
    backend/photo_model/photo_classifier_v1.json
"""
import csv
import json
import sys
from datetime import date
from pathlib import Path

import joblib
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PHOTOS = ROOT / 'photo_data'
OUT = ROOT / 'backend' / 'photo_model'
FP32_FILE = HERE / 'model' / 'clip_image_fp32.onnx'  # big, git-ignored, only for this check
INT8_FILE = OUT / 'clip_image_int8.onnx'
JSON_FILE = OUT / 'photo_classifier_v1.json'
# The same image preparation as Hugging Face's CLIPProcessor for this model.
SIZE = 224
MEAN = [0.48145466, 0.4578275, 0.40821073]
STD = [0.26862954, 0.26130258, 0.27577711]

sys.path.insert(0, str(ROOT / 'backend'))
import photo_classifier  # noqa: E402  (the backend's own code, so the check uses exactly what the site runs)


def export_fp32(saved):
    import torch
    from transformers import CLIPModel

    clip = CLIPModel.from_pretrained(saved['clip_name']).eval()

    class ImageFeatures(torch.nn.Module):
        def __init__(self, m):
            super().__init__()
            self.m = m

        def forward(self, pixel_values):
            out = self.m.get_image_features(pixel_values=pixel_values)
            return out if hasattr(out, 'norm') else out.pooler_output  # same as train_v1.as_tensor

    dummy = torch.zeros(1, 3, SIZE, SIZE)
    torch.onnx.export(ImageFeatures(clip), (dummy,), str(FP32_FILE), input_names=['pixel_values'],
                      output_names=['image_embeds'], dynamic_axes={'pixel_values': {0: 'batch'}},
                      opset_version=17, dynamo=False)


BLOCK_SIZE = 128  # one scale per 128 weights; 128 keeps the file under GitHub's 100 MB limit


def quantize():
    """WEIGHT-ONLY int8 (MatMulNBits, 8 bits): the matrix weights are stored as 8-bit numbers with
    one scale per block of 128; the calculations themselves stay in 32-bit floats.
    Tried first (2026-11-26): onnxruntime's "dynamic" int8, which ALSO rounds the activations to
    8 bits -> only 96.8% same top class / 94.7% same final answer, below the 98% the student set.
    Weight-only int8 reached 99.7% / 98.9% on the same test photos (see results_onnx.md)."""
    import onnx
    from onnxruntime.quantization.matmul_nbits_quantizer import MatMulNBitsQuantizer
    q = MatMulNBitsQuantizer(onnx.load(str(FP32_FILE)), bits=8, block_size=BLOCK_SIZE, is_symmetric=True)
    q.process()
    onnx.save_model(q.model.model, str(INT8_FILE))


def write_json(saved, results):
    clf = saved['model']
    classes = saved['classes']
    full_coef = np.zeros((len(classes), clf.coef_.shape[1]))
    full_int = np.full(len(classes), -1e9)  # a class missing from training could never win
    full_coef[clf.classes_] = clf.coef_
    full_int[clf.classes_] = clf.intercept_
    JSON_FILE.write_text(json.dumps({
        'about': 'SpectralTurf photo classifier v1 (Stage 11). CLIP ViT-B/32 image features (int8 ONNX) + '
                 'multinomial logistic regression. "Looks most like", NOT a diagnosis.',
        'made_by': 'ml_photo/export_onnx.py from ml_photo/model/photo_logreg_v1.joblib',
        'trained_on': saved['trained_on'], 'clip_name': saved['clip_name'],
        'classes': classes, 'uncertain_cutoff': saved['uncertain_cutoff'],
        'uncertain_label': 'Uncertain — inspect in person',
        'image_size': SIZE, 'mean': MEAN, 'std': STD,
        'coef': np.round(full_coef, 7).tolist(), 'intercept': np.round(full_int, 7).tolist(),
        'test_results': results,
    }, indent=1), encoding='utf-8')


def main():
    saved = joblib.load(HERE / 'model' / 'photo_logreg_v1.joblib')
    OUT.mkdir(exist_ok=True)
    if not FP32_FILE.exists():
        print('Exporting CLIP image encoder to ONNX ...', flush=True)
        export_fp32(saved)
    print('Quantizing to int8 ...', flush=True)
    quantize()
    write_json(saved, None)  # first without results, so photo_classifier can load it

    with open(PHOTOS / 'split.csv', encoding='utf-8') as f:
        test = [r for r in csv.DictReader(f) if r['split'] == 'test' and r['label'] in saved['classes']]
    classes = saved['classes']
    y = np.array([classes.index(r['label']) for r in test])

    # ORIGINAL: the embeddings train_v1.py made with PyTorch CLIP (cache) + the scikit-learn model.
    cache = np.load(HERE / 'cache' / 'clip_image_embeddings.npz')
    keys = []
    for r in test:
        st = (PHOTOS / r['filename']).stat()
        keys.append(f"{r['filename']}|{st.st_size}|{int(st.st_mtime)}")
    orig_emb = np.stack([cache[k] for k in keys])
    orig_p = np.zeros((len(test), len(classes)))
    orig_p[:, saved['model'].classes_] = saved['model'].predict_proba(orig_emb)

    import onnxruntime as ort
    fp32 = ort.InferenceSession(str(FP32_FILE), providers=['CPUExecutionProvider'])
    model = photo_classifier.load_model()
    cut = saved['uncertain_cutoff']

    new_p, fp32_cos, int8_cos = [], [], []
    for r, oe in zip(test, orig_emb):
        # Exactly the website's path: check + re-save without metadata (max 1024 px), then preprocess.
        img = photo_classifier.clean_photo((PHOTOS / r['filename']).read_bytes())
        x = photo_classifier.preprocess(img, model)
        e32 = fp32.run(None, {'pixel_values': x})[0][0]
        e8 = model['session'].run(None, {'pixel_values': x})[0][0]
        e32, e8 = e32 / np.linalg.norm(e32), e8 / np.linalg.norm(e8)
        fp32_cos.append(float(e32 @ oe))
        int8_cos.append(float(e8 @ oe))
        new_p.append(photo_classifier.probabilities(e8, model))
    new_p = np.array(new_p)

    def answers(p):
        top = p.argmax(1)
        return np.where(p.max(1) >= cut, top, -1)  # -1 = Uncertain

    o_top, n_top = orig_p.argmax(1), new_p.argmax(1)
    o_ans, n_ans = answers(orig_p), answers(new_p)
    from sklearn.metrics import balanced_accuracy_score

    def summary(top, ans):
        answered = ans >= 0
        return {'accuracy': float((top == y).mean()), 'balanced_accuracy': float(balanced_accuracy_score(y, top)),
                'uncertain_rate': float((~answered).mean()), 'uncertain_count': int((~answered).sum()),
                'answered_accuracy': float((ans[answered] == y[answered]).mean()) if answered.any() else None}

    results = {
        'date': date.today().isoformat(), 'test_photos': len(test), 'uncertain_cutoff': cut,
        'agreement_top_class': float((o_top == n_top).mean()),
        'agreement_final_answer_incl_uncertain': float((o_ans == n_ans).mean()),
        'disagreements': [{'photo': r['filename'], 'true': r['label'],
                           'original': classes[a] if a >= 0 else 'Uncertain',
                           'int8': classes[b] if b >= 0 else 'Uncertain'}
                          for r, a, b in zip(test, o_ans, n_ans) if a != b],
        'max_probability_change': float(np.abs(orig_p - new_p).max()),
        'embedding_cosine_fp32_min': min(fp32_cos), 'embedding_cosine_int8_min': min(int8_cos),
        'embedding_cosine_int8_mean': float(np.mean(int8_cos)),
        'original': summary(o_top, o_ans), 'int8': summary(n_top, n_ans),
        'per_class_test_photos': {c: int((y == i).sum()) for i, c in enumerate(classes)},
        'per_class_recall_int8': {c: float((n_top[y == i] == i).mean()) for i, c in enumerate(classes)},
        'file_size_mb': {'fp32': round(FP32_FILE.stat().st_size / 1e6, 1), 'int8': round(INT8_FILE.stat().st_size / 1e6, 1)},
    }
    write_json(saved, results)
    (HERE / 'results_onnx.json').write_text(json.dumps(results, indent=1), encoding='utf-8')
    write_report(results)
    print(json.dumps({k: v for k, v in results.items() if k != 'disagreements'}, indent=1))
    print('disagreements:', len(results['disagreements']))


def pct(v):
    return '—' if v is None else f'{v:.1%}'


def write_report(r):
    o, n = r['original'], r['int8']
    lines = [
        '# Stage 11 photo classifier — shrunken (int8 ONNX) model vs original',
        '',
        f"Date: {r['date']}. Made by `ml_photo/export_onnx.py` (numbers copied from `results_onnx.json`).",
        f"Same {r['test_photos']} test photos as `results_v1.md`. Uncertain below {r['uncertain_cutoff']:.0%}.",
        '',
        f"- Same top class as the original: **{pct(r['agreement_top_class'])}**",
        f"- Same final answer (including \"Uncertain\"): **{pct(r['agreement_final_answer_incl_uncertain'])}** "
        f"({len(r['disagreements'])} photos differ)",
        f"- Largest change in any class percentage: {r['max_probability_change']:.1%}",
        f"- Image features vs original (cosine similarity, 1 = identical): fp32 ONNX min "
        f"{r['embedding_cosine_fp32_min']:.4f}; int8 min {r['embedding_cosine_int8_min']:.4f}, mean "
        f"{r['embedding_cosine_int8_mean']:.4f}",
        f"- File size: fp32 {r['file_size_mb']['fp32']} MB -> int8 {r['file_size_mb']['int8']} MB",
        '',
        '| | Accuracy | Balanced accuracy | Uncertain rate | Accuracy on answered photos |',
        '|---|---|---|---|---|',
        f"| Original (PyTorch) | {pct(o['accuracy'])} | {pct(o['balanced_accuracy'])} | {pct(o['uncertain_rate'])} "
        f"({o['uncertain_count']}) | {pct(o['answered_accuracy'])} |",
        f"| Shrunken (int8 ONNX, website) | {pct(n['accuracy'])} | {pct(n['balanced_accuracy'])} | "
        f"{pct(n['uncertain_rate'])} ({n['uncertain_count']}) | {pct(n['answered_accuracy'])} |",
        '',
        'Per-class recall of the website model (without Uncertain): ' + ', '.join(
            f"{c} {pct(v)} ({r['per_class_test_photos'][c]} photos)" for c, v in r['per_class_recall_int8'].items()),
        '',
        '## Photos where the answer changed',
        '',
        '| Photo | True label | Original | Int8 |',
        '|---|---|---|---|',
    ] + [f"| {d['photo']} | {d['true']} | {d['original']} | {d['int8']} |" for d in r['disagreements']] + [
        '',
        'Limitations (same as v1): each class came mostly from ONE kind of source (robot-camera video frames for',
        'healthy/drought, figures from articles for fungal/insect, a few web photos for wear/dormant), so the',
        'model may partly recognize the source instead of the turf problem. Wear and dormant have 2 test photos each.',
    ]
    (HERE / 'results_onnx.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

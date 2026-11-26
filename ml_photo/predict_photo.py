"""
predict_photo.py - Stage 11: classify turf photos with the trained v1 model (ml_photo/model/).

Run from the project folder (after ml_photo/train_v1.py has saved the model):
    backend\\venv\\Scripts\\python.exe ml_photo\\predict_photo.py path\\to\\photo.jpg [more photos ...]

For each photo it prints the most likely class and the model's confidence for every class. If the top
confidence is below the cutoff saved with the model (chosen on training photos only), the answer is
"Uncertain - inspect in person".

RESEARCH ONLY: this is "the photo looks most like training photos labeled X", not a diagnosis. The v1
model was trained on photos where each class came from a different source (see results_v1.md), so its
answers on new photos are unproven.
"""
import sys
from pathlib import Path

import joblib
import numpy as np
from PIL import Image

MODEL_FILE = Path(__file__).resolve().parent / 'model' / 'photo_logreg_v1.joblib'


def load():
    if not MODEL_FILE.exists():
        sys.exit('No model yet - run ml_photo/train_v1.py first.')
    saved = joblib.load(MODEL_FILE)
    import torch
    from transformers import CLIPModel, CLIPProcessor
    clip = CLIPModel.from_pretrained(saved['clip_name']).eval()
    return saved, torch, clip, CLIPProcessor.from_pretrained(saved['clip_name'])


def predict(paths, saved, torch, clip, proc):
    imgs = [Image.open(p).convert('RGB') for p in paths]
    with torch.no_grad():
        emb = clip.get_image_features(**proc(images=imgs, return_tensors='pt'))
    emb = emb if hasattr(emb, 'norm') else emb.pooler_output
    emb = (emb / emb.norm(dim=-1, keepdim=True)).numpy()
    model, classes = saved['model'], saved['classes']
    probs = np.zeros((len(paths), len(classes)))
    probs[:, model.classes_] = model.predict_proba(emb)
    results = []
    for p, row in zip(paths, probs):
        top = int(row.argmax())
        answer = classes[top] if row[top] >= saved['uncertain_cutoff'] else saved['uncertain_label']
        results.append({'photo': str(p), 'answer': answer, 'confidence': float(row[top]),
                        'all': {c: float(v) for c, v in zip(classes, row)}})
    return results


def main():
    paths = [Path(a) for a in sys.argv[1:]]
    if not paths:
        sys.exit(__doc__)
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        sys.exit(f'Not found: {missing}')
    saved, torch, clip, proc = load()
    print(f"Model trained {saved['trained_on']}; Uncertain below {saved['uncertain_cutoff']:.0%} confidence.\n")
    for r in predict(paths, saved, torch, clip, proc):
        print(f"{r['photo']}\n  -> {r['answer']}  (top confidence {r['confidence']:.0%})")
        print('     ' + ', '.join(f'{c} {v:.0%}' for c, v in sorted(r['all'].items(), key=lambda kv: -kv[1])))
    print('\nResearch only: "looks most like photos labeled X", not a diagnosis.')


if __name__ == '__main__':
    main()

"""
train_v1.py - Stage 11, Step 2+3: CLIP zero-shot and CLIP + logistic regression turf-photo classifier.

Run from the project folder (after ml_photo/check_dataset.py has written photo_data/split.csv):
    backend\\venv\\Scripts\\python.exe ml_photo\\train_v1.py

What it does:
  1. Loads photo_data/split.csv (train/test BY GROUP, made by check_dataset.py).
  2. Computes a CLIP image embedding (openai/clip-vit-base-patch32, CPU) for every photo and caches
     them in ml_photo/cache/ (git-ignored), so a rerun only embeds new or changed photos.
  3. ZERO-SHOT (no training): compares each photo with the text prompts in
     ml_photo/class_descriptions.md; a class's text = the average of its prompts' embeddings.
  4. TRAINED: logistic regression on the training embeddings. Its one setting (C) is chosen by
     cross-validation on the TRAINING photos only, folds kept by group.
  5. "Uncertain - inspect in person": if the top confidence is below a cutoff. The cutoff is chosen
     from the TRAINING photos only (cross-validation predictions for the trained model, plain
     predictions for zero-shot) - the test photos are never used to choose anything.
  6. Evaluates both on the TEST photos only, against "always guess the most common training class".
  7. Saves ml_photo/model/ (git-ignored), ml_photo/results_v1.md, results_v1.json and
     confusion matrix images.

Project choices (not published standards): TARGET_ANSWERED_ACCURACY 0.90, cutoff grid 0.30-0.95,
C grid 0.01-100, 5 folds, seed 2026. Classes: the 6 folders listed in check_dataset.CLASSES.
"""
import csv
import datetime as dt
import json
import re
import sys
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import StratifiedGroupKFold

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PHOTOS = ROOT / 'photo_data'
CACHE = HERE / 'cache'
MODEL_DIR = HERE / 'model'
CLIP_NAME = 'openai/clip-vit-base-patch32'
CLASSES = ['healthy', 'drought', 'fungal_disease', 'insect_damage', 'wear', 'dormant']
UNCERTAIN = 'Uncertain - inspect in person'
TARGET_ANSWERED_ACCURACY = 0.90
CUTOFF_GRID = np.round(np.arange(0.30, 0.951, 0.05), 2)
C_GRID = [0.01, 0.1, 1, 10, 100]
SEED = 2026


# ---------- data ----------
def load_split():
    with open(PHOTOS / 'split.csv', encoding='utf-8') as f:
        rows = [r for r in csv.DictReader(f) if r['label'] in CLASSES]
    if not rows:
        sys.exit('photo_data/split.csv is empty - run ml_photo/check_dataset.py first')
    return rows


def load_prompts():
    """Quoted prompts from class_descriptions.md, by class (see that file's headings)."""
    prompts = {c: [] for c in CLASSES}
    current = None
    for line in (HERE / 'class_descriptions.md').read_text(encoding='utf-8').splitlines():
        if line.startswith('## '):
            head = line[3:].strip().split()[0]
            current = head if head in CLASSES else ('table' if line.startswith('## Classes not covered') else None)
            continue
        if not line.startswith('|') or current is None:
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        quoted = re.findall(r'"([^"]+)"', line)
        if not quoted:
            continue
        cls = cells[0] if current == 'table' else current
        if cls in prompts:
            prompts[cls].extend(quoted)
    missing = [c for c in CLASSES if not prompts[c]]
    if missing:
        sys.exit(f'No prompts found for {missing} in class_descriptions.md')
    return prompts


# ---------- CLIP ----------
def clip():
    import torch
    from transformers import CLIPModel, CLIPProcessor
    torch.manual_seed(SEED)
    model = CLIPModel.from_pretrained(CLIP_NAME).eval()
    return torch, model, CLIPProcessor.from_pretrained(CLIP_NAME)


def as_tensor(out):
    # newer transformers may return an output object instead of a plain tensor
    return out if hasattr(out, 'norm') else out.pooler_output


def embed_images(files, torch, model, proc):
    CACHE.mkdir(exist_ok=True)
    path = CACHE / 'clip_image_embeddings.npz'
    cache = dict(np.load(path, allow_pickle=False)) if path.exists() else {}
    keys = []
    todo = []
    for f in files:
        st = (PHOTOS / f).stat()
        key = f'{f}|{st.st_size}|{int(st.st_mtime)}'
        keys.append(key)
        if key not in cache:
            todo.append((f, key))
    for i in range(0, len(todo), 32):
        batch = todo[i:i + 32]
        imgs = [Image.open(PHOTOS / f).convert('RGB') for f, _ in batch]
        with torch.no_grad():
            emb = as_tensor(model.get_image_features(**proc(images=imgs, return_tensors='pt')))
        emb = (emb / emb.norm(dim=-1, keepdim=True)).numpy().astype(np.float32)
        for (f, key), e in zip(batch, emb):
            cache[key] = e
        print(f'  embedded {min(i + 32, len(todo))}/{len(todo)} new photos', flush=True)
    if todo:
        np.savez(path, **cache)
    return np.stack([cache[k] for k in keys])


def embed_texts(prompts, torch, model, proc):
    out = []
    for c in CLASSES:
        with torch.no_grad():
            t = as_tensor(model.get_text_features(**proc(text=prompts[c], return_tensors='pt', padding=True)))
        t = t / t.norm(dim=-1, keepdim=True)
        m = t.mean(dim=0)
        out.append((m / m.norm()).numpy())
    return np.stack(out), float(model.logit_scale.exp().detach())


# ---------- uncertain cutoff + scores ----------
def choose_cutoff(probs, y_true):
    """Lowest cutoff whose ANSWERED accuracy reaches the target (training photos only)."""
    pred, conf = probs.argmax(1), probs.max(1)
    table = []
    for t in CUTOFF_GRID:
        ans = conf >= t
        acc = float((pred[ans] == y_true[ans]).mean()) if ans.any() else float('nan')
        table.append({'cutoff': float(t), 'answered': float(ans.mean()), 'answered_accuracy': acc})
    ok = [r for r in table if r['answered'] > 0 and r['answered_accuracy'] >= TARGET_ANSWERED_ACCURACY]
    chosen = ok[0] if ok else max((r for r in table if r['answered'] > 0), key=lambda r: r['answered_accuracy'])
    return chosen['cutoff'], ok != [], table


def scores(y_true, probs, cutoff):
    pred, conf = probs.argmax(1), probs.max(1)
    labels = list(range(len(CLASSES)))
    p, r, f, n = precision_recall_fscore_support(y_true, pred, labels=labels, zero_division=0)
    ans = conf >= cutoff
    return {
        'n_test': int(len(y_true)),
        'accuracy': float(accuracy_score(y_true, pred)),
        'balanced_accuracy': float(balanced_accuracy_score(y_true, pred)),
        'per_class': {CLASSES[i]: {'precision': float(p[i]), 'recall': float(r[i]), 'f1': float(f[i]),
                                    'n_test': int(n[i])} for i in labels},
        'confusion': confusion_matrix(y_true, pred, labels=labels).tolist(),
        'cutoff': float(cutoff),
        'uncertain_count': int((~ans).sum()),
        'uncertain_rate': float((~ans).mean()),
        'answered_accuracy': float((pred[ans] == y_true[ans]).mean()) if ans.any() else None,
        # with the Uncertain option, an Uncertain answer counts as NOT correct
        'accuracy_counting_uncertain_as_wrong': float(((pred == y_true) & ans).mean()),
        'answered_per_class_recall': {CLASSES[i]: (float(((pred == y_true) & ans)[y_true == i].sum() / max(1, (y_true == i).sum())))
                                      for i in labels},
    }


def draw_confusion(cm, title, path):
    n, cell, left, top = len(CLASSES), 70, 150, 90
    img = Image.new('RGB', (left + n * cell + 20, top + n * cell + 40), 'white')
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    d.text((10, 10), title, fill='black', font=font)
    d.text((left, 40), 'predicted ->', fill='black', font=font)
    d.text((10, top - 20), 'true (rows)', fill='black', font=font)
    cm = np.array(cm)
    for i in range(n):
        d.text((10, top + i * cell + cell // 2 - 5), CLASSES[i], fill='black', font=font)
        d.text((left + i * cell + 4, top - 18 + (i % 2) * 10), CLASSES[i][:11], fill='black', font=font)
        row = cm[i].sum() or 1
        for j in range(n):
            share = cm[i, j] / row
            shade = int(255 - 200 * share)
            color = (shade, shade, 255) if i == j else (255, shade, shade)
            x, y = left + j * cell, top + i * cell
            d.rectangle([x, y, x + cell - 2, y + cell - 2], fill=color, outline='gray')
            d.text((x + 8, y + cell // 2 - 5), f'{cm[i, j]} ({share:.0%})', fill='black', font=font)
    img.save(path)


# ---------- main ----------
def main():
    rows = load_split()
    files = [r['filename'] for r in rows]
    y = np.array([CLASSES.index(r['label']) for r in rows])
    is_test = np.array([r['split'] == 'test' for r in rows])
    groups = np.array([r['group'] for r in rows])
    prompts = load_prompts()

    print(f'Loading CLIP ({CLIP_NAME}) on CPU ...', flush=True)
    torch, model, proc = clip()
    X = embed_images(files, torch, model, proc)
    T, scale = embed_texts(prompts, torch, model, proc)
    tr, te = ~is_test, is_test

    # 1) zero-shot
    logits = scale * X @ T.T
    zs_probs = np.exp(logits - logits.max(1, keepdims=True))
    zs_probs /= zs_probs.sum(1, keepdims=True)
    zs_cut, zs_reached, zs_table = choose_cutoff(zs_probs[tr], y[tr])
    zs = scores(y[te], zs_probs[te], zs_cut)

    # 2) logistic regression; CV folds by group. A class whose training photos all come from ONE
    # group (wear, dormant) can't be split by group, so its photos are their own CV groups (weak).
    cv_groups = groups[tr].copy()
    for c in range(len(CLASSES)):
        m = y[tr] == c
        if len(set(cv_groups[m])) == 1:
            cv_groups[m] = [f'{g}#{k}' for k, g in enumerate(cv_groups[m])]
    folds = list(StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
                 .split(X[tr], y[tr], cv_groups))

    def oof(C):
        out = np.zeros((tr.sum(), len(CLASSES)))
        for a, b in folds:
            clf = LogisticRegression(C=C, class_weight='balanced', max_iter=5000)
            clf.fit(X[tr][a], y[tr][a])
            p = np.zeros((len(b), len(CLASSES)))
            p[:, clf.classes_] = clf.predict_proba(X[tr][b])
            out[b] = p
        return out

    cv_table = []
    for C in C_GRID:
        p = oof(C)
        cv_table.append({'C': C, 'cv_balanced_accuracy': float(balanced_accuracy_score(y[tr], p.argmax(1)))})
    best_C = max(cv_table, key=lambda r: r['cv_balanced_accuracy'])['C']
    lr_cut, lr_reached, lr_table = choose_cutoff(oof(best_C), y[tr])
    clf = LogisticRegression(C=best_C, class_weight='balanced', max_iter=5000).fit(X[tr], y[tr])
    lr_probs = np.zeros((len(y), len(CLASSES)))
    lr_probs[:, clf.classes_] = clf.predict_proba(X)
    lr = scores(y[te], lr_probs[te], lr_cut)

    # 3) baseline: always the most common TRAINING class
    common = Counter(y[tr]).most_common(1)[0][0]
    base_probs = np.zeros((te.sum(), len(CLASSES)))
    base_probs[:, common] = 1.0
    base = scores(y[te], base_probs, 0.0)

    # save model + cutoffs
    MODEL_DIR.mkdir(exist_ok=True)
    today = dt.date.today().isoformat()
    joblib.dump({'model': clf, 'classes': CLASSES, 'uncertain_cutoff': lr_cut, 'uncertain_label': UNCERTAIN,
                 'C': best_C, 'clip_name': CLIP_NAME, 'trained_on': today,
                 'note': 'Input = L2-normalised CLIP image embedding. Research only, not a diagnosis.'},
                MODEL_DIR / 'photo_logreg_v1.joblib')
    np.savez(MODEL_DIR / 'zeroshot_v1.npz', text_embeddings=T, logit_scale=scale, cutoff=zs_cut,
             classes=np.array(CLASSES))
    draw_confusion(zs['confusion'], 'Zero-shot CLIP - test photos', HERE / 'confusion_zeroshot_v1.png')
    draw_confusion(lr['confusion'], 'CLIP + logistic regression - test photos', HERE / 'confusion_logreg_v1.png')

    # counts for the report
    counts = {c: {'total': int((y == i).sum()), 'train': int(((y == i) & tr).sum()),
                  'test': int(((y == i) & te).sum()), 'groups': len(set(groups[y == i]))}
              for i, c in enumerate(CLASSES)}
    methods = Counter((r['label'], r['split_method']) for r in rows)
    out = {'date': today, 'clip': CLIP_NAME, 'counts': counts,
           'split_methods': {f'{a}: {b}': n for (a, b), n in methods.items()},
           'prompts_per_class': {c: len(prompts[c]) for c in CLASSES},
           'zero_shot': zs, 'zero_shot_cutoff_table_train': zs_table, 'zero_shot_target_reached': zs_reached,
           'logreg': lr, 'logreg_cv': cv_table, 'logreg_C': best_C,
           'logreg_cutoff_table_train_cv': lr_table, 'logreg_target_reached': lr_reached,
           'baseline_most_common': {'class': CLASSES[common], **base}}
    (HERE / 'results_v1.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
    write_report(out)
    print(f"\nZero-shot: accuracy {zs['accuracy']:.3f}, balanced {zs['balanced_accuracy']:.3f}, "
          f"uncertain {zs['uncertain_rate']:.1%} (cutoff {zs_cut})")
    print(f"LogReg   : accuracy {lr['accuracy']:.3f}, balanced {lr['balanced_accuracy']:.3f}, "
          f"uncertain {lr['uncertain_rate']:.1%} (cutoff {lr_cut}, C {best_C})")
    print(f"Baseline : accuracy {base['accuracy']:.3f} (always '{CLASSES[common]}')")
    print('Wrote ml_photo/results_v1.md, results_v1.json, confusion_*_v1.png, model/')


def pct(v):
    return '—' if v is None else f'{v:.1%}'


def write_report(o):
    L = []
    a = L.append
    a('# Stage 11 photo classifier — results v1\n')
    a(f"Date: {o['date']}. Made by `ml_photo/train_v1.py` (numbers below are copied from `results_v1.json`).")
    a(f"Image features: CLIP `{o['clip']}` on CPU. **Research only: a prediction is not a diagnosis.**\n")
    a('## Data\n')
    a('| Class | Photos | Train | Test | Groups (sites / recordings / sources) |')
    a('|---|---|---|---|---|')
    for c, v in o['counts'].items():
        a(f"| {c} | {v['total']} | {v['train']} | {v['test']} | {v['groups']} |")
    a('\nSplit (from `ml_photo/check_dataset.py`, saved in `photo_data/split.csv`): train/test **by group**, so a')
    a('site, video recording or source article is never in both. Group = metadata `site` if known, else the')
    a('recording time in the file name, else the source article, else "unknown". Split methods used:\n')
    for k, n in sorted(o['split_methods'].items()):
        a(f'- {k}: {n} photos')
    a('\nPrompts per class (zero-shot): ' + ', '.join(f'{c} {n}' for c, n in o['prompts_per_class'].items()) + '.\n')

    a('## Test results (test photos only)\n')
    a('| | Accuracy | Balanced accuracy | Uncertain rate | Accuracy on answered photos | Accuracy, Uncertain counted wrong |')
    a('|---|---|---|---|---|---|')
    b = o['baseline_most_common']
    a(f"| Baseline: always \"{b['class']}\" | {pct(b['accuracy'])} | {pct(b['balanced_accuracy'])} | — | — | — |")
    for name, key in (('Zero-shot CLIP (no training)', 'zero_shot'), ('CLIP + logistic regression', 'logreg')):
        s = o[key]
        a(f"| {name} | {pct(s['accuracy'])} | {pct(s['balanced_accuracy'])} | {pct(s['uncertain_rate'])} "
          f"({s['uncertain_count']}/{s['n_test']}) | {pct(s['answered_accuracy'])} | {pct(s['accuracy_counting_uncertain_as_wrong'])} |")
    a('\n"Accuracy" and "Balanced accuracy" = without the Uncertain option (every photo gets a class).')
    a('Balanced accuracy = the average of the per-class recalls, so the big classes do not hide the small ones.\n')
    for name, key in (('Zero-shot CLIP', 'zero_shot'), ('CLIP + logistic regression', 'logreg')):
        s = o[key]
        a(f'### {name} — per class (without Uncertain)\n')
        a('| Class | Test photos | Precision | Recall | Recall with Uncertain (answered and right) |')
        a('|---|---|---|---|---|')
        for c in CLASSES:
            pc = s['per_class'][c]
            a(f"| {c} | {pc['n_test']} | {pct(pc['precision'])} | {pct(pc['recall'])} | {pct(s['answered_per_class_recall'][c])} |")
        img = 'confusion_zeroshot_v1.png' if key == 'zero_shot' else 'confusion_logreg_v1.png'
        a(f'\nConfusion matrix: `ml_photo/{img}` (rows = true class, columns = predicted).\n')
        a('| true \\ predicted | ' + ' | '.join(CLASSES) + ' |')
        a('|---' * (len(CLASSES) + 1) + '|')
        for i, c in enumerate(CLASSES):
            a(f'| {c} | ' + ' | '.join(str(v) for v in s['confusion'][i]) + ' |')
        a('')

    a('## How the Uncertain cutoff was chosen (training photos only)\n')
    a(f'Rule (project choice): the lowest cutoff in {CUTOFF_GRID[0]}–{CUTOFF_GRID[-1]} whose accuracy on the photos it')
    a(f'still answers reaches {TARGET_ANSWERED_ACCURACY:.0%}; if none does, the cutoff with the best answered accuracy.')
    a(f"- Zero-shot: cutoff **{o['zero_shot']['cutoff']}** (target reached on training photos: {o['zero_shot_target_reached']}).")
    a(f"- Logistic regression: cutoff **{o['logreg']['cutoff']}**, chosen on 5-fold cross-validation predictions of the")
    a(f"  training photos (target reached: {o['logreg_target_reached']}). Regularisation C = {o['logreg_C']}, chosen by")
    a('  cross-validated balanced accuracy: ' + ', '.join(f"C={r['C']}: {r['cv_balanced_accuracy']:.3f}" for r in o['logreg_cv']) + '.')
    a('  CV folds keep groups together, except wear and dormant (one group each), whose photos are their own folds.\n')
    L.append(LIMITATIONS)
    (HERE / 'results_v1.md').write_text('\n'.join(L) + '\n', encoding='utf-8')


LIMITATIONS = """## Limitations (read before quoting any number)

- **Each class comes from a different kind of picture.** healthy and drought are frames from the same
  robot-camera video recordings (one day, 2022-10-18, no metadata row); fungal_disease and insect_damage
  are photos from extension / company articles; wear and dormant are 10 web photos each with no source.
  So a model can score well by recognising **where a photo came from** (camera, framing, article style)
  instead of the turf problem. A high score here does NOT show the model would work on a new phone photo.
- **insect_damage is mostly not turf damage**: by the student's choice it holds every picture from the
  insect PDFs (insect close-ups, weeds, cereal-crop diseases, a tree, thatch, wasp nests). The model
  learns "pictures from these articles", not "insect damage on a lawn". The prompts describe turf damage,
  so zero-shot is expected to miss most of these.
- **wear and dormant**: 10 photos each from one unknown source, split by file order (2 test photos each).
  Their test scores rest on 2 photos and the test photos may come from the same place as training.
- **Labels are not expert-confirmed** (captions or folder names only). Disease photos are mostly golf
  greens and fairways, not sports fields; 4 fungal photos are warm-season-grass diseases not found in
  Colorado.
- **Video frames** in healthy/drought are many near-identical views from a few recordings, so the
  test set is smaller than the photo count suggests; each recording counts more like one sample.
- **Licenses not checked** (permission "not asked"; 1,390 photos have no metadata row). The model and
  embeddings are kept out of git; nothing here may be published until licenses are checked.
- Cutoff rule, target 90%, C grid and 5 folds are project choices, not published standards.
- Nothing was tuned on the test photos; v1 is the first and only test run of this setup.
"""

if __name__ == '__main__':
    main()

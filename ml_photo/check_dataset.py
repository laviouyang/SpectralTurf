"""
check_dataset.py - Stage 11, Step 1: check the turf photo dataset and make a train/test split.

Run from the project folder (D:\\Lavi\\SpectralTurf):
    backend\\venv\\Scripts\\python.exe ml_photo\\check_dataset.py

What it does (no photos are changed, moved or deleted):
  1. Opens every image in photo_data/<class>/ (the 6 classes below) and lists the ones that
     fail to open or have no row in photo_data/metadata.csv.
  2. Finds exact duplicates (same pixels) and near-duplicates (almost the same picture, found with
     a small "difference hash" of each image). Video frames next to each other are near-duplicates.
  3. Counts images per class, per site/recording and per source.
  4. Splits into train / test BY GROUP, so one place (site) or one video recording is never in both.
     Group = the `site` column if it is known; otherwise the recording name in the file name;
     otherwise the source in metadata; otherwise "unknown source" (all such photos of a class
     together). A class with only ONE group cannot be split by group: its photos are split in
     file-name order (first 80% train, last 20% test) and the class is marked WEAK, because test
     photos then come from the same place/recording as training photos.
  5. Saves photo_data/split.csv and prints a report. Exit code 1 if a serious problem is found
     (unreadable photos, or a class with no photos). Classes under MIN_PER_CLASS only get a warning.

Project choices (not published standards): TEST_FRACTION 0.2, MIN_PER_CLASS 30,
NEAR_DUP_BITS 4 (out of 64), seed 2026.
"""
import csv
import hashlib
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent / 'photo_data'
CLASSES = ['healthy', 'drought', 'fungal_disease', 'insect_damage', 'wear', 'dormant']
IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
TEST_FRACTION = 0.2
MIN_PER_CLASS = 30
NEAR_DUP_BITS = 4
SEED = 2026
RECORDING_RE = re.compile(r'recording_(\d{4}_\d{2}_\d{2}_\d{2}_\d{2}_\d{2})')


def dhash(img, size=8):
    """64-bit difference hash: 1 where a pixel is brighter than its right-hand neighbour."""
    small = np.asarray(img.convert('L').resize((size + 1, size), Image.BILINEAR), dtype=np.int16)
    return np.packbits((small[:, 1:] > small[:, :-1]).flatten())


def load_metadata():
    path = ROOT / 'metadata.csv'
    with open(path, encoding='utf-8') as f:
        return {row['filename'].replace('\\', '/'): row for row in csv.DictReader(f)}


def group_of(rel, meta_row):
    """Return (group, how) - the unit that must stay on one side of the split."""
    site = (meta_row or {}).get('site', '').strip()
    if site and not site.startswith('unknown'):
        return f'site:{site}', 'site'
    m = RECORDING_RE.search(rel)
    if m:
        return f'recording:{m.group(1)}', 'recording'
    source = (meta_row or {}).get('source', '').strip()
    if source:
        return f'source:{source.split(" (page")[0]}', 'source'
    return f'unknown:{rel.split("/")[0]}', 'unknown'


def scan():
    meta = load_metadata()
    items, unreadable, not_class = [], [], Counter()
    for folder in sorted(p for p in ROOT.iterdir() if p.is_dir()):
        if folder.name not in CLASSES:
            not_class[folder.name] = sum(1 for _ in folder.rglob('*') if _.suffix.lower() in IMAGE_EXT)
            continue
        for p in sorted(folder.iterdir()):
            if p.suffix.lower() not in IMAGE_EXT:
                continue
            rel = f'{folder.name}/{p.name}'
            try:
                with Image.open(p) as im:
                    im.load()
                    pixels = hashlib.sha1(im.convert('RGB').tobytes()).hexdigest()
                    h = dhash(im)
                    size = im.size
            except Exception as e:  # noqa: BLE001 - report any reason
                unreadable.append((rel, str(e)[:80]))
                continue
            row = meta.get(rel)
            group, how = group_of(rel, row)
            items.append({'file': rel, 'label': folder.name, 'meta': row is not None,
                          'source': (row or {}).get('source', '').split(' (page')[0] or 'not in metadata',
                          'license': (row or {}).get('license', '') or 'not in metadata',
                          'group': group, 'group_how': how, 'pixels': pixels, 'dhash': h, 'size': size})
    meta_without_file = [f for f in meta if not (ROOT / f).exists()]
    return items, unreadable, not_class, meta_without_file


def find_duplicates(items):
    by_pixels = defaultdict(list)
    for it in items:
        by_pixels[it['pixels']].append(it)
    exact = [g for g in by_pixels.values() if len(g) > 1]
    # near duplicates: Hamming distance between 64-bit hashes (exact copies excluded)
    bits = np.unpackbits(np.stack([it['dhash'] for it in items]), axis=1).astype(bool)
    near = []
    for i in range(len(items)):
        d = (bits[i + 1:] != bits[i]).sum(axis=1)
        for j in np.nonzero(d <= NEAR_DUP_BITS)[0]:
            a, b = items[i], items[i + 1 + j]
            if a['pixels'] != b['pixels']:
                near.append((a, b))
    return exact, near


def make_split(items):
    """Group split per class. Returns {file: (split, method)} and per-class notes."""
    rng = random.Random(SEED)
    by_class = defaultdict(lambda: defaultdict(list))
    for it in items:
        by_class[it['label']][it['group']].append(it)
    assign, notes = {}, {}
    group_split = {}
    # Classes with the fewest groups choose first: they have the least freedom (e.g. drought shares
    # its recordings with healthy, so it must pick before healthy fixes those recordings' sides).
    for label in sorted(CLASSES, key=lambda c: len(by_class.get(c, {}))):
        groups = by_class.get(label, {})
        names = sorted(groups)
        if not names:
            notes[label] = 'NO PHOTOS'
            continue
        if len(names) == 1:
            files = sorted(groups[names[0]], key=lambda it: it['file'])
            cut = max(1, round(len(files) * (1 - TEST_FRACTION))) if len(files) > 1 else 1
            for k, it in enumerate(files):
                assign[it['file']] = ('train' if k < cut else 'test', 'WEAK: one group, split by file order')
            notes[label] = f'WEAK - only 1 group ({names[0]}); test photos come from the same group as training'
            continue
        # Groups already used by another class keep their side (one recording = one side).
        # Free groups go to test, in a seeded random order, until about TEST_FRACTION of this
        # class's PHOTOS are in test (counting photos, not groups, because group sizes differ a lot).
        total = sum(len(groups[g]) for g in names)
        in_test = sum(len(groups[g]) for g in names if group_split.get(g) == 'test')
        free = [g for g in names if g not in group_split]
        rng.shuffle(free)
        for g in free:
            fits = in_test + len(groups[g]) <= total * TEST_FRACTION * 1.5
            if in_test < total * TEST_FRACTION and (fits or in_test == 0):
                group_split[g] = 'test'
                in_test += len(groups[g])
            else:
                group_split[g] = 'train'
        if all(group_split[g] == 'test' for g in names):  # keep at least one training group
            group_split[names[0]] = 'train'
        for g in names:
            for it in groups[g]:
                assign[it['file']] = (group_split[g], 'by group')
        notes[label] = f'by group ({len(names)} groups)'
    return assign, notes


def main():
    items, unreadable, not_class, meta_without_file = scan()
    exact, near = find_duplicates(items)
    assign, notes = make_split(items)

    # drop exact copies after the first (keep the copy that sorts first)
    drop = set()
    for g in exact:
        for it in sorted(g, key=lambda it: it['file'])[1:]:
            drop.add(it['file'])
    cross_class_exact = [g for g in exact if len({it['label'] for it in g}) > 1]
    leak_near = [(a, b) for a, b in near
                 if a['file'] not in drop and b['file'] not in drop
                 and assign[a['file']][0] != assign[b['file']][0]]

    print(f'\n=== Stage 11 dataset check ({ROOT}) ===')
    print(f'Images opened: {len(items)}   unreadable: {len(unreadable)}')
    for rel, err in unreadable:
        print(f'  UNREADABLE {rel}: {err}')
    if not_class:
        print('Folders that are NOT one of the 6 classes (ignored):',
              ', '.join(f'{k} ({v} images)' for k, v in not_class.items()))
    missing = [it['file'] for it in items if not it['meta']]
    print(f'Images with NO metadata row: {len(missing)}')
    for label in CLASSES:
        n = sum(1 for f in missing if f.startswith(label + '/'))
        if n:
            print(f'  {label}: {n} (e.g. {next(f for f in missing if f.startswith(label + "/"))})')
    if meta_without_file:
        print(f'Metadata rows whose file is missing: {len(meta_without_file)} (e.g. {meta_without_file[:3]})')

    print(f'\nExact duplicates: {len(exact)} groups, {len(drop)} extra copies dropped from the split')
    for g in cross_class_exact[:5]:
        print('  SAME PICTURE IN DIFFERENT CLASSES:', ', '.join(it['file'] for it in g))
    print(f'Near-duplicate pairs (<= {NEAR_DUP_BITS}/64 bits different): {len(near)}; '
          f'pairs split across train/test: {len(leak_near)}')
    near_by_class = Counter(a['label'] for a, b in near if a['label'] == b['label'])
    if near_by_class:
        print('  within-class near-duplicate pairs:', dict(near_by_class))
    cross_near = Counter(tuple(sorted((a['label'], b['label']))) for a, b in near if a['label'] != b['label'])
    if cross_near:
        print('  near-duplicates across classes:', dict(cross_near))

    print('\nPer class (after dropping exact copies):')
    print(f'  {"class":15s} {"images":>6s} {"train":>6s} {"test":>5s} {"groups":>6s}  split')
    serious = list(unreadable)
    warnings = []
    for label in CLASSES:
        its = [it for it in items if it['label'] == label and it['file'] not in drop]
        tr = sum(assign[it['file']][0] == 'train' for it in its)
        groups = {it['group'] for it in its}
        print(f'  {label:15s} {len(its):6d} {tr:6d} {len(its) - tr:5d} {len(groups):6d}  {notes[label]}')
        if len(its) == 0:
            serious.append((label, 'no usable photos'))
        elif len(its) < MIN_PER_CLASS:  # student: can't find more; warn only (2026-11-25)
            warnings.append(f'{label}: only {len(its)} photos (< {MIN_PER_CLASS}) - its test score rests on very few photos')
        if len({it["group"] for it in its}) == 1:
            warnings.append(f'{label}: all photos from one site/source - test score less trustworthy')

    print('\nPer group (site / recording / source):')
    per_group = Counter((it['label'], it['group']) for it in items if it['file'] not in drop)
    for (label, group), n in sorted(per_group.items()):
        print(f'  {label:15s} {n:5d}  {group[:90]}')
    print('\nPer source:')
    for (label, src), n in sorted(Counter((it['label'], it['source'][:70]) for it in items
                                          if it['file'] not in drop).items()):
        print(f'  {label:15s} {n:5d}  {src}')
    print('\nLicense column:', dict(Counter(it['license'] for it in items)))

    out = ROOT / 'split.csv'
    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['filename', 'label', 'group', 'split', 'split_method', 'in_metadata'])
        for it in items:
            if it['file'] in drop:
                continue
            split, method = assign[it['file']]
            w.writerow([it['file'], it['label'], it['group'], split, method, 'yes' if it['meta'] else 'no'])
    print(f'\nSaved {out}')

    if missing:
        warnings.append(f'{len(missing)} photos have no metadata.csv row (site/source/license unknown)')
    if warnings:
        print('\nWARNINGS (training can go ahead, but report these):')
        for w_ in warnings:
            print(f'  - {w_}')
    if serious:
        print('\nSERIOUS PROBLEMS (fix before training):')
        for what, why in serious:
            print(f'  - {what}: {why}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())

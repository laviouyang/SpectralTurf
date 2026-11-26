# photo_data — turf photos for the Stage 11 photo classifier

Plan: `docs/STAGE_11_PHOTO_AI.md`. Photos in this folder are **never committed to git**
(`.gitignore`). Only this README and the `metadata.csv` template are tracked.

## Folders (one per label)

| Folder | Put photos here that show… |
|---|---|
| `healthy/` | green, actively growing turf with no visible problem |
| `drought/` | turf that is dry / wilting / browning from lack of water (blue-gray tint, footprints that stay, straw color) |
| `fungal_disease/` | a fungal disease **confirmed by an expert or a lab** (e.g. a plant diagnostic clinic) |
| `insect_damage/` | damage from insects **confirmed by an expert** (e.g. grubs found under the patch) |
| `wear/` | worn areas from foot traffic or play (goal mouths, paths, bare spots) |
| `dormant/` | healthy grass that is brown because it is dormant (winter, or summer dormancy) |

## How to add a photo

1. Copy the photo into the folder of its label. Use a simple, unique file name, e.g.
   `drought/vg_2026-08-12_01.jpg` (site, date, number). JPG or PNG.
2. Add **one row** to `metadata.csv` for it. Columns:
   - `filename` — path inside photo_data, e.g. `drought/vg_2026-08-12_01.jpg`
   - `label` — the folder name (`healthy`, `drought`, `fungal_disease`, `insect_damage`, `wear`, `dormant`)
   - `site` — a short name for the place (the same name for every photo from that place).
     **Very important:** train/test is split by this column, so photos from one place never end up
     in both. Use the same spelling every time.
   - `date` — when the photo was taken, `YYYY-MM-DD` (leave blank if unknown)
   - `source` — `own` for your photos, otherwise the web page URL where you found it
   - `license` — e.g. `own`, `CC0`, `CC BY 4.0`, `CC BY-SA 4.0`, `permission (email 2026-12-01)`
   - `credit` — the photographer / owner name exactly as the license asks
   - `confirmed_by` — who confirmed the label (e.g. `self`, `CSU Plant Diagnostic Clinic`,
     `groundskeeper`, `photo caption`). Disease and insect photos need an expert or lab here.
3. Don't put in photos of people's faces, license plates or house numbers.

## Example row

```
filename,label,site,date,source,license,credit,confirmed_by
drought/vg_2026-08-12_01.jpg,drought,village_greens,2026-08-12,own,own,Lavi Ouyang,groundskeeper
```

(The example is NOT in `metadata.csv`; the file starts with only the header line.)

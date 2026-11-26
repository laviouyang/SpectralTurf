# CLIP text prompts per turf problem (Stage 11)

Made 2026-11-25 from `docs/disease_references.csv` (the symptoms column, which describes the PDFs in
`reference_articles/` in our own words). The prompts below are **our own wording**: nothing is copied
from the articles. Plan: `docs/STAGE_11_PHOTO_AI.md`.

How these will be used: for the CLIP **zero-shot** baseline (no training), each photo is compared
with every prompt, and a class's score is the best (or average) of its prompts. Prompts only
describe what a **camera can see** (colors, shapes, patterns); things that need a hand lens, a lab
or digging (spores, root color, grubs under the soil) are left out on purpose, except where the
damage is visible on the surface.

> These prompts are for a research baseline. A match means "this photo looks like photos described
> this way", **not a diagnosis**. Many problems below look almost the same in a photo (the PDFs say
> so too, e.g. Pythium root rot usually needs a lab test).

---

## fungal_disease

Turf diseases (lawns, sports fields, golf turf):

| Disease | Prompts |
|---|---|
| Brown patch | "a lawn with round brown patches of dead grass that appeared suddenly" · "a circular brown blighted patch in tall fescue with a darker ring at its edge" |
| Dollar spot | "many small bleached straw-colored spots scattered across short green turf" · "grass blades with tan spots bordered by brown bands" |
| Fairy ring | "a ring of dark green grass on a lawn" · "a circle of mushrooms growing in a lawn" · "an arc of wilted brown grass with greener grass beside it" |
| Necrotic ring spot | "round straw-colored patches in Kentucky bluegrass with green grass in the center" · "thin brown rings of dying grass in a lawn, like a frog eye" |
| Summer patch | "irregular yellow and straw-colored patches with bronze edges in a summer lawn" · "wilted thin bluegrass patches with a living green center" |
| Leaf spot / melting-out | "grass blades with small reddish-brown and purple spots" · "a thinning, browning lawn where the grass is dying out in patches" |
| Red thread | "pink and reddish patches in a lawn" · "grass blades with thin red threads sticking out of them" |
| Rusts | "a lawn with an orange-yellow tint from a distance" · "grass blades covered in orange powdery spots" |
| Powdery mildew | "grass blades covered with a white powdery coating" · "shaded lawn grass that looks dusted with white powder" |
| Gray snow mold | "matted gray and bleached circular patches of grass after snow melts" |
| Pink snow mold (Microdochium patch) | "round tan patches with pinkish edges on grass after snow melt" · "small reddish-brown and pink spots on cold wet turf" |
| Pythium blight | "dark greasy-looking dead grass along a water drainage path" · "orange and bronze spots of collapsed matted grass after a hot humid night" |
| Pythium root rot / root dysfunction | "irregular yellow and bronze thinning patches on a putting green" · "orange patches of collapsing turf on a golf green" |
| Anthracnose | "thinning golf turf turning bright yellow and orange in irregular areas" |
| Bentgrass dead spot | "many small sunken copper-colored spots on a putting green that look like ball marks" |
| Brown ring patch / yellow patch | "yellow rings in the grass of a golf green" · "several yellow and reddish-brown rings linked together on short turf" |
| Take-all patch | "bronze and red-brown circular patches on a bentgrass green" |
| Gray leaf spot | "ryegrass turf with a grayish, scorched look and gray-tipped twisted leaves" |
| Smuts | "grass blades with long silvery-gray to black streaks, shredding at the tips" |
| Yellow tuft | "small yellow tufts of crowded grass shoots on a green" |
| Helminthosporium leaf spot | "grass leaves with small spots that have red borders and gray centers" |

Warm-season-grass diseases (bermudagrass, zoysiagrass, St. Augustinegrass). Listed for
completeness; the CSV marks them `colorado_relevant = no`, so they will probably not be used:

| Disease | Prompts |
|---|---|
| Large patch | "large reddish-brown rings with orange edges in a zoysiagrass lawn" |
| Spring dead spot | "bleached round dead patches in bermudagrass that stay brown in spring" |
| Take-all root rot | "yellow and orange declining patches on a bermudagrass green" |
| Mini-ring | "scalloped tan and orange rings on a bermudagrass putting green" |
| Southern blight | "fast-growing orange and reddish-brown circles of dead grass in hot weather" |

Not used as prompts (in the PDFs, but about cereal crops / seed heads, not mowed turf):
ergot, leaf rust and stem rust of cereals, Septoria blotch, Stagonospora blotch (P-00394).

## insect_damage

| Problem | Prompts |
|---|---|
| White grubs (incl. Japanese beetle larvae) | "brown dead patches of lawn that peel back like a carpet" · "a lawn torn up by animals digging, with brown dead grass" · "irregular light-brown wilted areas of grass spreading across a lawn" |
| Sod webworm | "small ragged brown patches in a lawn that look scalped" · "a thin, patchy lawn with silk webbing in the grass" |
| Bronzed cutworm | "small round brown spots, a few inches wide, scattered in a green lawn" |
| Cigarette paper webworm | "white paper-like tubes lying on a lawn" |
| Black grass bug | "grass blades covered in tiny pale and white speckles" |

Not used as prompts: grasshoppers (the article shows no lawn symptoms), cicadas (no turf damage).

## drought

| Problem | Prompts |
|---|---|
| Drought stress | "a dry lawn turning brown and straw-colored in summer heat" · "a patchy lawn with green and brown areas during a drought" · "wilting grass with a dull blue-gray tint" |

Note: brown patch, fairy ring, white grubs and summer patch are all described in the PDFs as
able to *look like* drought, so expect the model to confuse these classes.

## other (from the PDFs; not one of the 6 photo classes)

These could be useful as **"not one of our classes"** prompts, so the model can say "Unsure" instead
of forcing a label:

| Problem | Prompts |
|---|---|
| Blue-green algae | "black slimy crust on thin wet turf in a shady spot" |
| Lawn weeds | "a lawn full of yellow dandelion flowers" · "a lawn with clover and broadleaf weeds" · "crabgrass growing in a lawn" |
| Excess thatch | "a cross-section of sod with a thick spongy brown layer above the soil" |
| Cicada killer nests | "small mounds of dug-up soil with holes in bare patches of a lawn" |

## Classes not covered by the PDFs (our own wording, no source)

The PDFs don't describe these, but the classifier needs them:

| Class | Prompts |
|---|---|
| healthy | "a dense, evenly green, healthy lawn" · "a well-kept green sports field with uniform grass" |
| dormant | "an evenly tan, brown dormant lawn in winter" · "a whole lawn of straw-colored grass in early spring before green-up" |
| wear | "a bare worn patch of dirt in front of a soccer goal" · "a worn path of thin grass and bare soil across a field" |

---

### Notes

- Prompts are short on purpose (CLIP's text side works best with short captions) and start with
  plain words a photo caption would use.
- When we test zero-shot, we report results **per prompt set** so we can see which prompts help;
  we never change prompts after looking at the test-site results (only on the training sites).
- Source of every symptom: `docs/disease_references.csv` (pdf_file + page). Articles were collected
  by the student's family; `permission_status` is "not asked" for all of them, and the PDFs are
  git-ignored (`reference_articles/`). Only our own summaries are committed.

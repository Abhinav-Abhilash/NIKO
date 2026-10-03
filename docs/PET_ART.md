# Desktop Pet Sprite Cleaning & Art Pipeline

This guide explains how to manually clean sprites, import cleaned art, and swap in higher-resolution character sheets.

---

## 1. Export Raw Crops

Generate raw crops from the master sheet with the original cream background untouched:

```bash
python scripts/slice_sprites.py --export-raw
```

This creates the following in `exports/`:
* `exports/pet_raw/<state>__<frame_name>.png` — Original-resolution raw crop (1x).
* `exports/pet_raw/<state>__<frame_name>__4x.png` — 4x Lanczos-upscaled copy for high-precision manual cleaning.
* `exports/pet_raw/INDEX.png` — Visual index showing all 71 frames with their exact filenames.
* `exports/master_sheet.png` — Full master sheet copy for single-pass cleaning.
* `exports/pet_raw_crops.zip` — Portable zip archive of all crops and indexes.

Folder location: `e:\NIKO AI\exports`

---

## 2. Clean Backgrounds

Remove the cream background, leaving transparent alpha. Keep soft hair edges clean, and preserve facial skin, eye reflections, and the white shirt collar.

You can clean frames in either of two ways:

### Option A: Per-Pose (Recommended)
Save transparent PNGs to:
```
frontend/design-import/cleaned/<state>__<frame_name>.png
```
*(The `__4x` suffix is optional — e.g., `idle__idle_neutral.png` or `idle__idle_neutral__4x.png` both match).*

### Option B: Whole Sheet
Save the full cleaned master sheet with a transparent background to:
```
frontend/design-import/cleaned_sheet.png
```

---

## 3. Import & Validate

Run the importer:

```bash
python scripts/slice_sprites.py --from-cleaned
```

* **No Background Removal Applied to Your Files:** Your cleaned alpha channels are preserved as-is.
* **Auto-Normalization:** Crops are trimmed to visible bounds, scaled to 2x HiDPI resolution, and aligned to the shared feet baseline anchor ($Y=432$).
* **Automatic Fallback:** Any frames you did not clean automatically keep their decontaminated version from the automatic slicer.
* **Built-in Validation:** The importer checks for:
  * Missing alpha channels (opaque RGB).
  * Leftover cream borders along hair/body perimeters.
  * Cut-off hands, hair, or feet touching crop edges.
  * Unmatched filenames.
* **Visual Audit:** Regenerates `frontend/public/pet/contact_sheet.png` with side-by-side Dark (`#181C24`) and Light (`#F5F7FA`) backdrops plus 4x hair inspection zooms.

---

## 4. Higher-Resolution Replacement Sheets

If you obtain or render a higher-resolution master character sheet:
1. Place the new sheet into `frontend/design-import/<new_file>.png`.
2. Update `"source_image"` and the `"crop": [x1, y1, x2, y2]` bounding boxes in `scripts/sprites_config.json`.
3. The slicing engine automatically scales any resolution to the shared 400x480 (2x of 200x240) canvas with consistent feet anchoring.

---

## 5. Recommended Free Tools

* **[Photopea](https://www.photopea.com/)** (Web, Free) — Photoshop clone in browser. Magic Wand (`W`), Color Range Select, and Refine Edge work great.
* **[Krita](https://krita.org/)** (Desktop, Free/Open Source) — Excellent contiguous/similar color selection and eraser brushes.
* **[GIMP](https://www.gimp.org/)** (Desktop, Free/Open Source) — Select by Color tool and Color to Alpha filter.
* **[Paint.NET](https://www.getpaint.net/)** (Windows, Free) — Lightweight Magic Wand with adjustable tolerance slider.

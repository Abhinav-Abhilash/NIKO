#!/usr/bin/env python3
"""
NIKO Desktop Companion - Production Sprite Slicing & Edge Decontamination Engine
Supports:
  1. Automatic background removal with enclosed hair-pocket decontamination and speck filtering.
  2. Raw crop exports (--export-raw): 1x and 4x Lanczos crops, master sheet, INDEX.png, and zip.
  3. Manual cleaned import (--from-cleaned): per-pose in frontend/design-import/cleaned/
     or whole sheet in frontend/design-import/cleaned_sheet.png, with full validation and fallback.
  4. Dual-backdrop contact sheet generation (Dark #181C24 vs Light #F5F7FA) with 4x hair zoom.
"""

import argparse
import json
import math
import os
import zipfile

import cv2
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import binary_dilation, label


def slice_frame_and_decontaminate(
    img_bgr: np.ndarray,
    crop_box: tuple[int, int, int, int],
    state_name: str = "",
    protect_boxes: list[list[int]] | None = None,
    target_w: int = 200,
    target_h: int = 240,
    anchor_y: int = 216,
    scale: float = 2.0,
    bg_bgr: tuple[float, float, float] = (228.0, 244.0, 250.0),
) -> tuple[np.ndarray, np.ndarray, int]:
    """
    Slices a single character pose from the source image, eliminates cream background
    including enclosed pockets between hair locks, removes detached specks,
    decontaminates edge pixels, and places the sprite on a normalized 2x canvas.
    Returns (normalized_canvas_bgra, tight_sprite_bgra, ground_offset).
    """
    x1, y1, x2, y2 = crop_box
    h_sheet, w_sheet = img_bgr.shape[:2]
    crop = img_bgr[max(0, y1) : min(h_sheet, y2), max(0, x1) : min(w_sheet, x2)].copy()
    ch, cw = crop.shape[:2]

    b = crop[:, :, 0].astype(float)
    g = crop[:, :, 1].astype(float)
    r = crop[:, :, 2].astype(float)
    dist = np.sqrt((b - bg_bgr[0]) ** 2 + (g - bg_bgr[1]) ** 2 + (r - bg_bgr[2]) ** 2)

    # 1. Identify pure cream background pixels
    is_bg_mask = (dist < 30.0) | (
        (r > 235)
        & (g > 224)
        & (b > 195)
        & (np.abs(r - g) < 22)
        & ((r - b) < 55)
    )

    # Strip faint ground shadow at the bottom margin of the crop
    for dy in range(max(0, ch - 12), ch):
        shadow_cond = (
            (r[dy] > 180)
            & (g[dy] > 150)
            & (b[dy] > 120)
            & (np.abs(r[dy] - g[dy]) < 35)
            & (b[dy] < 210)
        )
        is_bg_mask[dy, shadow_cond] = True

    # 2. Flood fill from perimeter to ensure internal skin/clothing are never breached
    bg_visited = np.zeros((ch, cw), dtype=np.uint8)
    queue = []
    for x in range(cw):
        if is_bg_mask[0, x]:
            bg_visited[0, x] = 1
            queue.append((0, x))
        if is_bg_mask[ch - 1, x]:
            bg_visited[ch - 1, x] = 1
            queue.append((ch - 1, x))
    for y in range(ch):
        if is_bg_mask[y, 0]:
            bg_visited[y, 0] = 1
            queue.append((y, 0))
        if is_bg_mask[y, cw - 1]:
            bg_visited[y, cw - 1] = 1
            queue.append((y, cw - 1))

    head = 0
    while head < len(queue):
        cy, cx = queue[head]
        head += 1
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            ny, nx = cy + dy, cx + dx
            if (
                0 <= ny < ch
                and 0 <= nx < cw
                and not bg_visited[ny, nx]
                and (is_bg_mask[ny, nx] or dist[ny, nx] < 36.0)
            ):
                bg_visited[ny, nx] = 1
                queue.append((ny, nx))

    # 2b. Enclosed Cream Pockets in Hair Removal
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    h_chan, s_chan, v_chan = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    is_hair = (h_chan >= 0) & (h_chan <= 26) & (s_chan >= 65) & (v_chan >= 120)
    is_skin = (h_chan >= 5) & (h_chan <= 22) & (s_chan >= 20) & (s_chan <= 68) & (v_chan >= 210) & (r > g) & (g > b)
    is_suit = (v_chan < 75) | ((r < 70) & (g < 70) & (b < 80))

    is_protected = np.zeros((ch, cw), dtype=bool)
    if protect_boxes:
        for pbox in protect_boxes:
            px1, py1, px2, py2 = pbox
            if px1 >= x1 or py1 >= y1:
                px1 = max(0, px1 - x1)
                py1 = max(0, py1 - y1)
                px2 = min(cw, px2 - x1)
                py2 = min(ch, py2 - y1)
            is_protected[max(0, py1) : min(ch, py2), max(0, px1) : min(cw, px2)] = True

    hair_float = is_hair.astype(np.float32)
    ones = np.ones((ch, cw), dtype=np.float32)
    hair_sum = cv2.boxFilter(hair_float, -1, (7, 7), normalize=False)
    total_sum = cv2.boxFilter(ones, -1, (7, 7), normalize=False)
    hair_ratio = hair_sum / np.maximum(total_sum, 1.0)

    is_near_cream = (bg_visited == 0) & (
        (dist < 40.0) | ((s_chan < 45) & (v_chan > 215) & ((r - b) < 35))
    )

    lbl_cream, num_cream = label(is_near_cream)
    pocket_mask = np.zeros((ch, cw), dtype=bool)

    for idx in range(num_cream):
        comp = (lbl_cream == (idx + 1))
        if np.any(is_protected[comp]):
            continue

        dilated = binary_dilation(comp, iterations=2)
        boundary = dilated & (~comp)

        # Never touch eyes (boundary touches skin) or collar (boundary touches dark suit)
        if np.any(boundary & is_skin) or np.any(boundary & is_suit):
            continue

        comp_hair_ratio = hair_ratio[comp]
        if np.mean(comp_hair_ratio) >= 0.48 or (
            np.sum(comp_hair_ratio >= 0.45) / len(comp_hair_ratio) >= 0.65
        ):
            pocket_mask[comp] = True

    bg_visited[pocket_mask] = 1
    fg_mask = (bg_visited == 0).astype(np.uint8)

    # 3. Connected component analysis to isolate character and eliminate detached specks
    num_labels, labels, stats, _centroids = cv2.connectedComponentsWithStats(
        fg_mask, connectivity=8
    )
    if num_labels > 1:
        largest_label = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        clean_fg = np.zeros_like(fg_mask)
        clean_fg[labels == largest_label] = 1

        main_stat = stats[largest_label]
        main_top = main_stat[cv2.CC_STAT_TOP]
        main_bottom = main_top + main_stat[cv2.CC_STAT_HEIGHT]

        dist_to_body = cv2.distanceTransform((clean_fg == 0).astype(np.uint8), cv2.DIST_L2, 3)

        for l_idx in range(1, num_labels):
            if l_idx == largest_label:
                continue

            comp = (labels == l_idx)
            area = stats[l_idx, cv2.CC_STAT_AREA]
            top = stats[l_idx, cv2.CC_STAT_TOP]
            w = stats[l_idx, cv2.CC_STAT_WIDTH]
            h = stats[l_idx, cv2.CC_STAT_HEIGHT]

            if area < 8:
                continue
            if top <= 2 and (w > 18 or h <= 4):
                continue
            if top < main_top - 30 and (w > 20 and h <= 5):
                continue
            if top >= main_bottom - 3:
                continue

            if np.any(is_protected[comp]):
                clean_fg[comp] = 1
                continue

            min_dist = float(np.min(dist_to_body[comp]))
            comp_color = crop[comp].mean(axis=0)  # BGR
            is_orange_speck = (comp_color[2] > 180 and comp_color[1] > 80 and comp_color[2] > comp_color[0] + 30)

            # In idle: pure standing poses with no external props
            if state_name == "idle":
                if min_dist <= 1.5:
                    clean_fg[comp] = 1
                continue

            # In active states: preserve props (thought bubble, sleep zzz, exclamation marks, sweat drops, clouds)
            if min_dist <= 1.5 or top < main_top and not is_orange_speck or area >= 16 and not is_orange_speck:
                clean_fg[comp] = 1

        fg_mask = clean_fg

    # 4. Find tight bounding box of character
    fg_y, fg_x = np.where(fg_mask == 1)
    if len(fg_y) == 0:
        empty = np.zeros((target_h, target_w, 4), dtype=np.uint8)
        return empty, empty, 0

    min_y, max_y = int(fg_y.min()), int(fg_y.max())
    min_x, max_x = int(fg_x.min()), int(fg_x.max())
    ground_offset = (ch - 1) - max_y

    # 5. Boundary-Band Edge Decontamination
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    eroded_fg = cv2.erode(fg_mask, kernel, iterations=1)
    boundary_band = (fg_mask == 1) & (eroded_fg == 0)
    core_fg = eroded_fg == 1

    out_bgr = crop.astype(float)
    alpha = np.zeros((ch, cw), dtype=float)
    alpha[core_fg] = 1.0

    band_dist = dist[boundary_band]
    band_alpha = np.clip((band_dist - 8.0) / 36.0, 0.15, 1.0)
    alpha[boundary_band] = band_alpha

    for c_idx, bg_val in enumerate(bg_bgr):
        c_chan = out_bgr[:, :, c_idx]
        b_chan = c_chan[boundary_band]
        unmixed = (b_chan - (1.0 - band_alpha) * bg_val) / band_alpha
        out_bgr[boundary_band, c_idx] = np.clip(unmixed, 0, 255)

    out_rgba = np.zeros((ch, cw, 4), dtype=np.uint8)
    out_rgba[:, :, :3] = np.clip(out_bgr, 0, 255).astype(np.uint8)
    out_rgba[:, :, 3] = (alpha * 255).astype(np.uint8)

    # 6. Extract tight sprite and upscale 2x with Lanczos4 for sharp HiDPI rendering
    tight_sprite = out_rgba[min_y : max_y + 1, min_x : max_x + 1]
    sh, sw = tight_sprite.shape[:2]
    scaled_w = int(sw * scale)
    scaled_h = int(sh * scale)
    scaled_sprite = cv2.resize(
        tight_sprite, (scaled_w, scaled_h), interpolation=cv2.INTER_LANCZOS4
    )

    # 7. Place on normalized canvas with feet anchor
    canvas = np.zeros((target_h, target_w, 4), dtype=np.uint8)
    scaled_offset = int(max(0, ground_offset - 2) * scale)
    paste_y = anchor_y - scaled_h - scaled_offset
    paste_x = (target_w - scaled_w) // 2

    if paste_y < 0:
        paste_y = 0
    if paste_x < 0:
        paste_x = 0
    actual_h = min(scaled_h, target_h - paste_y)
    actual_w = min(scaled_w, target_w - paste_x)

    canvas[paste_y : paste_y + actual_h, paste_x : paste_x + actual_w] = (
        scaled_sprite[:actual_h, :actual_w]
    )
    return canvas, tight_sprite, ground_offset


def normalize_cleaned_sprite(
    cleaned_img: np.ndarray,
    target_scaled_h: int,
    ground_offset_base: int,
    target_w: int = 200,
    target_h: int = 240,
    anchor_y: int = 216,
    scale: float = 2.0,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Takes a user-provided cleaned sprite (with alpha channel), trims to visible bounds,
    scales to match target size, and places on the normalized canvas at the feet anchor.
    """
    alpha = cleaned_img[:, :, 3]
    fg_y, fg_x = np.where(alpha > 10)
    if len(fg_y) == 0:
        empty = np.zeros((target_h, target_w, 4), dtype=np.uint8)
        return empty, empty

    min_y, max_y = int(fg_y.min()), int(fg_y.max())
    min_x, max_x = int(fg_x.min()), int(fg_x.max())
    tight = cleaned_img[min_y : max_y + 1, min_x : max_x + 1]
    th, tw = tight.shape[:2]

    # Scale proportionally to match the target rendered character height
    if th > 0:
        scale_ratio = target_scaled_h / th
        scaled_w = max(1, int(round(tw * scale_ratio)))
        scaled_h = target_scaled_h
    else:
        scaled_w, scaled_h = tw, th

    scaled_sprite = cv2.resize(tight, (scaled_w, scaled_h), interpolation=cv2.INTER_LANCZOS4)

    canvas = np.zeros((target_h, target_w, 4), dtype=np.uint8)
    scaled_offset = int(max(0, ground_offset_base - 2) * scale)
    paste_y = anchor_y - scaled_h - scaled_offset
    paste_x = (target_w - scaled_w) // 2

    if paste_y < 0:
        paste_y = 0
    if paste_x < 0:
        paste_x = 0
    actual_h = min(scaled_h, target_h - paste_y)
    actual_w = min(scaled_w, target_w - paste_x)

    canvas[paste_y : paste_y + actual_h, paste_x : paste_x + actual_w] = (
        scaled_sprite[:actual_h, :actual_w]
    )
    return canvas, tight


def validate_cleaned_frame(
    img: np.ndarray | None,
    _frame_label: str = "",
    _orig_crop: np.ndarray | None = None,
    bg_bgr: tuple[float, float, float] = (228.0, 244.0, 250.0),
) -> list[str]:
    """
    Validates a cleaned frame for common problems:
      - Missing alpha channel
      - Leftover cream border
      - Suspicious dimensions / empty frame
      - Cut-off hair or hands
    """
    issues = []
    if img is None:
        issues.append("Failed to load image file")
        return issues

    # 1. Check alpha channel
    if img.ndim != 3 or img.shape[2] != 4:
        issues.append("No alpha channel found (image is RGB/opaque, transparent PNG required)")
        return issues

    alpha = img[:, :, 3]
    if np.max(alpha) == 0:
        issues.append("Image is completely transparent / empty")
        return issues

    h, w = img.shape[:2]
    if h < 20 or w < 20:
        issues.append(f"Suspiciously small image ({w}x{h})")

    # 2. Check for leftover cream border along visible boundary
    fg_mask = (alpha > 20).astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    eroded = cv2.erode(fg_mask, kernel, iterations=1)
    boundary = (fg_mask == 1) & (eroded == 0)

    b = img[:, :, 0].astype(float)
    g = img[:, :, 1].astype(float)
    r = img[:, :, 2].astype(float)
    dist = np.sqrt((b - bg_bgr[0]) ** 2 + (g - bg_bgr[1]) ** 2 + (r - bg_bgr[2]) ** 2)

    cream_fringe = boundary & (dist < 32.0)
    cream_fringe_count = int(cream_fringe.sum())
    if cream_fringe_count > 12:
        issues.append(
            f"Leftover cream border detected ({cream_fringe_count} border pixels near cream background color)"
        )

    # 3. Check for cut-off hands or hair (touching extreme crop borders)
    touches_top = bool(np.any(alpha[0, :] > 50))
    touches_left = bool(np.any(alpha[:, 0] > 50))
    touches_right = bool(np.any(alpha[:, -1] > 50))

    if touches_top or touches_left or touches_right:
        borders = []
        if touches_top:
            borders.append("top")
        if touches_left:
            borders.append("left")
        if touches_right:
            borders.append("right")
        issues.append(f"Art touches crop boundary at [{', '.join(borders)}] (possible cut-off hair or hands)")

    return issues


def export_raw_crops(repo_root: str, config: dict):
    """
    Exports raw untouched crops for every frame in scripts/sprites_config.json:
      - 1x raw crop: exports/pet_raw/<state>__<frame_name>.png
      - 4x Lanczos copy: exports/pet_raw/<state>__<frame_name>__4x.png
      - Visual Index: exports/pet_raw/INDEX.png
      - Master Sheet copy: exports/master_sheet.png
      - Zip Archive: exports/pet_raw_crops.zip
    """
    exports_dir = os.path.join(repo_root, "exports")
    pet_raw_dir = os.path.join(exports_dir, "pet_raw")
    os.makedirs(pet_raw_dir, exist_ok=True)

    source_rel = config.get("source_image", "frontend/design-import/character-sheet=2.png")
    source_path = os.path.join(repo_root, source_rel)
    sheet = cv2.imread(source_path)
    if sheet is None:
        raise FileNotFoundError(f"Source master sheet not found at: {source_path}")

    h_sheet, w_sheet = sheet.shape[:2]

    # Copy master sheet to exports/master_sheet.png
    master_copy_path = os.path.join(exports_dir, "master_sheet.png")
    cv2.imwrite(master_copy_path, sheet)
    print(f"[EXPORT] Master sheet copied to: {master_copy_path}")

    by_state = {}
    total_exported = 0

    for state_name, s_data in config.get("states", {}).items():
        for f_meta in s_data.get("frames", []):
            x1, y1, x2, y2 = f_meta["crop"]
            fname = f_meta["name"]
            crop = sheet[max(0, y1) : min(h_sheet, y2), max(0, x1) : min(w_sheet, x2)].copy()

            base_name = f"{state_name}__{fname}"
            out_1x = os.path.join(pet_raw_dir, f"{base_name}.png")
            out_4x = os.path.join(pet_raw_dir, f"{base_name}__4x.png")

            # 1x raw crop (original cream background untouched)
            cv2.imwrite(out_1x, crop)

            # 4x Lanczos upscaled copy for easy manual cleaning
            crop_4x = cv2.resize(
                crop, (crop.shape[1] * 4, crop.shape[0] * 4), interpolation=cv2.INTER_LANCZOS4
            )
            cv2.imwrite(out_4x, crop_4x)

            total_exported += 1
            by_state.setdefault(state_name, []).append(
                {
                    "name": fname,
                    "filename": f"{base_name}.png",
                    "img_path": out_1x,
                }
            )

    print(f"[EXPORT] Saved {total_exported} 1x crops and {total_exported} 4x crops to: {pet_raw_dir}")

    # Generate INDEX.png
    cell_w = 160
    cell_h = 160
    header_h = 32
    padding = 12
    cols = 6

    total_rows = sum(math.ceil(len(frames) / cols) for frames in by_state.values())
    sheet_w = cols * (cell_w + padding) + padding * 2
    sheet_h = len(by_state) * (header_h + padding) + total_rows * (cell_h + padding) + 80

    index_img = Image.new("RGB", (sheet_w, sheet_h), (24, 28, 36))
    draw = ImageDraw.Draw(index_img)

    draw.rectangle([0, 0, sheet_w, 54], fill=(225, 109, 39))
    draw.text((padding + 8, 12), "NIKO Companion Pet - Raw Crop Index & Filename Mapping", fill=(255, 255, 255))
    draw.text((padding + 8, 32), "Directory: exports/pet_raw/ - Both 1x (.png) and 4x (__4x.png) crops available", fill=(255, 230, 210))

    curr_y = 66
    for state_name, frames in by_state.items():
        draw.rectangle([padding, curr_y, sheet_w - padding, curr_y + header_h], fill=(36, 44, 58))
        draw.text((padding + 10, curr_y + 8), f"STATE: {state_name.upper()} ({len(frames)} frames)", fill=(245, 166, 35))
        curr_y += header_h + padding

        for idx, f in enumerate(frames):
            r_idx = idx // cols
            c_idx = idx % cols
            x = padding + c_idx * (cell_w + padding)
            y = curr_y + r_idx * (cell_h + padding)

            draw.rectangle([x, y, x + cell_w, y + cell_h], fill=(18, 22, 28), outline=(48, 56, 72))

            im = Image.open(f["img_path"])
            max_thumb_h = cell_h - 36
            max_thumb_w = cell_w - 16
            scale_ratio = min(max_thumb_w / im.width, max_thumb_h / im.height)
            tw, th = int(im.width * scale_ratio), int(im.height * scale_ratio)
            thumb = im.resize((tw, th), Image.Resampling.LANCZOS)

            paste_x = x + (cell_w - tw) // 2
            paste_y = y + 6 + (max_thumb_h - th) // 2
            index_img.paste(thumb, (paste_x, paste_y))

            lbl = f["filename"]
            if len(lbl) > 23:
                lbl = lbl[:21] + ".."
            draw.text((x + 6, y + cell_h - 22), lbl, fill=(180, 195, 215))

        rows = math.ceil(len(frames) / cols)
        curr_y += rows * (cell_h + padding) + padding

    index_path = os.path.join(pet_raw_dir, "INDEX.png")
    index_img.save(index_path, optimize=True)
    print(f"[EXPORT] Visual index image saved to: {index_path}")

    # Build exports/pet_raw_crops.zip
    zip_path = os.path.join(exports_dir, "pet_raw_crops.zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(master_copy_path):
            zf.write(master_copy_path, "master_sheet.png")
        for root, _, files in os.walk(pet_raw_dir):
            for file in files:
                fp = os.path.join(root, file)
                arcname = os.path.join("pet_raw", file)
                zf.write(fp, arcname)

    zip_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"[EXPORT] Packed zip archive to: {zip_path} ({zip_mb:.2f} MB)")
    print(f"[EXPORT] Full exports folder path: {exports_dir}")


def generate_contact_sheet(
    frames_meta: list[dict],
    hair_zoom_frames: list[dict],
    output_path: str,
):
    """
    Renders ONE comprehensive contact sheet containing all frames grouped by state.
    Each frame is displayed on BOTH a dark (#181C24) and a light (#F5F7FA) background
    side by side, plus a dedicated high-magnification zoom section of hair-heavy frames.
    """
    by_state: dict[str, list[dict]] = {}
    for f in frames_meta:
        by_state.setdefault(f["state"], []).append(f)

    sub_w = 90
    sub_h = 108
    card_w = sub_w * 2 + 6
    card_h = sub_h + 24
    header_h = 28
    padding = 12
    cols = 6

    total_rows = 0
    for state_frames in by_state.values():
        total_rows += math.ceil(len(state_frames) / cols)

    sheet_w = cols * (card_w + padding) + padding * 2
    zoom_section_h = 320
    sheet_h = (
        len(by_state) * (header_h + padding)
        + total_rows * (card_h + padding)
        + padding * 4
        + zoom_section_h
        + 60
    )

    sheet = Image.new("RGBA", (sheet_w, sheet_h), (18, 22, 28, 255))
    draw = ImageDraw.Draw(sheet)

    # Master Banner
    draw.rectangle([0, 0, sheet_w, 54], fill=(225, 109, 39, 255))
    draw.text(
        (padding + 6, 12),
        "NIKO Companion Pet - Precision Sprite Sheet Contact (Dark vs Light Dual Backdrop)",
        fill=(255, 255, 255, 255),
    )
    draw.text(
        (padding + 6, 32),
        "Each frame shown side-by-side: [ Dark #181C24 | Light #F5F7FA ] - Verified Zero Hair Halos & Intact Features",
        fill=(255, 230, 210, 255),
    )

    curr_y = 66
    for state, state_frames in by_state.items():
        draw.rectangle(
            [padding, curr_y, sheet_w - padding, curr_y + header_h],
            fill=(32, 38, 50, 255),
        )
        draw.text(
            (padding + 10, curr_y + 7),
            f"STATE: {state.upper()} ({len(state_frames)} frames)",
            fill=(245, 166, 35, 255),
        )
        curr_y += header_h + padding

        for idx, f in enumerate(state_frames):
            row_idx = idx // cols
            col_idx = idx % cols
            x = padding + col_idx * (card_w + padding)
            y = curr_y + row_idx * (card_h + padding)

            draw.rectangle(
                [x, y, x + card_w, y + card_h],
                fill=(24, 28, 36, 255),
                outline=(48, 56, 72, 255),
            )

            # Left: Dark Backdrop (#181C24)
            draw.rectangle(
                [x + 2, y + 2, x + 2 + sub_w, y + 2 + sub_h],
                fill=(24, 28, 36, 255),
            )
            # Right: Light Backdrop (#F5F7FA)
            draw.rectangle(
                [x + 4 + sub_w, y + 2, x + card_w - 2, y + 2 + sub_h],
                fill=(245, 247, 250, 255),
            )

            ground_y = y + 2 + int(sub_h * 0.90)
            draw.line([x + 6, ground_y, x + sub_w - 2, ground_y], fill=(60, 70, 88, 255), width=1)
            draw.line([x + 8 + sub_w, ground_y, x + card_w - 6, ground_y], fill=(205, 212, 222, 255), width=1)

            sprite_img = f["pil_image"]
            thumb_w = sub_w - 8
            thumb_h = int(thumb_w * (240 / 200))
            thumb = sprite_img.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)

            sheet.paste(thumb, (x + 6, y + 4), thumb)
            sheet.paste(thumb, (x + 8 + sub_w, y + 4), thumb)

            source_tag = f.get("source_tag", "")
            caption = f"#{f['index']}: {f['name']}{source_tag}"
            draw.text(
                (x + 6, y + card_h - 17),
                caption[:23],
                fill=(170, 182, 198, 255),
            )

        rows = math.ceil(len(state_frames) / cols)
        curr_y += rows * (card_h + padding) + padding

    # Dedicated High-Magnification Zoom Section
    draw.rectangle(
        [padding, curr_y, sheet_w - padding, curr_y + header_h],
        fill=(225, 109, 39, 255),
    )
    draw.text(
        (padding + 10, curr_y + 7),
        "HAIR POCKET INSPECTION: 4x HIGH-MAGNIFICATION CLOSE-UP ON 3 HAIR-HEAVY FRAMES",
        fill=(255, 255, 255, 255),
    )
    curr_y += header_h + padding

    zoom_card_w = (sheet_w - padding * 2 - (len(hair_zoom_frames) - 1) * padding) // len(hair_zoom_frames)
    zoom_card_h = zoom_section_h - header_h - padding * 2

    for z_idx, zf in enumerate(hair_zoom_frames):
        zx = padding + z_idx * (zoom_card_w + padding)
        zy = curr_y

        draw.rectangle(
            [zx, zy, zx + zoom_card_w, zy + zoom_card_h],
            fill=(24, 28, 36, 255),
            outline=(245, 166, 35, 255),
            width=2,
        )

        draw.text(
            (zx + 10, zy + 8),
            f"ZOOM #{z_idx + 1}: {zf['state'].upper()} / {zf['name']}",
            fill=(245, 166, 35, 255),
        )

        half_w = (zoom_card_w - 24) // 2
        half_h = zoom_card_h - 48
        px_dark = zx + 8
        px_light = zx + 16 + half_w
        py = zy + 32

        draw.rectangle([px_dark, py, px_dark + half_w, py + half_h], fill=(24, 28, 36, 255), outline=(50, 60, 75, 255))
        draw.rectangle([px_light, py, px_light + half_w, py + half_h], fill=(245, 247, 250, 255), outline=(190, 200, 215, 255))

        draw.text((px_dark + 6, py + 4), "DARK #181C24", fill=(140, 150, 170, 255))
        draw.text((px_light + 6, py + 4), "LIGHT #F5F7FA", fill=(90, 100, 120, 255))

        pil_raw = zf["pil_image"]
        hair_crop = pil_raw.crop((60, 40, 340, 310))
        target_zoom_w = half_w - 12
        target_zoom_h = int(target_zoom_w * (hair_crop.height / hair_crop.width))
        if target_zoom_h > half_h - 26:
            target_zoom_h = half_h - 26
            target_zoom_w = int(target_zoom_h * (hair_crop.width / hair_crop.height))

        hair_zoomed = hair_crop.resize((target_zoom_w, target_zoom_h), Image.Resampling.NEAREST)

        paste_zoom_y = py + 22 + (half_h - 22 - target_zoom_h) // 2
        paste_zoom_x_dark = px_dark + (half_w - target_zoom_w) // 2
        paste_zoom_x_light = px_light + (half_w - target_zoom_w) // 2

        sheet.paste(hair_zoomed, (paste_zoom_x_dark, paste_zoom_y), hair_zoomed)
        sheet.paste(hair_zoomed, (paste_zoom_x_light, paste_zoom_y), hair_zoomed)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    sheet.save(output_path, optimize=True)
    print(f"Contact sheet saved to: {output_path} ({sheet_w}x{sheet_h})")


def process_sprites(
    from_cleaned: bool = False,
):
    """
    Main sprite generation pipeline.
    If from_cleaned is True:
      - Reads per-pose files in frontend/design-import/cleaned/
      - Or whole sheet in frontend/design-import/cleaned_sheet.png
      - Validates every imported frame and reports issues
      - Keeps automatic slicing for any frames not supplied
    If from_cleaned is False:
      - Runs production automatic slicing engine with hair pocket decontamination
    """
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(repo_root, "scripts", "sprites_config.json")
    output_base = os.path.join(repo_root, "frontend", "public", "pet")

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file missing: {config_path}")

    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    source_rel = config.get(
        "source_image", "frontend/design-import/character-sheet=2.png"
    )
    source_path = os.path.join(repo_root, source_rel)

    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Source character sheet missing: {source_path}")

    source_bgr = cv2.imread(source_path)
    if source_bgr is None:
        raise ValueError(f"Failed to read image at {source_path}")

    master_h, master_w = source_bgr.shape[:2]

    canvas_cfg = config.get("canvas", {})
    target_w = canvas_cfg.get("width", 200)
    target_h = canvas_cfg.get("height", 240)
    anchor_y = canvas_cfg.get("anchor_y", 216)
    scale = canvas_cfg.get("scale", 2.0)

    bg_rgb = config.get("background_color", [248, 240, 224])
    bg_bgr = (float(bg_rgb[2]), float(bg_rgb[1]), float(bg_rgb[0]))

    states = config.get("states", {})

    # Check for manual cleaned sources
    cleaned_dir = os.path.join(repo_root, "frontend", "design-import", "cleaned")
    cleaned_sheet_path = os.path.join(repo_root, "frontend", "design-import", "cleaned_sheet.png")

    cleaned_poses = {}
    unmatched_files = []

    if from_cleaned:
        print("[MODE] Manual Background Removal Import Mode (--from-cleaned)")
        # 1. Scan per-pose cleaned directory
        if os.path.exists(cleaned_dir):
            all_known_keys = set()
            for s_name, s_info in states.items():
                for f_info in s_info.get("frames", []):
                    all_known_keys.add(f"{s_name}__{f_info['name']}")

            for fname in os.listdir(cleaned_dir):
                if not fname.lower().endswith(".png"):
                    continue
                stem = fname[:-4]
                if stem.endswith("__4x"):
                    stem = stem[:-4]

                if stem in all_known_keys:
                    cleaned_poses[stem] = os.path.join(cleaned_dir, fname)
                else:
                    unmatched_files.append(fname)

            print(f"  Found {len(cleaned_poses)} matched per-pose cleaned files in {cleaned_dir}")
            if unmatched_files:
                print(f"  [WARN] {len(unmatched_files)} files match nothing in sprites_config.json:")
                for uf in unmatched_files:
                    print(f"    - {uf}")
        else:
            print(f"  Note: Per-pose cleaned directory not present: {cleaned_dir}")

        # 2. Check for whole sheet
        has_cleaned_sheet = os.path.exists(cleaned_sheet_path)
        if has_cleaned_sheet:
            print(f"  Found whole cleaned sheet at: {cleaned_sheet_path}")
        else:
            print("  Note: No cleaned_sheet.png found.")
    else:
        print(f"Processing {len(states)} animation states with automatic hair pocket decontamination...")

    manifest = {
        "source": source_rel,
        "canvas": {
            "width": target_w,
            "height": target_h,
            "anchor_y": anchor_y,
            "scale": scale,
        },
        "states": {},
    }

    all_frames_meta = []
    total_bytes = 0
    validation_reports = []
    imported_count = 0
    auto_count = 0

    # Load cleaned sheet if available
    cleaned_sheet_img = None
    sheet_sx = 1.0
    sheet_sy = 1.0
    if from_cleaned and os.path.exists(cleaned_sheet_path):
        cleaned_sheet_img = cv2.imread(cleaned_sheet_path, cv2.IMREAD_UNCHANGED)
        if cleaned_sheet_img is not None:
            c_sh, c_sw = cleaned_sheet_img.shape[:2]
            sheet_sx = c_sw / master_w
            sheet_sy = c_sh / master_h
            if cleaned_sheet_img.ndim != 3 or cleaned_sheet_img.shape[2] != 4:
                validation_reports.append(
                    "cleaned_sheet.png: ERROR - No alpha channel found (image is RGB/opaque)"
                )
                cleaned_sheet_img = None

    for state_name, state_data in states.items():
        state_dir = os.path.join(output_base, state_name)
        os.makedirs(state_dir, exist_ok=True)

        frames_info = state_data.get("frames", [])
        fps = state_data.get("fps", 4)
        loop = state_data.get("loop", True)

        exported_frame_names = []

        for idx, frame_meta in enumerate(frames_info):
            crop_box = tuple(frame_meta["crop"])
            frame_name = frame_meta.get("name", f"frame_{idx}")
            protect_boxes = frame_meta.get("protect", None)
            base_key = f"{state_name}__{frame_name}"

            # First, run automatic slicer to compute baseline ground offset & dimensions
            auto_rgba, auto_tight, ground_offset = slice_frame_and_decontaminate(
                source_bgr,
                crop_box,
                state_name=state_name,
                protect_boxes=protect_boxes,
                target_w=target_w,
                target_h=target_h,
                anchor_y=anchor_y,
                scale=scale,
                bg_bgr=bg_bgr,
            )

            frame_rgba = auto_rgba
            source_tag = ""
            is_cleaned = False

            # Check if cleaned frame is provided
            if from_cleaned:
                cleaned_crop = None
                crop_source_desc = ""

                # Priority 1: Per-pose cleaned file
                if base_key in cleaned_poses:
                    cpath = cleaned_poses[base_key]
                    cleaned_crop = cv2.imread(cpath, cv2.IMREAD_UNCHANGED)
                    crop_source_desc = f"cleaned/{os.path.basename(cpath)}"
                # Priority 2: Whole cleaned sheet
                elif cleaned_sheet_img is not None:
                    x1, y1, x2, y2 = crop_box
                    c_x1 = int(round(x1 * sheet_sx))
                    c_y1 = int(round(y1 * sheet_sy))
                    c_x2 = int(round(x2 * sheet_sx))
                    c_y2 = int(round(y2 * sheet_sy))
                    cleaned_crop = cleaned_sheet_img[
                        max(0, c_y1) : min(cleaned_sheet_img.shape[0], c_y2),
                        max(0, c_x1) : min(cleaned_sheet_img.shape[1], c_x2),
                    ].copy()
                    crop_source_desc = "cleaned_sheet.png"

                if cleaned_crop is not None:
                    # Validate
                    orig_crop = source_bgr[crop_box[1] : crop_box[3], crop_box[0] : crop_box[2]]
                    issues = validate_cleaned_frame(cleaned_crop, base_key, orig_crop, bg_bgr=bg_bgr)
                    for issue in issues:
                        validation_reports.append(f"{base_key} ({crop_source_desc}): {issue}")

                    # If alpha exists and is valid, normalize and use
                    if cleaned_crop.ndim == 3 and cleaned_crop.shape[2] == 4 and np.max(cleaned_crop[:, :, 3]) > 0:
                        target_scaled_h = int(auto_tight.shape[0] * scale)
                        norm_rgba, _tight = normalize_cleaned_sprite(
                            cleaned_crop,
                            target_scaled_h=target_scaled_h,
                            ground_offset_base=ground_offset,
                            target_w=target_w,
                            target_h=target_h,
                            anchor_y=anchor_y,
                            scale=scale,
                        )
                        frame_rgba = norm_rgba
                        is_cleaned = True
                        source_tag = " (Cleaned)"
                        imported_count += 1

            if not is_cleaned:
                auto_count += 1

            # Convert to PIL for saving and contact sheet
            frame_rgb = cv2.cvtColor(frame_rgba[:, :, :3], cv2.COLOR_BGR2RGB)
            alpha_chan = frame_rgba[:, :, 3]
            pil_img = Image.fromarray(np.dstack([frame_rgb, alpha_chan]), mode="RGBA")

            frame_filename = f"frame_{idx}.png"
            frame_out_path = os.path.join(state_dir, frame_filename)
            pil_img.save(frame_out_path, optimize=True)

            f_size = os.path.getsize(frame_out_path)
            total_bytes += f_size
            exported_frame_names.append(frame_filename)

            all_frames_meta.append(
                {
                    "state": state_name,
                    "index": idx,
                    "name": frame_name,
                    "source_tag": source_tag,
                    "pil_image": pil_img,
                    "crop": crop_box,
                    "size_bytes": f_size,
                }
            )

        manifest["states"][state_name] = {
            "fps": fps,
            "loop": loop,
            "frames": exported_frame_names,
            "description": state_data.get("description", ""),
        }
        print(f"  [OK] [{state_name}] -> {len(exported_frame_names)} frames (fps={fps}, loop={loop})")

    # Print Validation Summary
    if from_cleaned:
        print("\n" + "=" * 60)
        print("MANUAL IMPORT VALIDATION REPORT")
        print("=" * 60)
        print(f"Total frames processed: {imported_count + auto_count}")
        print(f"  - Imported from cleaned files: {imported_count}")
        print(f"  - Kept automatic slicer result: {auto_count}")
        if unmatched_files:
            print("\nUnmatched files in frontend/design-import/cleaned/:")
            for uf in unmatched_files:
                print(f"  - {uf}")
        if validation_reports:
            print(f"\nIssues detected during validation ({len(validation_reports)}):")
            for rpt in validation_reports:
                print(f"  * {rpt}")
        else:
            print("\nValidation Result: All imported frames passed validation cleanly.")
        print("=" * 60 + "\n")

    # Save manifest.json
    manifest_path = os.path.join(output_base, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    total_mb = total_bytes / (1024 * 1024)
    print(f"\nManifest saved to: {manifest_path}")
    print(f"Total exported assets footprint: {total_mb:.2f} MB (Budget: 10.0 MB)")

    # Select 3 hair-heavy frames for high-magnification inspection zoom
    zoom_targets = [
        ("idle", "idle_neutral"),
        ("idle", "idle_hair_move"),
        ("surprised", "surprised_head_tilt"),
    ]
    hair_zoom_frames = []
    for s_target, n_target in zoom_targets:
        for f in all_frames_meta:
            if f["state"] == s_target and f["name"] == n_target:
                hair_zoom_frames.append(f)
                break

    if len(hair_zoom_frames) < 3:
        hair_zoom_frames = all_frames_meta[:3]

    contact_sheet_path = os.path.join(output_base, "contact_sheet.png")
    generate_contact_sheet(all_frames_meta, hair_zoom_frames, contact_sheet_path)


def main():
    parser = argparse.ArgumentParser(
        description="NIKO Desktop Pet - Production Sprite Slicing & Edge Decontamination Engine"
    )
    parser.add_argument(
        "--export-raw",
        action="store_true",
        help="Export raw 1x and 4x crops with original cream background to exports/pet_raw/, with INDEX.png and zip",
    )
    parser.add_argument(
        "--from-cleaned",
        action="store_true",
        help="Import user-cleaned transparent sprites from frontend/design-import/cleaned/ or cleaned_sheet.png",
    )

    args = parser.parse_args()
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(repo_root, "scripts", "sprites_config.json")

    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    if args.export_raw:
        export_raw_crops(repo_root, config)
    elif args.from_cleaned:
        process_sprites(from_cleaned=True)
    else:
        process_sprites(from_cleaned=False)


if __name__ == "__main__":
    main()

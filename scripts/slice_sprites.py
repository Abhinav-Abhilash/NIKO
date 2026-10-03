#!/usr/bin/env python3
"""
NIKO Desktop Companion - Production Sprite Slicing & Edge Decontamination Engine
Reads configuration from scripts/sprites_config.json, slices character poses,
eliminates cream background including enclosed hair pockets, protects facial features
and white clothing, decontaminates edge pixels to prevent halos, removes detached specks,
normalizes to a common feet anchor, exports at 2x HiDPI resolution, and generates
a dual-background contact sheet with high-magnification hair inspection zooms.
"""

import json
import math
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import binary_dilation, label, find_objects


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
) -> tuple[np.ndarray, np.ndarray]:
    """
    Slices a single character pose from the source image, eliminates cream background
    including enclosed pockets between hair locks, removes detached specks,
    decontaminates edge pixels, and places the sprite on a normalized 2x canvas.
    Returns (normalized_canvas_bgra, tight_sprite_bgra).
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
    # Find enclosed pockets of near-cream color surrounded mostly by orange hair.
    # Never touch protected areas: eyes, white shirt collar, speech bubbles, icons.
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

    # 7x7 neighborhood hair ratio calculation
    hair_float = is_hair.astype(np.float32)
    ones = np.ones((ch, cw), dtype=np.float32)
    hair_sum = cv2.boxFilter(hair_float, -1, (7, 7), normalize=False)
    total_sum = cv2.boxFilter(ones, -1, (7, 7), normalize=False)
    hair_ratio = hair_sum / np.maximum(total_sum, 1.0)

    # Near-cream candidates not reached from perimeter
    is_near_cream = (bg_visited == 0) & (
        (dist < 40.0) | ((s_chan < 45) & (v_chan > 215) & ((r - b) < 35))
    )

    lbl_cream, num_cream = label(is_near_cream)
    objs_cream = find_objects(lbl_cream)
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
        # Make transparent ONLY when surrounded mostly by orange hair (>= 0.48 ratio)
        if np.mean(comp_hair_ratio) >= 0.48 or (
            np.sum(comp_hair_ratio >= 0.45) / len(comp_hair_ratio) >= 0.65
        ):
            pocket_mask[comp] = True

    # Mark enclosed hair pockets as background
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

            # Reject tiny dust (< 8 pixels)
            if area < 8:
                continue

            # Reject top border lines / category banner fragments
            if top <= 2 and (w > 18 or h <= 4):
                continue
            if top < main_top - 30 and (w > 20 and h <= 5):
                continue

            # Reject bottom label fragments / ground smudges
            if top >= main_bottom - 3:
                continue

            # If explicitly protected, always keep
            if np.any(is_protected[comp]):
                clean_fg[comp] = 1
                continue

            min_dist = float(np.min(dist_to_body[comp]))
            comp_color = crop[comp].mean(axis=0)  # BGR
            is_orange_speck = (comp_color[2] > 180 and comp_color[1] > 80 and comp_color[2] > comp_color[0] + 30)

            # In idle state: pure character standing, zero external accessories
            if state_name == "idle":
                # Remove all detached specks in idle poses
                if min_dist <= 1.5:
                    clean_fg[comp] = 1
                continue

            # In other states: keep accessories (thought bubble, zzz, sweat drops, clouds, desks)
            if min_dist <= 1.5:
                clean_fg[comp] = 1
            elif top < main_top and not is_orange_speck:
                clean_fg[comp] = 1
            elif area >= 16 and not is_orange_speck:
                clean_fg[comp] = 1

        fg_mask = clean_fg

    # 4. Find tight bounding box of character
    fg_y, fg_x = np.where(fg_mask == 1)
    if len(fg_y) == 0:
        empty = np.zeros((target_h, target_w, 4), dtype=np.uint8)
        return empty, empty

    min_y, max_y = int(fg_y.min()), int(fg_y.max())
    min_x, max_x = int(fg_x.min()), int(fg_x.max())
    ground_offset = (ch - 1) - max_y

    # 5. Boundary-Band Edge Decontamination
    # Core interior remains 100% solid. Only the 1-2px outer boundary is unmixed.
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

    # Un-mix background color from edge pixels: F = (C - (1-a)*B) / a
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

    # Clamp bounds safely
    if paste_y < 0:
        paste_y = 0
    if paste_x < 0:
        paste_x = 0
    actual_h = min(scaled_h, target_h - paste_y)
    actual_w = min(scaled_w, target_w - paste_x)

    canvas[paste_y : paste_y + actual_h, paste_x : paste_x + actual_w] = (
        scaled_sprite[:actual_h, :actual_w]
    )
    return canvas, tight_sprite


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

    # Dual-background card dimensions
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
        # State group bar
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

            # Card border
            draw.rectangle(
                [x, y, x + card_w, y + card_h],
                fill=(24, 28, 36, 255),
                outline=(48, 56, 72, 255),
            )

            # Left half: Dark Background (#181C24)
            draw.rectangle(
                [x + 2, y + 2, x + 2 + sub_w, y + 2 + sub_h],
                fill=(24, 28, 36, 255),
            )
            # Right half: Light Background (#F5F7FA)
            draw.rectangle(
                [x + 4 + sub_w, y + 2, x + card_w - 2, y + 2 + sub_h],
                fill=(245, 247, 250, 255),
            )

            # Ground lines on both halves (90% height)
            ground_y = y + 2 + int(sub_h * 0.90)
            draw.line([x + 6, ground_y, x + sub_w - 2, ground_y], fill=(60, 70, 88, 255), width=1)
            draw.line([x + 8 + sub_w, ground_y, x + card_w - 6, ground_y], fill=(205, 212, 222, 255), width=1)

            # Resize sprite thumbnail
            sprite_img = f["pil_image"]
            thumb_w = sub_w - 8
            thumb_h = int(thumb_w * (240 / 200))
            thumb = sprite_img.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)

            # Paste onto Dark half
            sheet.paste(thumb, (x + 6, y + 4), thumb)
            # Paste onto Light half
            sheet.paste(thumb, (x + 8 + sub_w, y + 4), thumb)

            # Caption label
            caption = f"#{f['index']}: {f['name']}"
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

        # Split into Dark and Light sides
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


def main():
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

    print(f"Loading source character sheet (read-only): {source_path}")
    source_bgr = cv2.imread(source_path)
    if source_bgr is None:
        raise ValueError(f"Failed to read image at {source_path}")

    canvas_cfg = config.get("canvas", {})
    target_w = canvas_cfg.get("width", 200)
    target_h = canvas_cfg.get("height", 240)
    anchor_y = canvas_cfg.get("anchor_y", 216)
    scale = canvas_cfg.get("scale", 2.0)

    # Cream paper background in BGR: B=228, G=244, R=250
    bg_rgb = config.get("background_color", [248, 240, 224])
    bg_bgr = (float(bg_rgb[2]), float(bg_rgb[1]), float(bg_rgb[0]))

    states = config.get("states", {})
    print(f"Processing {len(states)} animation states with hair pocket decontamination...")

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

            # Slice, remove enclosed hair pockets, decontaminate edges, filter specks
            frame_rgba, _tight_rgba = slice_frame_and_decontaminate(
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

            # Convert to PIL for saving and contact sheet
            frame_rgb = cv2.cvtColor(frame_rgba[:, :, :3], cv2.COLOR_BGR2RGB)
            alpha_chan = frame_rgba[:, :, 3]
            pil_img = Image.fromarray(
                np.dstack([frame_rgb, alpha_chan]), mode="RGBA"
            )

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

    # Generate ONE comprehensive contact sheet image with light and dark side-by-side
    contact_sheet_path = os.path.join(output_base, "contact_sheet.png")
    generate_contact_sheet(all_frames_meta, hair_zoom_frames, contact_sheet_path)


if __name__ == "__main__":
    main()

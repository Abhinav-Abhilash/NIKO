#!/usr/bin/env python3
"""
NIKO Desktop Companion - Production Sprite Slicing & Edge Decontamination Engine
Reads configuration from scripts/sprites_config.json, slices character poses,
removes cream background with boundary-band edge color decontamination, normalizes to a common
feet anchor, exports at 2x HiDPI resolution, and generates manifest & contact sheet.
"""

import json
import math
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw


def slice_frame_and_decontaminate(
    img_bgr: np.ndarray,
    crop_box: tuple[int, int, int, int],
    target_w: int = 200,
    target_h: int = 240,
    anchor_y: int = 216,
    scale: float = 2.0,
    bg_bgr: tuple[float, float, float] = (228.0, 244.0, 250.0),
) -> np.ndarray:
    """
    Slices a single character pose from the source image, eliminates cream background
    and text labels, decontaminates edge pixels to prevent cream halos on dark backgrounds,
    and places the sprite on a normalized 2x canvas with consistent feet anchoring.
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

    fg_mask = (bg_visited == 0).astype(np.uint8)

    # 3. Connected component analysis to isolate character and discard artifacts
    num_labels, labels, stats, _centroids = cv2.connectedComponentsWithStats(
        fg_mask, connectivity=8
    )
    if num_labels > 1:
        largest_label = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        clean_fg = np.zeros_like(fg_mask)
        main_stat = stats[largest_label]
        main_top = main_stat[cv2.CC_STAT_TOP]
        main_bottom = main_top + main_stat[cv2.CC_STAT_HEIGHT]
        main_left = main_stat[cv2.CC_STAT_LEFT]
        main_right = main_left + main_stat[cv2.CC_STAT_WIDTH]

        for l_idx in range(1, num_labels):
            area = stats[l_idx, cv2.CC_STAT_AREA]
            top = stats[l_idx, cv2.CC_STAT_TOP]
            left = stats[l_idx, cv2.CC_STAT_LEFT]
            right = left + stats[l_idx, cv2.CC_STAT_WIDTH]
            w = stats[l_idx, cv2.CC_STAT_WIDTH]
            h = stats[l_idx, cv2.CC_STAT_HEIGHT]

            if l_idx == largest_label:
                clean_fg[labels == l_idx] = 1
                continue

            # Reject tiny dust (< 8 pixels)
            if area < 8:
                continue

            # Reject top border lines / category banner fragments (thin horizontal bands near top)
            if top <= 2 and (w > 18 or h <= 4):
                continue
            if top < main_top - 30 and (w > 20 and h <= 5):
                continue

            # Reject bottom label fragments / ground smudges (below feet)
            if top >= main_bottom - 3:
                continue

            # Reject disconnected transition arrows / neighbor characters on far left/right
            if area < 150 and (right < main_left - 12 or left > main_right + 12):
                continue

            # Keep accessories/expressions (thought bubble, zzz, notes, butterfly) or hair curls
            clean_fg[labels == l_idx] = 1

        fg_mask = clean_fg

    # 4. Find tight bounding box of character
    fg_y, fg_x = np.where(fg_mask == 1)
    if len(fg_y) == 0:
        return np.zeros((target_h, target_w, 4), dtype=np.uint8)

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

    # 6. Extract tight sprite and upscale 2x for sharp HiDPI rendering
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
    return canvas


def generate_contact_sheet(frames_meta: list[dict], output_path: str):
    """
    Renders ONE comprehensive contact sheet containing all frames grouped by state
    with state labels, frame indices, and frame names on a sleek dark canvas.
    """
    by_state: dict[str, list[dict]] = {}
    for f in frames_meta:
        by_state.setdefault(f["state"], []).append(f)

    cell_w = 140
    cell_h = 175
    header_h = 32
    padding = 14
    cols = 8

    total_rows = 0
    for state_frames in by_state.values():
        total_rows += math.ceil(len(state_frames) / cols)

    sheet_w = cols * (cell_w + padding) + padding * 2
    sheet_h = (
        len(by_state) * (header_h + padding)
        + total_rows * (cell_h + padding)
        + padding * 4
        + 60
    )

    # Dark studio background to clearly highlight edge decontamination and transparency
    sheet = Image.new("RGBA", (sheet_w, sheet_h), (24, 28, 36, 255))
    draw = ImageDraw.Draw(sheet)

    # Header banner
    draw.rectangle([0, 0, sheet_w, 54], fill=(225, 109, 39, 255))
    draw.text(
        (padding + 6, 16),
        "NIKO Companion Pet - 2x Decontaminated Sprite Sheet Contact",
        fill=(255, 255, 255, 255),
    )

    curr_y = 66
    for state, state_frames in by_state.items():
        # State group bar
        draw.rectangle(
            [padding, curr_y, sheet_w - padding, curr_y + header_h],
            fill=(36, 44, 58, 255),
        )
        draw.text(
            (padding + 12, curr_y + 8),
            f"STATE: {state.upper()} ({len(state_frames)} frames)",
            fill=(245, 166, 35, 255),
        )
        curr_y += header_h + padding

        for idx, f in enumerate(state_frames):
            row_idx = idx // cols
            col_idx = idx % cols
            x = padding + col_idx * (cell_w + padding)
            y = curr_y + row_idx * (cell_h + padding)

            # Cell card
            draw.rectangle(
                [x, y, x + cell_w, y + cell_h],
                fill=(18, 22, 28, 255),
                outline=(48, 56, 72, 255),
            )

            # Ground line marker in cell (normalized anchor)
            ground_y = y + int(cell_h * 0.90)
            draw.line(
                [x + 8, ground_y, x + cell_w - 8, ground_y],
                fill=(65, 75, 95, 255),
                width=1,
            )

            # Paste thumbnail
            sprite_img = f["pil_image"]
            thumb = sprite_img.resize(
                (cell_w - 16, int((cell_w - 16) * (240 / 200))),
                Image.Resampling.LANCZOS,
            )
            sheet.paste(thumb, (x + 8, y + 6), thumb)

            # Caption label
            caption = f"#{f['index']}: {f['name']}"
            draw.text(
                (x + 8, y + cell_h - 18),
                caption[:17],
                fill=(170, 180, 195, 255),
            )

        rows = math.ceil(len(state_frames) / cols)
        curr_y += rows * (cell_h + padding) + padding

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
    print(f"Processing {len(states)} animation states...")

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

            # Slice, remove cream bg, decontaminate edges, anchor normalize
            frame_rgba = slice_frame_and_decontaminate(
                source_bgr,
                crop_box,
                target_w=target_w,
                target_h=target_h,
                anchor_y=anchor_y,
                scale=scale,
                bg_bgr=bg_bgr,
            )

            # Convert to PIL for saving and contact sheet
            # frame_rgba is BGRA from OpenCV
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

    # Generate ONE comprehensive contact sheet image
    contact_sheet_path = os.path.join(output_base, "contact_sheet.png")
    generate_contact_sheet(all_frames_meta, contact_sheet_path)


if __name__ == "__main__":
    main()

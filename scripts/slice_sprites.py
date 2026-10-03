#!/usr/bin/env python3
"""
NIKO Desktop Companion - Sprite Slicing & Edge Decontamination Engine
Reads configuration from scripts/sprites_config.json, slices character poses,
removes cream background with edge color decontamination, normalizes to a common
feet anchor, exports at 2x HiDPI resolution, and generates manifest & contact sheet.
"""

import json
import math
import os

from PIL import Image, ImageDraw


def color_distance(c1, c2):
    return math.sqrt((c1[0] - c2[0])**2 + (c1[1] - c2[1])**2 + (c1[2] - c2[2])**2)

def decontaminate_and_remove_bg(crop_img, bg_rgb=(248.0, 240.0, 224.0)):
    """
    Flood fills from the bounding borders to isolate background cream pixels.
    Applies color un-mixing (decontamination) on transition edges to remove cream halos
    from soft hair fringes without stripping internal skin or shirt tones.
    """
    img = crop_img.convert('RGB')
    w, h = img.size
    pix = img.load()

    visited = bytearray(w * h)
    queue = []

    # Seed flood fill from the outer perimeter
    for x in range(w):
        queue.append((x, 0))
        visited[x] = 1
        queue.append((x, h - 1))
        visited[(h - 1) * w + x] = 1
    for y in range(h):
        queue.append((0, y))
        visited[y * w] = 1
        queue.append((w - 1, y))
        visited[y * w + (w - 1)] = 1

    head = 0
    bg_thresh = 30.0

    while head < len(queue):
        x, y = queue[head]
        head += 1
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h:
                idx = ny * w + nx
                if not visited[idx]:
                    c = pix[nx, ny]
                    dist = color_distance(c, bg_rgb)
                    # Cream background criteria
                    if dist < bg_thresh or (c[0] > 234 and c[1] > 224 and c[2] > 206 and abs(c[0] - c[1]) < 18):
                        visited[idx] = 1
                        queue.append((nx, ny))

    out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    out_pix = out.load()

    for y in range(h):
        for x in range(w):
            idx = y * w + x
            if visited[idx]:
                out_pix[x, y] = (0, 0, 0, 0)
            else:
                c = pix[x, y]
                dist = color_distance(c, bg_rgb)
                if dist < 52.0:
                    # Soft edge transition
                    alpha = max(0.0, min(1.0, (dist - 12.0) / 40.0))
                    if alpha < 0.08:
                        out_pix[x, y] = (0, 0, 0, 0)
                    else:
                        # Decontaminate edge: un-mix cream background
                        unmix_r = int(max(0, min(255, (c[0] - (1.0 - alpha) * bg_rgb[0]) / alpha)))
                        unmix_g = int(max(0, min(255, (c[1] - (1.0 - alpha) * bg_rgb[1]) / alpha)))
                        unmix_b = int(max(0, min(255, (c[2] - (1.0 - alpha) * bg_rgb[2]) / alpha)))
                        out_pix[x, y] = (unmix_r, unmix_g, unmix_b, int(alpha * 255))
                else:
                    out_pix[x, y] = (c[0], c[1], c[2], 255)

    return out

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(root_dir, 'scripts', 'sprites_config.json')
    output_base = os.path.join(root_dir, 'frontend', 'public', 'pet')

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config not found at {config_path}")

    with open(config_path, encoding='utf-8') as f:
        config = json.load(f)

    source_path = os.path.join(root_dir, config.get('source_image', 'frontend/design-import/character-sheet=2.png'))
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Source character sheet not found at {source_path}")

    print(f"Loading source character sheet: {source_path}")
    source_img = Image.open(source_path)

    bg_rgb = tuple(config.get('background_color', [248, 240, 224]))
    canvas_cfg = config.get('canvas', {})
    canvas_w = canvas_cfg.get('width', 200)
    canvas_h = canvas_cfg.get('height', 240)
    anchor_y = canvas_cfg.get('anchor_y', 224)
    export_scale = canvas_cfg.get('scale', 2.0)

    # HiDPI target dimensions
    target_w = int(canvas_w * export_scale)
    target_h = int(canvas_h * export_scale)
    target_anchor_y = int(anchor_y * export_scale)

    os.makedirs(output_base, exist_ok=True)

    manifest = {
        "source": config.get('source_image'),
        "canvas": {
            "width": target_w,
            "height": target_h,
            "anchor_y": target_anchor_y,
            "scale": export_scale
        },
        "states": {}
    }

    all_processed_frames = [] # For contact sheet: list of (state, frame_idx, frame_name, image)
    total_exported_bytes = 0

    states = config.get('states', {})
    print(f"\nProcessing {len(states)} states...")

    for state_name, state_data in states.items():
        state_dir = os.path.join(output_base, state_name)
        os.makedirs(state_dir, exist_ok=True)

        frames_info = state_data.get('frames', [])
        fps = state_data.get('fps', 4)
        loop = state_data.get('loop', True)

        exported_frame_names = []

        for idx, frame_meta in enumerate(frames_info):
            crop_box = tuple(frame_meta['crop'])
            frame_name = frame_meta.get('name', f'frame_{idx}')

            # 1. Crop raw from source (without modifying original)
            raw_crop = source_img.crop(crop_box)

            # 2. Decontaminate edges and remove cream background
            clean_rgba = decontaminate_and_remove_bg(raw_crop, bg_rgb)

            # 3. Trim transparent boundaries
            bbox = clean_rgba.getbbox()
            trimmed = clean_rgba.crop(bbox) if bbox else clean_rgba

            # 4. Scale at 2x for sharp rendering
            scaled_w = int(trimmed.width * export_scale)
            scaled_h = int(trimmed.height * export_scale)
            scaled_sprite = trimmed.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)

            # 5. Feet Anchor Normalization
            # Align bottom of sprite to target_anchor_y, center horizontally
            frame_canvas = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))
            paste_x = int((target_w - scaled_w) / 2)
            paste_y = target_anchor_y - scaled_h

            # Safety bounds clamping
            if paste_y < 0:
                # If sprite is slightly taller, scale down proportionally
                oversize_ratio = target_anchor_y / float(scaled_h)
                new_w = int(scaled_w * oversize_ratio)
                new_h = int(scaled_h * oversize_ratio)
                scaled_sprite = scaled_sprite.resize((new_w, new_h), Image.Resampling.LANCZOS)
                paste_x = int((target_w - new_w) / 2)
                paste_y = target_anchor_y - new_h

            frame_canvas.paste(scaled_sprite, (paste_x, paste_y), scaled_sprite)

            # 6. Save individual frame
            frame_filename = f"frame_{idx}.png"
            frame_out_path = os.path.join(state_dir, frame_filename)
            frame_canvas.save(frame_out_path, optimize=True)

            file_size = os.path.getsize(frame_out_path)
            total_exported_bytes += file_size
            exported_frame_names.append(frame_filename)

            all_processed_frames.append({
                "state": state_name,
                "index": idx,
                "name": frame_name,
                "image": frame_canvas,
                "size_bytes": file_size,
                "crop": crop_box
            })

        manifest["states"][state_name] = {
            "fps": fps,
            "loop": loop,
            "frames": exported_frame_names,
            "description": state_data.get('description', '')
        }
        print(f"  [OK] [{state_name}] -> {len(exported_frame_names)} frames (fps={fps}, loop={loop})")

    # Save manifest.json
    manifest_path = os.path.join(output_base, 'manifest.json')
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)

    total_mb = total_exported_bytes / (1024 * 1024)
    print(f"\nManifest saved to: {manifest_path}")
    print(f"Total sprite asset footprint: {total_mb:.2f} MB (Budget: 10.0 MB)")

    # 7. Generate Comprehensive Contact Sheet Image
    print("\nGenerating contact sheet image...")
    generate_contact_sheet(all_processed_frames, output_base)

def generate_contact_sheet(frames, output_dir):
    """
    Renders ONE comprehensive contact sheet containing all frames grouped by state
    with state labels, frame indices, and frame names.
    """
    # Group frames by state
    by_state = {}
    for f in frames:
        by_state.setdefault(f["state"], []).append(f)

    # Layout parameters
    cell_w = 150
    cell_h = 180
    header_h = 36
    padding = 16
    cols = 8 # max frames per row

    # Calculate total height
    total_rows = 0
    for _state, state_frames in by_state.items():
        rows_for_state = math.ceil(len(state_frames) / cols)
        total_rows += rows_for_state

    sheet_w = cols * (cell_w + padding) + padding * 2
    sheet_h = len(by_state) * (header_h + padding) + total_rows * (cell_h + padding) + padding * 3

    contact_sheet = Image.new('RGBA', (sheet_w, sheet_h), (250, 248, 245, 255)) # Warm cream paper backdrop
    draw = ImageDraw.Draw(contact_sheet)

    # Title header
    draw.rectangle([0, 0, sheet_w, 60], fill=(225, 112, 45, 255))
    draw.text((padding, 18), "NIKO Companion Pet - Sprite Animation Contact Sheet", fill=(255, 255, 255, 255))

    curr_y = 70

    for state, state_frames in by_state.items():
        # State header bar
        draw.rectangle([padding, curr_y, sheet_w - padding, curr_y + header_h], fill=(235, 230, 222, 255))
        draw.text(
            (padding + 12, curr_y + 10),
            f"STATE: {state.upper()} ({len(state_frames)} frames)",
            fill=(40, 30, 20, 255)
        )
        curr_y += header_h + padding

        for idx, f in enumerate(state_frames):
            row_idx = idx // cols
            col_idx = idx % cols

            x = padding + col_idx * (cell_w + padding)
            y = curr_y + row_idx * (cell_h + padding)

            # Thumbnail background tile with subtle border
            draw.rectangle([x, y, x + cell_w, y + cell_h], fill=(255, 255, 255, 255), outline=(220, 215, 205, 255))

            # Ground line marker
            draw.line([x + 10, y + cell_h - 25, x + cell_w - 10, y + cell_h - 25], fill=(240, 220, 210, 255), width=1)

            # Resize frame to fit thumbnail
            thumb = f["image"].resize((cell_w - 16, cell_h - 36), Image.Resampling.LANCZOS)
            contact_sheet.paste(thumb, (x + 8, y + 4), thumb)

            # Frame label
            caption = f"#{f['index']}: {f['name']}"
            draw.text((x + 8, y + cell_h - 20), caption[:18], fill=(90, 80, 70, 255))

        rows_for_state = math.ceil(len(state_frames) / cols)
        curr_y += rows_for_state * (cell_h + padding) + padding

    out_path = os.path.join(output_dir, 'contact_sheet.png')
    contact_sheet.save(out_path, optimize=True)
    print(f"Contact sheet saved to: {out_path} ({contact_sheet.size[0]}x{contact_sheet.size[1]})")

if __name__ == '__main__':
    main()

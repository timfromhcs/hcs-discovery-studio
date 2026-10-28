"""Generate crisp 1280x640 social preview image for GitHub repository and OpenGraph."""

from __future__ import annotations

import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def create_social_preview(output_path: Path) -> None:
    width = 1280
    height = 640

    # 1. Background gradient (dark navy slate)
    img = Image.new("RGBA", (width, height), (8, 14, 22, 255))
    draw = ImageDraw.Draw(img)

    # Subtle radial glow behind the mark
    center_x, center_y = 640, 220
    for r in range(350, 0, -5):
        alpha = int(45 * (1.0 - (r / 350.0) ** 1.5))
        draw.ellipse(
            [center_x - r, center_y - r, center_x + r, center_y + r],
            fill=(26, 45, 70, alpha),
        )

    # Top border accent line
    for x in range(width):
        t = x / width
        # Interpolate between #3dd6c3 (61, 214, 195) and #6aa9ff (106, 169, 255)
        red = int(61 * (1 - t) + 106 * t)
        green = int(214 * (1 - t) + 169 * t)
        blue = int(195 * (1 - t) + 255 * t)
        draw.line([(x, 0), (x, 3)], fill=(red, green, blue, 255))

    # 2. Draw Vector Discovery Mark at (center_x, 150)
    mark_cx, mark_cy = 640, 155
    hex_radius = 65

    # Draw Hexagon bonds
    points = []
    for i in range(6):
        angle = math.radians(60 * i - 30)
        px = mark_cx + hex_radius * math.cos(angle)
        py = mark_cy + hex_radius * math.sin(angle)
        points.append((px, py))

    # Outer hexagon
    draw.polygon(points, outline=(61, 214, 195, 255), width=5)

    # Radial spokes to inner core
    for px, py in points:
        draw.line([(mark_cx, mark_cy), (px, py)], fill=(61, 214, 195, 140), width=3)

    # Vertices
    for px, py in points:
        r_node = 8
        draw.ellipse([px - r_node, py - r_node, px + r_node, py + r_node], fill=(61, 214, 195, 255))

    # Central coordination circle
    core_r = 20
    draw.ellipse(
        [mark_cx - core_r, mark_cy - core_r, mark_cx + core_r, mark_cy + core_r],
        fill=(11, 20, 32, 255),
        outline=(106, 169, 255, 255),
        width=4,
    )
    dot_r = 8
    draw.ellipse([mark_cx - dot_r, mark_cy - dot_r, mark_cx + dot_r, mark_cy + dot_r], fill=(106, 169, 255, 255))

    # 3. Load Fonts
    windir = os.environ.get("WINDIR", "C:\\Windows")
    font_bold_path = os.path.join(windir, "Fonts", "segoeuib.ttf")
    font_reg_path = os.path.join(windir, "Fonts", "segoeui.ttf")

    if os.path.exists(font_bold_path):
        font_title = ImageFont.truetype(font_bold_path, 48)
        font_tagline = ImageFont.truetype(font_reg_path, 23)
        font_pill = ImageFont.truetype(font_bold_path, 15)
        font_brand = ImageFont.truetype(font_bold_path, 18)
    else:
        font_title = ImageFont.load_default()
        font_tagline = ImageFont.load_default()
        font_pill = ImageFont.load_default()
        font_brand = ImageFont.load_default()

    # 4. Text - Title
    title = "HCS Discovery Studio"
    bbox_title = draw.textbbox((0, 0), title, font=font_title)
    tw = bbox_title[2] - bbox_title[0]
    draw.text(((width - tw) / 2, 260), title, font=font_title, fill=(245, 250, 255, 255))

    # Text - Tagline
    tagline = "Local-first, reproducible drug discovery & virtual screening workbench"
    bbox_tag = draw.textbbox((0, 0), tagline, font=font_tagline)
    tag_w = bbox_tag[2] - bbox_tag[0]
    draw.text(((width - tag_w) / 2, 325), tagline, font=font_tagline, fill=(160, 182, 208, 255))

    # 5. Feature Badges / Pills
    pills = [
        "AutoDock Vina CPU Docking",
        "Delaney ESOL & CNS MPO",
        "DAG Multi-Branch Workflows",
        "PubChem & ChEMBL Connectors",
        "Safe Research Assistant",
    ]

    pill_y = 390
    pill_widths = []
    for p in pills:
        bb = draw.textbbox((0, 0), p, font=font_pill)
        pill_widths.append(bb[2] - bb[0] + 32)

    spacing = 14
    total_pills_w = sum(pill_widths) + spacing * (len(pills) - 1)
    start_x = (width - total_pills_w) / 2

    curr_x = start_x
    for i, p in enumerate(pills):
        pw = pill_widths[i]
        # Draw pill container
        draw.rounded_rectangle(
            [curr_x, pill_y, curr_x + pw, pill_y + 36],
            radius=18,
            fill=(18, 30, 48, 255),
            outline=(45, 75, 115, 255),
            width=1,
        )
        # Small accent indicator dot
        draw.ellipse([curr_x + 12, pill_y + 14, curr_x + 20, pill_y + 22], fill=(61, 214, 195, 255))
        # Text
        draw.text((curr_x + 26, pill_y + 8), p, font=font_pill, fill=(225, 238, 252, 255))
        curr_x += pw + spacing

    # 6. Bottom Brand Banner
    brand_line = "Open science. Reproducible discovery. Made with ❤️ by hcsmedia."
    bbox_brand = draw.textbbox((0, 0), brand_line, font=font_brand)
    bw = bbox_brand[2] - bbox_brand[0]

    # Bottom container bar
    draw.rectangle([0, 560, width, 640], fill=(6, 10, 16, 255))
    draw.line([(0, 560), (width, 560)], fill=(24, 38, 58, 255), width=1)
    draw.text(((width - bw) / 2, 585), brand_line, font=font_brand, fill=(130, 155, 185, 255))

    # Save PNG
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Convert RGBA to RGB for standard image viewing without transparency anomalies
    rgb_img = Image.new("RGB", (width, height), (8, 14, 22))
    rgb_img.paste(img, mask=img.split()[3])
    rgb_img.save(output_path, "PNG", optimize=True)
    print(f"Generated {output_path} ({os.path.getsize(output_path)} bytes)")


if __name__ == "__main__":
    out = Path("docs/assets/branding/social-preview.png")
    create_social_preview(out)

#!/usr/bin/env python3
"""Generate the tracker.app icon: a blue pawn on a rounded pastel-glass tile
(light blue → soft pink gradient, white glass sheen, pink accent dot).
Writes PNGs in several sizes into scripts/icons/."""

import os
from PIL import Image, ImageDraw

SIZES = [512, 256, 128, 64, 48, 32, 16]
BG_TOP = (157, 198, 246)      # light blue
BG_BOTTOM = (246, 186, 213)   # soft pink
PAWN = (37, 99, 235)          # blue
PAWN_HI = (147, 197, 253)     # light blue highlight
PINK_ACCENT = (236, 72, 153)  # pink
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "icons")


def vertical_gradient(size):
    image = Image.new("RGB", (size, size))
    draw = ImageDraw.Draw(image)
    for y in range(size):
        t = y / size
        color = tuple(round(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM))
        draw.line([(0, y), (size, y)], fill=color)
    return image


def pawn_geometry(size):
    s = size / 512.0

    def scale(points):
        return [(x * s, y * s) for x, y in points]

    pieces = []
    pieces.append(("ellipse", scale([(136, 372), (376, 436)]), PAWN))
    pieces.append(("ellipse", scale([(196, 205), (316, 258)]), PAWN))
    pieces.append(("polygon", scale([(205, 252), (307, 252), (336, 352), (176, 352)]), PAWN))
    pieces.append(("ellipse", scale([(196, 92), (316, 212)]), PAWN))
    pieces.append(("ellipse", scale([(224, 118), (272, 166)]), PAWN_HI))
    return pieces


def glass_sheen(size):
    """A semi-transparent white swoosh across the top for the frosted look."""
    sheen = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(sheen)
    s = size / 512.0
    draw.ellipse([int(-60 * s), int(-40 * s), int(330 * s), int(160 * s)],
                 fill=(255, 255, 255, 70))
    draw.ellipse([int(-90 * s), int(-80 * s), int(560 * s), int(110 * s)],
                 fill=(255, 255, 255, 40))
    return sheen


def draw_icon(size):
    image = vertical_gradient(size)
    mask = Image.new("L", (size, size), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.rounded_rectangle([0, 0, size, size], radius=round(size * 0.22), fill=255)

    out = Image.new("RGB", (size, size), BG_BOTTOM)
    out.paste(image, (0, 0), mask)

    sheen = glass_sheen(size)
    out_rgba = out.convert("RGBA")
    out_rgba = Image.alpha_composite(out_rgba, sheen)
    out = out_rgba.convert("RGB")
    out.paste(image, (0, 0), mask)

    draw = ImageDraw.Draw(out)
    for kind, points, fill in pawn_geometry(size):
        if kind == "ellipse":
            draw.ellipse(points, fill=fill)
        else:
            draw.polygon(points, fill=fill)

    s = size / 512.0
    r = int(26 * s)
    cx, cy = 404 * s, 396 * s
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=PINK_ACCENT)
    return out


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    images = {}
    for size in SIZES:
        images[size] = draw_icon(size)
        path = os.path.join(OUT_DIR, f"tracker-{size}.png")
        images[size].save(path)
        print(f"wrote {path}")

    ico_path = os.path.join(OUT_DIR, "tracker.ico")
    images[512].save(
        ico_path,
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"wrote {ico_path}")


if __name__ == "__main__":
    main()

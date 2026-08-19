#!/usr/bin/env python3
"""Generate the tracker.app icon: a blue pawn on a rounded pastel-glass tile
(light blue → soft pink gradient, white glass sheen, pink accent dot).

The icon is drawn once at 4x master resolution (2048px) for supersampling and
downscaled with LANCZOS to every target size, giving smooth anti-aliased
edges. Writes PNGs in several sizes into scripts/icons/."""

import os
from PIL import Image, ImageDraw

HIGH = 2048                      # master canvas (4x the 512 source)
SIZES = [512, 256, 128, 64, 48, 40, 32, 16]
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


def draw_master():
    """Draw the icon at HIGH resolution (supersampled, no aliasing)."""
    image = vertical_gradient(HIGH)
    mask = Image.new("L", (HIGH, HIGH), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.rounded_rectangle([0, 0, HIGH, HIGH], radius=round(HIGH * 0.22), fill=255)

    out = Image.new("RGB", (HIGH, HIGH), BG_BOTTOM)
    out.paste(image, (0, 0), mask)

    sheen = glass_sheen(HIGH)
    out_rgba = out.convert("RGBA")
    out_rgba = Image.alpha_composite(out_rgba, sheen)
    out = out_rgba.convert("RGB")
    out.paste(image, (0, 0), mask)

    draw = ImageDraw.Draw(out)
    for kind, points, fill in pawn_geometry(HIGH):
        if kind == "ellipse":
            draw.ellipse(points, fill=fill)
        else:
            draw.polygon(points, fill=fill)

    s = HIGH / 512.0
    r = int(26 * s)
    cx, cy = 404 * s, 396 * s
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=PINK_ACCENT)
    return out


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    master = draw_master()
    for size in SIZES:
        if size == HIGH:
            image = master
        else:
            image = master.resize((size, size), Image.LANCZOS)
        path = os.path.join(OUT_DIR, f"tracker-{size}.png")
        image.save(path)
        print(f"wrote {path}")

    ico_path = os.path.join(OUT_DIR, "tracker.ico")
    ico_images = []
    for size in (16, 32, 48, 64, 128, 256):
        ico_images.append(master.resize((size, size), Image.LANCZOS))
    ico_images[0].save(
        ico_path,
        format="ICO",
        append_images=ico_images[1:],
        sizes=[(s, s) for s in (16, 32, 48, 64, 128, 256)],
    )
    print(f"wrote {ico_path}")


if __name__ == "__main__":
    main()

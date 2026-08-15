#!/usr/bin/env python3
"""Generate the tracker.app icon: a white chess pawn on a rounded navy square.
Writes PNGs in several sizes into scripts/icons/."""

import os
from PIL import Image, ImageDraw

SIZES = [512, 256, 128, 64, 48, 32, 16]
BG_TOP = (37, 99, 235)
BG_BOTTOM = (23, 37, 84)
PAWN = (248, 250, 252)
PAWN_SHADOW = (203, 213, 225)
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

    # base plate (bottom ellipse)
    pieces.append(("ellipse", scale([(136, 372), (376, 436)]), PAWN))
    # collar
    pieces.append(("ellipse", scale([(196, 205), (316, 258)]), PAWN))
    # body (trapezoid)
    pieces.append(("polygon", scale([(205, 252), (307, 252), (336, 352), (176, 352)]), PAWN))
    # head
    pieces.append(("ellipse", scale([(196, 92), (316, 212)]), PAWN))
    # highlight on head
    pieces.append(("ellipse", scale([(224, 118), (272, 166)]), PAWN_SHADOW))
    return pieces


def draw_icon(size):
    image = vertical_gradient(size)
    mask = Image.new("L", (size, size), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.rounded_rectangle([0, 0, size, size], radius=round(size * 0.22), fill=255)
    out = Image.new("RGB", (size, size), BG_BOTTOM)
    out.paste(image, (0, 0), mask)
    draw = ImageDraw.Draw(out)

    for kind, points, fill in pawn_geometry(size):
        if kind == "ellipse":
            draw.ellipse(points, fill=fill)
        else:
            draw.polygon(points, fill=fill)
    return out


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for size in SIZES:
        path = os.path.join(OUT_DIR, f"tracker-{size}.png")
        draw_icon(size).save(path)
        print(f"wrote {path}")


if __name__ == "__main__":
    main()

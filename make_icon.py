#!/usr/bin/env python3
"""
KBD icon builder
Version: 2.0.0

Turns Tim's KBD artwork into the app's icon set, plus the small glyph the app
draws in its own credit bar.

    ./venv/bin/python make_icon.py [--style blue|plain]

The source art (icon/KBDIcon_source.png) is black on white with no alpha, so
the first step is to recover a transparency mask from its luminance: black
becomes opaque, white becomes clear, and the grey anti-aliased edges keep
their softness.  Everything else is composed from that mask, which is why the
glyph can be recoloured for any background without touching the original.

Outputs, all under icon/:
    KBD_glyph.png    white glyph on transparency, tinted at runtime by the app
    KBD.iconset/     the ten PNGs iconutil wants
    KBD.icns         the app icon
    KBD_1024.png     a full-size preview of the icon

Styles:
    blue    white glyph on the app's blue rounded square (default, and what
            matches the keypad and the credit-bar glyph)
    plain   the original black glyph on a white rounded square

History:
  2.0.0  Rebuilt around Tim's supplied artwork; earlier version drew a
         keypad motif of its own, which the artwork replaces.
"""

import os
import subprocess
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ICON_DIR = os.path.join(HERE, "icon")
SOURCE = os.path.join(ICON_DIR, "KBDIcon_source.png")

MASTER = 1024
CORNER_RADIUS = 0.2237          # macOS rounded-square proportion
BODY_INSET = 0.055              # transparent margin around the rounded square
GLYPH_SCALE = 0.66              # glyph width as a fraction of the square

# The app's default field blue, top and bottom of a gentle vertical gradient.
FIELD_TOP = (110, 175, 255)
FIELD_BOTTOM = (10, 102, 219)
PLAIN_BACKGROUND = (250, 250, 250)

ICONSET_FILES = [
    ("icon_16x16.png", 16), ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32), ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128), ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256), ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512), ("icon_512x512@2x.png", 1024),
]


def load_mask():
    """Alpha mask from the artwork's luminance: black opaque, white clear."""
    art = Image.open(SOURCE).convert("L")
    return art.point(lambda level: 255 - level)


def coloured_glyph(mask, rgb):
    """The glyph in one flat colour, on transparency, trimmed to its ink."""
    glyph = Image.new("RGBA", mask.size, rgb + (0,))
    glyph.putalpha(mask)
    box = mask.getbbox()
    return glyph.crop(box) if box else glyph


def rounded_square(size, fill_top, fill_bottom):
    """A rounded square with a vertical gradient, on transparency."""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    inset = int(round(size * BODY_INSET))
    body = size - inset * 2

    gradient = Image.new("RGB", (1, body))
    for y in range(body):
        ratio = y / max(body - 1, 1)
        gradient.putpixel((0, y), tuple(
            int(round(top + (bottom - top) * ratio))
            for top, bottom in zip(fill_top, fill_bottom)))
    gradient = gradient.resize((body, body))

    mask = Image.new("L", (body, body), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, body - 1, body - 1],
        radius=int(round(body * CORNER_RADIUS)), fill=255)

    canvas.paste(gradient, (inset, inset), mask)
    return canvas


def compose(mask, style):
    """The full-size icon: rounded square with the glyph centred on it."""
    if style == "plain":
        base = rounded_square(MASTER, PLAIN_BACKGROUND, PLAIN_BACKGROUND)
        glyph = coloured_glyph(mask, (0, 0, 0))
    else:
        base = rounded_square(MASTER, FIELD_TOP, FIELD_BOTTOM)
        glyph = coloured_glyph(mask, (255, 255, 255))

    width = int(round(MASTER * GLYPH_SCALE))
    height = int(round(glyph.height * width / glyph.width))
    glyph = glyph.resize((width, height), Image.LANCZOS)

    base.paste(glyph, ((MASTER - width) // 2, (MASTER - height) // 2), glyph)
    return base


def main(argv):
    style = "blue"
    if "--style" in argv:
        style = argv[argv.index("--style") + 1]
    if style not in ("blue", "plain"):
        print("error: style must be blue or plain", file=sys.stderr)
        return 1
    if not os.path.exists(SOURCE):
        print("error: missing %s" % SOURCE, file=sys.stderr)
        return 1

    mask = load_mask()

    # The runtime glyph: white on transparency, recoloured by the app to suit
    # whatever field colour is in use.
    glyph = coloured_glyph(mask, (255, 255, 255))
    glyph.save(os.path.join(ICON_DIR, "KBD_glyph.png"))

    icon = compose(mask, style)
    icon.save(os.path.join(ICON_DIR, "KBD_1024.png"))

    iconset = os.path.join(ICON_DIR, "KBD.iconset")
    os.makedirs(iconset, exist_ok=True)
    for filename, pixels in ICONSET_FILES:
        icon.resize((pixels, pixels), Image.LANCZOS).save(
            os.path.join(iconset, filename))

    icns = os.path.join(ICON_DIR, "KBD.icns")
    subprocess.run(["iconutil", "-c", "icns", iconset, "-o", icns], check=True)
    print("style=%s  glyph=%dx%d  wrote %s" % (
        style, glyph.width, glyph.height, icns))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

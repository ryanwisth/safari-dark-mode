#!/usr/bin/env python3
"""Draw the extension, toolbar and app icons with Pillow.

App/extension icon: a cream crescent moon on a night-blue rounded square.
Toolbar icon: a gray crescent, filled when dark mode is on, outlined when off.
Gray reads on both light and dark toolbars whether or not Safari tints it.

Run:  python3 tools/make_icons.py   (writes extension/icons/*.png and build/AppIcon.icns)
"""
import pathlib
import subprocess
import tempfile

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parent.parent
ICONS = ROOT / "extension" / "icons"
BUILD = ROOT / "build"


def crescent_mask(size, cx, cy, r, cut_dx, cut_dy, cut_r):
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    cut = Image.new("L", (size, size), 0)
    ImageDraw.Draw(cut).ellipse([cx + cut_dx - cut_r, cy + cut_dy - cut_r, cx + cut_dx + cut_r, cy + cut_dy + cut_r], fill=255)
    return ImageChops.subtract(m, cut)


def app_icon(px=1024):
    s = px * 4  # supersample
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    # macOS icon grid: 824/1024 body, corner radius ~ 185/1024
    inset, body = int(s * 100 / 1024), int(s * 824 / 1024)
    grad = Image.new("RGBA", (body, body))
    top, bottom = (52, 61, 92), (14, 16, 26)
    gd = ImageDraw.Draw(grad)
    for y in range(body):
        t = y / (body - 1)
        gd.line([(0, y), (body, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,))
    shape = Image.new("L", (body, body), 0)
    ImageDraw.Draw(shape).rounded_rectangle([0, 0, body - 1, body - 1], radius=int(body * 0.225), fill=255)
    img.paste(grad, (inset, inset), shape)

    c = s / 2
    r = s * 0.25
    moon = crescent_mask(s, c - s * 0.02, c + s * 0.01, r, r * 0.55, -r * 0.42, r * 0.92)
    glow = moon.filter(ImageFilter.GaussianBlur(s * 0.035))
    glow_layer = Image.new("RGBA", (s, s), (255, 214, 140, 0))
    glow_layer.putalpha(glow.point(lambda v: int(v * 0.55)))
    img = Image.alpha_composite(img, glow_layer)
    cream = Image.new("RGBA", (s, s), (247, 232, 196, 255))
    img.paste(cream, (0, 0), moon)

    d = ImageDraw.Draw(img)
    for (x, y, k) in [(0.66, 0.30, 0.016), (0.73, 0.43, 0.010), (0.60, 0.20, 0.008)]:
        rr = s * k
        d.ellipse([s * x - rr, s * y - rr, s * x + rr, s * y + rr], fill=(247, 232, 196, 235))
    return img.resize((px, px), Image.LANCZOS)


def toolbar_icon(px, filled):
    s = px * 8
    r = s * 0.40
    c = s / 2
    color = (142, 142, 147, 255)
    outer = crescent_mask(s, c, c, r, r * 0.62, -r * 0.48, r * 0.95)
    if filled:
        mask = outer
    else:
        w = s * (0.085 if px >= 32 else 0.11)
        inner = crescent_mask(s, c, c, r - w, r * 0.62, -r * 0.48, r * 0.95 + w)
        mask = ImageChops.subtract(outer, inner)
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    img.paste(Image.new("RGBA", (s, s), color), (0, 0), mask)
    return img.resize((px, px), Image.LANCZOS)


def main():
    ICONS.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    master = app_icon(1024)
    for n in (48, 96, 128, 256, 512):
        master.resize((n, n), Image.LANCZOS).save(ICONS / f"icon-{n}.png")
    for state, filled in (("on", True), ("off", False)):
        for n in (16, 32, 64):
            toolbar_icon(n, filled).save(ICONS / f"toolbar-{state}-{n}.png")

    with tempfile.TemporaryDirectory() as tmp:
        iconset = pathlib.Path(tmp) / "AppIcon.iconset"
        iconset.mkdir()
        for n in (16, 32, 128, 256, 512):
            master.resize((n, n), Image.LANCZOS).save(iconset / f"icon_{n}x{n}.png")
            master.resize((n * 2, n * 2), Image.LANCZOS).save(iconset / f"icon_{n}x{n}@2x.png")
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(BUILD / "AppIcon.icns")], check=True)
    master.save(BUILD / "AppIcon-1024.png")
    print("icons written")


if __name__ == "__main__":
    main()

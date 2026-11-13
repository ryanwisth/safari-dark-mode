#!/usr/bin/env python3
"""Fit each theme's target colors to a chain of CSS filter functions.

Why filters: Safari runs CSS shorthand filters (invert, hue-rotate, sepia,
contrast, brightness, saturate) on the GPU through Core Animation, so the
whole page darkens with no per-element work and no white flash. The cost is
that a theme can only be reached approximately, so this script searches for
the chain whose output lands closest to the theme's target page background
and text color, while keeping link/button colors recognisable.

Chain (applied left to right, each step clamped to 0..1, sRGB space):
    brightness(a) hue-rotate(-h1) sepia(s1) hue-rotate(h1)
        -> tint the light page BEFORE inverting, so the tint lands on the
           new dark background and not on the text (sepia only multiplies,
           so a tint added after inverting would be strongest on the text)
    invert(1) hue-rotate(180deg)                       -> dark page
    contrast(c) brightness(b)                          -> background/text levels
    hue-rotate(-h2) sepia(s2) hue-rotate(h2)           -> text tint (Sepia's cream)
    saturate(k)                                        -> win back color the tints dulled

Images get their own reverse filter, `saturate(r) invert(1) hue-rotate(180deg)`,
so they come out un-inverted, spanning the theme's background-to-text range.
The saturate(r < 1) matters: invert + hue-rotate applied twice is exact in
theory, but a saturated yellow or red leaves the 0..1 range after the first
hue-rotate and gets clipped, turning yellow beige. Shrinking image color
first keeps it in range; the theme's final saturate(k) puts it back.

Run:  python3 tools/fit_themes.py      (writes extension/themes.js)
"""
import json
import math
import pathlib

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "extension" / "themes.js"

# id, display name, target page background, target text color
THEMES = [
    ("dark", "Dark", "#1b1b1d", "#e3e3e3"),
    ("black", "Black", "#000000", "#dedede"),
    ("dim", "Dim", "#15202b", "#e1e8ed"),
    ("sepia", "Sepia", "#262018", "#e9d9bd"),
    ("nord", "Nord", "#2e3440", "#d8dee9"),
    ("dracula", "Dracula", "#282a36", "#f8f8f2"),
]

# Typical page colors whose hue should survive (links, buttons, alerts).
SAMPLES = ["#1a0dab", "#1a73e8", "#d93025", "#188038", "#f29900", "#681da8", "#f1f3f4", "#5f6368"]

# Photo colors. Images are flipped back before the theme runs, so these should
# come out with their own hue and chroma, only squeezed into the theme's range.
PHOTO = ["#ffd23c", "#dc1e28", "#286e32", "#4696eb", "#e0ac8a", "#8a5a3c", "#7fa3c8", "#c8c8c8", "#404040"]


# ---------- CSS filter primitives (Filter Effects Level 1) ----------

def hue_matrix(deg):
    t = math.radians(deg)
    c, s = math.cos(t), math.sin(t)
    base = np.array([[0.213, 0.715, 0.072]] * 3)
    cm = np.array([[0.787, -0.715, -0.072], [-0.213, 0.285, -0.072], [-0.213, -0.715, 0.928]])
    sm = np.array([[-0.213, -0.715, 0.928], [0.143, 0.140, -0.283], [-0.787, 0.715, 0.072]])
    return base + c * cm + s * sm


def sepia_matrix(a):
    r = 1 - a
    return np.array([
        [0.393 + 0.607 * r, 0.769 - 0.769 * r, 0.189 - 0.189 * r],
        [0.349 - 0.349 * r, 0.686 + 0.314 * r, 0.168 - 0.168 * r],
        [0.272 - 0.272 * r, 0.534 - 0.534 * r, 0.131 + 0.869 * r],
    ])


def saturate_matrix(s):
    return np.array([
        [0.213 + 0.787 * s, 0.715 - 0.715 * s, 0.072 - 0.072 * s],
        [0.213 - 0.213 * s, 0.715 + 0.285 * s, 0.072 - 0.072 * s],
        [0.213 - 0.213 * s, 0.715 - 0.715 * s, 0.072 + 0.928 * s],
    ])


def mat(x, m):
    return np.clip(x @ m.T, 0, 1)


def reverse(x, r):
    """The filter images get before the page filter runs on them."""
    x = mat(x, saturate_matrix(r))
    return mat(1 - x, hue_matrix(180))


def run_chain(x, p):
    a, h1, s1, c, b, h2, s2, k = p[:8]
    x = np.clip(a * x, 0, 1)                    # brightness: headroom for the tint
    x = mat(x, hue_matrix(-h1)); x = mat(x, sepia_matrix(s1)); x = mat(x, hue_matrix(h1))
    x = 1 - x                                   # invert(1)
    x = mat(x, hue_matrix(180))
    x = np.clip(c * x + 0.5 - 0.5 * c, 0, 1)    # contrast
    x = np.clip(b * x, 0, 1)                    # brightness
    x = mat(x, hue_matrix(-h2)); x = mat(x, sepia_matrix(s2)); x = mat(x, hue_matrix(h2))
    x = mat(x, saturate_matrix(k))
    return x


def reverse_css(p):
    r = p[8]
    return ("" if abs(r - 1) <= 0.005 else f"saturate({r:.3f}) ") + "invert(1) hue-rotate(180deg)"


def chain_css(p):
    a, h1, s1, c, b, h2, s2, k = p[:8]
    parts = []
    if s1 > 0.005:
        if abs(a - 1) > 0.0005:
            parts.append(f"brightness({a:.3f})")
        parts += [f"hue-rotate({-h1:.1f}deg)", f"sepia({s1:.3f})", f"hue-rotate({h1:.1f}deg)"]
    parts += ["invert(1)", "hue-rotate(180deg)", f"contrast({c:.3f})", f"brightness({b:.3f})"]
    if s2 > 0.005:
        parts += [f"hue-rotate({-h2:.1f}deg)", f"sepia({s2:.3f})", f"hue-rotate({h2:.1f}deg)"]
    if abs(k - 1) > 0.005:
        parts.append(f"saturate({k:.3f})")
    return " ".join(parts)


def snap(p):
    """Zero out the stages chain_css drops, so the reported colors are exact."""
    a, h1, s1, c, b, h2, s2, k, r = p
    if s1 <= 0.005:
        a, s1 = 1.0, 0.0
    if abs(a - 1) <= 0.0005:
        a = 1.0
    return [a, h1, s1, c, b, h2, s2 if s2 > 0.005 else 0.0, k if abs(k - 1) > 0.005 else 1.0,
            r if abs(r - 1) > 0.005 else 1.0]


# ---------- color math ----------

def hex_rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])


def rgb_hex(v):
    return "#" + "".join(f"{int(round(min(max(c, 0), 1) * 255)):02x}" for c in v)


def oklab(rgb):
    rgb = np.atleast_2d(rgb)
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    lms = lin @ np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                          [0.2119034982, 0.6806995451, 0.1073969566],
                          [0.0883024619, 0.2817188376, 0.6299787005]]).T
    lms = np.cbrt(lms)
    return lms @ np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                           [1.9779984951, -2.4285922050, 0.4505937099],
                           [0.0259040371, 0.7827717662, -0.8086757660]]).T


def de(a, b):
    return 100 * np.linalg.norm(oklab(a) - oklab(b), axis=1)


# ---------- fit ----------

LO = np.array([0.4, -180, 0, 0.2, 0.2, -180, 0, 0.5, 0.3])
HI = np.array([1.0, 180, 1, 1.3, 1.6, 180, 1, 3.0, 1.0])


def make_objective(bg, fg):
    white, black = np.array([[1, 1, 1.0]]), np.array([[0, 0, 0.0]])
    samples = np.array([hex_rgb(h) for h in SAMPLES])
    lab_s = oklab(samples)
    L_bg, L_fg = oklab(bg)[0, 0], oklab(fg)[0, 0]
    ideal = np.column_stack([L_fg - (L_fg - L_bg) * lab_s[:, 0], 0.85 * lab_s[:, 1], 0.85 * lab_s[:, 2]])

    photo = np.array([hex_rgb(h) for h in PHOTO])
    lab_p = oklab(photo)
    photo_ideal = np.column_stack([L_bg + (L_fg - L_bg) * lab_p[:, 0], lab_p[:, 1], lab_p[:, 2]])

    def f(p):
        p = np.asarray(p)
        out_of = np.sum(np.maximum(LO - p, 0) ** 2 + np.maximum(p - HI, 0) ** 2)
        p = np.clip(p, LO, HI)
        e_bg = de(run_chain(white, p), bg[None])[0]
        e_fg = de(run_chain(black, p), fg[None])[0]
        e_s = 100 * np.linalg.norm(oklab(run_chain(samples, p)) - ideal, axis=1)
        e_p = 100 * np.linalg.norm(oklab(run_chain(reverse(photo, p[8]), p)) - photo_ideal, axis=1)
        return (40 * e_bg ** 2 + 8 * e_fg ** 2 + 0.1 * np.sum(e_s ** 2) + 0.5 * np.sum(e_p ** 2)
                + 20 * (p[2] ** 2 + p[6] ** 2) + 10 * (p[7] - 1) ** 2 + 1e4 * out_of)
    return f


def nelder_mead(f, x0, scale, iters=1500):
    n = len(x0)
    pts = [np.array(x0, float)] + [np.array(x0, float) + np.eye(n)[i] * scale[i] for i in range(n)]
    vals = [f(p) for p in pts]
    for _ in range(iters):
        order = np.argsort(vals)
        pts, vals = [pts[i] for i in order], [vals[i] for i in order]
        cen = np.mean(pts[:-1], axis=0)
        xr = cen + (cen - pts[-1]); fr = f(xr)
        if fr < vals[0]:
            xe = cen + 2 * (cen - pts[-1]); fe = f(xe)
            pts[-1], vals[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < vals[-2]:
            pts[-1], vals[-1] = xr, fr
        else:
            xc = cen + 0.5 * (pts[-1] - cen); fc = f(xc)
            if fc < vals[-1]:
                pts[-1], vals[-1] = xc, fc
            else:
                pts = [pts[0] + 0.5 * (p - pts[0]) for p in pts]
                vals = [f(p) for p in pts]
    i = int(np.argmin(vals))
    return pts[i], vals[i]


def fit(bg, fg, rng):
    f = make_objective(bg, fg)
    scale = np.array([0.1, 40, 0.2, 0.15, 0.15, 40, 0.2, 0.3, 0.15])
    best = None
    for _ in range(12):
        x0 = rng.uniform(LO, HI)
        x0[2] *= 0.6; x0[6] *= 0.4; x0[7] = rng.uniform(0.9, 1.6); x0[8] = rng.uniform(0.5, 1.0)
        x, v = nelder_mead(f, x0, scale)
        x, v = nelder_mead(f, x, scale * 0.2)
        if best is None or v < best[1]:
            best = (np.clip(x, LO, HI), v)
    return best[0]


def main():
    rng = np.random.default_rng(7)
    themes = []
    print(f"{'theme':8} {'target bg':>9} {'got bg':>8} {'dE':>5}   {'target fg':>9} {'got fg':>8} {'dE':>5}")
    for tid, name, bg_hex, fg_hex in THEMES:
        bg, fg = hex_rgb(bg_hex), hex_rgb(fg_hex)
        p = snap(fit(bg, fg, rng))
        got_bg = run_chain(np.array([[1, 1, 1.0]]), p)[0]
        got_fg = run_chain(np.array([[0, 0, 0.0]]), p)[0]
        print(f"{tid:8} {bg_hex:>9} {rgb_hex(got_bg):>8} {de(got_bg[None], bg[None])[0]:5.1f}   "
              f"{fg_hex:>9} {rgb_hex(got_fg):>8} {de(got_fg[None], fg[None])[0]:5.1f}")
        photo = np.array([hex_rgb(h) for h in PHOTO])
        got_p = run_chain(reverse(photo, p[8]), p)
        print("          photos: " + " ".join(f"{h}->{rgb_hex(g)}" for h, g in zip(PHOTO, got_p)))
        themes.append({"id": tid, "name": name, "bg": rgb_hex(got_bg), "fg": rgb_hex(got_fg),
                       "target": [bg_hex, fg_hex], "filter": chain_css(p), "reverse": reverse_css(p)})
    body = json.dumps(themes, indent=2)
    OUT.write_text(
        "// Generated by tools/fit_themes.py. Do not hand-edit: change the targets there and re-run.\n"
        "// bg/fg are what the filter actually produces from a white page with black text.\n"
        "// `reverse` goes on images and video so they come out un-inverted.\n"
        f"const SDM_THEMES = {body};\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

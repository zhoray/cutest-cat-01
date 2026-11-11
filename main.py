# SPDX-License-Identifier: MIT
"""make.fun cutest-cat-01 entry: "Mochi", a cream kitten drawn entirely in code.

Pure Python 3 standard library (the python3.13 sandbox ships nothing else).
The picture is painted with signed-distance shapes onto float planes, then
written as a PNG with a small adaptive-filter encoder.  No randomness, no
clock, no network: every run writes byte-identical output.
"""

import math
import os
import struct
import zlib
from array import array

W = H = 1024
N = W * H

# ---------------------------------------------------------------- canvas ----
R = array("f", bytes(4 * N))
G = array("f", bytes(4 * N))
B = array("f", bytes(4 * N))


def clamp01(v):
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


def render(x0, y0, x1, y1, layers):
    """Composite layers (fn(x, y) -> (r, g, b, a) | None) in painter order."""
    x0 = max(0, int(x0)); y0 = max(0, int(y0))
    x1 = min(W, int(x1)); y1 = min(H, int(y1))
    for yy in range(y0, y1):
        base = yy * W
        fy = yy + 0.5
        for xx in range(x0, x1):
            fx = xx + 0.5
            i = base + xx
            r, g, b = R[i], G[i], B[i]
            dirty = False
            for fn in layers:
                c = fn(fx, fy)
                if c is None:
                    continue
                cr, cg, cb, a = c
                if a <= 0.0:
                    continue
                dirty = True
                if a >= 1.0:
                    r, g, b = cr, cg, cb
                else:
                    ia = 1.0 - a
                    r = r * ia + cr * a
                    g = g * ia + cg * a
                    b = b * ia + cb * a
            if dirty:
                R[i] = r; G[i] = g; B[i] = b


# ------------------------------------------------------------ sdf helpers ----
def cov(d):
    """Coverage for a hard shape from its signed distance (1px AA band)."""
    return clamp01(0.5 - d)


def sd_circle(x, y, cx, cy, r):
    return math.hypot(x - cx, y - cy) - r


def sd_ellipse(x, y, cx, cy, rx, ry):
    qx = (x - cx) / rx
    qy = (y - cy) / ry
    return (math.hypot(qx, qy) - 1.0) * min(rx, ry)


def sd_segment(x, y, ax, ay, bx, by):
    pax, pay = x - ax, y - ay
    bax, bay = bx - ax, by - ay
    h = clamp01((pax * bax + pay * bay) / (bax * bax + bay * bay))
    return math.hypot(pax - bax * h, pay - bay * h)


def sd_cone(x, y, ax, ay, ra, bx, by, rb):
    """Distance to a capsule whose radius lerps ra -> rb along the segment."""
    pax, pay = x - ax, y - ay
    bax, bay = bx - ax, by - ay
    h = clamp01((pax * bax + pay * bay) / (bax * bax + bay * bay))
    return math.hypot(pax - bax * h, pay - bay * h) - (ra + (rb - ra) * h)


def sd_triangle(x, y, ax, ay, bx, by, cx, cy):
    def edge(px, py, qx, qy, rx, ry):
        ex, ey = qx - px, qy - py
        wx, wy = rx - px, ry - py
        t = clamp01((wx * ex + wy * ey) / (ex * ex + ey * ey))
        dx, dy = wx - ex * t, wy - ey * t
        return dx * dx + dy * dy, (qx - px) * (ry - py) - (qy - py) * (rx - px)
    d1, s1 = edge(ax, ay, bx, by, x, y)
    d2, s2 = edge(bx, by, cx, cy, x, y)
    d3, s3 = edge(cx, cy, ax, ay, x, y)
    d = min(d1, d2, d3)
    inside = (s1 <= 0 and s2 <= 0 and s3 <= 0) or (s1 >= 0 and s2 >= 0 and s3 >= 0)
    return -math.sqrt(d) if inside else math.sqrt(d)


def hexcol(h):
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


# --------------------------------------------------------------- palette ----
BG_IN = hexcol("fff9ef")
BG_MID = hexcol("fdeeda")
BG_OUT = hexcol("f7d7b8")
SHADOW = hexcol("dd9c72")
FUR = hexcol("fdf6ec")
FUR_SHADE = hexcol("eeddc6")
FUR_DEEP = hexcol("e0c69f")
BELLY = hexcol("fffdf8")
GINGER = hexcol("f4a95c")
GINGER_DEEP = hexcol("dd8438")
PINK = hexcol("f28ba0")
PINK_SOFT = hexcol("f7a8b8")
INNER_EAR = hexcol("f9b7c4")
LINE = hexcol("b98a5f")
YARN = hexcol("ef8f9f")
YARN_DEEP = hexcol("d96a7f")
SPARK = hexcol("ffd9a0")
LASH = (0.30, 0.17, 0.08)


# ------------------------------------------------------------- background ----
def _bg_colour(d):
    t = d / 880.0
    if t < 0.55:
        k = t / 0.55
        return (BG_IN[0] + (BG_MID[0] - BG_IN[0]) * k,
                BG_IN[1] + (BG_MID[1] - BG_IN[1]) * k,
                BG_IN[2] + (BG_MID[2] - BG_IN[2]) * k)
    k = (t - 0.55) / 0.45
    if k > 1.0:
        k = 1.0
    return (BG_MID[0] + (BG_OUT[0] - BG_MID[0]) * k,
            BG_MID[1] + (BG_OUT[1] - BG_MID[1]) * k,
            BG_MID[2] + (BG_OUT[2] - BG_MID[2]) * k)


_BG_LUT = [_bg_colour(float(d)) for d in range(900)]
_DX2 = [(x + 0.5 - 512.0) ** 2 for x in range(W)]


def paint_background():
    for yy in range(H):
        dy2 = (yy + 0.5 - 400.0) ** 2
        base = yy * W
        for xx in range(W):
            d = math.sqrt(_DX2[xx] + dy2)
            c = _BG_LUT[int(d)] if d < 899.0 else _BG_LUT[899]
            i = base + xx
            R[i], G[i], B[i] = c


paint_background()


def ellipse_fn(cx, cy, rx, ry, col, max_a, softw=1.0, grow=0.0):
    def fn(x, y):
        if abs(x - cx) > rx + softw + grow + 2 or abs(y - cy) > ry + softw + grow + 2:
            return None
        d = sd_ellipse(x, y, cx, cy, rx, ry) - grow
        a = cov(d) if softw <= 1.0 else clamp01(0.5 - d / softw)
        if a <= 0.0:
            return None
        return (col[0], col[1], col[2], a * max_a)
    return fn


def circle_fn(cx, cy, r, col, max_a, softw=1.0):
    return ellipse_fn(cx, cy, r, r, col, max_a, softw)


# ground shadow, one wide soft ellipse
render(150, 872, 875, 1024,
       [ellipse_fn(512, 946, 335, 40, SHADOW, 0.30, softw=55)])

# ------------------------------------------------------- tail + body pass ----
TAIL = [(712, 806, 38), (768, 838, 43), (826, 880, 44), (838, 918, 39),
        (772, 946, 34), (684, 960, 29), (606, 950, 21)]


def tail_d(x, y, grow=0.0):
    d = 1e9
    for i in range(len(TAIL) - 1):
        ax, ay, ra = TAIL[i]
        bx, by, rb = TAIL[i + 1]
        dd = sd_cone(x, y, ax, ay, ra + grow, bx, by, rb + grow)
        if dd < d:
            d = dd
    return d


def tail_rim(x, y):
    if x < 545 or x > 915 or y < 725 or y > 995:
        return None
    a = cov(tail_d(x, y, 3.5))
    return (FUR_DEEP[0], FUR_DEEP[1], FUR_DEEP[2], a) if a > 0 else None


def tail_fur(x, y):
    if x < 545 or x > 915 or y < 725 or y > 995:
        return None
    a = cov(tail_d(x, y))
    return (GINGER[0], GINGER[1], GINGER[2], a) if a > 0 else None


def tail_stripes(x, y):
    if x < 545 or x > 915 or y < 725 or y > 995:
        return None
    if tail_d(x, y) > 0:
        return None
    a = max(cov(sd_segment(x, y, 716, 892, 700, 968) - 11),
            cov(sd_segment(x, y, 792, 884, 780, 956) - 11))
    return (GINGER_DEEP[0], GINGER_DEEP[1], GINGER_DEEP[2], a * 0.5) if a > 0 else None


def body_rim(x, y):
    a = cov(sd_ellipse(x, y, 512, 748, 252, 210) - 2.5)
    return (FUR_DEEP[0], FUR_DEEP[1], FUR_DEEP[2], a) if a > 0 else None


def body_fur(x, y):
    a = cov(sd_ellipse(x, y, 512, 745, 246, 205))
    return (FUR[0], FUR[1], FUR[2], a) if a > 0 else None


def belly(x, y):
    if abs(x - 512) > 185 or y < 640 or y > 955:
        return None
    a = clamp01(0.5 - sd_ellipse(x, y, 512, 806, 148, 128) / 30.0)
    return (BELLY[0], BELLY[1], BELLY[2], a * 0.95) if a > 0 else None


def hind_paws(x, y):
    if y < 850 or y > 960:
        return None
    out = None
    for cx in (296, 728):
        if abs(x - cx) > 86:
            continue
        a = cov(sd_ellipse(x, y, cx, 904, 80, 45) - 2.0)
        if a > 0:
            out = (FUR_DEEP[0], FUR_DEEP[1], FUR_DEEP[2], a)
        a = cov(sd_ellipse(x, y, cx, 902, 76, 41))
        if a > 0:
            out = (FUR[0], FUR[1], FUR[2], a)
    return out


def yarn_ball(x, y):
    if abs(x - 372) > 66 or abs(y - 890) > 66:
        return None
    a = cov(sd_circle(x, y, 372, 890, 60) - 2.0)
    out = None
    if a > 0:
        out = (YARN_DEEP[0], YARN_DEEP[1], YARN_DEEP[2], a)
    a = cov(sd_circle(x, y, 372, 890, 58))
    if a > 0:
        out = (YARN[0], YARN[1], YARN[2], a)
    if out is None:
        return None
    d = math.hypot(x - 372.0, y - 890.0)
    if d <= 59:
        w = 0.0
        for rr in (17, 34, 50):
            w = max(w, cov(abs(d - rr) - 3.2))
        w = max(w, cov(sd_segment(x, y, 330, 848, 420, 928) - 3.0))
        if w > 0:
            ia = 1.0 - w * 0.65
            out = (out[0] * ia + YARN_DEEP[0] * w * 0.65,
                   out[1] * ia + YARN_DEEP[1] * w * 0.65,
                   out[2] * ia + YARN_DEEP[2] * w * 0.65, 1.0)
    return out


def yarn_strand(x, y):
    if x < 195 or x > 350 or y < 915 or y > 990:
        return None
    d = min(sd_segment(x, y, 330, 928, 272, 960),
            sd_segment(x, y, 272, 960, 212, 946))
    a = cov(d - 3.4)
    return (YARN_DEEP[0], YARN_DEEP[1], YARN_DEEP[2], a * 0.8) if a > 0 else None


def front_legs(x, y):
    if y < 780 or y > 945 or x < 415 or x > 610:
        return None
    out = None
    for cx in (466, 558):
        a = cov(sd_cone(x, y, cx, 798, 41, cx, 896, 44) - 1.5)
        if a > 0:
            out = (FUR_SHADE[0], FUR_SHADE[1], FUR_SHADE[2], a * 0.55)
        a = cov(sd_cone(x, y, cx, 798, 37, cx, 896, 40))
        if a > 0:
            out = (FUR[0], FUR[1], FUR[2], a)
        a = cov(sd_ellipse(x, y, cx, 910, 42, 25) - 2.0)
        if a > 0:
            out = (FUR_DEEP[0], FUR_DEEP[1], FUR_DEEP[2], a)
        a = cov(sd_ellipse(x, y, cx, 908, 39, 22))
        if a > 0:
            out = (BELLY[0], BELLY[1], BELLY[2], a)
    if out is not None:
        return out
    a = cov(sd_segment(x, y, 512, 812, 512, 898) - 3.0) * 0.28
    return (LINE[0], LINE[1], LINE[2], a) if a > 0 else None


def toe_lines(x, y):
    if y < 872 or y > 930 or x < 200 or x > 830:
        return None
    a = 0.0
    for cx in (296, 728):
        for dx in (-24, 0, 24):
            a = max(a, cov(sd_segment(x, y, cx + dx, 880, cx + dx, 900) - 2.6))
    for cx in (466, 558):
        for dx in (-13, 13):
            a = max(a, cov(sd_segment(x, y, cx + dx, 894, cx + dx, 912) - 2.6))
    return (LINE[0], LINE[1], LINE[2], a * 0.75) if a > 0 else None


render(205, 520, 920, 1000,
       [tail_rim, tail_fur, tail_stripes, body_rim, body_fur, belly,
        hind_paws, yarn_ball, yarn_strand, front_legs, toe_lines])

# ------------------------------------------------------------- head group ----
HCX, HCY = 512.0, 418.0
TILT = 0.12                      # radians; the charm head tilt
_ct, _st = math.cos(TILT), math.sin(TILT)


def head_sdf(hx, hy):
    d = sd_ellipse(hx, hy, HCX, HCY, 230, 206)
    d = min(d, sd_circle(hx, hy, 296, 512, 58))   # cheek fluff L
    d = min(d, sd_circle(hx, hy, 728, 512, 58))   # cheek fluff R
    d = min(d, sd_circle(hx, hy, 322, 578, 44))
    d = min(d, sd_circle(hx, hy, 702, 578, 44))
    return d


EYE_Y = 452


def ear_layers(sign):
    ax, ay = HCX + sign * 168, HCY - 128
    bx, by = HCX + sign * 198, HCY - 282
    cx, cy = HCX + sign * 52, HCY - 208
    gx, gy = (ax + bx + cx) / 3.0, (ay + by + cy) / 3.0

    def shrink(px, py, k):
        return gx + (px - gx) * k, gy + (py - gy) * k

    ia = shrink(ax, ay, 0.58); ib = shrink(bx, by, 0.58); ic = shrink(cx, cy, 0.58)

    def rim(hx, hy):
        a = cov(sd_triangle(hx, hy, ax, ay, bx, by, cx, cy) - 3.5)
        return (FUR_DEEP[0], FUR_DEEP[1], FUR_DEEP[2], a) if a > 0 else None

    def fur(hx, hy):
        a = cov(sd_triangle(hx, hy, ax, ay, bx, by, cx, cy))
        return (FUR[0], FUR[1], FUR[2], a) if a > 0 else None

    def inner(hx, hy):
        a = cov(sd_triangle(hx, hy, ia[0], ia[1], ib[0], ib[1], ic[0], ic[1]))
        return (INNER_EAR[0], INNER_EAR[1], INNER_EAR[2], a) if a > 0 else None

    return rim, fur, inner


def h_head_rim(hx, hy, hd):
    a = cov(hd - 2.5)
    return (FUR_DEEP[0], FUR_DEEP[1], FUR_DEEP[2], a) if a > 0 else None


def h_head_fur(hx, hy, hd):
    a = cov(hd)
    return (FUR[0], FUR[1], FUR[2], a) if a > 0 else None


def h_head_shade(hx, hy, hd):
    if hd > 0:
        return None
    a = clamp01(0.5 - sd_ellipse(hx, hy, HCX - 148, HCY + 118, 118, 128) / 55.0)
    a = max(a, clamp01(0.5 - sd_ellipse(hx, hy, HCX + 148, HCY + 118, 118, 128) / 55.0))
    a *= 0.30
    return (FUR_SHADE[0], FUR_SHADE[1], FUR_SHADE[2], a) if a > 0 else None


def h_forehead(hx, hy, hd):
    if hd > 0 or hy > HCY - 40:
        return None
    a = clamp01(0.5 - sd_ellipse(hx, hy, HCX + 88, HCY - 172, 98, 76) / 16.0)
    a = max(a, clamp01(0.5 - sd_circle(hx, hy, HCX + 158, HCY - 92, 17) / 8.0))
    a = max(a, clamp01(0.5 - sd_circle(hx, hy, HCX + 44, HCY - 80, 12) / 8.0))
    a *= 0.95
    return (GINGER[0], GINGER[1], GINGER[2], a) if a > 0.01 else None


def eye_layers(ex):
    def socket(hx, hy, hd):
        if abs(hx - ex) > 78 or abs(hy - EYE_Y) > 88:
            return None
        a = clamp01(0.5 - sd_ellipse(hx, hy, ex, EYE_Y, 52, 66) / 26.0) * 0.32
        return (FUR_SHADE[0], FUR_SHADE[1], FUR_SHADE[2], a) if a > 0 else None

    def eye(hx, hy, hd):
        if abs(hx - ex) > 44 or abs(hy - EYE_Y) > 60:
            return None
        a = cov(sd_ellipse(hx, hy, ex, EYE_Y, 39, 55))
        if a <= 0.0:
            return None
        t = clamp01((hy - (EYE_Y - 55)) / 110.0)
        top = (0.13, 0.07, 0.04)
        mid = (0.32, 0.18, 0.08)
        bot = (0.62, 0.36, 0.13)
        if t < 0.6:
            k = t / 0.6
            r = top[0] + (mid[0] - top[0]) * k
            g = top[1] + (mid[1] - top[1]) * k
            b = top[2] + (mid[2] - top[2]) * k
        else:
            k = (t - 0.6) / 0.4
            r = mid[0] + (bot[0] - mid[0]) * k
            g = mid[1] + (bot[1] - mid[1]) * k
            b = mid[2] + (bot[2] - mid[2]) * k
        glow = clamp01(0.5 - sd_ellipse(hx, hy, ex, EYE_Y + 30, 26, 20) / 18.0)
        return (min(r + 0.30 * glow, 1.0), min(g + 0.16 * glow, 1.0),
                min(b + 0.02 * glow, 1.0), a)

    def shine(hx, hy, hd):
        if abs(hx - ex) > 44 or abs(hy - EYE_Y) > 60:
            return None
        a = cov(sd_circle(hx, hy, ex - 12, EYE_Y - 18, 13.5))
        a = max(a, cov(sd_circle(hx, hy, ex + 13, EYE_Y + 16, 6.5)))
        a = max(a, cov(sd_circle(hx, hy, ex - 17, EYE_Y + 6, 3.4)))
        a *= cov(sd_ellipse(hx, hy, ex, EYE_Y, 39, 55))
        return (1.0, 1.0, 1.0, a) if a > 0 else None

    def lash(hx, hy, hd):
        if abs(hx - ex) > 52 or abs(hy - EYE_Y) > 66 or hy > EYE_Y - 18:
            return None
        d = 1e9
        steps = 8
        for k in range(steps):
            f0 = k / steps
            f1 = (k + 1) / steps
            ph0 = math.pi * (1.08 + 0.84 * f0)
            ph1 = math.pi * (1.08 + 0.84 * f1)
            ax = ex + 42 * math.cos(ph0); ay = EYE_Y + 58 * math.sin(ph0)
            bx = ex + 42 * math.cos(ph1); by = EYE_Y + 58 * math.sin(ph1)
            dd = sd_segment(hx, hy, ax, ay, bx, by)
            if dd < d:
                d = dd
        a = cov(d - 3.0) * 0.5
        return (LASH[0], LASH[1], LASH[2], a) if a > 0 else None

    return socket, eye, shine, lash


def h_nose(hx, hy, hd):
    if abs(hx - HCX) > 30 or abs(hy - (HCY + 114)) > 26:
        return None
    d = sd_triangle(hx, hy, HCX - 19, HCY + 102, HCX + 19, HCY + 102, HCX, HCY + 127)
    a = cov(d - 5)
    if a <= 0.0:
        return None
    hl = clamp01(0.5 - sd_circle(hx, hy, HCX - 5, HCY + 107, 5) / 5.0)
    return (PINK[0] + 0.25 * hl, PINK[1] + 0.25 * hl, PINK[2] + 0.22 * hl, a)


def h_mouth(hx, hy, hd):
    if abs(hx - HCX) > 36 or hy < HCY + 118 or hy > HCY + 148:
        return None
    a = 0.0
    for sgn in (-1, 1):
        for k in range(8):
            s0 = k / 8.0
            s1 = (k + 1) / 8.0
            ax = HCX + sgn * 27 * s0
            ay = HCY + 127 + 7 * math.sin(math.pi * s0) - 2 * s0
            bx = HCX + sgn * 27 * s1
            by = HCY + 127 + 7 * math.sin(math.pi * s1) - 2 * s1
            a = max(a, cov(sd_segment(hx, hy, ax, ay, bx, by) - 2.8))
    return (0.60, 0.34, 0.20, a * 0.9) if a > 0 else None


def blush_fn(bx):
    def fn(hx, hy, hd):
        if abs(hx - bx) > 70 or abs(hy - 548) > 46:
            return None
        a = clamp01(0.5 - sd_ellipse(hx, hy, bx, 548, 44, 23) / 20.0) * 0.55
        return (PINK_SOFT[0], PINK_SOFT[1], PINK_SOFT[2], a) if a > 0 else None
    return fn


def h_whiskers(hx, hy, hd):
    if abs(hx - HCX) < 150 or hy < HCY + 78 or hy > HCY + 168:
        return None
    sgn = 1.0 if hx > HCX else -1.0
    a = 0.0
    for dy, tilt in ((-6, -14), (16, 0), (38, 16)):
        ax, ay = HCX + sgn * 168, HCY + 108 + dy
        bx, by = HCX + sgn * 238, HCY + 104 + dy + tilt * 0.4
        cx2, cy2 = HCX + sgn * 302, HCY + 100 + dy + tilt
        d = min(sd_segment(hx, hy, ax, ay, bx, by),
                sd_segment(hx, hy, bx, by, cx2, cy2))
        a = max(a, cov(d - 1.7))
    return (LINE[0], LINE[1], LINE[2], a * 0.5) if a > 0 else None


def render_head():
    ear_l = ear_layers(-1)
    ear_r = ear_layers(1)
    eye_l = eye_layers(424)
    eye_r = eye_layers(600)
    layers = [
        lambda hx, hy, hd: ear_l[0](hx, hy), lambda hx, hy, hd: ear_r[0](hx, hy),
        lambda hx, hy, hd: ear_l[1](hx, hy), lambda hx, hy, hd: ear_r[1](hx, hy),
        lambda hx, hy, hd: ear_l[2](hx, hy), lambda hx, hy, hd: ear_r[2](hx, hy),
        h_head_rim, h_head_fur, h_head_shade, h_forehead,
        eye_l[0], eye_r[0], eye_l[1], eye_r[1], eye_l[2], eye_r[2],
        eye_l[3], eye_r[3],
        h_nose, h_mouth, blush_fn(346), blush_fn(678), h_whiskers,
    ]
    x0, y0, x1, y1 = 235, 105, 790, 665
    for yy in range(y0, y1):
        base = yy * W
        fy = yy + 0.5
        for xx in range(x0, x1):
            fx = xx + 0.5
            dx, dy = fx - HCX, fy - HCY
            hx = HCX + dx * _ct + dy * _st
            hy = HCY - dx * _st + dy * _ct
            hd = head_sdf(hx, hy)
            i = base + xx
            r, g, b = R[i], G[i], B[i]
            dirty = False
            for fn in layers:
                c = fn(hx, hy, hd)
                if c is None:
                    continue
                cr, cg, cb, a = c
                if a <= 0.0:
                    continue
                dirty = True
                if a >= 1.0:
                    r, g, b = cr, cg, cb
                else:
                    ia = 1.0 - a
                    r = r * ia + cr * a
                    g = g * ia + cg * a
                    b = b * ia + cb * a
            if dirty:
                R[i] = r; G[i] = g; B[i] = b


render_head()

# --------------------------------------------------------------- sparkles ----
def sparkle(cx, cy, s):
    def fn(x, y):
        a = 0.0
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            a = max(a, cov(sd_cone(x, y, cx, cy, s * 0.20, cx + dx * s, cy + dy * s, 0.0)))
        a = max(a, cov(sd_circle(x, y, cx, cy, s * 0.16)))
        return (SPARK[0], SPARK[1], SPARK[2], a * 0.8) if a > 0 else None
    render(cx - s - 4, cy - s - 4, cx + s + 4, cy + s + 4, [fn])


sparkle(212, 318, 26)
sparkle(824, 350, 17)
sparkle(772, 196, 11)

# -------------------------------------------------------------- PNG write ----
def encode_png():
    raw = bytearray()
    prev = bytearray(W * 3)
    for yy in range(H):
        base = yy * W
        row = bytearray(W * 3)
        for xx in range(W):
            i = base + xx
            j = xx * 3
            row[j] = int(clamp01(R[i]) * 255 + 0.5)
            row[j + 1] = int(clamp01(G[i]) * 255 + 0.5)
            row[j + 2] = int(clamp01(B[i]) * 255 + 0.5)
        best = None
        for ftype in (0, 1, 2):
            out = bytearray(W * 3)
            s = 0
            if ftype == 0:
                out[:] = row
                s = sum(b if b < 128 else 256 - b for b in row)
            elif ftype == 1:
                for j in range(W * 3):
                    left = row[j - 3] if j >= 3 else 0
                    v = (row[j] - left) & 0xFF
                    out[j] = v
                    s += v if v < 128 else 256 - v
            else:
                for j in range(W * 3):
                    v = (row[j] - prev[j]) & 0xFF
                    out[j] = v
                    s += v if v < 128 else 256 - v
            if best is None or s < best[0]:
                best = (s, ftype, out)
        raw.append(best[1])
        raw += best[2]
        prev = row

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b""))


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "entry.png"), "wb") as fh:
        fh.write(encode_png())


if __name__ == "__main__":
    main()

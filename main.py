"""Make the best-looking food picture — food-picture-01 entry.

Draws one picture, in code, to /output/entry.png (MAKEFUN_OUTPUT_DIR outside
the grader): a steaming bowl of tonkotsu ramen on a dark walnut table —
chopsticks lifting a glossy bundle of noodles from a golden broth, a jammy
egg, rolled chashu, a sheet of nori, green onions and chilli oil, steam
curling up into warm light.

Pure Python 3.13 standard library only: no network, no clock, no randomness.
The scene is fixed, so two runs write byte-identical output. A minimal PNG
encoder (zlib + per-row filter choice) writes the file; the canvas is drawn
at 2x and box-downsampled for smooth edges.
"""

import math
import os
import struct
import zlib

# ---------------------------------------------------------------- canvas
SS = 2                    # supersampling factor
W, H = 512 * SS, 512 * SS  # working canvas
OW, OH = 512, 512          # output size

buf = bytearray(W * H * 3)


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def blend(fg, bg, a):
    """fg over bg, a in 0..1."""
    return tuple(int(round(fg[i] * a + bg[i] * (1.0 - a))) for i in range(3))


def hspan(y, x0, x1, c):
    """Solid horizontal span in design coords (y, x0, x1 are design px).
    One design row covers SS canvas rows, so fill all of them — filling
    only one would leave every other canvas row black and halve the
    brightness after the 2x2 downsample."""
    y0c = int(round(y * SS))
    x0 = int(round(x0 * SS))
    x1 = int(round(x1 * SS))
    x0 = _clamp(x0, 0, W)
    x1 = _clamp(x1, 0, W)
    if x1 <= x0:
        return
    row = bytes(c) * (x1 - x0)
    for y in range(y0c, min(H, y0c + SS)):
        o = (y * W + x0) * 3
        buf[o:(o + (x1 - x0) * 3)] = row


def vgrad(y0, y1, c_top, c_bot):
    """Vertical gradient over design rows y0..y1."""
    for y in range(int(y0), int(y1) + 1):
        t = (y - y0) / max(1, (y1 - y0))
        hspan(y, 0, OW, lerp(c_top, c_bot, t))


def circle(cx, cy, r, c, alpha=1.0):
    """Filled circle, design coords. alpha<1 blends over what's there."""
    cx, cy, r = cx * SS, cy * SS, r * SS
    if alpha >= 1.0:
        for dy in range(-int(r), int(r) + 1):
            y = int(cy) + dy
            if y < 0 or y >= H:
                continue
            dx = int(math.sqrt(max(0.0, r * r - dy * dy)))
            x0 = int(cx) - dx
            x1 = int(cx) + dx + 1
            x0 = _clamp(x0, 0, W)
            x1 = _clamp(x1, 0, W)
            if x1 > x0:
                o = (y * W + x0) * 3
                buf[o:(o + (x1 - x0) * 3)] = bytes(c) * (x1 - x0)
    else:
        for dy in range(-int(r), int(r) + 1):
            y = int(cy) + dy
            if y < 0 or y >= H:
                continue
            dx = int(math.sqrt(max(0.0, r * r - dy * dy)))
            for x in range(int(cx) - dx, int(cx) + dx + 1):
                if 0 <= x < W:
                    o = (y * W + x) * 3
                    bg = (buf[o], buf[o + 1], buf[o + 2])
                    nc = blend(c, bg, alpha)
                    buf[o], buf[o + 1], buf[o + 2] = nc


def ellipse(cx, cy, rx, ry, c):
    cx, cy, rx, ry = cx * SS, cy * SS, rx * SS, ry * SS
    for dy in range(-int(ry), int(ry) + 1):
        y = int(cy) + dy
        if y < 0 or y >= H:
            continue
        t = 1.0 - (dy * dy) / max(1.0, ry * ry)
        dx = int(rx * math.sqrt(max(0.0, t)))
        x0 = _clamp(int(cx) - dx, 0, W)
        x1 = _clamp(int(cx) + dx + 1, 0, W)
        if x1 > x0:
            o = (y * W + x0) * 3
            buf[o:(o + (x1 - x0) * 3)] = bytes(c) * (x1 - x0)


def poly(points, c):
    """Scanline fill of a polygon (design coords)."""
    pts = [(x * SS, y * SS) for x, y in points]
    if len(pts) < 3:
        return
    ys = [p[1] for p in pts]
    y0, y1 = int(min(ys)), int(max(ys))
    for y in range(max(0, y0), min(H, y1 + 1)):
        yc = y + 0.5
        xs = []
        n = len(pts)
        for i in range(n):
            x0, y0p = pts[i]
            x1, y1p = pts[(i + 1) % n]
            if (y0p <= yc < y1p) or (y1p <= yc < y0p):
                t = (yc - y0p) / (y1p - y0p)
                xs.append(x0 + t * (x1 - x0))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            x0 = _clamp(int(xs[i]), 0, W)
            x1 = _clamp(int(xs[i + 1]) + 1, 0, W)
            if x1 > x0:
                o = (y * W + x0) * 3
                buf[o:(o + (x1 - x0) * 3)] = bytes(c) * (x1 - x0)


def line(x0, y0, x1, y1, w, c):
    """Thick line (design coords, w = design px)."""
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy)
    if L < 1e-6:
        circle(x0, y0, w / 2.0, c)
        return
    nx, ny = -dy / L * w / 2.0, dx / L * w / 2.0
    poly([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny),
          (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)], c)
    circle(x0, y0, w / 2.0, c)
    circle(x1, y1, w / 2.0, c)


def arc(cx, cy, r, a0, a1, w, c):
    """Arc of a circle, angles in degrees, drawn as thick segments."""
    steps = max(4, int(abs(a1 - a0) / 6.0))
    pts = []
    for i in range(steps + 1):
        a = math.radians(a0 + (a1 - a0) * i / steps)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    for i in range(len(pts) - 1):
        line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], w, c)


def radial_glow(cx, cy, r_max, color, a_max):
    """Soft radial glow (design coords). alpha falls off with distance."""
    cx, cy, r_max = cx * SS, cy * SS, r_max * SS
    x0 = _clamp(int(cx - r_max), 0, W)
    x1 = _clamp(int(cx + r_max), 0, W)
    y0 = _clamp(int(cy - r_max), 0, H)
    y1 = _clamp(int(cy + r_max), 0, H)
    for y in range(y0, y1):
        dy = y - cy
        for x in range(x0, x1):
            dx = x - cx
            d = math.sqrt(dx * dx + dy * dy) / r_max
            if d >= 1.0:
                continue
            a = a_max * (1.0 - d) * (1.0 - d)
            o = (y * W + x) * 3
            bg = (buf[o], buf[o + 1], buf[o + 2])
            nc = blend(color, bg, a)
            buf[o], buf[o + 1], buf[o + 2] = nc


def strand(x0, y0, x1, y1, amp, waves, phase, w, c):
    """One wavy noodle strand from (x0,y0) to (x1,y1), design coords."""
    steps = 14
    px, py = x0, y0
    for i in range(1, steps + 1):
        t = i / steps
        # perpendicular wiggle: sine along the path
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / L, dx / L
        s = amp * math.sin(2.0 * math.pi * waves * t + phase)
        x = x0 + dx * t + nx * s
        y = y0 + dy * t + ny * s
        line(px, py, x, y, w, c)
        px, py = x, y


def steam_column(cx, y_top, y_bot, amp, alpha):
    """A rising wisp of steam: many heavily-overlapping soft white
    ellipses with a slow sine sway, so the column reads as one soft
    wisp instead of a stack of separate bubbles."""
    steps = 30
    for i in range(steps):
        t = i / (steps - 1)
        y = y_bot + (y_top - y_bot) * t
        x = cx + amp * math.sin(1.6 * math.pi * t + 0.6)
        r = 15 + 6 * math.sin(math.pi * t)
        circle(x, y, r, (255, 255, 255), alpha * (0.6 + 0.6 * t))


# ---------------------------------------------------------------- palette
TABLE_TOP = (66, 44, 30)
TABLE_BOT = (36, 23, 15)
PLANK = (50, 32, 21)
SHADOW = (24, 14, 8)
BOWL_RED = (122, 28, 28)
BOWL_DARK = (84, 18, 18)
BOWL_HI = (184, 64, 50)
RIM = (245, 235, 215)
RIM_INNER = (140, 30, 28)
BROTH = (232, 178, 92)
BROTH_D = (212, 148, 64)
BROTH_L = (246, 206, 132)
OIL = (198, 128, 38)
NOODLE = (244, 214, 140)
NOODLE_D = (226, 186, 102)
NOODLE_HI = (255, 236, 180)
EGG_W = (250, 246, 235)
YOLK = (242, 146, 44)
YOLK_L = (252, 176, 66)
CHASHU = (214, 140, 110)
CHASHU_FAT = (232, 196, 160)
CHASHU_D = (150, 80, 60)
NORI = (26, 40, 28)
NORI_HI = (64, 86, 64)
ONION = (90, 160, 70)
ONION_L = (162, 212, 122)
CHILI = (198, 58, 30)
STICK = (190, 140, 80)
STICK_D = (148, 102, 52)
SESAME = (250, 240, 220)


# ------------------------------------------------------------------ scene
def draw_scene():
    # --- dark walnut table
    vgrad(0, 512, TABLE_TOP, TABLE_BOT)
    for y in (128, 256, 384):
        hspan(y, 0, OW, PLANK)
        hspan(y + 2, 0, OW, (72, 48, 32))
    # soft dark corners (vignette) so the bowl glows in the middle
    for (cx, cy) in [(0, 0), (512, 0), (0, 512), (512, 512)]:
        circle(cx, cy, 210, (18, 10, 6), 0.20)
    # warm light from the upper left
    radial_glow(120, 60, 320, (255, 196, 120), 0.10)

    # --- shadow under the bowl
    ellipse(256, 428, 196, 20, SHADOW)

    # --- nori sheet standing at the back of the bowl
    poly([(188, 272), (188, 164), (282, 164), (282, 272)], NORI)
    line(200, 172, 200, 264, 3, NORI_HI)
    line(266, 172, 266, 264, 3, NORI_HI)

    # --- bowl body (lacquer red): deep, so it reads as a bowl, not a plate
    ellipse(256, 344, 168, 80, BOWL_RED)
    ellipse(256, 412, 80, 15, BOWL_DARK)
    # soft light on the body's left flank (a glow, not a hard arc)
    radial_glow(140, 350, 95, (200, 80, 60), 0.22)

    # --- rim: cream band, then thin red inner band, then golden broth
    ellipse(256, 300, 186, 68, RIM)
    ellipse(256, 300, 170, 60, RIM_INNER)
    ellipse(256, 300, 158, 54, BROTH)

    # --- broth: wavy swirls and noodle strands, all kept inside the
    #     broth ellipse (circular arcs would spill over the rim)
    strand(150, 272, 250, 288, 4, 2, 0.0, 6, BROTH_D)
    strand(160, 330, 262, 338, 4, 2, 1.2, 6, BROTH_L)
    strand(300, 268, 380, 292, 4, 2, 2.0, 6, BROTH_D)
    # wavy noodle strands lying in the broth
    strand(128, 288, 238, 304, 3.5, 2, 0.0, 6, NOODLE_D)
    strand(134, 308, 244, 320, 3.5, 2, 1.4, 6, NOODLE)
    strand(142, 326, 248, 332, 3.5, 2, 2.6, 6, NOODLE_D)
    strand(378, 292, 302, 314, 3.5, 2, 0.8, 6, NOODLE)
    strand(380, 314, 308, 328, 3.5, 2, 2.0, 6, NOODLE_D)
    # glossy oil droplets on the broth
    for (x, y, r) in [(210, 268, 5), (300, 262, 4), (352, 276, 5),
                      (150, 296, 4), (396, 306, 4), (240, 336, 5)]:
        circle(x, y, r, OIL)
        circle(x - 1, y - 1, 1.6, (255, 220, 140))

    # --- jammy egg, front-left (white + glossy orange yolk)
    ellipse(178, 292, 36, 27, EGG_W)
    circle(178, 292, 19, YOLK)
    circle(178, 292, 12, YOLK_L)
    circle(174, 287, 4, (255, 236, 190))

    # --- rolled chashu, front-right (two overlapping slices)
    for (cx, cy, r) in [(332, 296, 30), (360, 308, 24)]:
        circle(cx, cy, r, CHASHU)
        circle(cx, cy, int(r * 0.72), CHASHU_FAT)
        circle(cx, cy, int(r * 0.44), CHASHU_D)
        circle(cx, cy, int(r * 0.20), CHASHU_FAT)
        circle(cx - r * 0.3, cy - r * 0.3, 3, (255, 220, 200))

    # --- green onion rings scattered on the broth
    for (x, y) in [(216, 318), (248, 268), (306, 336), (338, 262),
                   (384, 292), (150, 316), (268, 340), (322, 322)]:
        circle(x, y, 5, ONION)
        circle(x, y, 2.4, ONION_L)
    # chilli oil dots
    for (x, y) in [(228, 286), (290, 272), (372, 318), (168, 330)]:
        circle(x, y, 3.4, CHILI)

    # --- the noodle lift: a wide curtain of glossy strands draped from
    #     the chopsticks down into the broth, right of centre. The strands
    #     stay mostly parallel (small wiggle) so the bundle reads as
    #     noodles being lifted, not a tangled knot.
    for (off, ph, col) in [
            (-24, 0.0, NOODLE_D), (-17, 1.1, NOODLE), (-10, 2.2, NOODLE_HI),
            (-3, 0.6, NOODLE), (4, 1.8, NOODLE_D), (11, 2.9, NOODLE),
            (18, 0.9, NOODLE_HI), (24, 1.5, NOODLE)]:
        strand(336 + off, 205, 314 + off, 300, 4.5, 1.0, ph, 7, col)
    # a loose strand slipping back into the soup
    strand(362, 222, 350, 296, 8, 1.2, 0.4, 6, NOODLE_D)

    # --- chopsticks gripping the bundle, from the upper right, drawn
    #     over the strands so they read as holding them
    line(440, 110, 334, 203, 9, STICK)
    line(452, 126, 344, 211, 9, STICK)
    line(440, 110, 334, 203, 3, STICK_D)
    circle(334, 203, 4.5, STICK_D)
    circle(344, 211, 4.5, STICK_D)

    # --- steam curling up above the bowl
    steam_column(208, 78, 272, 14, 0.09)
    steam_column(256, 62, 268, 18, 0.10)
    steam_column(302, 80, 272, 14, 0.09)
    radial_glow(256, 150, 150, (255, 250, 235), 0.10)

    # --- a few sesame seeds and onion rings on the table
    for (x, y) in [(330, 424), (352, 430), (314, 434), (368, 418)]:
        ellipse(x, y, 3.2, 2.0, SESAME)
    for (x, y) in [(150, 430), (168, 442), (128, 446)]:
        circle(x, y, 4, ONION)
        circle(x, y, 1.8, ONION_L)

    # --- final warm light wash over the whole scene
    radial_glow(150, 80, 300, (255, 205, 120), 0.08)


# ------------------------------------------------------------------ PNG
def _crc(data):
    return struct.pack('>I', zlib.crc32(data) & 0xFFFFFFFF)


def _chunk(typ, data):
    return struct.pack('>I', len(data)) + typ + data + _crc(typ + data)


def _filter_row(f, row, prev, bpp=3):
    n = len(row)
    out = bytearray(n)
    if f == 0:
        return bytes(row)
    if f == 1:  # Sub
        for i in range(n):
            left = row[i - bpp] if i >= bpp else 0
            out[i] = (row[i] - left) & 0xFF
    elif f == 2:  # Up
        for i in range(n):
            out[i] = (row[i] - prev[i]) & 0xFF
    elif f == 4:  # Paeth
        for i in range(n):
            a = row[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            p = a + b - c
            pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
            pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
            out[i] = (row[i] - pr) & 0xFF
    return bytes(out)


def _score(filtered):
    return sum((b - 256) if b > 127 else b for b in filtered)


def write_png(rgb, w, h):
    raw = bytearray()
    prev = bytes(w * 3)
    for y in range(h):
        row = rgb[y * w * 3:(y + 1) * w * 3]
        best = None
        for f in (0, 2, 4):
            fr = _filter_row(f, row, prev)
            s = _score(fr)
            if best is None or s < best[0]:
                best = (s, f, fr)
        raw.append(best[1])
        raw += best[2]
        prev = row
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)
    return (b'\x89PNG\r\n\x1a\n' + _chunk(b'IHDR', ihdr)
            + _chunk(b'IDAT', zlib.compress(bytes(raw), 9))
            + _chunk(b'IEND', b''))


def downsample():
    """2x2 box average of the 1024 canvas down to 512x512."""
    out = bytearray(OW * OH * 3)
    for oy in range(OH):
        sy = oy * SS
        for ox in range(OW):
            sx = ox * SS
            i00 = (sy * W + sx) * 3
            i01 = i00 + 3
            i10 = ((sy + 1) * W + sx) * 3
            i11 = i10 + 3
            o = (oy * OW + ox) * 3
            out[o] = (buf[i00] + buf[i01] + buf[i10] + buf[i11]) >> 2
            out[o + 1] = (buf[i00 + 1] + buf[i01 + 1] + buf[i10 + 1] + buf[i11 + 1]) >> 2
            out[o + 2] = (buf[i00 + 2] + buf[i01 + 2] + buf[i10 + 2] + buf[i11 + 2]) >> 2
    return out


def main():
    draw_scene()
    rgb = downsample()
    data = write_png(rgb, OW, OH)
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "entry.png"), "wb") as f:
        f.write(data)


if __name__ == "__main__":
    main()

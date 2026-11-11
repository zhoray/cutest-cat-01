"""A tiny, deterministic supersampled kitten portrait renderer."""

import os
import struct
import zlib

SIZE = 1024
SCALE = 2
W = SIZE * SCALE
PIXELS = bytearray(W * W * 3)


def blend(x, y, color, alpha=255):
    if x < 0 or y < 0 or x >= W or y >= W:
        return
    i = (y * W + x) * 3
    if alpha == 255:
        PIXELS[i:i + 3] = bytes(color)
    else:
        inv = 255 - alpha
        PIXELS[i] = (PIXELS[i] * inv + color[0] * alpha) // 255
        PIXELS[i + 1] = (PIXELS[i + 1] * inv + color[1] * alpha) // 255
        PIXELS[i + 2] = (PIXELS[i + 2] * inv + color[2] * alpha) // 255


def ellipse(cx, cy, rx, ry, color, alpha=255):
    x0, x1 = max(0, int(cx - rx)), min(W, int(cx + rx + 1))
    y0, y1 = max(0, int(cy - ry)), min(W, int(cy + ry + 1))
    for y in range(y0, y1):
        dy = (y + 0.5 - cy) / ry
        for x in range(x0, x1):
            dx = (x + 0.5 - cx) / rx
            d = dx * dx + dy * dy
            if d <= 1:
                edge = min(1.0, max(0.0, (1.0 - d) * min(rx, ry) * 0.8))
                blend(x, y, color, int(alpha * edge))


def polygon(points, color, alpha=255):
    pts = [(int(x), int(y)) for x, y in points]
    ymin = max(0, min(y for _, y in pts))
    ymax = min(W - 1, max(y for _, y in pts))
    for y in range(ymin, ymax + 1):
        scan = y + 0.5
        crosses = []
        for i, (x1, y1) in enumerate(pts):
            x2, y2 = pts[(i + 1) % len(pts)]
            if (y1 <= scan < y2) or (y2 <= scan < y1):
                crosses.append(x1 + (scan - y1) * (x2 - x1) / (y2 - y1))
        crosses.sort()
        for j in range(0, len(crosses), 2):
            left, right = max(0, int(crosses[j])), min(W - 1, int(crosses[j + 1]))
            for x in range(left, right + 1):
                blend(x, y, color, alpha)


def line(x1, y1, x2, y2, color, width, alpha=255):
    steps = max(1, int(max(abs(x2 - x1), abs(y2 - y1))))
    radius = width / 2
    for n in range(steps + 1):
        t = n / steps
        ellipse(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t,
                radius, radius, color, alpha)


def S(v):
    return v * SCALE


def draw():
    for y in range(W):
        for x in range(W):
            dx, dy = (x - W * 0.48) / W, (y - W * 0.43) / W
            d = min(1.0, (dx * dx + dy * dy) ** 0.5 * 1.7)
            c = (int(255 - 7 * d), int(246 - 20 * d), int(225 - 24 * d))
            i = (y * W + x) * 3
            PIXELS[i:i + 3] = bytes(c)

    for x, y, r in [(115, 210, 7), (870, 190, 5), (130, 720, 5),
                    (900, 735, 7), (815, 390, 4), (205, 410, 4)]:
        ellipse(S(x), S(y), S(r), S(r), (255, 255, 255), 105)
    for x, y in [(160, 330), (865, 570), (780, 250), (245, 650)]:
        line(S(x - 7), S(y), S(x + 7), S(y), (255, 255, 255), S(2), 150)
        line(S(x), S(y - 7), S(x), S(y + 7), (255, 255, 255), S(2), 150)

    polygon([(S(205), S(374)), (S(225), S(75)), (S(455), S(292))], (235, 172, 111))
    polygon([(S(819), S(374)), (S(799), S(75)), (S(569), S(292))], (235, 172, 111))
    ellipse(S(225), S(83), S(11), S(14), (235, 172, 111))
    ellipse(S(799), S(83), S(11), S(14), (235, 172, 111))
    polygon([(S(250), S(319)), (S(262), S(136)), (S(406), S(291))], (239, 158, 157))
    polygon([(S(774), S(319)), (S(762), S(136)), (S(618), S(291))], (239, 158, 157))

    # A faint warm shadow gives the plush silhouette depth without a hard rim.
    ellipse(S(512), S(528), S(331), S(346), (222, 180, 139), 55)
    ellipse(S(512), S(520), S(325), S(338), (255, 239, 205))
    # Rounded cheek fullness and a soft chin shadow replace the low pale patch.
    ellipse(S(405), S(626), S(112), S(92), (255, 245, 222), 155)
    ellipse(S(619), S(626), S(112), S(92), (255, 245, 222), 155)
    ellipse(S(512), S(706), S(118), S(37), (222, 180, 139), 32)

    ellipse(S(512), S(302), S(144), S(75), (244, 190, 126), 115)
    for x, lean in [(460, -13), (512, 0), (564, 13)]:
        line(S(x), S(218), S(x + lean), S(300), (216, 145, 86), S(9), 88)

    for cx in (390, 634):
        ellipse(S(cx), S(482), S(79), S(91), (226, 185, 132))
        ellipse(S(cx), S(481), S(72), S(84), (43, 112, 111))
        ellipse(S(cx), S(490), S(54), S(65), (25, 78, 83))
        ellipse(S(cx), S(499), S(34), S(44), (17, 48, 59))
        ellipse(S(cx - 20), S(452), S(22), S(25), (255, 255, 249))
        ellipse(S(cx + 24), S(510), S(9), S(10), (222, 250, 240))
        ellipse(S(cx - 21), S(452), S(8), S(9), (255, 255, 255))
        if cx < 500:
            line(S(320), S(426), S(300), S(413), (120, 83, 68), S(5))
        else:
            line(S(704), S(426), S(724), S(413), (120, 83, 68), S(5))

    ellipse(S(320), S(611), S(68), S(36), (246, 157, 157), 82)
    ellipse(S(704), S(611), S(68), S(36), (246, 157, 157), 82)
    ellipse(S(459), S(610), S(71), S(48), (255, 249, 234))
    ellipse(S(565), S(610), S(71), S(48), (255, 249, 234))
    polygon([(S(512), S(565)), (S(487), S(586)), (S(512), S(601)), (S(537), S(586))],
            (236, 139, 151))
    ellipse(S(506), S(575), S(4), S(3), (255, 214, 214))
    line(S(512), S(600), S(512), S(619), (126, 83, 76), S(4))
    line(S(512), S(619), S(496), S(632), (126, 83, 76), S(4))
    line(S(496), S(632), S(482), S(620), (126, 83, 76), S(4))
    line(S(512), S(619), S(528), S(632), (126, 83, 76), S(4))
    line(S(528), S(632), S(542), S(620), (126, 83, 76), S(4))

    for side in (-1, 1):
        for j, yy in enumerate((593, 620, 647)):
            x1 = 445 if side < 0 else 579
            x2 = 282 if side < 0 else 742
            line(S(x1), S(yy), S(x2), S(yy + (j - 1) * 12),
                 (183, 143, 112), S(2), 145)

    polygon([(S(706), S(240)), (S(659), S(211)), (S(662), S(266))], (239, 133, 139))
    polygon([(S(714), S(240)), (S(762), S(211)), (S(758), S(266))], (239, 133, 139))
    ellipse(S(711), S(240), S(12), S(12), (255, 190, 166))
    ellipse(S(711), S(240), S(5), S(5), (255, 228, 200))
    for x, y in [(775, 188), (786, 289)]:
        line(S(x - 5), S(y), S(x + 5), S(y), (255, 255, 255), S(2), 190)
        line(S(x), S(y - 5), S(x), S(y + 5), (255, 255, 255), S(2), 190)


def png_bytes():
    raw = bytearray()
    for y in range(SIZE):
        raw.append(0)
        sy = y * 2
        for x in range(SIZE):
            i = (sy * W + x * 2) * 3
            j, k, m = i + 3, i + W * 3, i + W * 3 + 3
            raw.extend(((PIXELS[i] + PIXELS[j] + PIXELS[k] + PIXELS[m]) // 4,
                        (PIXELS[i + 1] + PIXELS[j + 1] + PIXELS[k + 1] + PIXELS[m + 1]) // 4,
                        (PIXELS[i + 2] + PIXELS[j + 2] + PIXELS[k + 2] + PIXELS[m + 2]) // 4))

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xffffffff)

    return (b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 2, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(bytes(raw), 9)) +
            chunk(b"IEND", b""))


def main():
    draw()
    output = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(output, exist_ok=True)
    with open(os.path.join(output, "entry.png"), "wb") as f:
        f.write(png_bytes())


if __name__ == "__main__":
    main()

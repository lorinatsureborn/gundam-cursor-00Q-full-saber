# -*- coding: utf-8 -*-
"""
最小示例：造几个几何图形当素材，然后打包成一套能用两下的指针。

    python examples/minimal/make_art.py     # 生成 art/
    python -m cursorforge build examples/minimal/spec.json
    python -m cursorforge verify examples/minimal/out

用几何图形而不是美术素材，是为了让这个示例**自包含** ——
clone 下来就能跑，不需要任何外部图片。
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ART = HERE / "art"

WHITE = (238, 238, 234, 255)
GREY = (150, 152, 156, 255)
BLUE = (74, 83, 188, 255)
DARK = (26, 28, 40, 255)


def canvas(S):
    return Image.new("RGBA", (S, S), (0, 0, 0, 0))


def arrow(S=256):
    im = canvas(S)
    d = ImageDraw.Draw(im)
    d.polygon([(14, 10), (14, S - 60), (S // 3, S - 110),
               (S - 40, S - 40), (S // 3, S // 3)], fill=BLUE, outline=DARK,
              width=6)
    return im


def crosshair(S=256):
    im = canvas(S)
    d = ImageDraw.Draw(im)
    m = S // 2
    for a, b in (((m, 10), (m, S - 10)), ((10, m), (S - 10, m))):
        d.line([a, b], fill=WHITE, width=14)
        d.line([a, b], fill=DARK, width=4)
    d.ellipse([m - 26, m - 26, m + 26, m + 26], fill=GREY, outline=DARK, width=5)
    return im


def spinner(S=256, phase=0.0):
    """会转的十字 —— 演示逐帧动画。"""
    import math
    im = canvas(S)
    d = ImageDraw.Draw(im)
    m = S // 2
    a = phase * 2 * math.pi
    for k in range(4):
        th = a + k * math.pi / 2
        x, y = m + math.cos(th) * m * 0.82, m + math.sin(th) * m * 0.82
        d.line([(m, m), (x, y)], fill=WHITE, width=26)
        d.line([(m, m), (x, y)], fill=DARK, width=8)
    d.ellipse([m - 30, m - 30, m + 30, m + 30], fill=BLUE, outline=DARK, width=6)
    return im


def hand(S=256):
    """指向手 —— 演示热点在食指尖。"""
    im = canvas(S)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([S * 0.30, S * 0.06, S * 0.42, S * 0.48],
                        radius=S * 0.03, fill=GREY, outline=DARK, width=5)
    d.rounded_rectangle([S * 0.26, S * 0.42, S * 0.76, S * 0.80],
                        radius=S * 0.05, fill=WHITE, outline=DARK, width=5)
    d.rounded_rectangle([S * 0.22, S * 0.76, S * 0.80, S * 0.92],
                        radius=S * 0.04, fill=BLUE, outline=DARK, width=5)
    return im


def main():
    ART.mkdir(exist_ok=True)
    (ART / "frames").mkdir(exist_ok=True)
    arrow().save(ART / "arrow.png")
    crosshair().save(ART / "crosshair.png")
    hand().save(ART / "hand.png")
    T = 12
    for t in range(T):
        spinner(phase=t / T).save(ART / "frames" / ("work_%02d.png" % t))
    print("生成 %d 个文件 -> %s" % (4 + T, ART))
    return 0


if __name__ == "__main__":
    sys.exit(main())

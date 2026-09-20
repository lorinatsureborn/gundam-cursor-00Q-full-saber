# -*- coding: utf-8 -*-
"""
多档位打包的纪律层：缩放、逐档描边、热点。

★★ 这个文件里只有一条核心规矩，但它在这个项目里被踩了 **6 次**：

    **一切以像素计的尺寸，必须在"该档自己的分辨率"上算。**

缩放在最后做，所以描边宽 / 模糊半径 / 粒子半径 / 刻线宽 / 位移动画幅度
统统不能在母版上定死：

  ⛔ 512 母版上画 6px 描边 → 缩到 32px 只剩 0.38px，再被 LANCZOS 一平均 = 灰雾
  ⛔ 3px 的粒子缩到 32px 只剩 0.19px → **直接消失**
  ⛔ 4× 超采样画布上 2px 的线，缩回 1× 只剩 **0.5px** → 刻线糊没

✅ 正确做法：**先缩到该档，再按该档的像素画**。32px 要的就是实打实 1px。
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter

__all__ = ["TIER_OUTLINE", "OUTLINE_RGB", "hotspot", "tier_outline",
           "static_tiers", "fit"]

#: 描边宽（**按该档实际像素**）
TIER_OUTLINE = {256: 4, 128: 3, 96: 2, 64: 2, 48: 1, 32: 1}
#: 静态 `.cur` 可用的档位（`.ani` 用 [96, 64, 48, 32]，见 ani.ICON_CHUNK_LIMIT）
CUR_SIZES = [256, 128, 96, 64, 48, 32]
OUTLINE_RGB = (12, 14, 18)


def hotspot(img: Image.Image, mode: str = "c"):
    """
    热点位置。`mode`：

        "c"    正中（十字 / 双向箭头 / I 型）
        "ul"   x+y 最小 = **左上**尖端（箭头 / 笔）
        "ll"   x−y 最小 = **左下**尖端（钢笔角度的手持物）
        "top"  最上一行的中点 = **食指尖**（Hand 类）

    ⚠️ **热点要逐档算**（每档取自己那张图的极值点），不要从大档等比缩 ——
       小档的极值点和大档未必在同一个相对位置。
    """
    a = np.asarray(img.convert("RGBA"))[..., 3]
    ys, xs = np.nonzero(a > 16)
    if not len(xs):
        return img.width // 2, img.height // 2
    if mode == "ul":
        k = int(np.argmin(xs.astype(np.int64) + ys))
        return int(xs[k]), int(ys[k])
    if mode == "ll":
        k = int(np.argmin(xs.astype(np.int64) - ys))
        return int(xs[k]), int(ys[k])
    if mode == "top":
        y0 = int(ys.min())
        return int(round(xs[ys == y0].mean())), y0
    return img.width // 2, img.height // 2


def tier_outline(img: Image.Image, width=None, color=OUTLINE_RGB) -> Image.Image:
    """
    在**该档的实际像素**上描一圈边（画在 alpha 之外，不侵占主体）。

    ⚠️ 判据是 `alpha > 100`。**如果主体带发光且峰值越过 100，
       描边会画在光晕的外缘**上 —— 一圈浮在雾里的黑环。
       要么把光压到阈值以下，要么这一格豁免描边（见 `static_tiers(outline=False)`）。
    """
    w = TIER_OUTLINE.get(img.width, 1) if width is None else width
    if w <= 0:
        return img
    a = np.asarray(img)[..., 3]
    m = Image.fromarray((a > 100).astype(np.uint8) * 255)
    k = 2 * w + 1
    ring = (np.asarray(m.filter(ImageFilter.MaxFilter(k))).astype(np.int16) -
            np.asarray(m).astype(np.int16))
    ring = np.clip(ring, 0, 255).astype(np.uint8)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(Image.new("RGBA", img.size, tuple(color) + (255,)), (0, 0),
              Image.fromarray(ring))
    out.alpha_composite(img)
    return out


def fit(master: Image.Image, size: int, fill: float = 0.94) -> Image.Image:
    """
    等比缩进 size×size 的空画布并居中。

    ⚠️ **`fill` 别给到 1.0** —— 主体顶到画布边缘时，`tier_outline` 的边会被裁掉
       （实测：刃尖落在 x=0 上，暗边直接出界）。
       0.94 是留出描边余量的经验值。
    """
    t = master.copy()
    t.thumbnail((max(1, int(size * fill)),) * 2, Image.LANCZOS)
    cv = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cv.paste(t, ((size - t.width) // 2, (size - t.height) // 2), t)
    return cv


def static_tiers(master: Image.Image, sizes=None, outline=True,
                 outline_map=None) -> list:
    """
    母版 → 各档（**逐档描边**）。

    outline=False 用于"带发光、不能描边"的格子
    outline_map   可覆盖某档的描边宽，如 `{32: 0}` 表示 32px 档不描边
    """
    tiers = []
    for s in (sizes or CUR_SIZES):
        cv = fit(master, s)
        if outline:
            w = None if outline_map is None else outline_map.get(s)
            if w == 0:
                tiers.append(cv)
            else:
                tiers.append(tier_outline(cv, w))
        else:
            tiers.append(cv)
    return tiers

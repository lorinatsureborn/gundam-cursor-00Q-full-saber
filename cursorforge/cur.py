# -*- coding: utf-8 -*-
"""
`.cur` 读写（Windows 静态指针）。

    .cur = ICO 结构 + 热点

★ **`.cur` 和 `.ico` 唯一的区别**：热点 X/Y 写在 `ICONDIRENTRY` 的
  `wPlanes` / `wBitCount` 字段里（`.ico` 那里写的是 1 / 32）。

    ICONDIR      6 B    reserved=0, type=2, count=N
    ICONDIRENTRY 16 B × N
      bWidth bHeight       宽高，**256 写作 0**
      bColorCount bReserved
      wPlanes              ← 热点 X
      wBitCount            ← 热点 Y
      dwBytesInRes dwImageOffset
    图像数据 × N

图像数据两种存法：

    宽 ≥ 128   **PNG**（直接嵌 PNG 字节流，Vista+ 支持，有 alpha、体积小）
    宽 <  128  **BMP**（BITMAPINFOHEADER + 自下而上 BGRA + AND 掩码）

⚠️ **静态 `.cur` 没有 `.ani` 那个 69632 B/块的限制**，所以可以放满六档。
"""
from __future__ import annotations

import io
import struct

import numpy as np
from PIL import Image

__all__ = ["bmp32", "cur_bytes", "cur_with_hotspot", "write_cur", "read_cur"]


def bmp32(img: Image.Image) -> bytes:
    """
    BITMAPINFOHEADER + **自下而上** BGRA + AND 掩码（32bpp）。

    两个最容易写错的点（写错的表现是**图像上下颠倒 + 红蓝互换**）：

    ① BMP 是**自下而上**存的，而且通道顺序是 **BGRA 不是 RGBA**。
    ② AND 掩码是**每像素 1 位**（不是 1 字节）：先把列按 8 个一组打包，
       再补到 4 字节对齐的 stride。
    """
    w, h = img.size
    a = np.asarray(img.convert("RGBA"), np.uint8)
    xor = np.ascontiguousarray(a[::-1][..., [2, 1, 0, 3]]).tobytes()

    stride = ((w + 31) // 32) * 4
    bits = (a[..., 3] < 128)[::-1].astype(np.uint8)
    nb = (w + 7) // 8
    bits = np.concatenate([bits, np.zeros((h, nb * 8 - w), np.uint8)], axis=1)
    packed = (bits.reshape(h, nb, 8) << np.arange(7, -1, -1)).sum(axis=2)
    mask = np.zeros((h, stride), np.uint8)
    mask[:, :nb] = packed.astype(np.uint8)

    return (struct.pack("<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0,
                        w * h * 4, 0, 0, 0, 0)
            + xor + mask.tobytes())


def cur_bytes(tiers) -> bytes:
    """
    tiers = [(PIL.Image, (hot_x, hot_y)), ...] —— 每档**自带热点**，全用 BMP。

    需要"大档用 PNG"就用 `cur_with_hotspot()`。
    """
    blocks = [bmp32(img) for img, _hot in tiers]
    return _assemble([(img.size, hot, blk)
                      for (img, hot), blk in zip(tiers, blocks)])


def cur_with_hotspot(tiers, hotspot, master_size: int, png_min: int = 128) -> bytes:
    """
    多档打包，**热点只给一个**，按档位等比缩放。

    tiers      [PIL.Image, ...] 从大到小
    hotspot    (x, y) 在 master_size 那张图上的坐标
    png_min    宽 ≥ 此值的档用 PNG，其余用 BMP
    """
    items = []
    for t in tiers:
        if t.width >= png_min:
            buf = io.BytesIO()
            t.save(buf, format="PNG", optimize=True)
            blk = buf.getvalue()
        else:
            blk = bmp32(t)
        w, h = t.size
        hx = min(round(hotspot[0] / master_size * w), w - 1)
        hy = min(round(hotspot[1] / master_size * h), h - 1)
        items.append(((w, h), (hx, hy), blk))
    return _assemble(items)


def _assemble(items) -> bytes:
    n = len(items)
    entries, off = bytearray(), 6 + 16 * n
    for (w, h), (hx, hy), blk in items:
        entries += struct.pack("<BBBBHHII", w % 256, h % 256, 0, 0, hx, hy,
                               len(blk), off)
        off += len(blk)
    return struct.pack("<HHH", 0, 2, n) + bytes(entries) + b"".join(
        blk for _s, _h, blk in items)


def write_cur(path, tiers, hotspot=None, master_size=None, png_min: int = 128):
    """便捷入口：给了 hotspot+master_size 就等比缩放，否则 tiers 必须自带热点。"""
    if hotspot is not None and master_size is not None:
        data = cur_with_hotspot(tiers, hotspot, master_size, png_min)
    else:
        data = cur_bytes(tiers)
    with open(path, "wb") as f:
        f.write(data)
    return len(data)


def read_cur(source):
    """
    读回 `.cur` 做复验。source 可以是路径或 bytes。

    返回 [(size, PIL.Image, (hx, hy)), ...]

    ★ **成品必须从容器里读回来验** —— 源图对不代表 `.cur` 里对。
    """
    blob = source if isinstance(source, (bytes, bytearray)) else \
        open(source, "rb").read()
    _res, typ, n = struct.unpack("<HHH", blob[:6])
    if typ != 2:
        raise ValueError("不是 .cur（type=%d）" % typ)
    out = []
    for i in range(n):
        e = blob[6 + 16 * i:6 + 16 * (i + 1)]
        # ICONDIRENTRY 16 B：
        #   [0]bW [1]bH [2]bColorCount [3]bReserved
        #   [4:6]wPlanes(=热点X) [6:8]wBitCount(=热点Y)
        #   [8:12]dwBytesInRes [12:16]dwImageOffset
        w = e[0] or 256
        hx, hy = struct.unpack("<HH", e[4:8])
        size, off = struct.unpack("<II", e[8:16])
        blk = blob[off:off + size]
        if blk[:8] == b"\x89PNG\r\n\x1a\n":
            im = Image.open(io.BytesIO(blk)).convert("RGBA")
        else:
            im = _read_bmp32(blk)
        out.append(((w, im.height), im, (hx, hy)))
    return out


def _read_bmp32(blk: bytes) -> Image.Image:
    """自下而上 BGRA → 正立的 RGBA。"""
    hdr = struct.unpack("<IiiHHIIiiII", blk[:40])
    bw, bh = hdr[1], hdr[2] // 2          # biHeight 是双倍高（含 AND 掩码）
    px = blk[40:40 + bw * bh * 4]
    buf = bytearray(bw * bh * 4)
    for y in range(bh):
        row = px[y * bw * 4:(y + 1) * bw * 4]
        base = (bh - 1 - y) * bw * 4
        for x in range(bw):
            b, g, r, a = row[x * 4:x * 4 + 4]
            j = base + x * 4
            buf[j], buf[j + 1], buf[j + 2], buf[j + 3] = r, g, b, a
    return Image.frombytes("RGBA", (bw, bh), bytes(buf))

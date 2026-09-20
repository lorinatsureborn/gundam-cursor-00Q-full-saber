# -*- coding: utf-8 -*-
"""
`.ani` 读写（Windows 动画指针）。

    RIFF....ACON
      anih   36 B   cbSize=36, nFrames, nSteps, iWidth, iHeight, ...
      rate   N×4B   每帧的 jiffy（**1 jiffy = 1/60 s**）
      LIST fram
        icon  ← ★ 每个 icon 块 = 一张**完整的、含全部档位的多分辨率 .cur**
        icon
        ...

★★ 两个必须记住的事实：

**① `.ani` 不是"每帧一张 32px 图"，而是每帧一个完整的多分辨率 `.cur`。**
   所以 4 档 × 32 帧 = 128 张位图。体积就是这么来的。

**② 每个 icon 块有上限（实测 ~66 KB，取 64 KB 作安全线）。** 超了不报错，只是**加载不出**。

       .ani 体积 ≈ 帧数 × 档数 × 68.7 KB
       32 帧 × 4 档 → 约 2.2 MB / 个指针

   要瘦身只有两条路，都会改动视觉：

       减帧数 32→16          体积减半，但动画周期快一倍
       减档位 4→3（削 96 档） 降 25%，大屏下略糊

**帧率**：`jiffy=4` ⇒ 15 fps。**想让动画变慢请加帧数，不要加大 jiffy** ——
`16 帧 × jiffy 8` = 7.5 fps，肉眼可见地一顿一顿；
`32 帧 × jiffy 4` = 2.13 s 一轮，顺。
"""
from __future__ import annotations

import struct

__all__ = ["chunk", "ani_bytes", "write_ani", "read_ani", "dump_ani",
           "cur_pixels", "ICON_CHUNK_LIMIT", "ICON_PIXEL_LIMIT"]

#: 每个 icon 块的**字节**上限。实测全 BMP 的 68,966 B 能加载 ⇒ 取 69,632。
ICON_CHUNK_LIMIT = 69632

#: ★ 每个 icon 块的**解码后总像素**上限。
#:
#: 只查字节是不够的 —— 实测数据里有一条**矛盾**：
#:
#:     全 BMP  96,64,48,32      68,966 B / 16,640 px  → ✅
#:     全 PNG  256..48          66,115 B / 97,536 px  → ✅
#:     全 PNG  256..32          67,548 B / 98,560 px  → ❌
#:
#: BMP 的字节更多却过了、PNG 的更少却没过 ⇒ **不是单看字节**。
#: 加上"解码后总像素"这条线，五个用例全部解释得通，
#: 阈值落在 (97,536, 98,560]，很接近 **96×1024 = 98,304**。取 96,000 作安全线。
ICON_PIXEL_LIMIT = 96000


def cur_pixels(blob: bytes) -> int:
    """数一个 `.cur` 字节流里**所有档的宽高乘积之和**（= 解码后的总像素）。"""
    n = struct.unpack("<H", blob[4:6])[0]
    tot = 0
    for i in range(n):
        e = blob[6 + 16 * i:6 + 16 * (i + 1)]
        tot += (e[0] or 256) * (e[1] or 256)
    return tot


def chunk(name: bytes, payload: bytes) -> bytes:
    """RIFF chunk：id + size + payload + **奇数长度补 1 字节**。"""
    return name + struct.pack("<I", len(payload)) + payload + (
        b"\x00" if len(payload) % 2 else b"")


def ani_bytes(cur_blobs, jiffy: int = 4, iwidth: int = 0, iheight: int = 0) -> bytes:
    """
    cur_blobs  每帧一个**完整的 `.cur` 字节流**（不是单张位图）
    jiffy      1 = 1/60 s

    ⚠️ `iWidth` / `iHeight` 写 0 是**正常的** ——
       Windows 自带的 `aero_working.ani` 也是 0，尺寸由 icon 块自己声明。
    """
    n = len(cur_blobs)
    if n == 0:
        raise ValueError("至少要一帧")
    # ⚠️ **两条线都要查**：字节 + 解码后总像素。
    #    只查字节会放过"PNG 压得很小但档位很多"的组合
    #    （实测 67,548 B / 98,560 px 就是加载不出的）。见 ICON_PIXEL_LIMIT。
    over = [i for i, c in enumerate(cur_blobs) if len(c) > ICON_CHUNK_LIMIT]
    if over:
        raise ValueError(
            "第 %s 帧的 icon 块超过 %d B 的字节上限（最胖 %d B）—— "
            "减少档位，或改用 PNG 存（`cur_bytes(png_min=0)`）"
            % (over[:5], ICON_CHUNK_LIMIT, max(len(cur_blobs[i]) for i in over)))
    px = [i for i, c in enumerate(cur_blobs) if cur_pixels(c) > ICON_PIXEL_LIMIT]
    if px:
        raise ValueError(
            "第 %s 帧的 icon 块解码后总像素超过 %d（最大 %d）—— "
            "**这条线和字节无关**：PNG 压得再小也算这么多像素。"
            "减少档位（尤其大档）或减帧数"
            % (px[:5], ICON_PIXEL_LIMIT, max(cur_pixels(cur_blobs[i]) for i in px)))
    anih = struct.pack("<IIIIIIIII", 36, n, n, iwidth, iheight, 32, 1, jiffy, 1)
    fb = b"".join(chunk(b"icon", c) for c in cur_blobs)
    fram = b"LIST" + struct.pack("<I", len(b"fram") + len(fb)) + b"fram" + fb
    body = (b"ACON" + chunk(b"anih", anih)
            + chunk(b"rate", struct.pack("<%dI" % n, *([jiffy] * n))) + fram)
    return b"RIFF" + struct.pack("<I", len(body)) + body


def write_ani(path, cur_blobs, jiffy: int = 4):
    data = ani_bytes(cur_blobs, jiffy)
    with open(path, "wb") as f:
        f.write(data)
    return len(data)


def _chunks(blob, off=0, end=None):
    """遍历 RIFF chunk。"""
    end = len(blob) if end is None else end
    while off + 8 <= end:
        cid = blob[off:off + 4]
        size = struct.unpack("<I", blob[off + 4:off + 8])[0]
        yield cid, off + 8, size
        off += 8 + size + (size & 1)


def read_ani(source):
    """
    读回 `.ani`。

    返回 (frames, nframes, nsteps, jiffy)
      frames = [ {档宽: (PIL.Image, (hx,hy)), ...}, ... ]  每帧一个 dict

    复用 `cur.read_cur` 解析每个 icon 块 —— 因为它**本来就是一个 .cur**。
    """
    from .cur import read_cur

    blob = source if isinstance(source, (bytes, bytearray)) else \
        open(source, "rb").read()
    if blob[:4] != b"RIFF" or blob[8:12] != b"ACON":
        raise ValueError("不是 .ani（RIFF/ACON 头不对）")

    anih = rate = None
    icons = []
    for cid, off, size in _chunks(blob, 12):
        if cid == b"anih":
            anih = struct.unpack("<IIIIIIIII", blob[off:off + 36])
        elif cid == b"rate":
            rate = list(struct.unpack("<%dI" % (size // 4), blob[off:off + size]))
        elif cid == b"LIST":
            for c2, o2, s2 in _chunks(blob, off + 4, off + size):
                if c2 == b"icon":
                    icons.append(blob[o2:o2 + s2])
    if anih is None:
        raise ValueError("没有 anih 块")

    frames = []
    for ic in icons:
        frames.append({w: (im, hot) for (w, _h), im, hot in read_cur(ic)})
    return frames, anih[1], anih[2], (rate[0] if rate else 4)


def dump_ani(path) -> str:
    """结构摘要（排查"为什么不动"的第一步）。"""
    blob = open(path, "rb").read()
    lines = ["文件 %d B" % len(blob)]
    for cid, off, size in _chunks(blob, 12):
        if cid == b"LIST":
            names = [c.decode("latin1") for c, _o, _s in
                     _chunks(blob, off + 4, off + size)]
            lines.append("LIST %s  %d 项  %s" % (
                blob[off:off + 4].decode("latin1"), len(names), names[:4]))
        elif cid == b"anih":
            # anih 是 9 个 DWORD：
            #   cbSize nFrames nSteps iWidth iHeight iBitCount nPlanes
            #   iDispRate bfAttributes
            v = struct.unpack("<IIIIIIIII", blob[off:off + 36])
            lines.append("anih  cbSize=%d nFrames=%d nSteps=%d iW=%d iH=%d "
                         "bitCount=%d planes=%d dispRate=%d attr=%d" % v)
        elif cid == b"rate":
            r = list(struct.unpack("<%dI" % (size // 4), blob[off:off + size]))
            lines.append("rate  %d 帧，值 %s" % (len(r), sorted(set(r))))
        else:
            lines.append("%s %d B" % (cid.decode("latin1"), size))
    return "\n".join(lines)

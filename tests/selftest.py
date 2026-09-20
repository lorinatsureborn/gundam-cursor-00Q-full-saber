# -*- coding: utf-8 -*-
"""
自测：造两个指针 → 打包 → **从容器读回来** → LoadCursorFromFile。

    python tests/selftest.py

为什么要有这个：`.cur` / `.ani` 的字节层写错了**往往不报错**，
只是加载不出或显示错乱（上下颠倒、红蓝互换、块超限）。
所以验证必须**从容器读回来**，不能只看源图。
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cursorforge import (CUR_SIZES, ani_bytes, cur_with_hotspot,  # noqa: E402
                         read_ani, read_cur, static_tiers, tier_outline)
from cursorforge.ani import ICON_CHUNK_LIMIT                      # noqa: E402
from cursorforge.tiers import hotspot                             # noqa: E402

TMP = Path(__file__).resolve().parent / "_tmp"
FAIL = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAIL.append(msg)


def make_arrow(size=256):
    """一个左上角有尖的箭头，用来验热点。"""
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.polygon([(6, 6), (6, size - 40), (size // 3, size - 90),
               (size - 30, size - 30), (size // 3, size // 3)], fill=(90, 220, 90, 255))
    return im


def make_dot(size=256, phase=0.0):
    """一个会上下动的圆点，用来验动画帧。"""
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cy = size // 2 + int(size * 0.2 * phase)
    ImageDraw.Draw(im).ellipse([size // 2 - 60, cy - 60, size // 2 + 60, cy + 60],
                               fill=(220, 90, 90, 255))
    return im


def main():
    TMP.mkdir(exist_ok=True)
    print("== 1. 多档 .cur ==")
    master = make_arrow(256)
    ts = static_tiers(master, CUR_SIZES)
    hot = hotspot(ts[0], "ul")
    print("     热点（256 档）= %s" % (hot,))
    cur_path = TMP / "test.cur"
    data = cur_with_hotspot(ts, hot, 256, png_min=128)
    cur_path.write_bytes(data)
    check(len(ts) == len(CUR_SIZES), "档位数 %d" % len(ts))

    back = read_cur(cur_path)
    check(len(back) == len(CUR_SIZES), "读回 %d 档" % len(back))
    check([s for (s, _i, _h) in back] ==
          [(s, s) for s in sorted(CUR_SIZES, reverse=True)],
          "读回的档位尺寸正确")
    # 热点必须**按档等比**，不能所有档一个值
    hots = [h for (_s, _i, h) in back]
    check(len(set(hots)) > 1, "热点逐档缩放（%s … %s）" % (hots[0], hots[-1]))
    # 抽一档验像素。⚠️ 别贴着边缘取样 —— 那里是 `tier_outline` 画的描边（不是缺陷）。
    #    正确断言是两条：**边缘有描边** + **内部有主体色**。
    big = np.asarray(back[0][1])
    edge_px = big[10, 10]
    body = big[(big[..., 3] > 200)]
    greens = body[(body[:, 1] > 150) & (body[:, 0] < 120)]
    check(edge_px[3] > 200 and int(edge_px[0]) < 60,
          "256 档边缘是描边色 %s" % edge_px.tolist())
    check(len(greens) > 500, "256 档内部有主体绿 %d px" % len(greens))

    print("\n== 2. BMP 方向 / 通道 ==")
    # 32 档一定是 BMP（<128）。造一张「上红下蓝」验证没有上下颠倒
    probe = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    for y in range(32):
        for x in range(32):
            probe.putpixel((x, y), (255, 0, 0, 255) if y < 16 else (0, 0, 255, 255))
    p2 = TMP / "probe.cur"
    p2.write_bytes(cur_with_hotspot([probe], (0, 0), 32, png_min=999))
    pback = read_cur(p2)[0][1]
    top = np.asarray(pback)[2, 16]
    bot = np.asarray(pback)[29, 16]
    check(top[0] > 200 and top[2] < 60, "上边是红（没颠倒、没换通道）%s" % top.tolist())
    check(bot[2] > 200 and bot[0] < 60, "下边是蓝 %s" % bot.tolist())

    print("\n== 3. 动画 .ani ==")
    T = 8
    blobs = []
    for t in range(T):
        m = make_dot(256, phase=-1 + 2 * t / T)
        ts2 = static_tiers(m, [96, 64, 48, 32])
        blobs.append(cur_with_hotspot(ts2, (48, 48), 96, png_min=128))
    ani_path = TMP / "test.ani"
    ani_path.write_bytes(ani_bytes(blobs, jiffy=4))
    print("     .ani %d B，最大 icon 块 %d B（上限 %d）"
          % (ani_path.stat().st_size, max(len(b) for b in blobs), ICON_CHUNK_LIMIT))
    check(max(len(b) for b in blobs) <= ICON_CHUNK_LIMIT, "icon 块没有超限")

    frames, nf, ns, jf = read_ani(ani_path)
    check(nf == T and ns == T, "nFrames=%d nSteps=%d" % (nf, ns))
    check(jf == 4, "jiffy=%d" % jf)
    check(len(frames) == T, "读回 %d 帧" % len(frames))
    check(sorted(frames[0].keys()) == [32, 48, 64, 96],
          "每帧含全部档位 %s" % sorted(frames[0].keys()))
    # 帧与帧必须**真的不同**（否则是"打包成了同一张"）
    imgs = [np.asarray(f[96][0]) for f in frames]
    diffs = [int(np.abs(imgs[i].astype(int) - imgs[0].astype(int)).sum())
             for i in range(1, T)]
    check(max(diffs) > 0, "帧之间有差异（max=%d）" % max(diffs))

    print("\n== 4. LoadCursorFromFile ==")
    exe = TMP / "_load.ps1"
    exe.write_text("\n".join(
        ['Add-Type @"', "using System;using System.Runtime.InteropServices;",
         'public class C{[DllImport("user32.dll")]public static extern IntPtr '
         'LoadCursorFromFile(string p);}', '"@'] +
        ['if([C]::LoadCursorFromFile("%s") -eq [IntPtr]::Zero)'
         '{Write-Host "FAIL %s"}else{Write-Host "ok   %s"}'
         % (p, p.name, p.name) for p in (cur_path, ani_path)]),
        encoding="utf-8-sig")
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                        "-File", str(exe)], capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    print("     " + out.strip().replace("\n", "\n     "))
    check("FAIL" not in out and out.count("ok") >= 2, "两个文件都能被 Windows 加载")

    print("\n" + ("全部通过 ✓" if not FAIL else "失败 %d 项：%s" % (len(FAIL), FAIL)))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())

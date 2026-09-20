# -*- coding: utf-8 -*-
"""
规格驱动的指针构建器。

    python -m cursorforge build spec.json
    python -m cursorforge verify out/            # 逐个 LoadCursorFromFile
    python -m cursorforge dump out/x.ani         # 结构摘要

### spec.json

```json
{
  "out": "out",
  "scheme_name": "MY-CURSORS",
  "reg_dir": "MYCURSORS",
  "sizes": [256, 128, 96, 64, 48, 32],
  "slots": [
    {"role": "arrow", "file": "my_arrow.cur", "master": "art/arrow.png",
     "hotspot": "ul"},
    {"role": "work",  "file": "my_work.ani",  "frames": "art/work/*.png",
     "hotspot": "c", "jiffy": 4, "sizes": [96, 64, 48, 32]}
  ]
}
```

`role` 取 `cursorforge.scheme.SCHEME_FIELDS` 里的名字（`Arrow` / `Wait` / `Hand` …），
大小写不敏感，可以带前缀（`01_arrow` 也行）。未提供的槽位会自动复用最接近的那个。

`hotspot` 同 `cursorforge.tiers.hotspot`：`c` / `ul` / `ll` / `top`，
也可以直接写 `"12,3"`。
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

from PIL import Image

from . import scheme, tiers
from .ani import ani_bytes, dump_ani
from .cur import bmp32, cur_with_hotspot
from .tiers import CUR_SIZES

ANI_SIZES = [96, 64, 48, 32]

#: Windows 方案值的 15 个造型槽 + 2 个复用槽（见 scheme.SCHEME_FIELDS）
ROLE_ALIASES = {
    "normal": "Arrow", "arrow": "Arrow", "help": "Help",
    "working": "AppStarting", "appstarting": "AppStarting", "work": "AppStarting",
    "busy": "Wait", "wait": "Wait",
    "precision": "Crosshair", "crosshair": "Crosshair", "cross": "Crosshair",
    "text": "IBeam", "ibeam": "IBeam",
    "handwriting": "NWPen", "nwpen": "NWPen", "pen": "NWPen",
    "unavailable": "No", "no": "No",
    "vertical": "SizeNS", "sizens": "SizeNS", "ns": "SizeNS",
    "horizontal": "SizeWE", "sizewe": "SizeWE", "ew": "SizeWE",
    "diagonal1": "SizeNWSE", "sizenwse": "SizeNWSE", "nwse": "SizeNWSE",
    "diagonal2": "SizeNESW", "sizenesw": "SizeNESW", "nesw": "SizeNESW",
    "move": "SizeAll", "sizeall": "SizeAll",
    "alternate": "UpArrow", "uparrow": "UpArrow", "up": "UpArrow",
    "link": "Hand", "hand": "Hand",
    "pin": "Pin", "person": "Person",
}


def _role_of(key: str) -> str:
    """`01_Arrow` / `arrow` / `ARROW` → `Arrow`"""
    k = str(key).strip().lower()
    if k in ROLE_ALIASES:
        return ROLE_ALIASES[k]
    for tok in reversed([t for t in k.replace("-", "_").split("_") if t]):
        if tok in ROLE_ALIASES:
            return ROLE_ALIASES[tok]
    for r in scheme.SCHEME_FIELDS[1:]:
        if r.lower() == k:
            return r
    raise ValueError("认不出 role: %r" % key)


def _hot(spec, img):
    h = spec.get("hotspot", "c")
    if isinstance(h, str) and "," in h:
        x, y = h.split(",")
        return int(x), int(y)
    return tiers.hotspot(img, h)


def _load_master(p: Path) -> Image.Image:
    im = Image.open(p)
    if im.format != "PNG":                     # ★ 别信扩展名
        print("  ⚠ %s 实际是 %s（不是 PNG）" % (p.name, im.format))
    return im.convert("RGBA")


def build(spec_path, only=None):
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    root = Path(spec_path).resolve().parent
    out = (root / spec.get("out", "out")).resolve()
    out.mkdir(parents=True, exist_ok=True)
    name = spec.get("scheme_name", "MY-CURSORS")
    reg_dir = spec.get("reg_dir", name.replace("-", "").replace(" ", ""))

    written, report = {}, []
    for sl in spec["slots"]:
        role = _role_of(sl["role"])
        if only and role.lower() not in [o.lower() for o in only]:
            continue
        fname = sl["file"]
        if "frames" in sl:
            pats = sl["frames"]
            if isinstance(pats, str):
                pats = [pats]
            files = sorted(f for p in pats for f in glob.glob(str(root / p)))
            if not files:
                raise FileNotFoundError("没有匹配到帧: %s" % sl["frames"])
            sizes = sl.get("sizes", ANI_SIZES)
            jiffy = int(sl.get("jiffy", 4))
            blobs, hots = [], []
            for fp in files:
                master = _load_master(Path(fp))
                ts = tiers.static_tiers(master, sizes,
                                        outline=sl.get("outline", True),
                                        outline_map=sl.get("outline_map"))
                hot = _hot(sl, tiers.fit(master, sizes[0]))
                hots.append(hot)
                blobs.append(cur_with_hotspot(ts, hot, sizes[0],
                                              png_min=sl.get("png_min", 128)))
            data = ani_bytes(blobs, jiffy)
            (out / fname).write_bytes(data)
            chunk_max = max(len(b) for b in blobs)
            report.append((fname, role, "%d 帧 %d 档 %.1f fps" %
                           (len(files), len(sizes), 60.0 / jiffy), len(data)))
            print("  %-22s %-12s %d 帧 · 每 icon 块 %.1f KB（上限 68.0）"
                  % (fname, role, len(files), chunk_max / 1024))
        else:
            master = _load_master(root / sl["master"])
            sizes = sl.get("sizes", spec.get("sizes", CUR_SIZES))
            ts = tiers.static_tiers(master, sizes,
                                    outline=sl.get("outline", True),
                                    outline_map=sl.get("outline_map"))
            hot = _hot(sl, tiers.fit(master, max(sizes)))
            data = cur_with_hotspot(ts, hot, max(sizes),
                                    png_min=sl.get("png_min", 128))
            (out / fname).write_bytes(data)
            report.append((fname, role, "%d 档" % len(sizes), len(data)))
            print("  %-22s %-12s %d 档 · 热点 %s" % (fname, role, len(sizes), hot))
        written[role] = fname

    if not written:
        print("没有任何槽位被写出")
        return 1

    # 未提供的槽位复用最接近的
    fallback = {"Pin": "Crosshair", "Person": "UpArrow", "AppStarting": "Wait"}
    order = []
    for f in scheme.SCHEME_FIELDS[1:]:
        if f in written:
            order.append(written[f])
        else:
            alt = written.get(fallback.get(f, ""), next(iter(written.values())))
            order.insert(len(order), alt)
            print("  · %-12s 未提供，复用 %s" % (f, alt))
    scheme.write_inf(out, name, reg_dir, order)
    scheme.write_install_ps1(out, name, reg_dir, order)
    print("\n-> %s/  %d 个指针 + %s.inf + install.ps1 + uninstall.ps1"
          % (out.name, len(written), name))
    return 0


def verify(out_dir):
    """逐个 LoadCursorFromFile（**成品必须从容器里读回来验**）。"""
    import subprocess
    out = Path(out_dir)
    files = sorted(list(out.glob("*.cur")) + list(out.glob("*.ani")))
    if not files:
        print("没找到 .cur/.ani")
        return 1
    ps = ["Add-Type @'", "using System;using System.Runtime.InteropServices;",
          "public class C{[DllImport(\"user32.dll\")]public static extern "
          "IntPtr LoadCursorFromFile(string p);}", "'@"]
    bad = 0
    for f in files:
        ps.append('if([C]::LoadCursorFromFile("%s") -eq [IntPtr]::Zero)'
                  '{Write-Host "FAIL %s"}else{Write-Host "ok   %s"}'
                  % (f, f.name, f.name))
    r = subprocess.run(["powershell", "-NoProfile", "-Command", "\n".join(ps)],
                       capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip())
    bad = r.stdout.count("FAIL")
    print("\n%s —— %d 个文件，%d 个失败" % (out, len(files), bad))
    return 1 if bad else 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="cursorforge")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="按 spec.json 构建")
    b.add_argument("spec")
    b.add_argument("--only", nargs="*", help="只构建这几个 role")
    v = sub.add_parser("verify", help="LoadCursorFromFile 复验")
    v.add_argument("out_dir")
    d = sub.add_parser("dump", help=".ani 结构摘要")
    d.add_argument("ani")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        return build(a.spec, a.only)
    if a.cmd == "verify":
        return verify(a.out_dir)
    if a.cmd == "dump":
        print(dump_ani(a.ani))
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())

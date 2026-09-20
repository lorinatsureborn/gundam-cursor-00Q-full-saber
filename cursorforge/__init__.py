# -*- coding: utf-8 -*-
"""
`cursorforge` —— Windows 鼠标指针打包工具链。

    .cur / .ani 字节层   → cur.py / ani.py
    多档位打包纪律       → tiers.py
    方案安装             → scheme.py
    规格驱动的构建入口   → build.py

设计原则只有一条：

    **一切以像素计的尺寸，必须在"该档自己的分辨率"上算。**

这条规矩在这个项目里被踩了 6 次（见 `tiers.py` 的文档），所以它被写进了 API：
`static_tiers()` 先把母版缩到该档，再按该档的像素描边。
"""
from .cur import bmp32, cur_bytes, cur_with_hotspot, read_cur, write_cur
from .ani import (ICON_CHUNK_LIMIT, ani_bytes, chunk, dump_ani, read_ani,
                  write_ani)
from .tiers import (CUR_SIZES, OUTLINE_RGB, TIER_OUTLINE, fit, hotspot,
                    static_tiers, tier_outline)
from .scheme import SCHEME_FIELDS, write_inf, write_install_ps1

__version__ = "0.1.0"
__all__ = [
    "bmp32", "cur_bytes", "cur_with_hotspot", "read_cur", "write_cur",
    "ICON_CHUNK_LIMIT", "ani_bytes", "chunk", "dump_ani", "read_ani",
    "write_ani", "CUR_SIZES", "OUTLINE_RGB", "TIER_OUTLINE", "fit", "hotspot",
    "static_tiers", "tier_outline", "SCHEME_FIELDS", "write_inf",
    "write_install_ps1",
]

# Windows 指针格式（.cur / .ani）与打包

2026-09-20 由「高达 00Q 指针套装」项目沉淀，全部经 `LoadCursorFromFile` 实测。

**适用**：要把图像做成 Windows 鼠标指针（静态 `.cur` 或动画 `.ani`），
尤其是**多分辨率档位** + **动画** + **热点**三件事凑一起的时候。

---

## 一、格式速查

### `.cur` = ICO 结构 + 热点

```
ICONDIR   (6 B)   reserved=0, type=2(.cur), count=N
ICONDIRENTRY ×N (16 B each)
  bWidth, bHeight   宽高，**256 写作 0**
  bColorCount       0
  bReserved         0
  wPlanes           ← ★ **热点 X 写在这里**
  wBitCount         ← ★ **热点 Y 写在这里**
  dwBytesInRes, dwImageOffset
图像数据
```

★ **这是 `.cur` 唯一和 `.ico` 不同的地方** —— 热点塞在 `wPlanes` / `wBitCount`。
其它字段和 `.ico` 完全一样。

> `.ico` 里 `wPlanes` 通常写 1、`wBitCount` 写 32；`.cur` 把它们挪用成热点坐标，
> 所以**热点最大只能到 65535**，而实际指针不会超过 256，够用。

### 每一档用 PNG 还是 BMP

| 档位 | 格式 | 理由 |
|---|---|---|
| **≥128** | **PNG**（直接嵌 PNG 字节流） | 有 alpha，体积小 |
| **<128** | BMP（BITMAPINFOHEADER + BGRA + AND 掩码） | 老 API 对小块 PNG 支持不稳 |

⚠️ **BMP 是自下而上存的**，而且通道顺序是 **BGRA 不是 RGBA**，
每行之后还有一段 AND 掩码。写错的表现是**图像上下颠倒 + 红蓝互换**。

### `.ani` = RIFF/ACON

```
RIFF....ACON
  anih   36 B    cbSize=36, nFrames, nSteps, iWidth, iHeight, ...
  rate   N×4B    每帧的 jiffy（1 jiffy = 1/60 s）
  LIST fram
    icon  ← ★ **每个 icon 块 = 一张完整的、含全部档位的多分辨率 .cur**
    icon
    ...
```

★ **关键结构**：`.ani` 不是"每帧一张 32px 图"，
而是**每帧一个完整的多分辨率 `.cur`**（里面装着 96/64/48/32 全部档位）。

### ★ `.ani` 每个 icon 块的**硬上限 ≈ 69632 B**

这是打包时最先撞到的墙：

```
单个 .ani 体积 ≈ 帧数 × 4档 × 68.7KB
32 帧 → 约 2.2 MB / 个指针
```

**超过就会静默失败或加载不出**。要瘦身只有两条路，都会改动视觉：

| 手段 | 效果 | 代价 |
|---|---|---|
| 减帧数 32→16 | 体积减半 | 动画周期快一倍 |
| 减档位 4→3（削掉 96 档） | 降 25% | 大屏下略糊 |

### 验证

```powershell
Add-Type @"
using System;using System.Runtime.InteropServices;
public class C { [DllImport("user32.dll")] public static extern IntPtr LoadCursorFromFile(string p); }
"@
[C]::LoadCursorFromFile("x.cur")   # 返回 0 = 失败
```

**必须逐档从容器里读回来复验**（不是看源 PNG）—— 打包格式、alpha、
热点都可能在这一步出问题。

---

## 二、帧率与动画节奏

- **1 jiffy = 1/60 s**，`jiffy=4` ⇒ 15 fps
- **想让动画变慢，加帧数，不要加大 jiffy**。
  `16 帧 × jiffy 8` = 7.5 fps，**肉眼可见地一顿一顿**；
  `32 帧 × jiffy 4` = 2.13 s 一轮，顺。
- 循环要**首尾相接**：用 `ph = 0.5 − 0.5·cos(2πt/T)`（0→1→0），
  或分段折线（点击类动作要"顿"感，余弦的软起软落像呼吸不像按键）。

---

## 三、热点怎么放

| 指针类型 | 热点 | 判据 |
|---|---|---|
| 箭头 / 笔 | **尖端** | `argmin(x + y)`（左上）或 `argmin(x − y)`（左下） |
| 十字 / 双向箭头 | **正中** | `(w//2, h//2)` |
| 手型（Hand） | **食指尖** | 最上一行的中点 |
| I 型 | 正中 | |

⚠️ **热点是逐档算的**（每档取自己那张图的极值点），不是从大档等比缩。

---

## 四、多档位打包的纪律

1. **档位**：`.ani` 用 `[96, 64, 48, 32]`；静态 `.cur` 可以多给
   `[256, 128, 96, 64, 48, 32]`（PNG≥128，BMP<128）。
2. **每一档独立生成**（见 `ASSET-PIPELINE.md` §二①）。
   绝不做"大档出图再缩"。
3. **缩略图填充率要留描边余量**：主体摆到画布的 94% 而不是 100%，
   否则加描边时**尖端会被裁掉**（实测：刃尖落在 x=0 上，暗边直接出界）。
4. **描边阈值会和发光打架**：描边的判据若是 `alpha > 100`，
   而发光峰值到 199，**描边会画在光晕的外缘**上 —— 一圈浮在雾里的黑环。
   ⇒ 要么把光压到阈值下，要么这一格**豁免描边**。

---

## 五、Windows 配色方案（`.inf`）

装指针要写一个 `.inf`，`[Control Panel\Cursors]` 下**每个槽位需要 17 个字段**
（其中一部分是历史遗留、必须给空值），少一个整个方案就装不上。

```
Arrow, Help, AppStarting, Wait, Crosshair, IBeam, NWPen, No, SizeNS,
SizeWE, SizeNWSE, SizeNESW, SizeAll, UpArrow, Hand, Pin, Person
```

`install.ps1` 里调用 `SystemParametersInfo(SPI_SETCURSORS)` **立即生效**，
不需要注销。

---

## 六、最常见的三个坑

1. **换了容器类型忘了同步白名单** —— 某个槽从 `.cur` 改成 `.ani` 后，
   构建脚本的"保留文件白名单"里还写着旧扩展名，
   于是**静默回退到上一个版本**，而不是报错。这个坑在一个项目里踩了 **8 次**。
   ⇒ **改容器类型 = 必须同时改白名单 + 复核清单**（两处，不是一处）。
2. **BMP 方向/通道**：写出来是上下颠倒 + 红蓝互换 → 见 §一。
3. **`.ani` 块超限**：不报错，只是加载不出 → 见 §一。

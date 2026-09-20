# -*- coding: utf-8 -*-
"""
指针方案：`.inf` + `install.ps1` / `uninstall.ps1`。

★ **Windows 方案值是 17 项**，顺序固定，少一项整个方案就装不上：

    "", Arrow, Help, AppStarting, Wait, Crosshair, IBeam, NWPen, No,
    SizeNS, SizeWE, SizeNWSE, SizeNESW, SizeAll, UpArrow, Hand, Pin, Person

  第一项是**空名**（**必须给**，历史遗留）。多数人只做 15 个造型，
  剩下的槽位复用最接近的那个即可。

★ `install.ps1` 调 `SystemParametersInfo(SPI_SETCURSORS)` → **立即生效，不用注销**。
"""
from __future__ import annotations

from pathlib import Path

__all__ = ["SCHEME_FIELDS", "write_inf", "write_install_ps1"]

SCHEME_FIELDS = ["", "Arrow", "Help", "AppStarting", "Wait", "Crosshair",
                 "IBeam", "NWPen", "No", "SizeNS", "SizeWE", "SizeNWSE",
                 "SizeNESW", "SizeAll", "UpArrow", "Hand", "Pin", "Person"]


def write_inf(out_dir, scheme_name: str, reg_dir: str, files_in_order) -> Path:
    """
    files_in_order 长度必须是 17（对应 SCHEME_FIELDS）。
    """
    if len(files_in_order) != 17:
        raise ValueError("方案值需要 17 项，收到 %d" % len(files_in_order))
    token = "%SystemRoot%\\Cursors\\" + reg_dir
    value = ",".join("%s\\%s" % (token, f) for f in files_in_order)
    files = "\n".join(sorted(set(files_in_order)))
    # ⚠️ 括号不能省：`Path(dir) / "%s.inf" % name` 会被解析成
    #    `(Path(dir) / "%s.inf") % name` —— `/` 和 `%` 同级且左结合。
    p = Path(out_dir) / ("%s.inf" % scheme_name)
    p.write_text(f"""[Version]
signature="$CHICAGO$"

[DefaultInstall]
CopyFiles = Scheme.Cur
AddReg    = Scheme.Reg

[DestinationDirs]
Scheme.Cur = 10,"Cursors\\{reg_dir}"

[Scheme.Cur]
{files}

[Scheme.Reg]
HKCU,"Control Panel\\Cursors\\Schemes","{scheme_name}",0x00020000,"{value}"
""", encoding="utf-8-sig")          # ★ 必须带 BOM，否则中文注释在 PS 5.1 里乱码
    return p


def write_install_ps1(out_dir, scheme_name: str, reg_dir: str,
                      files_in_order) -> Path:
    files = "\n".join('    "%s"' % f for f in sorted(set(files_in_order)))
    order = ", ".join('"%s"' % f for f in files_in_order)
    fields = ", ".join('"%s"' % n for n in SCHEME_FIELDS[1:])
    p = Path(out_dir) / "install.ps1"
    p.write_text(f'''# {scheme_name} 指针方案安装脚本（Win10/11）
# 用法：右键 -> 使用 PowerShell 运行（会提权，装完立即生效，不用注销）
$ErrorActionPreference = "Stop"
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$pr = New-Object Security.Principal.WindowsPrincipal($id)
if (-not $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {{
    Write-Host "需要管理员权限，正在提权..." -ForegroundColor Yellow
    Start-Process powershell -Verb RunAs -ArgumentList "-ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
}}
$src  = $PSScriptRoot
$dest = Join-Path $env:SystemRoot "Cursors\\{reg_dir}"
Write-Host "安装到 $dest"
New-Item -ItemType Directory -Force -Path $dest | Out-Null

$files = @(
{files}
)
foreach ($f in $files) {{
    $p = Join-Path $src $f
    if (Test-Path $p) {{ Copy-Item $p $dest -Force }} else {{ Write-Warning "缺少 $f" }}
}}

$order = @({order})
$fields = @({fields})
$paths = @(); foreach ($f in $order) {{ $paths += (Join-Path $dest $f) }}
$value = $paths -join ","

$base = "HKCU:\\Control Panel\\Cursors"
New-Item -Path "$base\\Schemes" -Force | Out-Null
New-ItemProperty -Path "$base\\Schemes" -Name "{scheme_name}" -Value $value -PropertyType ExpandString -Force | Out-Null

$map = @{{ "" = $paths[0] }}
for ($i = 0; $i -lt $fields.Count; $i++) {{ $map[$fields[$i]] = $paths[$i] }}
foreach ($k in $map.Keys) {{
    New-ItemProperty -Path $base -Name $k -Value $map[$k] -PropertyType ExpandString -Force | Out-Null
}}
New-ItemProperty -Path $base -Name "Scheme Source" -Value 1 -PropertyType DWord -Force | Out-Null

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Cur {{
    [DllImport("user32.dll", SetLastError=true)]
    public static extern bool SystemParametersInfo(uint a, uint b, IntPtr c, uint d);
}}
"@
[Cur]::SystemParametersInfo(0x0057, 0, [IntPtr]::Zero, 0x01 -bor 0x02) | Out-Null
Write-Host "完成。方案 '{scheme_name}' 已应用（设置 -> 鼠标 -> 指针 里也能切换）。" -ForegroundColor Green
''', encoding="utf-8-sig")

    (Path(out_dir) / "uninstall.ps1").write_text(f'''# {scheme_name} 指针方案卸载
$base = "HKCU:\\Control Panel\\Cursors"
$dest = Join-Path $env:SystemRoot "Cursors\\{reg_dir}"
Remove-ItemProperty -Path "$base\\Schemes" -Name "{scheme_name}" -ErrorAction SilentlyContinue
$keys = @("", {", ".join('"%s"' % n for n in SCHEME_FIELDS[1:])})
foreach ($k in $keys) {{
    $cur = (Get-ItemProperty -Path $base -Name $k -ErrorAction SilentlyContinue).$k
    if ($cur -and $cur -like "*{reg_dir}*") {{ Remove-ItemProperty -Path $base -Name $k -ErrorAction SilentlyContinue }}
}}
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$pr = New-Object Security.Principal.WindowsPrincipal($id)
if ($pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {{
    if (Test-Path $dest) {{ Remove-Item $dest -Recurse -Force; Write-Host "已删除 $dest" }}
}} else {{ Write-Host "请以管理员身份手动删除 $dest" -ForegroundColor Yellow }}
Write-Host "卸载完成，注销或重启后指针完全恢复默认。" -ForegroundColor Green
''', encoding="utf-8-sig")
    return p

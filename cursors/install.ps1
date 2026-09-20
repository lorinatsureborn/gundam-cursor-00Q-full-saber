# GUNDAM-00Q 指针方案安装脚本（Win10/11）
# 用法：右键 -> 使用 PowerShell 运行
$ErrorActionPreference = "Stop"
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$pr = New-Object Security.Principal.WindowsPrincipal($id)
if (-not $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "需要管理员权限，正在提权..." -ForegroundColor Yellow
    Start-Process powershell -Verb RunAs -ArgumentList "-ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
}
$src  = $PSScriptRoot
$dest = Join-Path $env:SystemRoot "Cursors\GUNDAM00Q"
Write-Host "安装到 $dest"
New-Item -ItemType Directory -Force -Path $dest | Out-Null

$files = @(
    "gn00_arrow.ani"
    "gn00_busy.ani"
    "gn00_cross.cur"
    "gn00_ew.ani"
    "gn00_hand.ani"
    "gn00_help.cur"
    "gn00_ibeam.ani"
    "gn00_move.ani"
    "gn00_nesw.ani"
    "gn00_no.cur"
    "gn00_ns.ani"
    "gn00_nwse.ani"
    "gn00_pen.ani"
    "gn00_up.cur"
    "gn00_work.ani"
)
foreach ($f in $files) {
    $p = Join-Path $src $f
    if (Test-Path $p) { Copy-Item $p $dest -Force } else { Write-Warning "缺少 $f" }
}

# 方案值按 Windows 真实字段顺序（17 项）
$order = @("gn00_arrow.ani", "gn00_help.cur", "gn00_work.ani", "gn00_busy.ani", "gn00_cross.cur", "gn00_ibeam.ani", "gn00_pen.ani", "gn00_no.cur", "gn00_ns.ani", "gn00_ew.ani", "gn00_nwse.ani", "gn00_nesw.ani", "gn00_move.ani", "gn00_up.cur", "gn00_hand.ani", "gn00_cross.cur", "gn00_up.cur")
$fields = @("Arrow", "Help", "AppStarting", "Wait", "Crosshair", "IBeam", "NWPen", "No", "SizeNS", "SizeWE", "SizeNWSE", "SizeNESW", "SizeAll", "UpArrow", "Hand", "Pin", "Person")
$paths = @(); foreach ($f in $order) { $paths += (Join-Path $dest $f) }
$value = $paths -join ","

$base = "HKCU:\Control Panel\Cursors"
New-Item -Path "$base\Schemes" -Force | Out-Null
New-ItemProperty -Path "$base\Schemes" -Name "GUNDAM-00Q" -Value $value -PropertyType ExpandString -Force | Out-Null

$map = @{ "" = $paths[0] }
for ($i = 0; $i -lt $fields.Count; $i++) { $map[$fields[$i]] = $paths[$i] }
foreach ($k in $map.Keys) {
    New-ItemProperty -Path $base -Name $k -Value $map[$k] -PropertyType ExpandString -Force | Out-Null
}
New-ItemProperty -Path $base -Name "Scheme Source" -Value 1 -PropertyType DWord -Force | Out-Null

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Cur {
    [DllImport("user32.dll", SetLastError=true)]
    public static extern bool SystemParametersInfo(uint a, uint b, IntPtr c, uint d);
}
"@
[Cur]::SystemParametersInfo(0x0057, 0, [IntPtr]::Zero, 0x01 -bor 0x02) | Out-Null
Write-Host "完成。方案 'GUNDAM-00Q' 已应用（设置 -> 鼠标 -> 指针 里也能切换）。" -ForegroundColor Green

# GUNDAM-00Q cursor scheme - installer (Win10/11)
# Usage: right-click this file -> "Run with PowerShell"
#
# NOTE: this script is intentionally ASCII-only. Chinese text in .ps1/.bat is a
# reliable way to break PowerShell 5.1 (it decodes BOM-less files as ANSI).
# Human-readable docs live in README.txt, which is UTF-8 and safe.
$ErrorActionPreference = "Stop"
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$pr = New-Object Security.Principal.WindowsPrincipal($id)
if (-not $pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Administrator rights required, elevating..." -ForegroundColor Yellow
    Start-Process powershell -Verb RunAs -ArgumentList "-ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
}
$src  = $PSScriptRoot
$dest = Join-Path $env:SystemRoot "Cursors\GUNDAM00Q"
Write-Host "Installing to $dest"
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
    if (Test-Path $p) { Copy-Item $p $dest -Force } else { Write-Warning "missing $f" }
}

# Scheme value must follow the real Windows field order (17 entries)
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
Write-Host "Done. Scheme 'GUNDAM-00Q' applied (also switchable in Settings -> Mouse -> Pointers)." -ForegroundColor Green

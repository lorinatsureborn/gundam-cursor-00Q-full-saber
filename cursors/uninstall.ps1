# GUNDAM-00Q cursor scheme - uninstaller
# ASCII-only on purpose; see install.ps1 for why.
$base = "HKCU:\Control Panel\Cursors"
$dest = Join-Path $env:SystemRoot "Cursors\GUNDAM00Q"
Remove-ItemProperty -Path "$base\Schemes" -Name "GUNDAM-00Q" -ErrorAction SilentlyContinue
$keys = @("", "Arrow", "Help", "AppStarting", "Wait", "Crosshair", "IBeam", "NWPen", "No", "SizeNS", "SizeWE", "SizeNWSE", "SizeNESW", "SizeAll", "UpArrow", "Hand", "Pin", "Person")
foreach ($k in $keys) {
    $cur = (Get-ItemProperty -Path $base -Name $k -ErrorAction SilentlyContinue).$k
    if ($cur -and $cur -like "*GUNDAM00Q*") { Remove-ItemProperty -Path $base -Name $k -ErrorAction SilentlyContinue }
}
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$pr = New-Object Security.Principal.WindowsPrincipal($id)
if ($pr.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    if (Test-Path $dest) { Remove-Item $dest -Recurse -Force; Write-Host "removed $dest" }
} else { Write-Host "Run as administrator to remove $dest" -ForegroundColor Yellow }
Write-Host "Uninstalled. Sign out or restart to fully restore the default pointers." -ForegroundColor Green

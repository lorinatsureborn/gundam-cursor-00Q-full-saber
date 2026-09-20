# GUNDAM-00Q 指针方案卸载
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
    if (Test-Path $dest) { Remove-Item $dest -Recurse -Force; Write-Host "已删除 $dest" }
} else { Write-Host "请以管理员身份手动删除 $dest" -ForegroundColor Yellow }
Write-Host "卸载完成，注销或重启后指针完全恢复默认。" -ForegroundColor Green

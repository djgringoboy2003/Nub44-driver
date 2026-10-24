<#
.SYNOPSIS
    Bundle the editable project and generated outputs into dist\nubm44-driver-<date>.zip (sources, KiCad
    projects, manufacturing files, reports, documentation; excludes tools, venv and build scratch).
#>
$Root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $Root 'dist'
New-Item -ItemType Directory -Force $dist | Out-Null
$name = "nubm44-driver-$(Get-Date -Format yyyyMMdd).zip"
$tmp = Join-Path $env:TEMP "nubm44-pkg"
if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
New-Item -ItemType Directory $tmp | Out-Null
foreach ($d in 'automation','documentation','engineering','firmware','hardware','manufacturing','reports','research','scripts','simulation','sourcing','tests') {
    if (Test-Path (Join-Path $Root $d)) { Copy-Item (Join-Path $Root $d) $tmp -Recurse -Exclude '*.exe','build' }
}
Get-ChildItem $Root -File -Include '*.md','*.txt','*.toml','.gitignore' -Depth 0 | Copy-Item -Destination $tmp
Remove-Item (Join-Path $tmp 'research\datasheets') -Recurse -Force -ErrorAction SilentlyContinue
Compress-Archive -Path (Join-Path $tmp '*') -DestinationPath (Join-Path $dist $name) -Force
Write-Host "package: $(Join-Path $dist $name)"

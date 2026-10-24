<#
.SYNOPSIS
    Generate the PCBWay fabrication and assembly package from the current board(s). Never places an order.
#>
param([string]$Variant = 'all')
$Root = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Root '.venv\Scripts\python.exe'
$variants = if ($Variant -eq 'all') { @('compact-22mm', 'evaluation-board') } else { @($Variant) }
$rc = 0
foreach ($v in $variants) {
    if (-not (Test-Path (Join-Path $Root "hardware\$v\nubm44_driver.kicad_pcb"))) { Write-Host "skip $v (no board yet)"; continue }
    & $Py (Join-Path $Root 'automation\export\export_pcbway.py') --variant $v
    if ($LASTEXITCODE -ne 0) { $rc = 1 }
}
exit $rc

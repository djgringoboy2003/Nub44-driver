<#
.SYNOPSIS
    Regenerate all design outputs from the source files (parameters, connectivity, placement).
.PARAMETER Variant
    compact-22mm, evaluation-board or all (default).
.PARAMETER SkipRouting
    Rebuild placement, pours and DRC without re-running FreeRouting (uses the existing session file).
#>
param([string]$Variant = 'all', [switch]$SkipRouting)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Root '.venv\Scripts\python.exe'
function Step([string]$msg, [string[]]$cmd) { Write-Host "== $msg"; & $Py @cmd; if ($LASTEXITCODE -ne 0) { throw "$msg failed" } }
Step 'library (symbols, footprints, 3D)' @((Join-Path $Root 'automation\setup\build_library.py'))
Step 'engineering calculations' @((Join-Path $Root 'engineering\calculations\power_stage.py'))
Step 'schematics + ERC + netlist check' @((Join-Path $Root 'automation\schematic\build_schematic.py'))
$variants = if ($Variant -eq 'all') { @('compact-22mm', 'evaluation-board') } else { @($Variant) }
foreach ($v in $variants) {
    if (-not (Test-Path (Join-Path $Root "hardware\$v\placement.yaml"))) { Write-Host "skip $v (no placement.yaml yet)"; continue }
    $stages = if ($SkipRouting) { @('place', 'finish', 'drc', 'cleanup') } else { @('place', 'route', 'finish', 'drc', 'cleanup') }
    foreach ($s in $stages) { Step "PCB $v : $s" @((Join-Path $Root 'automation\placement\build_pcb.py'), '--variant', $v, '--stage', $s) }
}
Step 'simulations' @((Join-Path $Root 'simulation\run_sims.py'))
Step 'sourcing database' @((Join-Path $Root 'sourcing\build_sourcing.py'))
& (Join-Path $Root 'firmware\build.ps1')

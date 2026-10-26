<#
.SYNOPSIS
    Build and test the NUBM44 driver firmware (ATtiny1616).
.DESCRIPTION
    Runs firmware\build.py, the single build driver shared with the validator and CI:
    1. Host unit tests (state machine, conversions, hold-up logic, runtime against a mock HAL, HAL register model).
    2. Target build with avr-gcc 15.2.0 (-mmcu=attiny1616, -Werror), producing build/nubm44_fw.hex.
    3. With -Mutation, re-injects each audited defect and requires the tests to catch it.
    Toolchains are project-local (tools\avr-gcc, tools\tcc), installed by scripts\setup.ps1.
.PARAMETER Flash
    Program the target with SerialUPDI (pymcuprog) on the given COM port, e.g. -Flash COM5.
    Disconnect the laser diode first; programming powers the board through the battery input.
    Fuses are NOT written by this script; program and verify them as described in firmware/README.md.
#>
[CmdletBinding()]
param([string]$Flash = "", [switch]$Mutation)

$ErrorActionPreference = 'Stop'
$Fw = $PSScriptRoot
$Root = Split-Path -Parent $Fw
$py = Join-Path $Root '.venv\Scripts\python.exe'

$buildArgs = @((Join-Path $Fw 'build.py'))
if ($Mutation) { $buildArgs += '--mutation' }
& $py @buildArgs
if ($LASTEXITCODE -ne 0) { throw 'firmware tests or build failed' }

if ($Flash) {
    Write-Host "== programming via SerialUPDI on $Flash"
    & $py -m pymcuprog.pymcuprog write -t uart -u $Flash -d attiny1616 -f (Join-Path $Fw 'build\nubm44_fw.hex') --erase --verify
    if ($LASTEXITCODE -ne 0) { throw 'programming failed' }
}

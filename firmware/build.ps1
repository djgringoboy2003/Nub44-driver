<#
.SYNOPSIS
    Build and test the NUBM44 driver firmware (ATtiny1616).
.DESCRIPTION
    1. Host unit tests of the hardware-independent state machine (src/app.c) with TinyCC.
    2. Target build with avr-gcc 15.2.0 (-mmcu=attiny1616), producing build/nubm44_fw.hex and a size report.
    Toolchains are project-local (tools\avr-gcc, tools\tcc), installed by scripts\setup.ps1.
.PARAMETER Flash
    Program the target with SerialUPDI (pymcuprog) on the given COM port, e.g. -Flash COM5.
    Disconnect the laser diode first; programming powers the board through the battery input.
#>
[CmdletBinding()]
param([string]$Flash = "")

$ErrorActionPreference = 'Stop'
$Fw = $PSScriptRoot
$Root = Split-Path -Parent $Fw
$Tcc = Get-ChildItem (Join-Path $Root 'tools\tcc') -Recurse -Filter tcc.exe | Select-Object -First 1
$Avr = Get-ChildItem (Join-Path $Root 'tools\avr-gcc') -Recurse -Filter avr-gcc.exe | Select-Object -First 1
if (-not $Tcc) { throw 'TinyCC not found; run scripts\setup.ps1' }
if (-not $Avr) { throw 'avr-gcc not found; run scripts\setup.ps1' }
$Bin = Split-Path $Avr.FullName
New-Item -ItemType Directory -Force (Join-Path $Fw 'build') | Out-Null

Write-Host '== host unit tests (src/app.c)'
& $Tcc.FullName -Wall -o (Join-Path $Fw 'build\test_app.exe') (Join-Path $Fw 'tests\test_app.c') (Join-Path $Fw 'src\app.c')
if ($LASTEXITCODE -ne 0) { throw 'unit test build failed' }
& (Join-Path $Fw 'build\test_app.exe')
if ($LASTEXITCODE -ne 0) { throw 'unit tests failed' }

Write-Host '== target build (ATtiny1616)'
$elf = Join-Path $Fw 'build\nubm44_fw.elf'
& (Join-Path $Bin 'avr-gcc.exe') -mmcu=attiny1616 -Os -std=gnu11 -Wall -Wextra -Werror -ffunction-sections `
    -fdata-sections '-Wl,--gc-sections' -o $elf (Join-Path $Fw 'src\main.c') (Join-Path $Fw 'src\app.c')
if ($LASTEXITCODE -ne 0) { throw 'firmware build failed' }
& (Join-Path $Bin 'avr-objcopy.exe') -O ihex -R .eeprom $elf (Join-Path $Fw 'build\nubm44_fw.hex')
& (Join-Path $Bin 'avr-size.exe') -A $elf | Select-String -Pattern '^\.(text|rodata|data|bss|noinit)'

if ($Flash) {
    Write-Host "== programming via SerialUPDI on $Flash"
    $py = Join-Path $Root '.venv\Scripts\python.exe'
    & $py -m pymcuprog.pymcuprog write -t uart -u $Flash -d attiny1616 -f (Join-Path $Fw 'build\nubm44_fw.hex') --erase --verify
    if ($LASTEXITCODE -ne 0) { throw 'programming failed' }
}

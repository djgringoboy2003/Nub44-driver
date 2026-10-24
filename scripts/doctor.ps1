<#
.SYNOPSIS
    Verify the NUBM44 toolchain without installing anything. Exit code 1 if anything required is missing.
#>
$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $PSScriptRoot
$fail = 0
function Check([string]$name, [scriptblock]$probe) {
    try { $v = & $probe; if (-not $v) { throw 'no output' }; Write-Host ("OK    {0,-22} {1}" -f $name, ($v | Select-Object -First 1)) }
    catch { Write-Host ("MISS  {0,-22} {1}" -f $name, $_.Exception.Message); $script:fail = 1 }
}
$KiCad = Join-Path $env:LOCALAPPDATA 'Programs\KiCad\10.0'
Check 'kicad-cli'          { & (Join-Path $KiCad 'bin\kicad-cli.exe') version }
Check 'KiCad python+pcbnew' { & (Join-Path $KiCad 'bin\python.exe') -c "import pcbnew; print('pcbnew', pcbnew.Version())" }
Check 'KiCad sym-lib-table' { if (Test-Path "$env:APPDATA\kicad\10.0\sym-lib-table") { 'present' } }
Check 'KiCad fp-lib-table'  { if (Test-Path "$env:APPDATA\kicad\10.0\fp-lib-table") { 'present' } }
Check 'Python venv'        { & (Join-Path $Root '.venv\Scripts\python.exe') -c "import numpy, scipy, matplotlib, yaml, fitz; print('venv ok')" }
Check 'ngspice'            { (& (Join-Path $Root 'tools\ngspice\Spice64\bin\ngspice_con.exe') --version 2>&1 | Select-String 'ngspice-').Line.Trim() }
Check 'Java 25 (router)'   { (& (Join-Path $Root 'tools\jre25\jdk-25.0.4.1+1-jre\bin\java.exe') -version 2>&1 | Select-Object -First 1).ToString() }
Check 'FreeRouting jar'    { if (Test-Path (Join-Path $Root 'tools\freerouting\freerouting-2.5.0.jar')) { 'freerouting-2.5.0.jar' } }
Check 'InteractiveHtmlBom' { if (Test-Path (Join-Path $Root 'tools\ibom\InteractiveHtmlBom\generate_interactive_bom.py')) { 'v2.12.0' } }
Check 'avr-gcc'            { & (Join-Path $Root 'tools\avr-gcc\avr-gcc-15.2.0-x64-windows\bin\avr-gcc.exe') --version | Select-Object -First 1 }
Check 'tcc (host tests)'   { if (Test-Path (Join-Path $Root 'tools\tcc\tcc\tcc.exe')) { 'tcc 0.9.27' } }
Check 'project library'    { if (Test-Path (Join-Path $Root 'hardware\libraries\nubm44.kicad_sym')) { 'nubm44.kicad_sym' } }
if ($fail) { Write-Host 'Some tools are missing: run scripts\setup.ps1'; exit 1 } else { Write-Host 'All tools present.' }

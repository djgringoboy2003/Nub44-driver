<#
.SYNOPSIS
    Install or repair the NUBM44 driver engineering toolchain (no administrator rights needed).

.DESCRIPTION
    Idempotent: each component is checked first and only installed when missing or broken.
    Existing KiCad configuration is preserved (library tables are only created if absent).
    Downloads come from official release locations and are verified against pinned SHA-256 hashes.

    Hash provenance:
      Temurin JRE      - published by the Adoptium API (package.checksum)
      InteractiveHtmlBom - published GitHub release asset digest
      ngspice, FreeRouting jar - no published SHA-256; pinned from the first download on 2026-10-24
                                 (FreeRouting's checksum file covers only its CLI archives)

    Components:
      - KiCad 10.0 (per-user via winget package KiCad.KiCad, installer /currentuser mode)
      - KiCad global symbol/footprint library tables (copied from KiCad's template if absent)
      - Project Python virtual environment (.venv) from requirements.txt
      - ngspice 47 (tools\ngspice)
      - Temurin Java 25 JRE (tools\jre25), needed because FreeRouting 2.5.0 targets Java 25
      - FreeRouting 2.5.0 jar (tools\freerouting). The 2.5.0 native freerouting-cli.exe is NOT used:
        it aborts with a GraalVM serialization error when routing.
      - InteractiveHtmlBom 2.12.0 (tools\ibom), run with KiCad's bundled Python

.PARAMETER Force
    Re-download and re-extract project-local tools even if they appear healthy.
#>
[CmdletBinding()]
param([switch]$Force)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Tools = Join-Path $Root 'tools'
$Reports = Join-Path $Root 'reports'
$Log = Join-Path $Reports 'setup.log'
New-Item -ItemType Directory -Force $Reports, $Tools | Out-Null

function Log([string]$msg) {
    $line = "{0:u}  {1}" -f (Get-Date), $msg
    Write-Host $line
    Add-Content -Path $Log -Value $line
}

function Get-Verified([string]$Url, [string]$Dest, [string]$Sha256) {
    if ((Test-Path $Dest) -and -not $Force) {
        if ((Get-FileHash $Dest -Algorithm SHA256).Hash -eq $Sha256.ToUpper()) { return }
        Log "hash mismatch for existing $Dest; downloading again"
    }
    New-Item -ItemType Directory -Force (Split-Path $Dest) | Out-Null
    Log "downloading $Url"
    & curl.exe -sSL --fail -o $Dest $Url
    if ($LASTEXITCODE -ne 0) { throw "download failed: $Url" }
    $h = (Get-FileHash $Dest -Algorithm SHA256).Hash
    if ($h -ne $Sha256.ToUpper()) {
        Remove-Item $Dest -Force
        throw "SHA-256 mismatch for $Dest (got $h, expected $Sha256); file deleted"
    }
    Log "verified $Dest"
}

function Expand-Zip([string]$Zip, [string]$Dest) {
    if (Test-Path $Dest) { Remove-Item $Dest -Recurse -Force }
    Expand-Archive -Path $Zip -DestinationPath $Dest -Force
}

# ------------------------------------------------------------------ KiCad
$KiCadRoot = Join-Path $env:LOCALAPPDATA 'Programs\KiCad\10.0'
$KiCadCli = Join-Path $KiCadRoot 'bin\kicad-cli.exe'
if (Test-Path $KiCadCli) {
    Log "KiCad present: $(& $KiCadCli version) at $KiCadRoot"
} else {
    Log 'KiCad 10 not found; installing per-user with winget (about 1 GB download)'
    winget install --id KiCad.KiCad --scope user --silent --accept-package-agreements `
        --accept-source-agreements --disable-interactivity
    if (-not (Test-Path $KiCadCli)) { throw "KiCad install did not produce $KiCadCli" }
    Log "KiCad installed: $(& $KiCadCli version)"
}

$KiCadCfg = Join-Path $env:APPDATA 'kicad\10.0'
New-Item -ItemType Directory -Force $KiCadCfg | Out-Null
foreach ($t in 'sym-lib-table', 'fp-lib-table') {
    $dst = Join-Path $KiCadCfg $t
    if (Test-Path $dst) { Log "kept existing $dst" }
    else {
        Copy-Item (Join-Path $KiCadRoot "share\kicad\template\$t") $dst
        Log "installed default $dst"
    }
}

# ------------------------------------------------------------------ Python venv
$Py = Join-Path $Root '.venv\Scripts\python.exe'
$venvOk = $false
if (Test-Path $Py) {
    & $Py -c "import numpy, scipy, matplotlib, yaml, jsonschema, pytest, py7zr" 2>$null
    $venvOk = ($LASTEXITCODE -eq 0)
}
if (-not $venvOk -or $Force) {
    $base = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $base) { throw 'Python 3.11+ not on PATH. Install it with: winget install Python.Python.3.11 --scope user' }
    if (Test-Path (Join-Path $Root '.venv')) { Log 'virtual environment missing packages; rebuilding' }
    & $base -m venv --clear (Join-Path $Root '.venv')
    & $Py -m pip install --quiet --upgrade pip
    & $Py -m pip install --quiet -r (Join-Path $Root 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'pip install failed' }
    Log "Python venv ready: $(& $Py --version)"
} else {
    Log "Python venv healthy: $(& $Py --version)"
}

# ------------------------------------------------------------------ ngspice 47
$Ngspice = Join-Path $Tools 'ngspice\Spice64\bin\ngspice_con.exe'
if ($Force -or -not (Test-Path $Ngspice)) {
    $arc = Join-Path $Tools 'dl-ngspice\ngspice-47_64.7z'
    Get-Verified 'https://sourceforge.net/projects/ngspice/files/ng-spice-rework/47/ngspice-47_64.7z/download' `
        $arc '59225971BD68CDD1199443649AA4615A9E6D684933F205AB49006A3942518F5A'
    $dest = Join-Path $Tools 'ngspice'
    if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
    & $Py -I -c "import sys, py7zr; py7zr.SevenZipFile(sys.argv[1]).extractall(sys.argv[2])" $arc $dest
    if (-not (Test-Path $Ngspice)) { throw 'ngspice extraction failed' }
}
Log "ngspice: $((& $Ngspice --version 2>&1 | Select-String 'ngspice-').Line.Trim())"

# ------------------------------------------------------------------ Java 25 (for FreeRouting)
$Java = Join-Path $Tools 'jre25\jdk-25.0.4.1+1-jre\bin\java.exe'
if ($Force -or -not (Test-Path $Java)) {
    $zip = Join-Path $Tools 'dl-jre\jre25.zip'
    Get-Verified 'https://github.com/adoptium/temurin25-binaries/releases/download/jdk-25.0.4.1%2B1/OpenJDK25U-jre_x64_windows_hotspot_25.0.4.1_1.zip' `
        $zip '4C95451CEA98556DEF2C54F7782933F52A26D4A36BD85E1D59F0364464828B07'
    Expand-Zip $zip (Join-Path $Tools 'jre25')
}
Log "java: $((& $Java -version 2>&1 | Select-Object -First 1))"

# ------------------------------------------------------------------ FreeRouting 2.5.0
$Jar = Join-Path $Tools 'freerouting\freerouting-2.5.0.jar'
Get-Verified 'https://github.com/freerouting/freerouting/releases/download/v2.5.0/freerouting-2.5.0.jar' `
    $Jar 'F6F51BB02245E8E717F9359BD260CC9C5C0B1BC0ACC8B7CB2CD5B8FFEB5DE3C7'
Log "freerouting: $Jar"

# ------------------------------------------------------------------ InteractiveHtmlBom 2.12.0
$Ibom = Join-Path $Tools 'ibom\InteractiveHtmlBom\generate_interactive_bom.py'
if ($Force -or -not (Test-Path $Ibom)) {
    $zip = Join-Path $Tools 'dl-ibom\InteractiveHtmlBom.zip'
    Get-Verified 'https://github.com/openscopeproject/InteractiveHtmlBom/releases/download/v2.12.0/InteractiveHtmlBom.zip' `
        $zip '2A7F7CA3EB75B174BFC86ECC321C4EED5813684B72341124D4E09416A912541E'
    Expand-Zip $zip (Join-Path $Tools 'ibom')
}
Log "InteractiveHtmlBom: $Ibom"

# ------------------------------------------------------------------ AVR toolchain (firmware)
$AvrGcc = Join-Path $Tools 'avr-gcc\avr-gcc-15.2.0-x64-windows\bin\avr-gcc.exe'
if ($Force -or -not (Test-Path $AvrGcc)) {
    $zip = Join-Path $Tools 'dl-avr\avr-gcc-15.2.0-x64-windows.zip'
    Get-Verified 'https://github.com/ZakKemble/avr-gcc-build/releases/download/v15.2.0-1/avr-gcc-15.2.0-x64-windows.zip' `
        $zip '3BCFDBDBFF6E3576EF0BEF9E119B16F7012657D30F002D6D9D4848A7EFD4F8B7'
    Expand-Zip $zip (Join-Path $Tools 'avr-gcc')
}
Log "avr-gcc: $((& $AvrGcc --version | Select-Object -First 1))"

# ------------------------------------------------------------------ TinyCC (host unit tests of firmware logic)
# No published SHA-256 (Savannah publishes a GPG .sig); hash pinned from the first download on 2026-10-24.
$Tcc = Join-Path $Tools 'tcc\tcc\tcc.exe'
if ($Force -or -not (Test-Path $Tcc)) {
    $zip = Join-Path $Tools 'dl-tcc\tcc-0.9.27-win64-bin.zip'
    Get-Verified 'https://download.savannah.gnu.org/releases/tinycc/tcc-0.9.27-win64-bin.zip' `
        $zip '34A721949A2583FDFF725312DA092FA0F5F1F284B702E6F811C6954714FAABB2'
    Expand-Zip $zip (Join-Path $Tools 'tcc')
}
Log "tcc: $Tcc"

Log 'setup complete; run scripts\doctor.ps1 to verify'

<#
.SYNOPSIS
    Create a DRAFT review ZIP with source/evidence hashes and recorded validation gates.
    Excludes tools, environments, downloads, caches, scratch builds and failed export drafts.
#>
param([string]$OutputDirectory = '')
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Root '.venv\Scripts\python.exe'
$PackageArgs = @((Join-Path $Root 'automation\export\package_project.py'))
if ($OutputDirectory) { $PackageArgs += @('--output-dir', $OutputDirectory) }
& $Py @PackageArgs
exit $LASTEXITCODE

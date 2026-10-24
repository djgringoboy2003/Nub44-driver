<#
.SYNOPSIS
    Run unit tests and build the validation register with computed release gates (reports/validation-register.md).
#>
$Root = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Root '.venv\Scripts\python.exe'
& $Py -m pytest (Join-Path $Root 'tests') -q
$t = $LASTEXITCODE
& $Py (Join-Path $Root 'automation\validation\validate.py')
$v = $LASTEXITCODE
exit ([int]($t -ne 0 -or $v -ne 0))

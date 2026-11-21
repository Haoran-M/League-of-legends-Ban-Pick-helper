param([string]$Python = "py")
$ErrorActionPreference = "Stop"
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
        if ($Python -eq 'py') { & $Python -3.12 -m venv .venv }
        else { & $Python -m venv .venv }
        if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 is required to create the virtual environment.' }
    }
    # A simple temp path also avoids setuptools interpolation of braces in sandbox temp paths.
    New-Item -ItemType Directory -Path '.tmp' -Force | Out-Null
    $previousTemp = $env:TEMP
    $previousTmp = $env:TMP
    try {
        $env:TEMP = (Resolve-Path -LiteralPath '.tmp').Path
        $env:TMP = $env:TEMP
        & .\.venv\Scripts\python.exe -c "import sys; assert sys.version_info[:2] == (3, 12), 'Python 3.12 required'"
        if ($LASTEXITCODE -ne 0) { throw 'Wrong Python version in .venv.' }
        & .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
        if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
        & .\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
        if ($LASTEXITCODE -ne 0) { throw 'Project installation failed.' }
    } finally { $env:TEMP = $previousTemp; $env:TMP = $previousTmp }
    Write-Output 'Ready. Launch: .\.venv\Scripts\python.exe -m league_draft'
} finally { Pop-Location }

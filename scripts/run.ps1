$ErrorActionPreference = "Stop"
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
        throw 'Run scripts\setup.ps1 with Python 3.12 first.'
    }
    & .\.venv\Scripts\python.exe -m league_draft @args
    exit $LASTEXITCODE
} finally { Pop-Location }

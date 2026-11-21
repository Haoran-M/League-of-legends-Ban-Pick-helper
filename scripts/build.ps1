param([ValidateSet('Both', 'OneDir', 'OneFile')][string]$Mode = 'Both', [switch]$SkipTests)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
$previousTemp = $env:TEMP
$previousTmp = $env:TMP
$previousMode = $env:LEAGUE_BUILD_MODE
try {
    New-Item -ItemType Directory -Path '.tmp' -Force | Out-Null
    $env:TEMP = (Resolve-Path -LiteralPath '.tmp').Path
    $env:TMP = $env:TEMP
    $pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Run scripts\setup.ps1 first.' }
    if (-not $SkipTests) {
        & $pythonPath -m pytest -q
        if ($LASTEXITCODE -ne 0) { throw 'Tests failed; stopped before packaging.' }
    }
    if ($Mode -in @('Both', 'OneDir')) {
        $env:LEAGUE_BUILD_MODE = 'onedir'
        & $pythonPath -m PyInstaller --noconfirm --workpath build\onedir --distpath dist\portable LeagueDraftAssistant.spec
        if ($LASTEXITCODE -ne 0) { throw 'Portable build failed.' }
        Copy-Item -LiteralPath 'README.md','DATA_SOURCES.md','THIRD_PARTY_NOTICES.md' -Destination 'dist\portable\LeagueDraftAssistant'
        Compress-Archive -Path 'dist\portable\LeagueDraftAssistant' -DestinationPath 'dist\LeagueDraftAssistant-portable.zip' -Force
    }
    if ($Mode -in @('Both', 'OneFile')) {
        $env:LEAGUE_BUILD_MODE = 'onefile'
        & $pythonPath -m PyInstaller --noconfirm --workpath build\onefile --distpath dist LeagueDraftAssistant.spec
        if ($LASTEXITCODE -ne 0) { throw 'Single-file build failed. The portable build remains available.' }
    }
    Copy-Item -LiteralPath 'README.md','DATA_SOURCES.md','THIRD_PARTY_NOTICES.md' -Destination 'dist'
    $hashLines = foreach ($artifactName in @('LeagueDraftAssistant.exe','LeagueDraftAssistant-portable.zip')) {
        $artifactPath = Join-Path $projectRoot "dist\$artifactName"
        if (Test-Path -LiteralPath $artifactPath) {
            $hash = Get-FileHash -LiteralPath $artifactPath -Algorithm SHA256
            "$($hash.Hash.ToLowerInvariant())  $artifactName"
        }
    }
    $hashLines | Set-Content -LiteralPath 'dist\SHA256SUMS.txt' -Encoding ascii
    Write-Output 'Build complete. Artifacts and SHA256SUMS.txt are in dist.'
} finally {
    $env:TEMP = $previousTemp
    $env:TMP = $previousTmp
    $env:LEAGUE_BUILD_MODE = $previousMode
    Pop-Location
}

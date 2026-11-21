# Dot-source inside build/setup scripts; changes only that PowerShell process.
$androidProjectRoot = Split-Path -Parent $PSScriptRoot
$androidToolchain = Get-Content -LiteralPath (Join-Path $androidProjectRoot 'android\toolchain.json') -Raw | ConvertFrom-Json
$env:JAVA_HOME = Join-Path $androidProjectRoot ".tmp\android-tools\jdk\$($androidToolchain.jdk.directory)"
$env:GRADLE_USER_HOME = Join-Path $androidProjectRoot '.tmp\g'
$env:ANDROID_HOME = Join-Path $androidProjectRoot '.tmp\as'
$env:ANDROID_USER_HOME = Join-Path $androidProjectRoot '.tmp\au'
$env:ANDROID_AVD_HOME = Join-Path $androidProjectRoot '.tmp\avd'
$env:LEAGUE_BUILD_PYTHON = Join-Path $androidProjectRoot '.venv\Scripts\python.exe'

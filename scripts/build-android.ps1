param([switch]$SkipTests, [switch]$DeviceTests)
$ErrorActionPreference = 'Stop'
$androidOldEnvironment = @{}
foreach ($key in @('JAVA_HOME','GRADLE_USER_HOME','ANDROID_HOME','ANDROID_USER_HOME','ANDROID_AVD_HOME','LEAGUE_BUILD_PYTHON')) { $androidOldEnvironment[$key] = [Environment]::GetEnvironmentVariable($key, 'Process') }
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    . (Join-Path $PSScriptRoot 'android-environment.ps1')
    $gradle = Join-Path $androidProjectRoot ".tmp\android-tools\gradle-$($androidToolchain.gradle.version)\bin\gradle.bat"
    if (-not (Test-Path -LiteralPath $gradle)) { throw 'Run scripts\setup-android.ps1 first.' }
    if (-not $SkipTests) {
        & $env:LEAGUE_BUILD_PYTHON -m pytest -q
        if ($LASTEXITCODE -ne 0) { throw 'Shared-core tests failed.' }
    }
    $androidTasks = @('assembleRelease','lintRelease')
    if ($DeviceTests) { $androidTasks += 'connectedDebugAndroidTest' }
    & $gradle -p android --console plain @androidTasks
    if ($LASTEXITCODE -ne 0) { throw 'Android build or requested verification failed.' }
    New-Item -ItemType Directory -Path 'dist' -Force | Out-Null
    $apk = Join-Path $androidProjectRoot 'dist\LeagueDraftAssistant.apk'
    Copy-Item -LiteralPath 'android\app\build\outputs\apk\release\app-release.apk' -Destination $apk
    & (Join-Path $env:ANDROID_HOME "build-tools\$($androidToolchain.build_tools)\apksigner.bat") verify --verbose $apk
    if ($LASTEXITCODE -ne 0) { throw 'APK signature verification failed.' }
    & (Join-Path $env:ANDROID_HOME "build-tools\$($androidToolchain.build_tools)\zipalign.exe") -c -P 16 4 $apk
    if ($LASTEXITCODE -ne 0) { throw 'APK alignment verification failed.' }
    $hash = (Get-FileHash -LiteralPath $apk -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  LeagueDraftAssistant.apk" | Set-Content -LiteralPath 'dist\APK_SHA256SUMS.txt' -Encoding ascii
    Write-Output "APK built: $apk ($((Get-Item -LiteralPath $apk).Length) bytes)"
} finally {
    foreach ($key in $androidOldEnvironment.Keys) { [Environment]::SetEnvironmentVariable($key, $androidOldEnvironment[$key], 'Process') }
    Pop-Location
}

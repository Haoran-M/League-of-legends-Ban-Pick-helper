param([switch]$AcceptSdkLicense)
$ErrorActionPreference = 'Stop'
$androidOldEnvironment = @{}
foreach ($key in @('JAVA_HOME','GRADLE_USER_HOME','ANDROID_HOME','ANDROID_USER_HOME','ANDROID_AVD_HOME','LEAGUE_BUILD_PYTHON')) { $androidOldEnvironment[$key] = [Environment]::GetEnvironmentVariable($key, 'Process') }
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    . (Join-Path $PSScriptRoot 'android-environment.ps1')
    $downloads = Join-Path $androidProjectRoot '.tmp\android-tools\downloads'
    New-Item -ItemType Directory -Path $downloads,$env:ANDROID_USER_HOME,$env:ANDROID_AVD_HOME -Force | Out-Null
    function Receive-VerifiedArchive($url, $hash, $destination) {
        if (-not (Test-Path -LiteralPath $destination)) { Invoke-WebRequest -Uri $url -OutFile $destination }
        if ((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant() -ne $hash) { throw "Checksum mismatch: $destination" }
    }
    if (-not (Test-Path -LiteralPath (Join-Path $env:JAVA_HOME 'bin\java.exe'))) {
        $archive = Join-Path $downloads 'jdk21.zip'
        Receive-VerifiedArchive $androidToolchain.jdk.url $androidToolchain.jdk.sha256 $archive
        Expand-Archive -LiteralPath $archive -DestinationPath '.tmp\android-tools\jdk' -Force
    }
    $gradle = Join-Path $androidProjectRoot ".tmp\android-tools\gradle-$($androidToolchain.gradle.version)\bin\gradle.bat"
    if (-not (Test-Path -LiteralPath $gradle)) {
        $archive = Join-Path $downloads 'gradle-8.11.1-bin.zip'
        Receive-VerifiedArchive $androidToolchain.gradle.url $androidToolchain.gradle.sha256 $archive
        Expand-Archive -LiteralPath $archive -DestinationPath '.tmp\android-tools' -Force
    }
    $manager = Join-Path $env:ANDROID_HOME 'cmdline-tools\latest\bin\sdkmanager.bat'
    if (-not (Test-Path -LiteralPath $manager)) {
        $archive = Join-Path $downloads 'android-commandline.zip'
        Receive-VerifiedArchive $androidToolchain.android_command_line.url $androidToolchain.android_command_line.sha256 $archive
        Expand-Archive -LiteralPath $archive -DestinationPath '.tmp\android-tools\commandline' -Force
        $source = [IO.Path]::GetFullPath((Join-Path $androidProjectRoot '.tmp\android-tools\commandline\cmdline-tools'))
        $destination = [IO.Path]::GetFullPath((Join-Path $env:ANDROID_HOME 'cmdline-tools\latest'))
        $boundary = $androidProjectRoot.TrimEnd('\') + '\'
        if (-not $source.StartsWith($boundary,[StringComparison]::OrdinalIgnoreCase) -or -not $destination.StartsWith($boundary,[StringComparison]::OrdinalIgnoreCase)) { throw 'SDK move escaped the project directory.' }
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        Move-Item -LiteralPath $source -Destination $destination
    }
    if ($AcceptSdkLicense) {
        1..100 | ForEach-Object { 'y' } | & $manager "--sdk_root=$env:ANDROID_HOME" "platforms;android-$($androidToolchain.compile_sdk)" "build-tools;$($androidToolchain.build_tools)" 'platform-tools'
    } else {
        & $manager "--sdk_root=$env:ANDROID_HOME" "platforms;android-$($androidToolchain.compile_sdk)" "build-tools;$($androidToolchain.build_tools)" 'platform-tools'
    }
    if ($LASTEXITCODE -ne 0) { throw 'Android SDK setup failed.' }
    ('sdk.dir=' + $env:ANDROID_HOME.Replace('\','/')) | Set-Content -LiteralPath 'android\local.properties' -Encoding ascii
    $keyDirectory = Join-Path $androidProjectRoot '.tmp\android-signing'
    New-Item -ItemType Directory -Path $keyDirectory -Force | Out-Null
    $keyFile = Join-Path $keyDirectory 'debug.keystore'
    if (-not (Test-Path -LiteralPath $keyFile)) {
        & (Join-Path $env:JAVA_HOME 'bin\keytool.exe') -genkeypair -keystore $keyFile -storepass android -alias androiddebugkey -keypass android -dname 'CN=Android Debug,O=Android,C=US' -keyalg RSA -keysize 2048 -validity 10000
        if ($LASTEXITCODE -ne 0) { throw 'Could not create local testing signing key.' }
    }
    Write-Output 'Android toolchain is ready. Build: .\scripts\build-android.ps1'
} finally {
    foreach ($key in $androidOldEnvironment.Keys) { [Environment]::SetEnvironmentVariable($key, $androidOldEnvironment[$key], 'Process') }
    Pop-Location
}

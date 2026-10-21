param(
    [string]$FlutterSdk = "$env:USERPROFILE\develop\flutter",
    [string]$Config = "",
    [switch]$Release
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$flutterTool = Join-Path $FlutterSdk 'bin/flutter.bat'
if (-not $Config) { $Config = if ($Release) { 'config/production.json' } else { 'config/development.json' } }
$buildMode = if ($Release) { 'release' } else { 'debug' }
if (-not (Test-Path -LiteralPath $flutterTool)) { throw 'Flutter SDK não encontrado. Informe -FlutterSdk.' }
Push-Location (Join-Path $projectRoot 'mobile')
try {
    $pubspecText = Get-Content -LiteralPath 'pubspec.yaml' -Raw
    if ($pubspecText -notmatch '(?m)^version:\s*(\d+\.\d+\.\d+)\+(\d+)') { throw 'Versão inválida no pubspec.' }
    $releaseVersion = $Matches[1]
    $releaseBuild = [int]$Matches[2]
    $appConfiguration = Get-Content -LiteralPath $Config -Raw | ConvertFrom-Json
    $releaseMetadata = @{ version = $releaseVersion; build = $releaseBuild; package_id = $appConfiguration.APP_ID; company_slug = $appConfiguration.COMPANY_SLUG } | ConvertTo-Json -Compress
    [System.IO.Directory]::CreateDirectory((Join-Path $PWD 'assets')) | Out-Null
    [System.IO.File]::WriteAllText((Join-Path $PWD 'assets/release.json'), $releaseMetadata, [System.Text.UTF8Encoding]::new($false))
    & $flutterTool pub get
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao resolver dependências.' }
    & $flutterTool analyze
    if ($LASTEXITCODE -ne 0) { throw 'Falha na análise do aplicativo.' }
    & $flutterTool test
    if ($LASTEXITCODE -ne 0) { throw 'Falha nos testes do aplicativo.' }
    & $flutterTool build apk "--$buildMode" "--dart-define-from-file=$Config"
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao compilar APK.' }
    $outputDirectory = Join-Path $projectRoot 'artifacts/mobile'
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
    Copy-Item -LiteralPath "build/app/outputs/flutter-apk/app-$buildMode.apk" -Destination (Join-Path $outputDirectory "nexus-rotafy-$buildMode.apk")
    if ($Release) {
        Copy-Item -LiteralPath (Join-Path $outputDirectory 'nexus-rotafy-release.apk') -Destination (Join-Path $outputDirectory "nexus-rotafy-$releaseVersion.apk")
        $apkHash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $outputDirectory "nexus-rotafy-$releaseVersion.apk")).Hash.ToLowerInvariant()
        [System.IO.File]::WriteAllText((Join-Path $outputDirectory "nexus-rotafy-$releaseVersion.apk.sha256"), "$apkHash  nexus-rotafy-$releaseVersion.apk`n")
    }
    Write-Output "APK: $outputDirectory\nexus-rotafy-$buildMode.apk"
} finally { Pop-Location }

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
    Write-Output "APK: $outputDirectory\nexus-rotafy-$buildMode.apk"
} finally { Pop-Location }

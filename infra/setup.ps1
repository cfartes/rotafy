$ErrorActionPreference = 'Stop'
$workspacePath = Split-Path -Parent $PSScriptRoot
$envFilePath = Join-Path $workspacePath '.env'
if (Test-Path -LiteralPath $envFilePath) {
    Write-Output '.env já existe; nenhuma credencial foi alterada.'
    exit 0
}
function New-RotafySecret {
    $secretBytes = New-Object byte[] 32
    $randomGenerator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $randomGenerator.GetBytes($secretBytes) } finally { $randomGenerator.Dispose() }
    return ([BitConverter]::ToString($secretBytes)).Replace('-', '').ToLowerInvariant()
}
$envContent = @"
POSTGRES_PASSWORD=$(New-RotafySecret)
APP_DB_PASSWORD=$(New-RotafySecret)
PLATFORM_DB_PASSWORD=$(New-RotafySecret)
BOOTSTRAP_EMAIL=admin@nexusdataanalytics.com.br
BOOTSTRAP_PASSWORD=$(New-RotafySecret)
WEB_PORT=5178
API_PORT=8018
DB_PORT=5448
COOKIE_SECURE=false
ALLOWED_ORIGINS=http://localhost:5178
"@
[IO.File]::WriteAllText($envFilePath, $envContent, (New-Object Text.UTF8Encoding $false))
Write-Output 'Credenciais locais geradas em .env. Não publique esse arquivo.'

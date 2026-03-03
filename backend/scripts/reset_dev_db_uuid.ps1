param(
    [string]$EnvFile = "backend/.env",
    [string]$SettingsModule = "config.settings.development",
    [switch]$SkipBackup,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-EnvMap {
    param([string]$Path)

    if (-not (Test-Path -Path $Path)) {
        throw "Env file not found: $Path"
    }

    $map = @{}
    foreach ($line in Get-Content -Path $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }
        $idx = $trimmed.IndexOf("=")
        if ($idx -lt 1) {
            continue
        }
        $key = $trimmed.Substring(0, $idx).Trim()
        $value = $trimmed.Substring($idx + 1).Trim().Trim('"').Trim("'")
        $map[$key] = $value
    }
    return $map
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$envPath = Join-Path $repoRoot $EnvFile
$envMap = Get-EnvMap -Path $envPath

$dbName = $envMap["POSTGRES_DB"]
$dbUser = $envMap["POSTGRES_USER"]
$dbPassword = $envMap["POSTGRES_PASSWORD"]
$dbHost = $envMap["POSTGRES_HOST"]
$dbPort = $envMap["POSTGRES_PORT"]

if (-not $dbName) { throw "POSTGRES_DB is missing in $envPath" }
if (-not $dbUser) { throw "POSTGRES_USER is missing in $envPath" }
if (-not $dbHost) { $dbHost = "localhost" }
if (-not $dbPort) { $dbPort = "5432" }

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDir = Join-Path $repoRoot "backend\backups"
$backupFile = Join-Path $backupDir "$dbName-pre-uuid-$timestamp.dump"

Write-Host "UUID DB reset plan"
Write-Host "  Env file:     $envPath"
Write-Host "  Database:     $dbName"
Write-Host "  Host:         ${dbHost}:$dbPort"
Write-Host "  User:         $dbUser"
if (-not $SkipBackup) {
    Write-Host "  Backup file:  $backupFile"
}
Write-Host "  Settings:     $SettingsModule"

if (-not $Force) {
    Write-Host ""
    Write-Host "Dry run only. Re-run with -Force to execute."
    exit 0
}

if (-not $SkipBackup) {
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    $env:PGPASSWORD = $dbPassword
    & pg_dump -h $dbHost -p $dbPort -U $dbUser -Fc -f $backupFile $dbName
    Write-Host "Backup complete: $backupFile"
}

$env:PGPASSWORD = $dbPassword
& dropdb --if-exists -h $dbHost -p $dbPort -U $dbUser $dbName
& createdb -h $dbHost -p $dbPort -U $dbUser $dbName
Write-Host "Database recreated: $dbName"

$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -Path $pythonExe)) {
    throw "Python venv not found at: $pythonExe"
}

$env:DJANGO_SETTINGS_MODULE = $SettingsModule
Set-Location -Path $repoRoot

& $pythonExe backend\manage.py migrate --noinput
& $pythonExe backend\manage.py check
& $pythonExe backend\manage.py check_uuid_schema

Write-Host "UUID DB reset and migration completed successfully."

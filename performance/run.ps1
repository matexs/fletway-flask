param(
    [ValidateSet('all', 'smoke', 'load', 'stress')]
    [string]$Profile = 'smoke',
    [string]$BaseUrl = ''
)

$ErrorActionPreference = 'Stop'
$performanceRoot = $PSScriptRoot
$backendRoot = Split-Path -Parent $performanceRoot
$envFile = Join-Path $performanceRoot '.env.performance'
$allowedKeys = @(
    'BASE_URL', 'SUPABASE_URL', 'SUPABASE_ANON_KEY',
    'CLIENT_EMAIL', 'CLIENT_PASSWORD', 'DRIVER_EMAIL', 'DRIVER_PASSWORD',
    'SEARCH_QUERY', 'REQUEST_TIMEOUT', 'THINK_TIME_SECONDS'
)

if (Test-Path -LiteralPath $envFile) {
    foreach ($line in Get-Content -LiteralPath $envFile) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#') -or -not $trimmed.Contains('=')) { continue }
        $parts = $trimmed.Split('=', 2)
        $key = $parts[0].Trim()
        $value = $parts[1].Trim()
        if ($allowedKeys -contains $key -and -not [Environment]::GetEnvironmentVariable($key, 'Process')) {
            [Environment]::SetEnvironmentVariable($key, $value, 'Process')
        }
    }
}

if ($BaseUrl) { $env:BASE_URL = $BaseUrl.TrimEnd('/') }
if (-not $env:BASE_URL) { $env:BASE_URL = 'https://fletway.onrender.com' }

$requiredKeys = @('SUPABASE_URL', 'SUPABASE_ANON_KEY', 'CLIENT_EMAIL', 'CLIENT_PASSWORD', 'DRIVER_EMAIL', 'DRIVER_PASSWORD')
$missingKeys = $requiredKeys | Where-Object { -not [Environment]::GetEnvironmentVariable($_, 'Process') }
if ($missingKeys) {
    throw "Faltan variables: $($missingKeys -join ', '). Copie .env.performance.example como .env.performance y complete los valores."
}

$k6Command = Get-Command k6 -ErrorAction SilentlyContinue
$k6Executable = if ($k6Command) { $k6Command.Source } else { '' }
if (-not $k6Executable) {
    $installedK6 = 'C:\Program Files\k6\k6.exe'
    if (Test-Path -LiteralPath $installedK6) { $k6Executable = $installedK6 }
}
if (-not $k6Executable) { throw 'k6 no está instalado o no está disponible en PATH.' }

New-Item -ItemType Directory -Force -Path (Join-Path $performanceRoot 'results') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $performanceRoot 'reports') | Out-Null

$runId = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH-mm-ssZ')
$profiles = if ($Profile -eq 'all') { @('smoke', 'load', 'stress') } else { @($Profile) }
$scriptPath = Join-Path $performanceRoot 'k6\scripts\fletway-api.js'

Push-Location $backendRoot
try {
    foreach ($selectedProfile in $profiles) {
        $env:PROFILE = $selectedProfile
        $env:RUN_ID = $runId
        Write-Host "`nEjecutando perfil $selectedProfile contra $($env:BASE_URL)..." -ForegroundColor Cyan
        & $k6Executable run $scriptPath
        if ($LASTEXITCODE -ne 0) {
            throw "El perfil $selectedProfile terminó con código $LASTEXITCODE. Revise el reporte generado."
        }
    }
}
finally {
    Pop-Location
}

Write-Host "`nReportes disponibles en $performanceRoot\reports" -ForegroundColor Green

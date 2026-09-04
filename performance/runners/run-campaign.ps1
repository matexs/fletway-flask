[CmdletBinding()]
param(
    [string]$ManifestPath = (Join-Path $PSScriptRoot '..\config\endpoints.manifest.json'),
    [string]$PerformanceRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$BaseUrl = '',
    [string]$RunId = ''
)

$ErrorActionPreference = 'Stop'
$PerformanceRoot = [IO.Path]::GetFullPath($PerformanceRoot)
$ManifestPath = [IO.Path]::GetFullPath($ManifestPath)
$envFile = Join-Path $PerformanceRoot 'env.performance'
if (-not (Test-Path -LiteralPath $envFile)) { $envFile = Join-Path $PerformanceRoot '.env.performance' }
if (-not (Test-Path -LiteralPath $envFile)) { throw 'Missing performance environment file' }
$allowed = @('BASE_URL','SUPABASE_URL','SUPABASE_ANON_KEY','CLIENT_EMAIL','CLIENT_PASSWORD','DRIVER_EMAIL','DRIVER_PASSWORD','LOCALIDAD_ORIGEN_ID','LOCALIDAD_DESTINO_ID','SOLICITUD_ID','MAX_SETUP_VUS','REQUEST_TIMEOUT','SETUP_REQUEST_TIMEOUT','THINK_TIME_SECONDS')
foreach ($line in Get-Content -LiteralPath $envFile) {
    $trimmed = $line.Trim()
    if (-not $trimmed -or $trimmed.StartsWith('#') -or -not $trimmed.Contains('=')) { continue }
    $parts = $trimmed.Split('=', 2)
    if ($allowed -contains $parts[0].Trim() -and -not [Environment]::GetEnvironmentVariable($parts[0].Trim(), 'Process')) { [Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim(), 'Process') }
}
if ($BaseUrl) { $env:BASE_URL = $BaseUrl.TrimEnd('/') }
if (-not $env:BASE_URL) { throw 'BASE_URL is required' }
foreach ($name in @('SUPABASE_URL','SUPABASE_ANON_KEY','CLIENT_EMAIL','CLIENT_PASSWORD','DRIVER_EMAIL','DRIVER_PASSWORD')) { if (-not [Environment]::GetEnvironmentVariable($name, 'Process')) { throw "Missing performance variable: $name" } }

$manifest = Get-Content -Raw -LiteralPath $ManifestPath | ConvertFrom-Json
$runId = if ($RunId) { $RunId } else { [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss') }
if ($runId -notmatch '^[A-Za-z0-9][A-Za-z0-9_-]{0,100}$') { throw "Unsafe RunId: $runId" }
$campaignDirectory = Join-Path $PerformanceRoot "campaigns\$runId"
$lockPath = Join-Path $PerformanceRoot 'campaigns\.run.lock'
$lock = $null
try {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $lockPath),$campaignDirectory | Out-Null
    $lock = [IO.FileStream]::new($lockPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    $endpoints = @($manifest.endpoints)
    $preflight = @{}
    foreach ($endpoint in $endpoints) {
        $out = Join-Path $campaignDirectory "preflight-$($endpoint.id).json"
        & pwsh -NoProfile -File (Join-Path $PSScriptRoot 'preflight.ps1') -EndpointId $endpoint.id -ManifestPath $ManifestPath -OutputPath $out
        $preflight[$endpoint.id] = ($LASTEXITCODE -eq 0)
    }
    $smokeStatus = @{}
    foreach ($profile in @('smoke','load','stress','spike')) {
        foreach ($endpoint in $endpoints) {
            if ($profile -notin @($endpoint.enabled_profiles)) { continue }
            $allowedToRun = $preflight[$endpoint.id]
            if ($profile -ne 'smoke' -and 'smoke' -in @($endpoint.enabled_profiles)) { $allowedToRun = $allowedToRun -and $smokeStatus[$endpoint.id] }
            if (-not $allowedToRun) {
                $rawDirectory = Join-Path $campaignDirectory 'raw'; New-Item -ItemType Directory -Force -Path $rawDirectory | Out-Null
                [ordered]@{ endpoint_id = $endpoint.id; profile = $profile; run_id = $runId; result = 'NO_EJECUTADA'; reason = 'preflight or smoke gate failed' } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $rawDirectory "$($endpoint.id)-$profile.json") -Encoding utf8NoBOM
                if ($profile -eq 'smoke') { $smokeStatus[$endpoint.id] = $false }
                continue
            }
            & pwsh -NoProfile -File (Join-Path $PSScriptRoot 'run-endpoint.ps1') -EndpointId $endpoint.id -Profile $profile -ManifestPath $ManifestPath -CampaignDirectory $campaignDirectory -PerformanceRoot $PerformanceRoot -RunId $runId
            $exitCode = $LASTEXITCODE
            if ($profile -eq 'smoke') { $smokeStatus[$endpoint.id] = ($exitCode -eq 0) }
        }
    }
    & pwsh -NoProfile -File (Join-Path $PerformanceRoot 'scripts\build-general-matrix.ps1') -CampaignDirectory $campaignDirectory -ManifestPath $ManifestPath
    & pwsh -NoProfile -File (Join-Path $PerformanceRoot 'scripts\generate-general-report.ps1') -CampaignDirectory $campaignDirectory -ManifestPath $ManifestPath
} finally {
    if ($lock) { $lock.Dispose() }
    if (Test-Path -LiteralPath $lockPath) { Remove-Item -LiteralPath $lockPath -Force -ErrorAction SilentlyContinue }
}
Write-Output "Campaign completed: $campaignDirectory"

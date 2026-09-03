param(
    [Parameter(Mandatory = $true)][string]$EndpointId,
    [ValidateSet('smoke', 'load', 'stress', 'stress_p0', 'spike')][string]$Profile = 'smoke',
    [string]$Stage = '',
    [int]$VuMin = 0,
    [int]$VuMax = 0,
    [int]$RecoveryVus = 0,
    [string]$RecoveryDuration = '',
    [string]$BaseUrl = '',
    [string]$K6Script = '',
    [string]$OutputPath = '',
    [switch]$WhatIf
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$scriptPath = if ($K6Script) { $K6Script } else { Join-Path $repoRoot 'performance\k6\scripts\fletway-api.js' }
$stageName = if ($Stage) { $Stage } else { $Profile }
$rawPath = if ($OutputPath) { $OutputPath } else { Join-Path $repoRoot ("performance\results\endpoint-{0}-{1}-{2}.json" -f $EndpointId, $Profile, ([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ'))) }
$arguments = @('run', $scriptPath, '--env', "ENDPOINT_ID=$EndpointId", '--env', "PROFILE=$Profile", '--env', "STAGE=$stageName", '--env', "VU_MIN=$VuMin", '--env', "VU_MAX=$VuMax")
if ($BaseUrl) { $arguments += @('--env', "BASE_URL=$BaseUrl") }
if ($RecoveryVus -gt 0) { $arguments += @('--env', "RECOVERY_VUS=$RecoveryVus") }
if ($RecoveryDuration) { $arguments += @('--env', "RECOVERY_DURATION=$RecoveryDuration") }
$arguments += @('--summary-export', $rawPath)

if ($WhatIf) {
    Write-Output ($arguments -join ' ')
    exit 0
}

$k6 = Get-Command k6 -ErrorAction SilentlyContinue
if (-not $k6) { throw 'k6 no está instalado o no está disponible en PATH.' }
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $rawPath) | Out-Null
& $k6.Source @arguments
if ($LASTEXITCODE -ne 0) { throw "k6 terminó con código $LASTEXITCODE." }

$raw = Get-Content -LiteralPath $rawPath -Raw | ConvertFrom-Json
$metadata = [ordered]@{
    endpoint_id = $EndpointId
    profile = $Profile
    stage = $stageName
    vu_min = $VuMin
    vu_max = $VuMax
}
if ($RecoveryVus -gt 0 -or $RecoveryDuration) {
    $metadata.recovery = [ordered]@{ target = $RecoveryVus; duration = $RecoveryDuration }
}
$envelope = [ordered]@{}
$metadata.GetEnumerator() | ForEach-Object { $envelope[$_.Key] = $_.Value }
$envelope.k6 = $raw
$envelope | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $rawPath -Encoding utf8
Write-Output $rawPath

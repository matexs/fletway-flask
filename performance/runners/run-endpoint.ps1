param(
    [Parameter(Mandatory = $true)][string]$EndpointId,
    [ValidateSet('smoke', 'load', 'stress', 'stress_p0', 'spike')][string]$Profile = 'smoke',
    [string]$Stage = '',
    [int]$VuMin = 0,
    [int]$VuMax = 0,
    [int]$BaselineVus = 0,
    [int]$SpikeVus = 0,
    [int]$RecoveryVus = 0,
    [string]$RecoveryDuration = '',
    [string]$BaseUrl = '',
    [string]$K6Script = '',
    [string]$OutputPath = '',
    [switch]$Force,
    [switch]$WhatIf
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$scriptPath = if ($K6Script) { $K6Script } else { Join-Path $repoRoot 'performance\k6\scripts\fletway-api.js' }
$manifestPath = Join-Path $repoRoot 'performance\config\endpoints.manifest.json'
$manifestIds = @((Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json).endpoints | ForEach-Object { $_.id })
if ($manifestIds -notcontains $EndpointId) { throw "Unknown endpoint ID: $EndpointId." }

$stageName = if ($Stage) { $Stage } else { $Profile }
$effectiveProfile = $Profile
switch ($Profile) {
    'smoke' { if ($VuMin -eq 0) { $VuMin = 0 }; if ($VuMax -eq 0) { $VuMax = 3 } }
    'load' { if ($VuMin -eq 0) { $VuMin = 0 }; if ($VuMax -eq 0) { $VuMax = 10 } }
    'stress' {
        if (-not $Stage -or $Stage -notmatch '^stress_(10|20|30)$') { throw 'Stress requires one canonical stage: stress_10, stress_20, or stress_30.' }
        $effectiveProfile = $Stage; $stageVus = [int]$Stage.Substring(7)
        if ($VuMin -eq 0) { $VuMin = $stageVus }; if ($VuMax -eq 0) { $VuMax = $stageVus }
    }
    'stress_p0' {
        if (-not $Stage -or $Stage -notmatch '^stress_p0_(20|40|60|80|100)$') { throw 'Stress P0 requires one canonical stage: stress_p0_20, stress_p0_40, stress_p0_60, stress_p0_80, or stress_p0_100.' }
        $effectiveProfile = $Stage; $stageVus = [int]$Stage.Substring(10)
        if ($VuMin -eq 0) { $VuMin = $stageVus }; if ($VuMax -eq 0) { $VuMax = $stageVus }
    }
    'spike' {
        if ($BaselineVus -eq 0) { $BaselineVus = 3 }; if ($SpikeVus -eq 0) { $SpikeVus = 30 }
        if ($RecoveryVus -eq 0) { $RecoveryVus = $BaselineVus }; if (-not $RecoveryDuration) { $RecoveryDuration = '30s' }
        if ($VuMin -eq 0) { $VuMin = $BaselineVus }; if ($VuMax -eq 0) { $VuMax = $SpikeVus }
    }
}
if ($VuMin -lt 0 -or $VuMax -le 0 -or $VuMin -gt $VuMax) { throw 'VU bounds must satisfy 0 <= vu_min <= vu_max and vu_max > 0.' }
if ($Profile -eq 'spike' -and ($BaselineVus -le 0 -or $SpikeVus -le 0 -or $RecoveryVus -le 0)) { throw 'Spike VU controls must be positive.' }

$resultsRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot 'performance\results')).TrimEnd('\') + '\'
if ($OutputPath) {
    $candidate = if ([IO.Path]::IsPathRooted($OutputPath)) { $OutputPath } else { Join-Path $repoRoot $OutputPath }
    $rawPath = [IO.Path]::GetFullPath($candidate)
    if (-not $rawPath.StartsWith($resultsRoot, [StringComparison]::OrdinalIgnoreCase) -or [IO.Path]::GetFileName($rawPath) -notmatch '^[A-Za-z0-9._-]+\.json$') { throw 'Output path must be a sanitized JSON file inside performance/results.' }
} else {
    $rawPath = Join-Path $resultsRoot ("endpoint-{0}-{1}-{2}-{3}.json" -f $EndpointId, $effectiveProfile, ([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')), ([guid]::NewGuid().ToString('N')))
}
if ((Test-Path -LiteralPath $rawPath) -and -not $Force) { throw "Output already exists; pass -Force to overwrite: $rawPath" }

$arguments = @('run', $scriptPath, '--env', "ENDPOINT_ID=$EndpointId", '--env', "PROFILE=$effectiveProfile", '--env', "STAGE=$stageName", '--env', "VU_MIN=$VuMin", '--env', "VU_MAX=$VuMax")
if ($BaseUrl) { $arguments += @('--env', "BASE_URL=$BaseUrl") }
if ($Profile -eq 'spike') { $arguments += @('--env', "BASELINE_VUS=$BaselineVus", '--env', "SPIKE_VUS=$SpikeVus", '--env', "RECOVERY_VUS=$RecoveryVus", '--env', "RECOVERY_DURATION=$RecoveryDuration") }
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
if ($Profile -eq 'spike') {
    $metadata.recovery = [ordered]@{ target = $RecoveryVus; duration = $RecoveryDuration }
}
$envelope = [ordered]@{}
$metadata.GetEnumerator() | ForEach-Object { $envelope[$_.Key] = $_.Value }
$envelope.k6 = $raw
$envelope | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $rawPath -Encoding utf8
Write-Output $rawPath

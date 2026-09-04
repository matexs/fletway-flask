[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$EndpointId,
    [Parameter(Mandatory = $true)][ValidateSet('smoke','load','stress','spike')][string]$Profile,
    [Parameter(Mandatory = $true)][string]$ManifestPath,
    [Parameter(Mandatory = $true)][string]$CampaignDirectory,
    [Parameter(Mandatory = $true)][string]$PerformanceRoot,
    [Parameter(Mandatory = $true)][string]$RunId
)

$ErrorActionPreference = 'Stop'
$manifest = Get-Content -Raw -LiteralPath $ManifestPath | ConvertFrom-Json
$endpoint = @($manifest.endpoints | Where-Object id -eq $EndpointId)[0]
if ($null -eq $endpoint) { throw "Unknown endpoint: $EndpointId" }
$scriptDirectory = if ([string]$endpoint.module -match 'presupuesto') { Join-Path $PerformanceRoot 'endpoints\presupuestos' } else { Join-Path $PerformanceRoot 'endpoints\solicitudes' }
$scriptPath = Join-Path $scriptDirectory "$EndpointId.js"
if (-not (Test-Path -LiteralPath $scriptPath)) { throw "Endpoint script not found: $scriptPath" }
$rawDirectory = Join-Path $CampaignDirectory 'raw'
$logDirectory = Join-Path $CampaignDirectory 'logs'
$ledgerDirectory = Join-Path $CampaignDirectory 'ledgers'
New-Item -ItemType Directory -Force -Path $rawDirectory,$logDirectory,$ledgerDirectory | Out-Null
$summaryPath = Join-Path $rawDirectory "$EndpointId-$Profile-k6.json"
$wrappedPath = Join-Path $rawDirectory "$EndpointId-$Profile.json"
$logPath = Join-Path $logDirectory "$EndpointId-$Profile.log"
$ledgerPath = Join-Path $ledgerDirectory "$EndpointId-$Profile.jsonl"
$k6 = (Get-Command k6 -ErrorAction Stop).Source

$env:PROFILE = $Profile
$env:RUN_ID = $RunId
& $k6 run --summary-export $summaryPath $scriptPath *> $logPath
$exitCode = $LASTEXITCODE
if (Test-Path -LiteralPath $summaryPath) {
    $k6Summary = Get-Content -Raw -LiteralPath $summaryPath | ConvertFrom-Json
    if ($null -ne $k6Summary.PSObject.Properties['setup_data']) { $k6Summary.PSObject.Properties.Remove('setup_data') }
    $k6Summary | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $summaryPath -Encoding utf8NoBom
    $wrapped = [ordered]@{ endpoint_id = $EndpointId; profile = $Profile; run_id = $RunId; result = if ($exitCode -eq 0) { 'EJECUTADA' } else { 'FALLIDA' }; exit_code = $exitCode; metrics = $k6Summary.metrics; k6 = [ordered]@{ metrics = $k6Summary.metrics; root_group = $k6Summary.root_group } }
    $wrapped | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $wrappedPath -Encoding utf8NoBOM
} else {
    [ordered]@{ endpoint_id = $EndpointId; profile = $Profile; run_id = $RunId; result = 'FALLIDA'; exit_code = $exitCode; reason = 'k6 did not produce a summary' } | ConvertTo-Json | Set-Content -LiteralPath $wrappedPath -Encoding utf8NoBOM
}
node (Join-Path $PerformanceRoot 'fixtures\resource-ledger.js') parse $logPath $ledgerPath
exit $exitCode

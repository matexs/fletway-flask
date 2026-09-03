$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$runner = Join-Path $repoRoot 'performance\runners\run-coverage80.ps1'
$allRunner = Join-Path $repoRoot 'performance\runners\run-all.ps1'
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('fletway-task7-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $testRoot | Out-Null

function Assert-True([bool]$condition, [string]$message) {
    if (-not $condition) { throw "ASSERTION FAILED: $message" }
}

function Write-Fixture([string]$name, [string]$content) {
    $path = Join-Path $testRoot $name
    Set-Content -LiteralPath $path -Value $content -Encoding utf8NoBOM
    return $path
}

try {
    $plan = Write-Fixture 'coverage-plan.json' @'
{
  "endpoints": [
    { "id": "z-endpoint", "order": 2, "script": "fixture-endpoint.ps1" },
    { "id": "a-endpoint", "order": 1, "script": "fixture-endpoint.ps1" }
  ]
}
'@
    $executor = Write-Fixture 'fixture-endpoint.ps1' @'
param([string]$EndpointId, [string]$Profile, [string]$RunDirectory)
$log = Join-Path $RunDirectory 'execution.log'
Add-Content -LiteralPath $log -Value "${Profile}:$EndpointId"
if ($EndpointId -eq 'a-endpoint' -and $Profile -eq 'smoke') { exit 7 }
exit 0
'@
    $preflight = Write-Fixture 'fixture-preflight.ps1' @'
param([string]$EndpointId, [string]$RunDirectory)
Add-Content -LiteralPath (Join-Path $RunDirectory 'execution.log') -Value "preflight:$EndpointId"
exit 0
'@

    $output = & pwsh -NoProfile -File $runner -PlanPath $plan -PerformanceRoot $testRoot -PreflightScript $preflight -EndpointRunnerScript $executor -WhatIf -WarmupSeconds 0 -CooldownSeconds 0 2>&1 | Out-String
    Assert-True ($LASTEXITCODE -eq 0) "WhatIf run should succeed. Output: $output"
    $runDirectory = Get-ChildItem -LiteralPath (Join-Path $testRoot 'results\runs') -Directory | Select-Object -First 1
    Assert-True ($null -ne $runDirectory) 'run directory should be created'
    $log = Get-Content -LiteralPath (Join-Path $runDirectory.FullName 'execution.log')
    Assert-True (($log -join '|') -eq 'preflight:a-endpoint|preflight:z-endpoint|smoke:a-endpoint|smoke:z-endpoint|load:z-endpoint|stress:z-endpoint|spike:z-endpoint') "queue order should be deterministic: $($log -join '|'); output=$output"

    $metadata = Get-Content -Raw -LiteralPath (Join-Path $runDirectory.FullName 'run.json') | ConvertFrom-Json
    Assert-True ([bool]$metadata.run_id) 'run metadata should contain run_id'
    Assert-True ([bool]$metadata.started_at -and [bool]$metadata.finished_at) 'run metadata should contain start and end'
    $records = Get-Content -Raw -LiteralPath (Join-Path $runDirectory.FullName 'results.json') | ConvertFrom-Json
    $failedSmoke = $records | Where-Object { $_.endpoint_id -eq 'a-endpoint' -and $_.profile -eq 'smoke' }
    Assert-True ($failedSmoke.exit_code -eq 7) 'failed profile exit code should be preserved'
    Assert-True ([bool]$failedSmoke.result_path) 'failed profile result metadata should be preserved'
    Assert-True (-not ($log | Where-Object { $_ -match '^(load|stress|spike):a-endpoint$' })) 'aggressive profiles should be gated after unavailable smoke'
    Assert-True (($records | Where-Object { $_.endpoint_id -eq 'a-endpoint' -and $_.profile -eq 'load' }).result -eq 'NO_EJECUTADA') 'gated profile should preserve a not-executed result'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $testRoot 'results\.run-lock'))) 'lock should be released after completion'

    $dryOutput = & pwsh -NoProfile -File $runner -PlanPath $plan -PerformanceRoot $testRoot -RunId 'dry-run' -PreflightScript $preflight -EndpointRunnerScript $executor -DryRun 2>&1 | Out-String
    Assert-True ($LASTEXITCODE -eq 0) 'DryRun should succeed without invoking fixtures'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $testRoot 'results\runs\dry-run\execution.log'))) 'DryRun should not invoke executors'

    $allOutput = & pwsh -NoProfile -File $allRunner -PlanPath $plan -PerformanceRoot $testRoot -RunId 'all-wrapper' -PreflightScript $preflight -EndpointRunnerScript $executor -WhatIf 2>&1 | Out-String
    Assert-True ($LASTEXITCODE -eq 0) "run-all wrapper should delegate successfully: $allOutput"

    $lockPath = Join-Path $testRoot 'held.lock'
    Set-Content -LiteralPath $lockPath -Value '{"run_id":"other-run"}' -Encoding utf8NoBOM
    $lockOutput = & pwsh -NoProfile -File $runner -PlanPath $plan -PerformanceRoot $testRoot -LockPath $lockPath -WhatIf 2>&1 | Out-String
    Assert-True ($LASTEXITCODE -ne 0) 'second runner should be rejected while lock exists'
    Assert-True ($lockOutput -match 'lock|bloque|concurrent') 'lock rejection should explain the conflict'

    Write-Output 'PASS run-queue.tests.ps1'
}
finally {
    if (Test-Path -LiteralPath $testRoot) { Remove-Item -LiteralPath $testRoot -Recurse -Force }
}

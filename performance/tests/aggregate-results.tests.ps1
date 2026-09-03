$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$aggregator = Join-Path $repoRoot 'performance\scripts\aggregate-results.ps1'
$thresholdConfig = Join-Path $repoRoot 'performance\config\thresholds.json'
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('fletway-task8-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $testRoot | Out-Null

function Assert-True([bool]$condition, [string]$message) {
    if (-not $condition) { throw "ASSERTION FAILED: $message" }
}

function Write-JsonFixture([string]$name, $value) {
    $path = Join-Path $testRoot $name
    $value | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $path -Encoding utf8NoBOM
    return $path
}

try {
    $thresholds = Get-Content -Raw -LiteralPath $thresholdConfig | ConvertFrom-Json
    Assert-True ($thresholds.profiles.smoke.p95_ms -eq 1000 -and $thresholds.profiles.load.error_pct -eq 5) 'tests must consume shared threshold config'
    $manifest = Write-JsonFixture 'manifest.json' @{ endpoints = @(
        @{ id = 'orders'; method = 'GET'; path = '/api/orders'; objective = 'Validate orders'; priority = 'P0'; enabled_profiles = @('smoke','load','stress','spike') },
        @{ id = 'secondary'; method = 'GET'; path = '/secondary'; objective = 'Secondary'; priority = 'P1'; enabled_profiles = @('smoke','load','stress','spike') }
    ) }

    $rawDir = Join-Path $testRoot 'raw'
    New-Item -ItemType Directory -Force -Path $rawDir | Out-Null
    $common = @{
        endpoint_id = 'orders'; profile = 'smoke'; vu_min = 1; vu_max = 3
        measured_duration_seconds = 20; metrics = @{
            http_reqs = @{ type = 'counter'; values = @{ count = 200 } }
            http_req_duration = @{ type = 'trend'; contains = 'time'; values = @{ 'p(95)' = 900 } }
            http_req_failed = @{ type = 'rate'; values = @{ rate = 0.005 } }
        }
    }
    foreach ($profile in @('smoke','load','stress','spike')) {
        $fixture = $common | ConvertTo-Json -Depth 20 | ConvertFrom-Json
        $fixture.profile = $profile
        if ($profile -eq 'load') { $fixture.vu_min = 0; $fixture.vu_max = 10; $fixture.measured_duration_seconds = 100; $fixture.metrics.http_req_duration.values.'p(95)' = 2500; $fixture.metrics.http_req_failed.values.rate = 0.06 }
        if ($profile -eq 'stress') { $fixture.vu_min = 10; $fixture.vu_max = 30; $fixture.metrics.http_req_duration.values.'p(95)' = 3200; $fixture.metrics.http_req_failed.values.rate = 0.11 }
        if ($profile -eq 'spike') { $fixture.vu_min = 3; $fixture.vu_max = 30; $fixture.metrics.http_req_duration.values.'p(95)' = 5100; $fixture.metrics.http_req_failed.values.rate = 0.21 }
        Write-JsonFixture "orders-$profile.json" $fixture | Move-Item -Destination (Join-Path $rawDir "orders-$profile.json") -Force
    }

    $output = Join-Path $testRoot 'matrix.csv'
    $stdout = & pwsh -NoProfile -File $aggregator -RawPath $rawDir -ManifestPath $manifest -OutputPath $output 2>&1 | Out-String
    Assert-True ($LASTEXITCODE -eq 0) "aggregation should succeed: $stdout"
    $rows = @(Import-Csv -LiteralPath $output)
    Assert-True ($rows.Count -eq 4) 'a P0 endpoint with data should produce exactly four rows'
    $expectedColumns = @('endpoint','test','objetivo','carga_vu_min','carga_vu_max','p95_ms','error_pct','capacidad_rps','resultado','usuarios')
    Assert-True ((@($rows[0].PSObject.Properties.Name) -join ',') -eq ($expectedColumns -join ',')) 'CSV columns must be exact and ordered'
    Assert-True ($rows[0].endpoint -eq 'GET /api/orders') 'endpoint must be normalized as METHOD /path'
    Assert-True ($rows[0].objetivo -eq 'Validate orders') 'manifest objective must be used'
    Assert-True ([double]$rows[0].p95_ms -eq 900) 'p95 must be numeric milliseconds'
    Assert-True ([double]$rows[0].error_pct -eq 0.5) "error rate must become a percentage (actual=$($rows[0].error_pct))"
    Assert-True ([double]$rows[0].capacidad_rps -eq 10) 'RPS must use count / measured seconds'
    Assert-True (($rows | Where-Object test -eq 'smoke').resultado -eq 'APROBADA') 'smoke should pass soft thresholds'
    Assert-True (($rows | Where-Object test -eq 'load').resultado -eq 'ADVERTENCIA') 'load soft threshold breach should warn'
    Assert-True (($rows | Where-Object test -eq 'stress').resultado -eq 'ADVERTENCIA') 'stress soft threshold breach should warn'
    Assert-True (($rows | Where-Object test -eq 'spike').resultado -eq 'FALLIDA') 'spike hard threshold breach should fail'

    $notExecuted = @{ endpoint_id='orders'; profile='load'; result='NOT_EXECUTED'; reason='preflight unavailable'; vu_min=0; vu_max=10 }
    $notExecutedPath = Join-Path $testRoot 'not-executed.json'
    Write-JsonFixture 'not-executed.json' $notExecuted | Out-Null
    $notOutput = Join-Path $testRoot 'not-executed.csv'
    $notStdout = & pwsh -NoProfile -File $aggregator -RawPath $notExecutedPath -ManifestPath $manifest -OutputPath $notOutput 2>&1 | Out-String
    Assert-True ($LASTEXITCODE -eq 0) "NOT_EXECUTED should be preserved: $notStdout"
    $notRows = @(Import-Csv $notOutput)
    Assert-True ($notRows.Count -eq 4 -and @($notRows | Where-Object { $_.resultado -eq 'NO_EJECUTADA' }).Count -eq 4) 'NOT_EXECUTED must normalize to four canonical NO_EJECUTADA rows'

    $missingDir = Join-Path $testRoot 'missing-profile-raw'
    New-Item -ItemType Directory -Force -Path $missingDir | Out-Null
    Copy-Item -LiteralPath (Join-Path $rawDir 'orders-smoke.json') -Destination (Join-Path $missingDir 'orders-smoke.json')
    $missingOutput = Join-Path $testRoot 'missing-profile.csv'
    $missingStdout = & pwsh -NoProfile -File $aggregator -RawPath $missingDir -ManifestPath $manifest -OutputPath $missingOutput 2>&1 | Out-String
    Assert-True ($LASTEXITCODE -eq 0) "missing profiles should synthesize rows: $missingStdout"
    $missingRows = @(Import-Csv $missingOutput)
    Assert-True ($missingRows.Count -eq 4) 'any raw input for a P0 endpoint must produce exactly four rows'
    Assert-True (@($missingRows | Where-Object { $_.resultado -eq 'NO_EJECUTADA' }).Count -eq 3) 'three absent profiles must be NO_EJECUTADA'
    Assert-True (($missingRows | Where-Object test -eq 'load').usuarios -match 'missing|not enabled|no raw') 'synthesized row must carry an explicit reason'

    $bad = @{ endpoint_id='orders'; profile='smoke'; metrics=@{ http_reqs=@{ values=@{ count=1 } } } }
    $badPath = Write-JsonFixture 'bad.json' $bad
    $badOutput = Join-Path $testRoot 'bad.csv'
    $badStdout = & pwsh -NoProfile -File $aggregator -RawPath $badPath -ManifestPath $manifest -OutputPath $badOutput 2>&1 | Out-String
    Assert-True ($LASTEXITCODE -ne 0) 'malformed summaries must be rejected'
    Assert-True ($badStdout -match 'duration|p95|schema|Malformed') 'malformed error should identify the missing schema'

    function Assert-Rejected($fixture, [string]$name) {
        $path = Write-JsonFixture "$name.json" $fixture
        $out = Join-Path $testRoot "$name.csv"
        $message = & pwsh -NoProfile -File $aggregator -RawPath $path -ManifestPath $manifest -OutputPath $out 2>&1 | Out-String
        Assert-True ($LASTEXITCODE -ne 0) "$name should be rejected: $message"
    }
    function Assert-RejectedWithManifest($fixture, $manifestPath, [string]$name) {
        $path = Write-JsonFixture "$name.json" $fixture
        $out = Join-Path $testRoot "$name.csv"
        $message = & pwsh -NoProfile -File $aggregator -RawPath $path -ManifestPath $manifestPath -OutputPath $out 2>&1 | Out-String
        Assert-True ($LASTEXITCODE -ne 0) "$name should be rejected: $message"
    }
    Assert-Rejected (@{ endpoint_id='orders'; profile='smoke'; unexpected='x' }) 'unknown-top-level'
    Assert-Rejected (@{ endpoint_id='orders'; profile='smoke'; measured_duration_seconds=20; duration_ms=20000; metrics=$common.metrics }) 'ambiguous-duration'
    Assert-Rejected (@{ endpoint_id='orders'; profile='smoke'; measured_duration_seconds=20; metrics=$common.metrics; k6=@{ metrics=$common.metrics } }) 'ambiguous-metrics'
    $invalidRatio = $common | ConvertTo-Json -Depth 20 | ConvertFrom-Json; $invalidRatio.profile='smoke'; $invalidRatio.metrics.http_req_failed.values.rate=1.1
    Assert-Rejected $invalidRatio 'invalid-ratio'
    $invalidUnit = $common | ConvertTo-Json -Depth 20 | ConvertFrom-Json; $invalidUnit.profile='smoke'; [void]$invalidUnit.PSObject.Properties.Add([PSNoteProperty]::new('duration_ms', -1))
    Assert-Rejected $invalidUnit 'invalid-unit'
    Assert-Rejected (@{ endpoint_id='orders'; profile='wat'; result='NOT_EXECUTED' }) 'invalid-profile'
    Assert-Rejected (@{ endpoint_id='orders'; profile='smoke'; result='NOT_EXECUTED'; extra='x' }) 'not-executed-extra'
    $invalidMetric = @{ endpoint_id='orders'; profile='smoke'; measured_duration_seconds=20; metrics=@{ http_reqs=@{ type='counter'; values=@{ count=1 } }; http_req_duration=@{ type='trend'; values=@{ 'p(95)'=900; bogus=1 } }; http_req_failed=@{ type='rate'; values=@{ rate=0 } } } }
    Assert-Rejected $invalidMetric 'invalid-metric-values'
    $badManifest = Write-JsonFixture 'bad-manifest.json' @{ endpoints = @(@{ id='orders'; method='GET'; path='/api/orders'; objective='x'; priority='P0' }); unexpected='x' }
    Assert-RejectedWithManifest $common $badManifest 'unknown-manifest-field'

    $timeout = $common | ConvertTo-Json -Depth 20 | ConvertFrom-Json; $timeout.profile='smoke'; [void]$timeout.PSObject.Properties.Add([PSNoteProperty]::new('timeout_pct', 11))
    $timeoutPath = Write-JsonFixture 'timeout.json' $timeout
    $timeoutOutput = Join-Path $testRoot 'timeout.csv'
    $timeoutMessage = & pwsh -NoProfile -File $aggregator -RawPath $timeoutPath -ManifestPath $manifest -OutputPath $timeoutOutput 2>&1 | Out-String
    Assert-True ($LASTEXITCODE -eq 0) "timeout summary should aggregate: $timeoutMessage"
    Assert-True ((@(Import-Csv $timeoutOutput) | Where-Object test -eq 'smoke').resultado -eq 'FALLIDA') 'hard timeout must fail the profile'

    $failed = @{ endpoint_id='orders'; profile='smoke'; result='FAILED'; reason='runner exit code 7'; vu_min=1; vu_max=3 }
    $failedPath = Write-JsonFixture 'failed.json' $failed
    $failedOutput = Join-Path $testRoot 'failed.csv'
    $failedMessage = & pwsh -NoProfile -File $aggregator -RawPath $failedPath -ManifestPath $manifest -OutputPath $failedOutput 2>&1 | Out-String
    Assert-True ($LASTEXITCODE -eq 0) "failed summary should be preserved: $failedMessage"
    Assert-True ((@(Import-Csv $failedOutput) | Where-Object test -eq 'smoke').resultado -eq 'FALLIDA') 'explicit failed state must remain FALLIDA'

    $wrapper = @{ endpoint_id='orders'; profile='smoke'; vu_min=1; vu_max=3; k6=@{ state=@{ testRunDurationMs=20000 }; metrics=$common.metrics } }
    $wrapperPath = Write-JsonFixture 'k6-wrapper.json' $wrapper
    $wrapperOutput = Join-Path $testRoot 'k6-wrapper.csv'
    $wrapperMessage = & pwsh -NoProfile -File $aggregator -RawPath $wrapperPath -ManifestPath $manifest -OutputPath $wrapperOutput 2>&1 | Out-String
    Assert-True ($LASTEXITCODE -eq 0) "k6 wrapper should aggregate: $wrapperMessage"
    $wrapperRows = @(Import-Csv $wrapperOutput)
    Assert-True ([double]$wrapperRows[0].capacidad_rps -eq 10) 'k6 wrapper must use explicit testRunDurationMs'

    $duplicateDir = Join-Path $testRoot 'duplicate-raw'
    New-Item -ItemType Directory -Force -Path $duplicateDir | Out-Null
    Copy-Item -LiteralPath (Join-Path $rawDir 'orders-smoke.json') -Destination (Join-Path $duplicateDir 'a.json')
    Copy-Item -LiteralPath (Join-Path $rawDir 'orders-smoke.json') -Destination (Join-Path $duplicateDir 'b.json')
    $duplicateOut = Join-Path $testRoot 'duplicate.csv'
    $duplicateMessage = & pwsh -NoProfile -File $aggregator -RawPath $duplicateDir -ManifestPath $manifest -OutputPath $duplicateOut 2>&1 | Out-String
    Assert-True ($LASTEXITCODE -ne 0 -and $duplicateMessage -match 'duplicate') 'duplicate endpoint/profile files must be rejected'

    Write-Output 'PASS aggregate-results.tests.ps1'
}
finally {
    if (Test-Path -LiteralPath $testRoot) { Remove-Item -LiteralPath $testRoot -Recurse -Force }
}

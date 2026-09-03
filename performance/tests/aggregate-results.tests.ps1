$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$aggregator = Join-Path $repoRoot 'performance\scripts\aggregate-results.ps1'
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
    $manifest = Write-JsonFixture 'manifest.json' @{ endpoints = @(
        @{ id = 'orders'; method = 'GET'; path = '/api/orders'; objective = 'Validate orders'; priority = 'P0'; enabled_profiles = @('smoke','load','stress','spike') },
        @{ id = 'secondary'; method = 'GET'; path = '/secondary'; objective = 'Secondary'; priority = 'P1'; enabled_profiles = @('smoke','load','stress','spike') }
    ) }

    $rawDir = Join-Path $testRoot 'raw'
    New-Item -ItemType Directory -Force -Path $rawDir | Out-Null
    $common = @{
        endpoint_id = 'orders'; profile = 'smoke'; objective = 'Raw objective must not override manifest'; vu_min = 1; vu_max = 3
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
    Assert-True ((Import-Csv $notOutput).resultado -eq 'NO_EJECUTADA') 'NOT_EXECUTED must normalize to canonical NO_EJECUTADA'

    $bad = @{ endpoint_id='orders'; profile='smoke'; metrics=@{ http_reqs=@{ values=@{ count=1 } } } }
    $badPath = Write-JsonFixture 'bad.json' $bad
    $badOutput = Join-Path $testRoot 'bad.csv'
    $badStdout = & pwsh -NoProfile -File $aggregator -RawPath $badPath -ManifestPath $manifest -OutputPath $badOutput 2>&1 | Out-String
    Assert-True ($LASTEXITCODE -ne 0) 'malformed summaries must be rejected'
    Assert-True ($badStdout -match 'duration|p95|schema|Malformed') 'malformed error should identify the missing schema'

    Write-Output 'PASS aggregate-results.tests.ps1'
}
finally {
    if (Test-Path -LiteralPath $testRoot) { Remove-Item -LiteralPath $testRoot -Recurse -Force }
}

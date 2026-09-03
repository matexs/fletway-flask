$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$generator = Join-Path $repoRoot 'performance\scripts\generate-endpoint-report.ps1'
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('fletway-task9-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $testRoot | Out-Null

function Assert-True([bool]$condition, [string]$message) {
    if (-not $condition) { throw "ASSERTION FAILED: $message" }
}

function Write-JsonFixture([string]$relativePath, $value) {
    $path = Join-Path $testRoot $relativePath
    $parent = Split-Path -Parent $path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $value | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $path -Encoding utf8NoBOM
    return $path
}

function Write-TextFixture([string]$relativePath, [string]$value) {
    $path = Join-Path $testRoot $relativePath
    $parent = Split-Path -Parent $path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $value | Set-Content -LiteralPath $path -Encoding utf8NoBOM
    return $path
}

function Invoke-Report($matrix, $raw, $manifest, [string]$name = 'report') {
    $matrixPath = Write-TextFixture "$name-matrix.csv" $matrix
    $manifestPath = Write-JsonFixture "$name-manifest.json" $manifest
    $rawPath = Join-Path $testRoot "$name-raw"
    New-Item -ItemType Directory -Force -Path $rawPath | Out-Null
    foreach ($item in $raw.GetEnumerator()) { Write-JsonFixture "$name-raw\$($item.Key).json" $item.Value | Out-Null }
    $output = Join-Path $testRoot "$name-output"
    $stdout = & pwsh -NoProfile -File $generator -MatrixPath $matrixPath -RawPath $rawPath -ManifestPath $manifestPath -EndpointId 'orders' -OutputDirectory $output 2>&1 | Out-String
    return [pscustomobject]@{ ExitCode=$LASTEXITCODE; Stdout=$stdout; Output=$output }
}

$header = 'endpoint,test,objetivo,carga_vu_min,carga_vu_max,p95_ms,error_pct,capacidad_rps,resultado,usuarios'
$manifest = @{ endpoints = @(@{ id='orders'; method='GET'; path='/api/orders'; objective='Validate orders under representative traffic'; priority='P0'; enabled_profiles=@('smoke','load','stress','spike') }) }
$matrix = @"
$header
GET /api/orders,smoke,Validate orders under representative traffic,1,3,900,0.5,10,APROBADA,1→3 VUs
GET /api/orders,load,Validate orders under representative traffic,0,10,1800,2,12,APROBADA,0→10 VUs
GET /api/orders,stress,Validate orders under representative traffic,10,30,3200,11,14,ADVERTENCIA,10→30 VUs
GET /api/orders,spike,Validate orders under representative traffic,3,30,4100,8,15,ADVERTENCIA,3→30 VUs
"@

function Metric([double]$p50, [double]$p90, [double]$p95, [double]$max, [double]$count, [double]$errorRate) {
    return @{ http_reqs=@{ type='counter'; values=@{ count=$count } }; http_req_duration=@{ type='trend'; values=@{ 'p(50)'=$p50; 'p(90)'=$p90; 'p(95)'=$p95; max=$max } }; http_req_failed=@{ type='rate'; values=@{ rate=$errorRate } } }
}

try {
    $raw = @{
        'smoke' = @{ endpoint_id='orders'; profile='smoke'; vu_min=1; vu_max=3; measured_duration_seconds=20; metrics=(Metric 300 700 900 1400 200 0.005) }
        'load' = @{ endpoint_id='orders'; profile='load'; vu_min=0; vu_max=10; measured_duration_seconds=30; metrics=(Metric 350 900 1800 2600 360 0.02) }
        'stress-10' = @{ endpoint_id='orders'; profile='stress_10'; vu_min=10; vu_max=10; measured_duration_seconds=20; metrics=(Metric 400 1000 1900 2800 220 0.01) }
        'stress-20' = @{ endpoint_id='orders'; profile='stress_20'; vu_min=20; vu_max=20; measured_duration_seconds=20; metrics=(Metric 600 1800 3100 4700 300 0.07) }
        'stress-30' = @{ endpoint_id='orders'; profile='stress_30'; vu_min=30; vu_max=30; measured_duration_seconds=20; metrics=(Metric 900 2500 3800 6200 280 0.12) }
        'spike' = @{ endpoint_id='orders'; profile='spike'; vu_min=3; vu_max=30; measured_duration_seconds=20; recovery_seconds=18; baseline=@{ vus=3; p95_ms=1200; error_pct=1; rps=10 }; peak=@{ vus=30; p95_ms=4100; error_pct=8; rps=15 }; recovery=@{ p95_ms=1300; error_pct=1; seconds=18 }; metrics=(Metric 800 2500 4100 6000 300 0.08) }
    }

    $first = Invoke-Report $matrix $raw $manifest
    Assert-True ($first.ExitCode -eq 0) "complete fixture should generate reports: $($first.Stdout)"
    $mdPath = Join-Path $first.Output 'endpoint-report.md'
    $htmlPath = Join-Path $first.Output 'endpoint-report.html'
    Assert-True ((Test-Path $mdPath -PathType Leaf) -and (Test-Path $htmlPath -PathType Leaf)) 'both report formats must be written'
    $md = Get-Content -Raw $mdPath
    $html = Get-Content -Raw $htmlPath
    foreach ($marker in @('GET /api/orders','Validate orders under representative traffic','APROBADA','3200','0.5')) {
        Assert-True ($md.Contains($marker) -and $html.Contains($marker)) "Markdown and HTML must include shared marker: $marker"
    }
    foreach ($section in @('Smoke','Load','Stress','Spike','Matriz')) {
        Assert-True ($md.Contains("## $section") -and $html.Contains("<h2>$section</h2>")) "both formats must include section: $section"
    }
    Assert-True ($md -match '\| 10 \|' -and $md -match '\| 20 \|' -and $md -match '\| 30 \|' -and $md -match '400.*1000.*1900.*2800.*1.*11' -and $md -match 'Primer punto de degradación.*20 VU') 'stress must include per-VU metrics and first degradation'
    Assert-True ($md -match '(?i)Baseline:' -and $md -match '3 VU' -and $md -match '(?i)Peak:' -and $md -match '30 VU' -and $md -match '18 s' -and $md -match '(?i)Recovery:') 'spike must include baseline, peak, recovery and result'
    Assert-True ($md -match '\| GET /api/orders \| smoke \|' -and $md -match '\| GET /api/orders \| load \|' -and $md -match '\| GET /api/orders \| stress \|' -and $md -match '\| GET /api/orders \| spike \|') 'matrix must include all four canonical rows'
    Assert-True ($md -match 'Hecho:' -and $md -match 'Hipótesis:' -and $md -match 'no hay telemetría') 'conclusion must distinguish evidence from hypothesis'
    Assert-True ($md -notmatch '(?i)(causad[oa]|debido|provocad[oa]).{0,30}(sql|memoria)|(sql|memoria).{0,30}(causad[oa]|debido|provocad[oa])|password|bearer|eyJ[A-Za-z0-9_-]+') 'report must not claim unsupported causes or leak secrets'

    $missingRaw = $raw.Clone(); $missingRaw.Remove('stress-30'); $missing = Invoke-Report $matrix $missingRaw $manifest 'missing'
    Assert-True ($missing.ExitCode -ne 0 -and $missing.Stdout -match 'stress|profile|missing') 'missing required stress detail must be rejected'

    $badOutput = Join-Path $testRoot 'unsafe-output\..\escape'
    $matrixPath = Write-TextFixture 'unsafe-matrix.csv' $matrix
    $manifestPath = Write-JsonFixture 'unsafe-manifest.json' $manifest
    $rawPath = Join-Path $testRoot 'unsafe-raw'; New-Item -ItemType Directory -Force -Path $rawPath | Out-Null
    foreach ($item in $raw.GetEnumerator()) { Write-JsonFixture "unsafe-raw\$($item.Key).json" $item.Value | Out-Null }
    $unsafe = & pwsh -NoProfile -File $generator -MatrixPath $matrixPath -RawPath $rawPath -ManifestPath $manifestPath -EndpointId 'orders' -OutputDirectory $badOutput 2>&1 | Out-String
    Assert-True ($LASTEXITCODE -ne 0 -and $unsafe -match 'path|output|safe') 'unsafe output path must be rejected'

    Write-Output 'PASS generate-endpoint-report.tests.ps1'
}
finally {
    if (Test-Path $testRoot) { Remove-Item -LiteralPath $testRoot -Recurse -Force }
}

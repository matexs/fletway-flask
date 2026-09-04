$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$builder = Join-Path $repoRoot 'performance\scripts\build-general-matrix.ps1'
$schema = 'endpoint,test,objetivo,carga_vu_min,carga_vu_max,p95_ms,error_pct,capacidad_rps,resultado,usuarios'
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('fletway-task11-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $testRoot | Out-Null

function Assert-True([bool]$condition, [string]$message) {
    if (-not $condition) { throw "ASSERTION FAILED: $message" }
}

function Write-Matrix([string]$path, [string]$content) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $path) | Out-Null
    [IO.File]::WriteAllText($path, $content, [Text.UTF8Encoding]::new($false))
}

function Invoke-Builder([string]$root, [string]$output, [string]$manifest = '') {
    $args = @('-NoProfile', '-File', $builder, '-ResultsRoot', $root, '-OutputPath', $output)
    if ($manifest) { $args += @('-ManifestPath', $manifest) }
    & pwsh @args *> $null
    return $LASTEXITCODE
}

try {
    # Empty input still creates the stable canonical header, and output is not an input.
    $emptyRoot = Join-Path $testRoot 'empty'
    $emptyOutput = Join-Path $emptyRoot 'matrix_general.csv'
    New-Item -ItemType Directory -Force -Path $emptyRoot | Out-Null
    $emptyExit = Invoke-Builder $emptyRoot $emptyOutput
    Assert-True ($emptyExit -eq 0) 'empty input should succeed'
    Assert-True ((Get-Content -Raw -LiteralPath $emptyOutput) -eq ($schema + "`n")) 'empty output should contain only canonical header'

    # Two endpoint matrices preserve rows, sort by status then P0, and retain distinct run IDs.
    $results = Join-Path $testRoot 'results'
    $csvA = @(
        $schema,
        'GET /slow,load,Slow objective,1,10,2500,1,4,ADVERTENCIA,1→10 VUs',
        'GET /slow,smoke,Slow objective,1,3,6000,0,2,FALLIDA,1→3 VUs'
    ) -join "`n"
    $csvB = @(
        $schema,
        'GET /fast,load,Fast objective,1,10,500,0,8,APROBADA,1→10 VUs',
        'GET /fast,smoke,Fast objective,,,,,,NO_EJECUTADA,not run'
    ) -join "`n"
    Write-Matrix (Join-Path $results 'runs\run-1\endpoints\slow\matrix.csv') $csvA
    Write-Matrix (Join-Path $results 'runs\run-2\endpoints\fast\matrix.csv') $csvB
    $manifest = Join-Path $testRoot 'manifest.json'
    [IO.File]::WriteAllText($manifest, (@{ endpoints = @(
        @{ id = 'slow'; method = 'GET'; path = '/slow'; objective = 'Slow objective'; priority = 'P1' },
        @{ id = 'fast'; method = 'GET'; path = '/fast'; objective = 'Fast objective'; priority = 'P0' }
    ) } | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
    $output = Join-Path $results 'matrix\matrix_general.csv'
    Assert-True ((Invoke-Builder $results $output $manifest) -eq 0) 'valid matrices should merge'
    $lines = Get-Content -LiteralPath $output
    Assert-True ($lines.Count -eq 5) 'all four valid rows should be preserved'
    Assert-True ($lines[1] -like 'GET /slow,smoke,*FALLIDA*') 'FALLIDA should sort first by severity'
    Assert-True ($lines[2] -like 'GET /slow,load,*ADVERTENCIA*') 'ADVERTENCIA should sort before APROBADA'
    Assert-True ($lines[3] -like 'GET /fast,load,*APROBADA*') 'P0 should sort before NO_EJECUTADA within stable severity ordering'
    Assert-True ($lines[4] -like 'GET /fast,smoke,*NO_EJECUTADA*') 'NO_EJECUTADA should sort last'

    # Same test in distinct enclosing runs is valid and must not be deduplicated.
    $duplicateRoot = Join-Path $testRoot 'duplicate-runs'
    $row = 'GET /same,load,Objective,1,10,500,0,8,APROBADA,1→10 VUs'
    Write-Matrix (Join-Path $duplicateRoot 'runs\run-a\endpoints\same\matrix.csv') ($schema + "`n" + $row)
    Write-Matrix (Join-Path $duplicateRoot 'runs\run-b\endpoints\same\matrix.csv') ($schema + "`n" + $row)
    $duplicateOutput = Join-Path $duplicateRoot 'matrix_general.csv'
    Assert-True ((Invoke-Builder $duplicateRoot $duplicateOutput) -eq 0) 'distinct runs should be retained'
    Assert-True ((Get-Content $duplicateOutput).Count -eq 3) 'duplicate valid runs must not be deduplicated'

    # Malformed headers and rows fail clearly.
    $badHeaderRoot = Join-Path $testRoot 'bad-header'
    Write-Matrix (Join-Path $badHeaderRoot 'runs\run\endpoints\x\matrix.csv') "endpoint,test`nGET /x,load"
    Assert-True ((Invoke-Builder $badHeaderRoot (Join-Path $badHeaderRoot 'out.csv')) -ne 0) 'invalid header should fail'
    $badRowRoot = Join-Path $testRoot 'bad-row'
    Write-Matrix (Join-Path $badRowRoot 'runs\run\endpoints\x\matrix.csv') ($schema + "`nGET /x,load,Objective,1,10,not-a-number,0,8,APROBADA,users")
    Assert-True ((Invoke-Builder $badRowRoot (Join-Path $badRowRoot 'out.csv')) -ne 0) 'invalid row should fail'

    # Unsafe endpoint identifiers and path traversal are rejected.
    $unsafeRoot = Join-Path $testRoot 'unsafe'
    Write-Matrix (Join-Path $unsafeRoot 'runs\run\endpoints\x\matrix.csv') ($schema + "`nGET /../secret,load,Objective,1,10,500,0,8,APROBADA,users")
    Assert-True ((Invoke-Builder $unsafeRoot (Join-Path $unsafeRoot 'out.csv')) -ne 0) 'unsafe endpoint should fail'

    # Canonical manifest matching must drive P0 ordering and reject semantic mismatches.
    $priorityRoot = Join-Path $testRoot 'priority'
    $priorityCsv = @(
        $schema,
        'GET /p1,load,P1 objective,1,10,500,0,8,APROBADA,users',
        'GET /p0,load,P0 objective,1,10,500,0,8,APROBADA,users',
        'GET /p0,smoke,P0 objective,,,,,,NO_EJECUTADA,not run'
    ) -join "`n"
    Write-Matrix (Join-Path $priorityRoot 'runs\2026-09-04T120000\endpoints\p1\matrix.csv') ($schema + "`nGET /p1,load,P1 objective,1,10,500,0,8,APROBADA,users")
    Write-Matrix (Join-Path $priorityRoot 'runs\2026-09-04T120000\endpoints\p0\matrix.csv') ($schema + "`nGET /p0,load,P0 objective,1,10,500,0,8,APROBADA,users")
    $priorityManifest = Join-Path $testRoot 'canonical-manifest.json'
    [IO.File]::WriteAllText($priorityManifest, (@{ schema_version = 1; endpoints = @(
        @{ id = 'p1'; method = 'GET'; path = '/p1'; objective = 'P1 objective'; priority = 'P1' },
        @{ id = 'p0'; method = 'GET'; path = '/p0'; objective = 'P0 objective'; priority = 'P0' }
    ) } | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
    $priorityOutput = Join-Path $priorityRoot 'matrix_general.csv'
    Assert-True ((Invoke-Builder $priorityRoot $priorityOutput $priorityManifest) -eq 0) 'canonical manifest should merge'
    $priorityLines = Get-Content $priorityOutput
    Assert-True ($priorityLines[1] -like 'GET /p0,*') 'equal-severity P0 row should sort before P1 row'

    $semanticRoot = Join-Path $testRoot 'semantic-invalid'
    $semanticManifest = Join-Path $testRoot 'semantic-manifest.json'
    [IO.File]::WriteAllText($semanticManifest, (@{ endpoints = @(
        @{ id = 'semantic'; method = 'GET'; path = '/semantic'; objective = 'Semantic objective'; priority = 'P0' }
    ) } | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
    foreach ($invalidRow in @(
        'GET /semantic,load,Wrong objective,1,10,500,0,8,APROBADA,users',
        'GET /semantic,load,Semantic objective,-1,10,500,0,8,APROBADA,users',
        'GET /semantic,load,Semantic objective,10,1,500,0,8,APROBADA,users',
        'GET /semantic,load,Semantic objective,1,10,500,101,8,APROBADA,users',
        'GET /semantic,load,Semantic objective,1,10,NaN,0,8,APROBADA,users',
        'GET /semantic,load,Semantic objective,1,10,,0,8,APROBADA,users',
        'GET /semantic,load,Semantic objective,1,10,500,,8,APROBADA,users',
        'GET /semantic,load,Semantic objective,1,10,500,0,,APROBADA,users'
    )) {
        $invalidPath = Join-Path $semanticRoot ([guid]::NewGuid().ToString('N'))
        Write-Matrix (Join-Path $invalidPath 'runs\run\endpoints\semantic\matrix.csv') ($schema + "`n" + $invalidRow)
        Assert-True ((Invoke-Builder $invalidPath (Join-Path $invalidPath 'out.csv') $semanticManifest) -ne 0) "semantic invalid row should fail: $invalidRow"
    }

    $ambiguousRoot = Join-Path $testRoot 'ambiguous-run'
    Write-Matrix (Join-Path $ambiguousRoot 'runs\run-a\endpoints\same\one\matrix.csv') ($schema + "`n" + $row)
    Write-Matrix (Join-Path $ambiguousRoot 'runs\run-a\endpoints\same\two\matrix.csv') ($schema + "`n" + $row)
    Assert-True ((Invoke-Builder $ambiguousRoot (Join-Path $ambiguousRoot 'out.csv')) -ne 0) 'ambiguous run identity should fail'

    $nestedRunsRoot = Join-Path $testRoot 'nested-runs'
    Write-Matrix (Join-Path $nestedRunsRoot 'nested\runs\run\endpoints\x\matrix.csv') ($schema + "`n" + $row)
    Assert-True ((Invoke-Builder $nestedRunsRoot (Join-Path $nestedRunsRoot 'out.csv')) -ne 0) 'nested runs path should fail'

    # The real manifest contains two declarations for this method/path. Exact objective selects one deterministically.
    $duplicateManifestRoot = Join-Path $testRoot 'duplicate-canonical-manifest'
    $duplicateManifestPath = Join-Path $testRoot 'duplicate-canonical-manifest.json'
    $duplicateManifestRow = 'GET /api/calificaciones/puede-calificar/<solicitud_id>,load,Check rating eligibility duplicate declaration,1,10,500,0,8,APROBADA,users'
    Write-Matrix (Join-Path $duplicateManifestRoot 'runs\run-1\endpoints\puede-calificar\matrix.csv') ($schema + "`n" + $duplicateManifestRow)
    [IO.File]::WriteAllText($duplicateManifestPath, (@{ schema_version = 1; endpoints = @(
        @{ id = 'puede-calificar-solicitud'; method = 'GET'; path = '/api/calificaciones/puede-calificar/<solicitud_id>'; objective = 'Check rating eligibility'; priority = 'P2' },
        @{ id = 'puede-calificar-solicitud-duplicado'; method = 'GET'; path = '/api/calificaciones/puede-calificar/<solicitud_id>'; objective = 'Check rating eligibility duplicate declaration'; priority = 'P2' }
    ) } | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
    $duplicateManifestOutput = Join-Path $duplicateManifestRoot 'matrix_general.csv'
    Assert-True ((Invoke-Builder $duplicateManifestRoot $duplicateManifestOutput $duplicateManifestPath) -eq 0) 'duplicate canonical manifest declaration should be accepted'
    Assert-True ((Get-Content $duplicateManifestOutput).Count -eq 2) 'duplicate canonical manifest should not invent rows'

    # Repeated builds are byte-for-byte deterministic.
    $first = [IO.File]::ReadAllBytes($output)
    Assert-True ((Invoke-Builder $results $output $manifest) -eq 0) 'repeat build should succeed'
    $second = [IO.File]::ReadAllBytes($output)
    Assert-True ([Convert]::ToBase64String($first) -eq [Convert]::ToBase64String($second)) 'repeated output should be identical'

    'PASS build-general-matrix.tests.ps1'
}
finally {
    if (Test-Path -LiteralPath $testRoot) { Remove-Item -LiteralPath $testRoot -Recurse -Force }
}

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$generator = Join-Path $repoRoot 'performance\scripts\generate-endpoint-report.ps1'
$PowerShellExecutable = if ($PSVersionTable.PSEdition -eq 'Desktop') { 'powershell.exe' } else { 'pwsh' }
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('fletway-task9-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $testRoot | Out-Null

function Assert-True([bool]$condition, [string]$message) {
    if (-not $condition) { throw "ASSERTION FAILED: $message" }
}

function Write-JsonFixture([string]$relativePath, $value) {
    $path = Join-Path $testRoot $relativePath
    $parent = Split-Path -Parent $path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    Write-Utf8NoBom $path ($value | ConvertTo-Json -Depth 30)
    return $path
}

function Write-Utf8NoBom([string]$path, [string]$content) {
    $encoding = New-Object System.Text.UTF8Encoding -ArgumentList $false
    [IO.File]::WriteAllText($path, $content, $encoding)
}

function Read-Utf8NoBom([string]$path) {
    $encoding = New-Object System.Text.UTF8Encoding -ArgumentList $false
    return [IO.File]::ReadAllText($path, $encoding)
}

function Write-TextFixture([string]$relativePath, [string]$value) {
    $path = Join-Path $testRoot $relativePath
    $parent = Split-Path -Parent $path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    Write-Utf8NoBom $path $value
    return $path
}

function Invoke-Report($matrix, $raw, $manifest, [string]$name = 'report') {
    $matrixPath = Write-TextFixture "$name-matrix.csv" $matrix
    $manifestPath = Write-JsonFixture "$name-manifest.json" $manifest
    $rawPath = Join-Path $testRoot "$name-raw"
    New-Item -ItemType Directory -Force -Path $rawPath | Out-Null
    foreach ($item in $raw.GetEnumerator()) { Write-JsonFixture "$name-raw\$($item.Key).json" $item.Value | Out-Null }
    $output = Join-Path $testRoot "$name-output"
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        if ($PSVersionTable.PSEdition -eq 'Desktop') {
            $stdout = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $generator -MatrixPath $matrixPath -RawPath $rawPath -ManifestPath $manifestPath -EndpointId orders -OutputDirectory $output 2>&1 | Out-String
        } else {
            $stdout = & pwsh -NoProfile -File $generator -MatrixPath $matrixPath -RawPath $rawPath -ManifestPath $manifestPath -EndpointId orders -OutputDirectory $output 2>&1 | Out-String
        }
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    return [pscustomobject]@{ ExitCode=$exitCode; Stdout=$stdout; Output=$output }
}

function Assert-NoBom([string]$path) {
    $bytes = [IO.File]::ReadAllBytes($path)
    Assert-True ($bytes.Length -lt 3 -or $bytes[0] -ne 0xEF -or $bytes[1] -ne 0xBB -or $bytes[2] -ne 0xBF) "UTF-8 output must not contain a BOM: $path"
}

function Clone-Value($value) { return ($value | ConvertTo-Json -Depth 30 | ConvertFrom-Json) }

function Assert-ReportRejected($matrix, $raw, $manifest, [string]$name, [string]$pattern = 'stress|spike|duration|metric|profile') {
    $result = Invoke-Report $matrix $raw $manifest $name
    Assert-True ($result.ExitCode -ne 0 -and $result.Stdout -match $pattern) "$name must be rejected: $($result.Stdout)"
}

$header = 'endpoint,test,objetivo,carga_vu_min,carga_vu_max,p95_ms,error_pct,capacidad_rps,resultado,usuarios'
$manifest = @{ endpoints = @(@{ id='orders'; method='GET'; path='/api/orders'; objective='Validate orders under representative traffic'; priority='P0'; enabled_profiles=@('smoke','load','stress','spike') }) }
$matrix = @"
$header
GET /api/orders,smoke,Validate orders under representative traffic,1,3,900,0.5,10,APROBADA,1→3 VUs
GET /api/orders,load,Validate orders under representative traffic,0,10,1800,2,12,APROBADA,0→10 VUs
GET /api/orders,stress,Validate orders under representative traffic,10,30,3200,11,14,ADVERTENCIA,10→30 VUs
GET /api/orders,spike,Validate orders under representative traffic,3,30,4100,8,15,APROBADA,3→30 VUs
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
        'spike' = @{ endpoint_id='orders'; profile='spike'; vu_min=3; vu_max=30; measured_duration_seconds=20; recovery_seconds=18; baseline=@{ vus=3; p95_ms=1200; error_pct=1; rps=10 }; peak=@{ vus=30; p95_ms=4100; error_pct=8; rps=15 }; recovery=@{ vus=3; p95_ms=1300; error_pct=1; rps=10; seconds=18 }; metrics=(Metric 800 2500 4100 6000 300 0.08) }
    }

    $first = Invoke-Report $matrix $raw $manifest
    Assert-True ($first.ExitCode -eq 0) "complete fixture should generate reports: $($first.Stdout)"
    $mdPath = Join-Path $first.Output 'endpoint-report.md'
    $htmlPath = Join-Path $first.Output 'endpoint-report.html'
    Assert-True ((Test-Path $mdPath -PathType Leaf) -and (Test-Path $htmlPath -PathType Leaf)) 'both report formats must be written'
    Assert-NoBom $mdPath; Assert-NoBom $htmlPath
    $md = Read-Utf8NoBom $mdPath
    $html = Read-Utf8NoBom $htmlPath
    Write-Output $md
    foreach ($marker in @('GET /api/orders','Validate orders under representative traffic','APROBADA','3200','0.5')) {
        Assert-True ($md.Contains($marker) -and $html.Contains($marker)) "Markdown and HTML must include shared marker: $marker"
    }
    foreach ($section in @('Smoke','Load','Stress','Spike','Matriz')) {
        Assert-True ($md.Contains("## $section") -and $html.Contains("<h2>$section</h2>")) "both formats must include section: $section"
    }
    Assert-True ($md -match 'Score endpoint:\*\*\s*N/D.*Task 10' -and $html -match 'N/D.*Task 10') 'score must be present but explicitly not calculated until Task 10'
    Assert-True ($md -match '\| 10 \|' -and $md -match '\| 20 \|' -and $md -match '\| 30 \|' -and $md -match '400.*1000.*1900.*2800.*1.*11' -and $md -match 'Primer punto.*20 VU') 'stress must include per-VU metrics and first degradation'
    Assert-True ($md -match '(?i)Baseline:' -and $md -match '3 VU' -and $md -match '(?i)Peak:' -and $md -match '30 VU' -and $md -match '18 s' -and $md -match '(?i)Recovery:') 'spike must include baseline, peak, recovery and result'
    Assert-True ($md -match '\*\*Resultado:\*\* APROBADA' -and $md -notmatch '\*\*Resultado:\*\* observado') 'profiles without raw result must emit metric-derived outcomes'
    $timeoutRaw = $raw.Clone(); $timeoutRaw['smoke'] = Clone-Value $raw['smoke']; [void]$timeoutRaw['smoke'].metrics.PSObject.Properties.Add([PSNoteProperty]::new('http_req_timeout',@{ type='rate'; values=@{ rate=0.11 } }))
    $timeoutMatrix = $matrix.Replace('GET /api/orders,smoke,Validate orders under representative traffic,1,3,900,0.5,10,APROBADA','GET /api/orders,smoke,Validate orders under representative traffic,1,3,900,0.5,10,FALLIDA')
    $timeoutReport = Invoke-Report $timeoutMatrix $timeoutRaw $manifest 'timeout-outcome'
    Assert-True ($timeoutReport.ExitCode -eq 0) "timeout outcome fixture should generate: $($timeoutReport.Stdout)"
    $timeoutMd = Read-Utf8NoBom (Join-Path $timeoutReport.Output 'endpoint-report.md')
    Assert-True ($timeoutMd -match '## Smoke[\s\S]*\*\*Resultado:\*\* FALLIDA') 'hard timeout rate must influence the metric-derived outcome'
    $invalidTimeoutRaw = $raw.Clone(); $invalidTimeoutRaw['smoke'] = Clone-Value $raw['smoke']; [void]$invalidTimeoutRaw['smoke'].metrics.PSObject.Properties.Add([PSNoteProperty]::new('http_req_timeout',@{ type='rate'; values=@{ rate=1.1 } }))
    Assert-ReportRejected $matrix $invalidTimeoutRaw $manifest 'invalid-timeout-rate' 'timeout|rate|ratio|invalid'
    $ordinaryWordsRaw = $raw.Clone(); $ordinaryWordsRaw['smoke'] = Clone-Value $raw['smoke']; [void]$ordinaryWordsRaw['smoke'].PSObject.Properties.Add([PSNoteProperty]::new('result','token budget and provider status observed'))
    $ordinaryWordsReport = Invoke-Report $matrix $ordinaryWordsRaw $manifest 'ordinary-secret-words'
    Assert-True ($ordinaryWordsReport.ExitCode -eq 0) 'ordinary token/provider words must not be treated as credentials'
    $freeFormResultRaw = $raw.Clone(); $freeFormResultRaw['smoke'] = Clone-Value $raw['smoke']; [void]$freeFormResultRaw['smoke'].PSObject.Properties.Add([PSNoteProperty]::new('result','[FAILED](https://evil.example) <b>*boom*</b> | `code`')); $freeFormResultRaw['spike'] = Clone-Value $raw['spike']; [void]$freeFormResultRaw['spike'].PSObject.Properties.Add([PSNoteProperty]::new('result',$freeFormResultRaw['smoke'].result))
    $freeFormResult = Invoke-Report $matrix $freeFormResultRaw $manifest 'free-form-result'
    Assert-True ($freeFormResult.ExitCode -eq 0) "free-form result fixture should generate: $($freeFormResult.Stdout)"
    $freeFormMd = Read-Utf8NoBom (Join-Path $freeFormResult.Output 'endpoint-report.md')
    Assert-True ($freeFormMd.Contains('\[FAILED\]\(https://evil\.example\) \<b\>\*boom\*\</b\> \| \`code\`')) 'free-form profile results must be Markdown-escaped in Report-Text and Render-Spike'
    Assert-True ($freeFormMd -notmatch '\[FAILED\]\(https://evil\.example\)' -and $freeFormMd -notmatch '<b>\*boom\*') 'raw Markdown/HTML result syntax must not remain active'

    $unsafeManifest = @{ endpoints = @(@{ id='orders'; method='GET'; path='/api/orders|<script>'; objective="Objective | line`n**bold** [link](x) <script>alert(1)</script>"; priority='P0'; enabled_profiles=@('smoke','load','stress','spike') }) }
    $unsafeRows = @(
        [pscustomobject]@{ endpoint='GET /api/orders|<script>'; test='smoke'; objetivo="Objective | line`n**bold** [link](x) <script>alert(1)</script>"; carga_vu_min='1'; carga_vu_max='3'; p95_ms='900'; error_pct='0.5'; capacidad_rps='10'; resultado='APROBADA'; usuarios="1→3 VUs | [users]`n<script>" },
        [pscustomobject]@{ endpoint='GET /api/orders|<script>'; test='load'; objetivo="Objective | line`n**bold** [link](x) <script>alert(1)</script>"; carga_vu_min='0'; carga_vu_max='10'; p95_ms='1800'; error_pct='2'; capacidad_rps='12'; resultado='APROBADA'; usuarios="0→10 VUs | [users]`n<script>" },
        [pscustomobject]@{ endpoint='GET /api/orders|<script>'; test='stress'; objetivo="Objective | line`n**bold** [link](x) <script>alert(1)</script>"; carga_vu_min='10'; carga_vu_max='30'; p95_ms='3200'; error_pct='11'; capacidad_rps='14'; resultado='ADVERTENCIA'; usuarios="10→30 VUs | [users]`n<script>" },
        [pscustomobject]@{ endpoint='GET /api/orders|<script>'; test='spike'; objetivo="Objective | line`n**bold** [link](x) <script>alert(1)</script>"; carga_vu_min='3'; carga_vu_max='30'; p95_ms='4100'; error_pct='8'; capacidad_rps='15'; resultado='APROBADA'; usuarios="3→30 VUs | [users]`n<script>" }
    )
    $unsafeMatrix = ($unsafeRows | ConvertTo-Csv -NoTypeInformation) -join "`n"
    $unsafeReport = Invoke-Report $unsafeMatrix $raw $unsafeManifest 'unsafe-free-form'
    Assert-True ($unsafeReport.ExitCode -eq 0) "free-form manifest/matrix fixture should generate: $($unsafeReport.Stdout)"
    $unsafeMd = Read-Utf8NoBom (Join-Path $unsafeReport.Output 'endpoint-report.md')
    foreach ($escaped in @('\|','\<script\>','\[link\]\(x\)','\*\*bold\*\*','\*bold\*','\[users\]')) { Assert-True ($unsafeMd.Contains($escaped)) "Markdown free-form value should escape $escaped" }
    Assert-True ($unsafeMd -notmatch '(?<!\\)<script>|(?<!\\)\*bold\*') 'Markdown must not retain active HTML or emphasis syntax'
    Assert-True ($unsafeMd -notmatch 'line\r?\n') 'Markdown line breaks must not be emitted as raw free-form newlines'
    Assert-True ($unsafeMd.Contains('## Smoke') -and $unsafeMd.Contains('**Resultado:**')) 'trusted structural labels must remain unescaped'

    $bothProfiles = $raw.Clone(); $bothProfiles['smoke'] = Clone-Value $raw['smoke']; [void]$bothProfiles['smoke'].PSObject.Properties.Add([PSNoteProperty]::new('requestedProfile','smoke'))
    Assert-ReportRejected $matrix $bothProfiles $manifest 'both-profile-fields' 'profile|requestedProfile|both'

    $badNumericMatrix = $matrix.Replace('1800,2,12','not-a-number,2,12')
    Assert-ReportRejected $badNumericMatrix $raw $manifest 'bad-matrix-p95' 'matrix|p95|numeric'
    $missingMatrixField = $matrix.Replace('GET /api/orders,smoke',' ,smoke')
    Assert-ReportRejected $missingMatrixField $raw $manifest 'missing-matrix-endpoint' 'matrix|endpoint|required'
    $invalidResultMatrix = $matrix.Replace('APROBADA','INVALID_RESULT')
    Assert-ReportRejected $invalidResultMatrix $raw $manifest 'invalid-matrix-result' 'matrix|resultado|result'
    $negativeErrorMatrix = $matrix.Replace('900,0.5,10','900,-0.1,10')
    Assert-ReportRejected $negativeErrorMatrix $raw $manifest 'negative-matrix-error' 'matrix|error|range|numeric'
    $overLimitErrorMatrix = $matrix.Replace('1800,2,12','1800,100.1,12')
    Assert-ReportRejected $overLimitErrorMatrix $raw $manifest 'over-limit-matrix-error' 'matrix|error|range|numeric'
    $reversedVuMatrix = $matrix.Replace('1,3,900','4,3,900')
    Assert-ReportRejected $reversedVuMatrix $raw $manifest 'reversed-matrix-vu' 'matrix|vu|carga|order'
    $objectiveMismatchMatrix = $matrix.Replace('Validate orders under representative traffic','Different manifest objective')
    Assert-ReportRejected $objectiveMismatchMatrix $raw $manifest 'matrix-objective-mismatch' 'matrix|objetivo|objective|manifest'
    $matrixP95Mismatch = $matrix.Replace('GET /api/orders,smoke,Validate orders under representative traffic,1,3,900','GET /api/orders,smoke,Validate orders under representative traffic,1,3,901')
    Assert-ReportRejected $matrixP95Mismatch $raw $manifest 'cross-source-p95-mismatch' 'cross-source|p95|mismatch'
    $matrixVuMismatch = $matrix.Replace('GET /api/orders,smoke,Validate orders under representative traffic,1,3,900','GET /api/orders,smoke,Validate orders under representative traffic,1,4,900')
    Assert-ReportRejected $matrixVuMismatch $raw $manifest 'cross-source-vu-mismatch' 'cross-source|vu|mismatch'
    $matrixRpsMismatch = $matrix.Replace('900,0.5,10,APROBADA','900,0.5,11,APROBADA')
    Assert-ReportRejected $matrixRpsMismatch $raw $manifest 'cross-source-rps-mismatch' 'cross-source|rps|duration|mismatch'
    $matrixErrorMismatch = $matrix.Replace('900,0.5,10,APROBADA','900,0.6,10,APROBADA')
    Assert-ReportRejected $matrixErrorMismatch $raw $manifest 'cross-source-error-mismatch' 'cross-source|error|mismatch'
    $durationMismatchRaw = $raw.Clone(); $durationMismatchRaw['smoke'] = Clone-Value $raw['smoke']; $durationMismatchRaw['smoke'].measured_duration_seconds = 25
    Assert-ReportRejected $matrix $durationMismatchRaw $manifest 'cross-source-duration-mismatch' 'cross-source|duration|rps|mismatch'
    $matrixOutcomeMismatch = $matrix.Replace('GET /api/orders,smoke,Validate orders under representative traffic,1,3,900,0.5,10,APROBADA','GET /api/orders,smoke,Validate orders under representative traffic,1,3,900,0.5,10,ADVERTENCIA')
    Assert-ReportRejected $matrixOutcomeMismatch $raw $manifest 'cross-source-outcome-mismatch' 'cross-source|outcome|resultado|mismatch'
    $noExecutedNumericMatrix = $matrix.Replace('GET /api/orders,smoke,Validate orders under representative traffic,1,3,900,0.5,10,APROBADA','GET /api/orders,smoke,Validate orders under representative traffic,1,3,900,0.5,10,NO_EJECUTADA')
    $noExecutedRaw = $raw.Clone(); $noExecutedRaw.Remove('smoke')
    Assert-ReportRejected $noExecutedNumericMatrix $noExecutedRaw $manifest 'no-executed-fabricated-numerics' 'NO_EJECUTADA|blank|numeric|carga'
    $stressRangeMismatch = $matrix.Replace('GET /api/orders,stress,Validate orders under representative traffic,10,30,3200','GET /api/orders,stress,Validate orders under representative traffic,10,31,3200')
    Assert-ReportRejected $stressRangeMismatch $raw $manifest 'cross-source-stress-vu-range-mismatch' 'cross-source|stress|vu|mismatch'
    $stressMetricMismatch = $matrix.Replace('GET /api/orders,stress,Validate orders under representative traffic,10,30,3200,11,14','GET /api/orders,stress,Validate orders under representative traffic,10,30,3900,11,14')
    Assert-ReportRejected $stressMetricMismatch $raw $manifest 'cross-source-stress-metric-mismatch' 'cross-source|stress|p95|mismatch'
    $spikePeakMismatch = $raw.Clone(); $spikePeakMismatch['spike'] = Clone-Value $raw['spike']; $spikePeakMismatch['spike'].peak.p95_ms = 4200
    Assert-ReportRejected $matrix $spikePeakMismatch $manifest 'cross-source-spike-peak-mismatch' 'cross-source|spike|peak|p95|mismatch'
    $spikeRecoveryMismatch = $raw.Clone(); $spikeRecoveryMismatch['spike'] = Clone-Value $raw['spike']; $spikeRecoveryMismatch['spike'].recovery.seconds = 19
    Assert-ReportRejected $matrix $spikeRecoveryMismatch $manifest 'cross-source-spike-recovery-mismatch' 'cross-source|spike|recovery|seconds|mismatch'
    $spikeVuMismatch = $raw.Clone(); $spikeVuMismatch['spike'] = Clone-Value $raw['spike']; $spikeVuMismatch['spike'].baseline.vus = 4
    Assert-ReportRejected $matrix $spikeVuMismatch $manifest 'cross-source-spike-vu-mismatch' 'cross-source|spike|baseline|vus|mismatch'
    $backtickManifest = @{ endpoints = @(@{ id='orders'; method='GET'; path='/api/orders`detail'; objective='Validate orders under representative traffic'; priority='P0'; enabled_profiles=@('smoke','load','stress','spike') }) }
    $backtickMatrix = $matrix.Replace('GET /api/orders','GET /api/orders`detail')
    $backtickReport = Invoke-Report $backtickMatrix $raw $backtickManifest 'backtick-endpoint'
    Assert-True ($backtickReport.ExitCode -eq 0) "backtick endpoint fixture should generate: $($backtickReport.Stdout)"
    $backtickMd = Read-Utf8NoBom (Join-Path $backtickReport.Output 'endpoint-report.md')
    Assert-True ($backtickMd.Contains('GET /api/orders\`detail') -and $backtickMd -notmatch '\*\*Método/ruta:\*\* `[^`]*`') 'endpoint backticks must not break Markdown code spans'
    $secretRaw = $raw.Clone(); $secretRaw['smoke'] = Clone-Value $raw['smoke']; [void]$secretRaw['smoke'].PSObject.Properties.Add([PSNoteProperty]::new('result','provider_api_key=AKIA1234567890ABCDEF'))
    Assert-ReportRejected $matrix $secretRaw $manifest 'provider-credential-result' 'secret|credential|api|key|token'
    Assert-True ($md -match '\| GET /api/orders \| smoke \|' -and $md -match '\| GET /api/orders \| load \|' -and $md -match '\| GET /api/orders \| stress \|' -and $md -match '\| GET /api/orders \| spike \|') 'matrix must include all four canonical rows'
    Assert-True ($md -match 'Hecho:' -and $md -match 'Hip.*tesis:' -and $md -match 'no hay telemetr') 'conclusion must distinguish evidence from hypothesis'
    Assert-True ($md -notmatch '(?i)(causad[oa]|debido|provocad[oa]).{0,30}(sql|memoria)|(sql|memoria).{0,30}(causad[oa]|debido|provocad[oa])|password|bearer|eyJ[A-Za-z0-9_-]+') 'report must not claim unsupported causes or leak secrets'
    Assert-True ($html -match 'carga máxima observada de 30 VU' -and $html -match 'no hay telemetr.*SQL') 'HTML conclusion must use the same model-derived facts and hypothesis as Markdown'

    $escapedMatrix = $matrix
    $escaped = Invoke-Report $escapedMatrix $raw $manifest 'escaped-matrix'
    Assert-True ($escaped.ExitCode -eq 0) "matrix values should be escaped, not rejected: $($escaped.Stdout)"
    $escapedHtml = Read-Utf8NoBom (Join-Path $escaped.Output 'endpoint-report.html')
    Assert-True ($escapedHtml.Contains('ADVERTENCIA') -and $escapedHtml -notmatch '<script>') 'HTML must render canonical matrix resultado'

    $duplicateStress = $raw.Clone(); $duplicateStress['stress-20-copy'] = Clone-Value $raw['stress-20']
    Assert-ReportRejected $matrix $duplicateStress $manifest 'duplicate-stress' 'duplicate|stress'

    foreach ($field in @('p(50)','p(90)','p(95)','max')) {
        $invalid = $raw.Clone(); $invalid['stress-20'] = Clone-Value $raw['stress-20']; $invalid['stress-20'].metrics.http_req_duration.values.PSObject.Properties.Remove($field)
        Assert-ReportRejected $matrix $invalid $manifest "missing-stress-$field" 'stress|p\('
    }
    $invalidStressError = $raw.Clone(); $invalidStressError['stress-20'] = Clone-Value $raw['stress-20']; $invalidStressError['stress-20'].metrics.http_req_failed.values.PSObject.Properties.Remove('rate')
    Assert-ReportRejected $matrix $invalidStressError $manifest 'missing-stress-error' 'stress|error|rate'
    $invalidStressCount = $raw.Clone(); $invalidStressCount['stress-20'] = Clone-Value $raw['stress-20']; $invalidStressCount['stress-20'].metrics.http_reqs.values.PSObject.Properties.Remove('count')
    Assert-ReportRejected $matrix $invalidStressCount $manifest 'missing-stress-count' 'stress|count'
    $invalidStressP90 = $raw.Clone(); $invalidStressP90['stress-20'] = Clone-Value $raw['stress-20']; $invalidStressP90['stress-20'].metrics.http_req_duration.values.'p(90)' = 'not-a-metric'
    Assert-ReportRejected $matrix $invalidStressP90 $manifest 'invalid-stress-p90' 'stress|p\(90\)|invalid'
    $invalidStressVu = $raw.Clone(); $invalidStressVu['stress-20'] = Clone-Value $raw['stress-20']; $invalidStressVu['stress-20'].vu_max = 'not-a-vu'
    Assert-ReportRejected $matrix $invalidStressVu $manifest 'invalid-stress-vu' 'stress|vu'
    $mismatchedStressVu = $raw.Clone(); $mismatchedStressVu['stress-20'] = Clone-Value $raw['stress-20']; $mismatchedStressVu['stress-20'].vu_min = 10
    Assert-ReportRejected $matrix $mismatchedStressVu $manifest 'mismatched-stress-vu' 'stress|vu'

    $missingDuration = $raw.Clone(); $missingDuration['load'] = Clone-Value $raw['load']; $missingDuration['load'].PSObject.Properties.Remove('measured_duration_seconds')
    Assert-ReportRejected $matrix $missingDuration $manifest 'missing-duration' 'duration|RPS'

    foreach ($profileToRemove in @('smoke','load','spike')) {
        $missingProfile = $raw.Clone(); $missingProfile.Remove($profileToRemove)
        $missingResult = Invoke-Report $matrix $missingProfile $manifest "missing-$profileToRemove"
        Assert-True ($missingResult.ExitCode -eq 0) "missing $profileToRemove should render NO_EJECUTADA: $($missingResult.Stdout)"
        $missingMd = Read-Utf8NoBom (Join-Path $missingResult.Output 'endpoint-report.md')
        Assert-True ($missingMd -match "## $([regex]::Escape($profileToRemove.Substring(0,1).ToUpperInvariant()+$profileToRemove.Substring(1)))" -and $missingMd -match 'NO_EJECUTADA') "missing $profileToRemove must be visible as NO_EJECUTADA"
    }

    foreach ($part in @('baseline','peak','recovery')) {
        $malformedSpike = $raw.Clone(); $malformedSpike['spike'] = Clone-Value $raw['spike']; $malformedSpike['spike'].$part.PSObject.Properties.Remove('p95_ms')
        Assert-ReportRejected $matrix $malformedSpike $manifest "missing-spike-$part-p95" 'spike|p95'
    }
    $invalidSpikeVus = $raw.Clone(); $invalidSpikeVus['spike'] = Clone-Value $raw['spike']; $invalidSpikeVus['spike'].baseline.vus = 'bad'
    Assert-ReportRejected $matrix $invalidSpikeVus $manifest 'invalid-spike-vus' 'spike|vus'
    $invalidSpikeRps = $raw.Clone(); $invalidSpikeRps['spike'] = Clone-Value $raw['spike']; $invalidSpikeRps['spike'].peak.rps = 'bad'
    Assert-ReportRejected $matrix $invalidSpikeRps $manifest 'invalid-spike-rps' 'spike|rps'
    $invalidSpikeRecoveryError = $raw.Clone(); $invalidSpikeRecoveryError['spike'] = Clone-Value $raw['spike']; $invalidSpikeRecoveryError['spike'].recovery.error_pct = 'bad'
    Assert-ReportRejected $matrix $invalidSpikeRecoveryError $manifest 'invalid-recovery-error' 'spike|recovery|error'
    $missingRecoveryDuration = $raw.Clone(); $missingRecoveryDuration['spike'] = Clone-Value $raw['spike']; $missingRecoveryDuration['spike'].recovery.PSObject.Properties.Remove('seconds'); $missingRecoveryDuration['spike'].PSObject.Properties.Remove('recovery_seconds')
    Assert-ReportRejected $matrix $missingRecoveryDuration $manifest 'missing-recovery-duration' 'spike|recovery|seconds'

    $missingRaw = $raw.Clone(); $missingRaw.Remove('stress-30'); $missing = Invoke-Report $matrix $missingRaw $manifest 'missing'
    Assert-True ($missing.ExitCode -ne 0 -and $missing.Stdout -match 'stress|profile|missing') 'missing required stress detail must be rejected'

    $badOutput = Join-Path $testRoot 'unsafe-output\..\escape'
    $matrixPath = Write-TextFixture 'unsafe-matrix.csv' $matrix
    $manifestPath = Write-JsonFixture 'unsafe-manifest.json' $manifest
    $rawPath = Join-Path $testRoot 'unsafe-raw'; New-Item -ItemType Directory -Force -Path $rawPath | Out-Null
    foreach ($item in $raw.GetEnumerator()) { Write-JsonFixture "unsafe-raw\$($item.Key).json" $item.Value | Out-Null }
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        if ($PSVersionTable.PSEdition -eq 'Desktop') {
            $unsafe = & $PowerShellExecutable -NoProfile -ExecutionPolicy Bypass -File $generator -MatrixPath $matrixPath -RawPath $rawPath -ManifestPath $manifestPath -EndpointId 'orders' -OutputDirectory $badOutput 2>&1 | Out-String
        } else {
            $unsafe = & $PowerShellExecutable -NoProfile -File $generator -MatrixPath $matrixPath -RawPath $rawPath -ManifestPath $manifestPath -EndpointId 'orders' -OutputDirectory $badOutput 2>&1 | Out-String
        }
        $unsafeExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    Assert-True ($unsafeExitCode -ne 0 -and $unsafe -match 'path|output|safe') 'unsafe output path must be rejected'

    Write-Output 'PASS generate-endpoint-report.tests.ps1'
}
finally {
    if (Test-Path $testRoot) { Remove-Item -LiteralPath $testRoot -Recurse -Force }
}

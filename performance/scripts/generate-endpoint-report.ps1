[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$MatrixPath,
    [Parameter(Mandatory = $true)][string]$RawPath,
    [Parameter(Mandatory = $true)][string]$ManifestPath,
    [Parameter(Mandatory = $true)][string]$EndpointId,
    [Parameter(Mandatory = $true)][string]$OutputDirectory,
    [string]$TemplatePath = (Join-Path $PSScriptRoot '..\templates\endpoint-report.md')
)

$ErrorActionPreference = 'Stop'
$Profiles = @('smoke','load','stress','spike')
$CanonicalColumns = @('endpoint','test','objetivo','carga_vu_min','carga_vu_max','p95_ms','error_pct','capacidad_rps','resultado','usuarios')

function Fail([string]$Message) { throw "Malformed endpoint report input: $Message" }
function Has-Property($Object, [string]$Name) { return $null -ne $Object -and $null -ne $Object.PSObject.Properties[$Name] }
function Read-Json([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { Fail "file not found: $Path" }
    try { return Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json }
    catch { Fail "invalid JSON in $Path" }
}
function Require-Text($Object, [string]$Name, [string]$Context) {
    if (-not (Has-Property $Object $Name) -or [string]::IsNullOrWhiteSpace([string]$Object.$Name)) { Fail "$Context requires non-empty $Name" }
    return [string]$Object.$Name
}
function Number($Value, [string]$Name, [string]$Context) {
    $parsed = 0.0
    if ($null -eq $Value -or $Value -is [bool] -or -not [double]::TryParse(([string]$Value), [Globalization.NumberStyles]::Float, [Globalization.CultureInfo]::InvariantCulture, [ref]$parsed) -or [double]::IsNaN($parsed) -or [double]::IsInfinity($parsed) -or $parsed -lt 0) { Fail "$Context has invalid $Name" }
    return $parsed
}
function Format-Number([double]$Value) { return $Value.ToString('0.###', [Globalization.CultureInfo]::InvariantCulture) }
function Escape-Md([string]$Value) { return ([string]$Value).Replace('|','\|').Replace("`r",' ').Replace("`n",' ') }
function Escape-Html([string]$Value) { return ([string]$Value).Replace('&','&amp;').Replace('<','&lt;').Replace('>','&gt;').Replace('"','&quot;') }
function Assert-SafeOutput([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path) -or $Path -match '[*?<>|]' -or $Path -match '(^|[\\/])\.\.([\\/]|$)') { Fail 'output path is not safe' }
    $full = [IO.Path]::GetFullPath($Path)
    if ([IO.Path]::GetPathRoot($full) -eq $full) { Fail 'output path cannot be a filesystem root' }
    return $full
}
function Assert-NoSecrets([string]$Text) {
    if ($Text -match '(?i)(password|passwd|secret|authorization\s*:\s*bearer|\bbearer\s+eyJ|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})' -or $Text -match '(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b') { Fail 'generated report contains a secret-like value' }
}
function Get-ManifestEntry([string]$Path, [string]$Id) {
    $manifest = Read-Json $Path
    $items = if ($manifest -is [array]) { @($manifest) } elseif (Has-Property $manifest 'endpoints') { @($manifest.endpoints) } else { Fail 'manifest must contain endpoints' }
    $entry = @($items | Where-Object { [string]$_.id -eq $Id })
    if ($entry.Count -ne 1) { Fail "manifest must contain exactly one endpoint: $Id" }
    foreach ($field in @('id','method','path','objective')) { [void](Require-Text $entry[0] $field "manifest endpoint $Id") }
    return [pscustomobject]@{ id=$Id; endpoint="$($entry[0].method.ToUpperInvariant()) $($entry[0].path)"; objective=[string]$entry[0].objective }
}
function Get-RawFiles([string]$Path) {
    if (Test-Path -LiteralPath $Path -PathType Leaf) { return @((Get-Item -LiteralPath $Path)) }
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) { Fail "raw path not found: $Path" }
    $files = @(Get-ChildItem -LiteralPath $Path -Filter '*.json' -File -Recurse | Sort-Object FullName)
    if ($files.Count -eq 0) { Fail 'raw path contains no JSON files' }
    return $files
}
function Get-Profile($Raw, [string]$Path) {
    $property = if (Has-Property $Raw 'profile') { 'profile' } elseif (Has-Property $Raw 'requestedProfile') { 'requestedProfile' } else { Fail "$Path requires profile" }
    $profile = [string]$Raw.$property
    if ($profile -match '^stress_(\d+)$') { return $profile }
    if ($profile -notin $Profiles) { Fail "$Path has unsupported profile: $profile" }
    return $profile
}
function Get-MetricValues($Raw, [string]$Path, [bool]$RequireStressDetail = $false) {
    if (-not (Has-Property $Raw 'metrics')) { Fail "$Path requires metrics" }
    $metrics = $Raw.metrics
    if (-not (Has-Property $metrics 'http_req_duration') -or -not (Has-Property $metrics 'http_req_failed')) { Fail "$Path requires duration and error metrics" }
    if (-not (Has-Property $metrics.http_req_duration 'values') -or -not (Has-Property $metrics.http_req_failed 'values')) { Fail "$Path requires metric values" }
    $duration = $metrics.http_req_duration.values
    $failed = $metrics.http_req_failed.values
    if (-not (Has-Property $duration 'p(95)')) { Fail "$Path duration requires p(95)" }
    if (-not (Has-Property $failed 'rate')) { Fail "$Path error metric requires rate" }
    if ($RequireStressDetail -and (-not (Has-Property $metrics 'http_reqs') -or -not (Has-Property $metrics.http_reqs 'values') -or -not (Has-Property $metrics.http_reqs.values 'count'))) { Fail "$Path stress request metrics require http_reqs.values.count" }
    $requestValues = if (Has-Property $metrics 'http_reqs' -and Has-Property $metrics.http_reqs 'values') { $metrics.http_reqs.values } else { $duration }
    if (-not (Has-Property $requestValues 'count')) { Fail "$Path request metrics require count" }
    foreach ($field in @('p(50)','p(90)','p(95)','max')) {
        if ($RequireStressDetail -and -not (Has-Property $duration $field)) { Fail "$Path stress duration requires $field" }
    }
    $p50 = if (Has-Property $duration 'p(50)') { Number $duration.'p(50)' 'p(50)' $Path } else { $null }
    $p90 = if (Has-Property $duration 'p(90)') { Number $duration.'p(90)' 'p(90)' $Path } else { $null }
    $max = if (Has-Property $duration 'max') { Number $duration.max 'max' $Path } else { $null }
    return [pscustomobject]@{ p50=$p50; p90=$p90; p95=(Number $duration.'p(95)' 'p(95)' $Path); max=$max; count=(Number $requestValues.count 'count' $Path); error_pct=(Number $failed.rate 'error rate' $Path) * 100 }
}
function Get-Vu([object]$Raw, [string]$Name, [string]$Path) {
    if (-not (Has-Property $Raw $Name)) { Fail "$Path requires $Name" }
    $value = Number $Raw.$Name $Name $Path
    if ([math]::Floor($value) -ne $value) { Fail "$Path requires integer $Name" }
    return [int]$value
}
function New-ProfileModel($Raw, [string]$Profile, [string]$Path) {
    $values = Get-MetricValues $Raw $Path ($Profile -like 'stress_*')
    $vuMin = if (Has-Property $Raw 'vu_min') { Get-Vu $Raw 'vu_min' $Path } else { 0 }
    $vuMax = if (Has-Property $Raw 'vu_max') { Get-Vu $Raw 'vu_max' $Path } else { 0 }
    $result = if (Has-Property $Raw 'result') { [string]$Raw.result } else { '' }
    if (-not (Has-Property $Raw 'measured_duration_seconds')) { Fail "$Path requires measured_duration_seconds for RPS" }
    $durationSeconds = Number $Raw.measured_duration_seconds 'measured_duration_seconds' $Path
    if ($durationSeconds -le 0) { Fail "$Path measured_duration_seconds must be greater than zero" }
    $rps = $values.count / $durationSeconds
    return [pscustomobject]@{ profile=$Profile; vu_min=$vuMin; vu_max=$vuMax; p95=$values.p95; error_pct=$values.error_pct; rps=$rps; result=$result; values=$values; raw=$Raw }
}
function Read-Models($Entry) {
    $models = @{}; $stress = @{}
    foreach ($file in Get-RawFiles $RawPath) {
        $raw = Read-Json $file.FullName
        if (-not (Has-Property $raw 'endpoint_id') -or [string]$raw.endpoint_id -ne $Entry.id) { continue }
        $profile = Get-Profile $raw $file.Name
        if ($profile -match '^stress_') {
            $vu = [int]($profile -replace '^stress_','')
            if ($stress.ContainsKey($vu)) { Fail "duplicate raw stress profile: stress_$vu" }
            $stressModel = New-ProfileModel $raw $profile $file.Name
            if ($stressModel.vu_min -ne $vu -or $stressModel.vu_max -ne $vu) { Fail "$file.Name stress VU must match stress_$vu" }
            $stress[$vu] = $stressModel
        }
        elseif ($models.ContainsKey($profile)) { Fail "duplicate raw profile: $profile" }
        else { $models[$profile] = New-ProfileModel $raw $profile $file.Name }
    }
    if ($models.Count -eq 0) { Fail "no raw data for endpoint: $($Entry.id)" }
    return [pscustomobject]@{ profiles=$models; stress=$stress }
}
function Read-Matrix([string]$Path, $Entry) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { Fail "matrix file not found: $Path" }
    $rows = @(Import-Csv -LiteralPath $Path)
    if ($rows.Count -eq 0) { Fail 'matrix cannot be empty' }
    if ((@($rows[0].PSObject.Properties.Name) -join ',') -ne ($CanonicalColumns -join ',')) { Fail 'matrix schema does not match canonical columns' }
    $selected = @($rows | Where-Object { $_.endpoint -eq $Entry.endpoint })
    if ($selected.Count -ne 4) { Fail "matrix must contain exactly four rows for $($Entry.endpoint)" }
    foreach ($profile in $Profiles) { if (@($selected | Where-Object test -eq $profile).Count -ne 1) { Fail "matrix missing profile: $profile" } }
    return @($selected | Sort-Object @{Expression={ $Profiles.IndexOf($_.test) }})
}
function Value-Or-NA($Value) { if ($null -eq $Value -or $Value -eq '') { return 'N/D' }; return (Format-Number ([double]$Value)) }
function State($Row) { if ([string]::IsNullOrWhiteSpace($Row.resultado)) { return 'NO_EJECUTADA' }; return [string]$Row.resultado }
function Get-WorstResult($Rows) {
    $states=@($Rows | ForEach-Object { State $_ })
    if ($states -contains 'FALLIDA') { return 'FALLIDA' }
    if ($states -contains 'ADVERTENCIA') { return 'ADVERTENCIA' }
    if ($states -contains 'NO_EJECUTADA') { return 'NO_EJECUTADA' }
    return 'APROBADA'
}
function Report-Text($Model, [string]$Name) {
    $p = $Model.profiles[$Name]
    if ($null -eq $p) { return "**Configuración:** no ejecutada o sin raw JSON.  `n**Resultado:** NO_EJECUTADA" }
    return "**Configuración:** $($p.vu_min)→$($p.vu_max) VUs  `n**p95:** $(Value-Or-NA $p.p95) ms  `n**Error:** $(Value-Or-NA $p.error_pct)%  `n**RPS:** $(Value-Or-NA $p.rps)  `n**Resultado:** $(if ($p.result) { $p.result } else { 'observado' })"
}
function Render-Stress($Model) {
    if ($Model.stress.Count -eq 0) { return '**Resultado:** NO_EJECUTADA; no hay escalones stress_<VU> disponibles.' }
    $lines = @('| VU | p50 ms | p90 ms | p95 ms | max ms | error % | RPS |','|---:|---:|---:|---:|---:|---:|---:|')
    foreach ($vu in ($Model.stress.Keys | Sort-Object)) { $x=$Model.stress[$vu]; $lines += "| $vu | $(Value-Or-NA $x.values.p50) | $(Value-Or-NA $x.values.p90) | $(Value-Or-NA $x.values.p95) | $(Value-Or-NA $x.values.max) | $(Value-Or-NA $x.values.error_pct) | $(Value-Or-NA ($x.rps)) |" }
    $degraded = @($Model.stress.Keys | Sort-Object | Where-Object { $x=$Model.stress[$_]; $x.values.p95 -ge 3000 -or $x.values.error_pct -ge 10 })
    $first = if ($degraded.Count) { "$($degraded[0]) VU" } else { 'No observado en los escalones disponibles' }
    return ($lines -join "`n") + "`n`n**Primer punto de degradación:** $first (p95 ≥ 3000 ms o error ≥ 10%)."
}
function Render-Spike($Model) {
    $p = $Model.profiles['spike']
    if ($null -eq $p) { return '**Resultado:** NO_EJECUTADA; no hay datos spike.' }
    $raw=$p.raw
    $spikeParts = @{}
    foreach ($name in @('baseline','peak','recovery')) {
        if (-not (Has-Property $raw $name)) { Fail "spike requires $name data" }
        $part = $raw.$name
        foreach ($field in @('vus','p95_ms','error_pct','rps')) { if (-not (Has-Property $part $field)) { Fail "spike $name requires $field" } }
        $vus = Get-Vu $part 'vus' "spike $name"
        $spikeParts[$name] = [pscustomobject]@{ vus=$vus; p95_ms=(Number $part.p95_ms 'p95_ms' "spike $name"); error_pct=(Number $part.error_pct 'error_pct' "spike $name"); rps=(Number $part.rps 'rps' "spike $name") }
    }
    $recoverySeconds = if (Has-Property $raw.recovery 'seconds') { Number $raw.recovery.seconds 'recovery seconds' 'spike' } elseif (Has-Property $raw 'recovery_seconds') { Number $raw.recovery_seconds 'recovery seconds' 'spike' } else { Fail 'spike requires recovery seconds' }
    return "**Baseline:** $($spikeParts.baseline.vus) VU, p95 $(Value-Or-NA $spikeParts.baseline.p95_ms) ms, error $(Value-Or-NA $spikeParts.baseline.error_pct)%, RPS $(Value-Or-NA $spikeParts.baseline.rps)`n`n**Peak:** $($spikeParts.peak.vus) VU, p95 $(Value-Or-NA $spikeParts.peak.p95_ms) ms, error $(Value-Or-NA $spikeParts.peak.error_pct)%, RPS $(Value-Or-NA $spikeParts.peak.rps)`n`n**Recovery:** $($spikeParts.recovery.vus) VU, p95 $(Value-Or-NA $spikeParts.recovery.p95_ms) ms, error $(Value-Or-NA $spikeParts.recovery.error_pct)%, RPS $(Value-Or-NA $spikeParts.recovery.rps), $recoverySeconds s.`n`n**Resultado:** $(if ($p.result) { $p.result } else { 'observado' })"
}
function Render-Matrix($Rows) {
    $lines=@('| endpoint | test | objetivo | carga_vu_min | carga_vu_max | p95_ms | error_pct | capacidad_rps | resultado | usuarios |','|---|---|---|---:|---:|---:|---:|---:|---|---|')
    foreach ($row in $Rows) { $lines += "| $(Escape-Md $row.endpoint) | $($row.test) | $(Escape-Md $row.objetivo) | $($row.carga_vu_min) | $($row.carga_vu_max) | $($row.p95_ms) | $($row.error_pct) | $($row.capacidad_rps) | $(Escape-Md $row.resultado) | $(Escape-Md $row.usuarios) |" }
    return $lines -join "`n"
}
function Get-ConclusionModel($Model, $Rows) {
    $result=Get-WorstResult $Rows
    $facts = @("el endpoint alcanzó una carga máxima observada de $((@($Rows | ForEach-Object {[int]$_.carga_vu_max} | Measure-Object -Maximum).Maximum)) VU y la matriz reporta estado $result.")
    if ($Model.stress.Count) { $facts += 'los escalones stress muestran las latencias, errores y RPS observados en la tabla; el primer punto de degradación se limita a esos escalones.' }
    return [pscustomobject]@{ facts=$facts; hypothesis='no hay telemetría de SQL, memoria, CPU o logs en este modelo; por tanto, no se atribuye la degradación a una causa técnica específica.' }
}
function Render-Conclusion($Model, $Rows) {
    $conclusion=Get-ConclusionModel $Model $Rows
    $lines=@($conclusion.facts | ForEach-Object { "**Hecho:** $_" }); $lines += "**Hipótesis:** $($conclusion.hypothesis)"
    return $lines -join "`n`n"
}
function Render-Html($Model, $Rows) {
    $entry=$Model.entry; $sections=@(); $overall=Get-WorstResult $Rows; $conclusion=Get-ConclusionModel $Model $Rows
    foreach ($name in @('smoke','load')) { $label = $name.Substring(0,1).ToUpperInvariant() + $name.Substring(1); $sections += "<section><h2>$label</h2><p>$(Escape-Html (Report-Text $Model $name))</p></section>" }
    $stress=Escape-Html (Render-Stress $Model) -replace '`n','<br>'
    $spike=Escape-Html (Render-Spike $Model) -replace '`n','<br>'
    $matrixRows=($Rows | ForEach-Object { "<tr><td>$(Escape-Html ([string]$_.endpoint))</td><td>$(Escape-Html ([string]$_.test))</td><td>$(Escape-Html ([string]$_.objetivo))</td><td>$(Escape-Html ([string]$_.carga_vu_min))</td><td>$(Escape-Html ([string]$_.carga_vu_max))</td><td>$(Escape-Html ([string]$_.p95_ms))</td><td>$(Escape-Html ([string]$_.error_pct))</td><td>$(Escape-Html ([string]$_.capacidad_rps))</td><td>$(Escape-Html ([string]$_.resultado))</td><td>$(Escape-Html ([string]$_.usuarios))</td></tr>" }) -join ''
    $summary="<p><strong>Score endpoint:</strong> N/D (no calculado hasta Task 10); resultado de matriz: $(Escape-Html $overall); carga máxima: $((@($Rows | ForEach-Object {[int]$_.carga_vu_max} | Measure-Object -Maximum).Maximum)) VU; capacidad máxima: $((@($Rows | ForEach-Object {[double]$_.capacidad_rps} | Measure-Object -Maximum).Maximum)) RPS.</p>"
    $factHtml=($conclusion.facts | ForEach-Object { "<p><strong>Hecho:</strong> $(Escape-Html $_)</p>" }) -join ''
    return "<!doctype html><html lang='es'><head><meta charset='utf-8'><title>$(Escape-Html $entry.endpoint)</title><style>body{font:16px Segoe UI, sans-serif;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#172033}section{border:1px solid #dfe6f0;border-radius:10px;padding:1rem;margin:1rem 0}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #dfe6f0;padding:.4rem;text-align:left}th{background:#f3f6fb}.hypothesis{background:#fff7db;padding:1rem}</style></head><body><h1>$(Escape-Html $entry.endpoint)</h1><p><strong>Método/ruta:</strong> $(Escape-Html $entry.endpoint)<br><strong>Objetivo:</strong> $(Escape-Html $entry.objective)</p><h2>Resumen</h2>$summary$($sections -join '')<section><h2>Stress</h2><p>$stress</p></section><section><h2>Spike</h2><p>$spike</p></section><section><h2>Matriz</h2><table><thead><tr><th>endpoint</th><th>test</th><th>objetivo</th><th>carga_vu_min</th><th>carga_vu_max</th><th>p95_ms</th><th>error_pct</th><th>capacidad_rps</th><th>resultado</th><th>usuarios</th></tr></thead><tbody>$matrixRows</tbody></table></section><section class='hypothesis'><h2>Conclusión</h2>$factHtml<p><strong>Hipótesis:</strong> $(Escape-Html $conclusion.hypothesis)</p></section></body></html>"
}

if (-not (Test-Path -LiteralPath $TemplatePath -PathType Leaf)) { Fail "template file not found: $TemplatePath" }
$safeOutput = Assert-SafeOutput $OutputDirectory
$entry = Get-ManifestEntry $ManifestPath $EndpointId
$rows = Read-Matrix $MatrixPath $entry
$rawModels = Read-Models $entry
if ($rawModels.stress.Count -eq 0) { Fail 'stress report requires at least one stress_<VU> raw profile' }
$stressMatrixRow = @($rows | Where-Object test -eq 'stress')[0]
$stressMaxVu = [int]$stressMatrixRow.carga_vu_max
if (-not $rawModels.stress.ContainsKey($stressMaxVu)) { Fail "stress raw profiles are missing the matrix maximum VU: $stressMaxVu" }
$model = [pscustomobject]@{ entry=$entry; profiles=$rawModels.profiles; stress=$rawModels.stress; rows=$rows }
$summary = "- **Score endpoint:** N/D (no calculado hasta Task 10)`n- **Resultado:** $(Get-WorstResult $rows)`n- **Carga máxima:** $((@($rows | ForEach-Object {[int]$_.carga_vu_max} | Measure-Object -Maximum).Maximum)) VU`n- **Capacidad máxima:** $((@($rows | ForEach-Object {[double]$_.capacidad_rps} | Measure-Object -Maximum).Maximum)) RPS"
$template = Get-Content -Raw -LiteralPath $TemplatePath
foreach ($token in @('{{ENDPOINT}}','{{OBJECTIVE}}','{{SUMMARY}}','{{SMOKE}}','{{LOAD}}','{{STRESS}}','{{SPIKE}}','{{MATRIX}}','{{CONCLUSION}}')) { if (-not $template.Contains($token)) { Fail "template missing token: $token" } }
$markdown = $template.Replace('{{ENDPOINT}}',(Escape-Md $entry.endpoint)).Replace('{{OBJECTIVE}}',(Escape-Md $entry.objective)).Replace('{{SUMMARY}}',$summary).Replace('{{SMOKE}}',(Report-Text $model 'smoke')).Replace('{{LOAD}}',(Report-Text $model 'load')).Replace('{{STRESS}}',(Render-Stress $model)).Replace('{{SPIKE}}',(Render-Spike $model)).Replace('{{MATRIX}}',(Render-Matrix $rows)).Replace('{{CONCLUSION}}',(Render-Conclusion $model $rows))
$html = Render-Html $model $rows
Assert-NoSecrets $markdown; Assert-NoSecrets $html
New-Item -ItemType Directory -Force -Path $safeOutput | Out-Null
$markdownPath=Join-Path $safeOutput 'endpoint-report.md'; $htmlPath=Join-Path $safeOutput 'endpoint-report.html'
$markdown | Set-Content -LiteralPath $markdownPath -Encoding utf8NoBOM
$html | Set-Content -LiteralPath $htmlPath -Encoding utf8NoBOM
Write-Output "Generated endpoint report: $markdownPath and $htmlPath"

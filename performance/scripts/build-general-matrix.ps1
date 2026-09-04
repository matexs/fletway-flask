[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ResultsRoot,
    [Parameter(Mandatory = $true)][string]$OutputPath,
    [string]$ManifestPath
)

$ErrorActionPreference = 'Stop'
$CanonicalHeader = 'endpoint,test,objetivo,carga_vu_min,carga_vu_max,p95_ms,error_pct,capacidad_rps,resultado,usuarios'
$Columns = $CanonicalHeader.Split(',')

function Fail([string]$message) { throw "General matrix validation failed: $message" }

function Parse-CsvLine([string]$line) {
    $values = [Collections.Generic.List[string]]::new()
    $buffer = [Text.StringBuilder]::new()
    $quoted = $false
    for ($i = 0; $i -lt $line.Length; $i++) {
        $char = $line[$i]
        if ($char -eq '"') {
            if ($quoted -and $i + 1 -lt $line.Length -and $line[$i + 1] -eq '"') {
                [void]$buffer.Append('"'); $i++
            } else { $quoted = -not $quoted }
        } elseif ($char -eq ',' -and -not $quoted) {
            $values.Add($buffer.ToString()); [void]$buffer.Clear()
        } else { [void]$buffer.Append($char) }
    }
    if ($quoted) { Fail 'unterminated quoted CSV field' }
    $values.Add($buffer.ToString())
    return ,$values.ToArray()
}

function Assert-SafeIdentifier([string]$value, [string]$label) {
    if ([string]::IsNullOrWhiteSpace($value) -or $value -notmatch '^[A-Za-z0-9][A-Za-z0-9._-]*$' -or $value -match '\.\.') {
        Fail "$label '$value' is unsafe"
    }
}

function Assert-SafeEndpoint([string]$endpoint) {
    if ([string]::IsNullOrWhiteSpace($endpoint) -or $endpoint -match '[\x00-\x1F\\]' -or $endpoint -match '\.\.' -or $endpoint -notmatch '^(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD) /[^\s]*$') {
        Fail "unsafe endpoint '$endpoint'"
    }
}

function Get-PriorityMap([string]$path) {
    $map = @{ byEndpoint = @{}; byAlias = @{} }
    if ([string]::IsNullOrWhiteSpace($path)) { return $map }
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { Fail "manifest does not exist: $path" }
    try { $manifest = Get-Content -Raw -LiteralPath $path | ConvertFrom-Json } catch { Fail "invalid manifest JSON: $($_.Exception.Message)" }
    if ($null -eq $manifest.endpoints) { Fail 'manifest must contain endpoints' }
    $declaration = 0
    foreach ($item in @($manifest.endpoints)) {
        $declaration++
        $method = [string]$item.method
        $pathValue = [string]$item.path
        $canonical = if ($method -and $pathValue) { "$method $pathValue" } else { '' }
        $legacy = [string]$item.endpoint
        if (-not $canonical -and -not $legacy) { Fail 'manifest endpoint must define method/path or endpoint' }
        if ($canonical) { Assert-SafeEndpoint $canonical }
        $priority = if ([string]$item.priority -eq 'P0') { 0 } else { 1 }
        $record = [pscustomobject]@{ Endpoint = $canonical; Objective = [string]$item.objective; Priority = $priority; Id = [string]$item.id; Declaration = $declaration }
        if ($canonical) {
            if ($map.byEndpoint.ContainsKey($canonical)) { $map.byEndpoint[$canonical] = @($map.byEndpoint[$canonical]) + @($record) }
            else { $map.byEndpoint[$canonical] = @($record) }
        }
        foreach ($alias in @($legacy, [string]$item.id)) {
            if ([string]::IsNullOrWhiteSpace($alias)) { continue }
            if ($map.byAlias.ContainsKey($alias)) {
                $existingAliases = @($map.byAlias[$alias])
                if (@($existingAliases | Where-Object { $_.Endpoint -ne $canonical }).Count -gt 0) { Fail "ambiguous manifest alias '$alias'" }
                $map.byAlias[$alias] = $existingAliases + @($record)
            } else { $map.byAlias[$alias] = @($record) }
        }
    }
    return $map
}

function Resolve-ManifestEntry([string]$endpoint, [string]$objective, [hashtable]$manifestMap) {
    $candidates = @()
    if ($manifestMap.byEndpoint.ContainsKey($endpoint)) { $candidates = @($manifestMap.byEndpoint[$endpoint]) }
    elseif ($manifestMap.byAlias.ContainsKey($endpoint)) { $candidates = @($manifestMap.byAlias[$endpoint]) }
    if ($candidates.Count -eq 0) { return $null }
    $exact = @($candidates | Where-Object { $_.Objective -and $_.Objective -ceq $objective } | Sort-Object Priority, Declaration)
    if ($exact.Count -gt 0) { return $exact[0] }
    return @($candidates | Sort-Object Priority, Declaration)[0]
}

function Read-Matrix([string]$path, [string]$runId, [hashtable]$manifestMap) {
    $lines = [IO.File]::ReadAllLines($path, [Text.UTF8Encoding]::new($false))
    if ($lines.Count -eq 0 -or ((Parse-CsvLine $lines[0]) -join ',') -cne $CanonicalHeader) {
        Fail "${path}: header must be exactly '$CanonicalHeader'"
    }
    $rows = @()
    for ($lineNumber = 1; $lineNumber -lt $lines.Count; $lineNumber++) {
        if ($lines[$lineNumber].Length -eq 0) { Fail "${path}: blank row at line $($lineNumber + 1)" }
        $fields = Parse-CsvLine $lines[$lineNumber]
        if ($fields.Count -ne $Columns.Count) { Fail "${path}: line $($lineNumber + 1) must have ten fields" }
        $row = [ordered]@{}
        for ($i = 0; $i -lt $Columns.Count; $i++) { $row[$Columns[$i]] = $fields[$i] }
        Assert-SafeEndpoint $row.endpoint
        if ($row.test -notin @('smoke', 'load', 'stress', 'spike')) { Fail "${path}: unsupported test '$($row.test)'" }
        if ($row.resultado -notin @('APROBADA', 'ADVERTENCIA', 'FALLIDA', 'NO_EJECUTADA')) { Fail "${path}: invalid resultado '$($row.resultado)'" }
        if ([string]::IsNullOrWhiteSpace($row.objetivo)) { Fail "${path}: objetivo cannot be empty" }
        $numeric = @('carga_vu_min', 'carga_vu_max', 'p95_ms', 'error_pct', 'capacidad_rps')
        foreach ($column in $numeric) {
            if ($row.resultado -eq 'NO_EJECUTADA' -and $row[$column] -ne '') { Fail "${path}: NO_EJECUTADA numeric '$column' must be blank" }
            if ($row.resultado -ne 'NO_EJECUTADA' -and $row[$column] -eq '') { Fail "${path}: executed row requires numeric '$column'" }
            if ($row[$column] -ne '') {
                $number = 0.0
                if (-not [double]::TryParse($row[$column], [Globalization.NumberStyles]::Float, [Globalization.CultureInfo]::InvariantCulture, [ref]$number) -or [double]::IsNaN($number) -or [double]::IsInfinity($number) -or $number -lt 0) { Fail "${path}: invalid nonnegative finite numeric '$column'" }
                if ($column -eq 'error_pct' -and ($number -gt 100)) { Fail "${path}: error_pct must be between 0 and 100" }
            }
        }
        if ($row.resultado -ne 'NO_EJECUTADA') {
            $min = [double]$row.carga_vu_min; $max = [double]$row.carga_vu_max
            if ($row.carga_vu_min -eq '' -or $row.carga_vu_max -eq '') { Fail "${path}: executed row requires VU bounds" }
            if ($min -gt $max) { Fail "${path}: carga_vu_min cannot exceed carga_vu_max" }
        }
        $manifestEntry = Resolve-ManifestEntry $row.endpoint $row.objetivo $manifestMap
        if (-not $manifestEntry -and $manifestMap.byEndpoint.Count -gt 0) { Fail "${path}: endpoint '$($row.endpoint)' is absent from canonical manifest" }
        if ($manifestEntry) {
            if ($manifestEntry.Endpoint -and $manifestEntry.Endpoint -ne $row.endpoint) { Fail "${path}: endpoint '$($row.endpoint)' does not match canonical manifest method/path" }
            if ($manifestEntry.Objective -and $manifestEntry.Objective -ne $row.objetivo) { Fail "${path}: objective does not match canonical manifest for '$($row.endpoint)'" }
        }
        $priority = if ($manifestEntry) { $manifestEntry.Priority } else { 1 }
        $rows += [pscustomobject]@{ Fields = $row; RunId = $runId; Priority = $priority; Source = $path; Line = $lineNumber + 1 }
    }
    return $rows
}

$root = [IO.Path]::GetFullPath($ResultsRoot)
$output = [IO.Path]::GetFullPath($OutputPath)
if (-not (Test-Path -LiteralPath $root -PathType Container)) { Fail "results root does not exist: $ResultsRoot" }
$priorityMap = Get-PriorityMap $ManifestPath
$files = @(Get-ChildItem -LiteralPath $root -Recurse -File -Filter 'matrix.csv' | Where-Object { [IO.Path]::GetFullPath($_.FullName) -ne $output })
$allRows = @()
foreach ($file in $files) {
    $relative = $file.FullName.Substring($root.Length).TrimStart('\', '/')
    $segments = $relative -split '[\\/]'
    if ($segments.Count -lt 3 -or $segments[0] -cne 'runs') { Fail "matrix path must be directly under results/runs/<run_id>/...: $($file.FullName)" }
    $runId = $segments[1]
    Assert-SafeIdentifier $runId 'run id'
    $allRows += Read-Matrix $file.FullName $runId $priorityMap
}

$seen = @{}
foreach ($item in $allRows) {
    $identity = "$($item.Fields.endpoint)|$($item.Fields.test)|$($item.RunId)"
    if ($seen.ContainsKey($identity)) { Fail "duplicate identity '$identity' in '$($item.Source)'" }
    $seen[$identity] = $true
}

$severity = @{ FALLIDA = 0; ADVERTENCIA = 1; APROBADA = 2; NO_EJECUTADA = 3 }
$sorted = @($allRows | Sort-Object @{ Expression = { $severity[$_.Fields.resultado] } }, @{ Expression = { $_.Priority } }, @{ Expression = { $_.Fields.endpoint } }, @{ Expression = { $_.Fields.test } }, @{ Expression = { $_.RunId } }, @{ Expression = { $_.Source } }, @{ Expression = { $_.Line } })
$outputDirectory = Split-Path -Parent $output
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
$content = @($CanonicalHeader) + @($sorted | ForEach-Object {
    $item = $_
    ($Columns | ForEach-Object { $column = $_; $value = [string]$item.Fields[$column]; if ($value -match '[",\r\n]') { '"' + ($value -replace '"', '""') + '"' } else { $value } }) -join ','
})
[IO.File]::WriteAllText($output, ($content -join "`n") + "`n", [Text.UTF8Encoding]::new($false))
Write-Output "Generated $output with $($allRows.Count) rows."
if ($allRows.Count -eq 0) { Write-Output 'No endpoint matrix artifacts found; emitted canonical header only.' }

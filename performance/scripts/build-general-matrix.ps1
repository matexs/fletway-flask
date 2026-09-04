[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$CampaignDirectory,
    [Parameter(Mandatory = $true)][string]$ManifestPath
)

$ErrorActionPreference = 'Stop'
$manifest = Get-Content -Raw -LiteralPath $ManifestPath | ConvertFrom-Json
$rawDirectory = Join-Path $CampaignDirectory 'raw'
$profiles = @('smoke','load','stress','spike')
$durations = @{ smoke = 40.0; load = 90.0; stress = 30.0; spike = 60.0 }
$soft = @{ smoke = @{ p95 = 1000; error = 1; timeout = 0 }; load = @{ p95 = 2000; error = 5; timeout = 1 }; stress = @{ p95 = 3000; error = 10; timeout = 10 }; spike = @{ p95 = 5000; error = 20; timeout = 10 } }

function Metric($metrics, [string]$name) { if ($null -eq $metrics) { return $null }; $property = $metrics.PSObject.Properties[$name]; if ($null -eq $property) { return $null }; return $property.Value }
function Value($metric, [string]$name) {
    if ($null -eq $metric) { return $null }
    $source = if ($null -ne $metric.values) { $metric.values } else { $metric }
    $property = $source.PSObject.Properties[$name]
    if ($null -eq $property) { return $null }
    return [double]$property.Value
}
function Safe([string]$value) { return $value -replace '[^A-Za-z0-9_]', '_' }
function Format-Number([double]$value) { return $value.ToString('0.###', [Globalization.CultureInfo]::InvariantCulture) }
function NoRow($endpoint, [string]$profile, [string]$reason) { return [pscustomobject][ordered]@{ endpoint = "$($endpoint.method) $($endpoint.path)"; test = $profile; objetivo = $endpoint.objective; carga_vu_min = ''; carga_vu_max = ''; p95_ms = ''; error_pct = ''; capacidad_rps = ''; resultado = 'NO_EJECUTADA'; usuarios = $reason } }

function BuildRow($endpoint, [string]$profile) {
    $path = Join-Path $rawDirectory "$($endpoint.id)-$profile.json"
    if (-not (Test-Path -LiteralPath $path)) { return NoRow $endpoint $profile 'missing raw result' }
    $raw = Get-Content -Raw -LiteralPath $path | ConvertFrom-Json
    if ([string]$raw.result -eq 'NO_EJECUTADA' -or $null -eq $raw.metrics) { return NoRow $endpoint $profile ([string]$raw.reason) }
    $p95Values = @(); $errorValues = @(); $timeoutValues = @(); $rpsValues = @(); $count = 0.0; $minVus = 0; $maxVus = 0
    if ($profile -eq 'stress') {
        $minVus = 10; $maxVus = 30
        foreach ($stage in @('stress_10','stress_20','stress_30')) {
            $duration = Metric $raw.metrics "fletway_${stage}_$(Safe $endpoint.id)_duration_ms"
            $errors = Metric $raw.metrics "fletway_${stage}_$(Safe $endpoint.id)_error_rate"
            $timeouts = Metric $raw.metrics "fletway_${stage}_$(Safe $endpoint.id)_timeout_rate"
            if ($null -eq $duration -or $null -eq $errors) { continue }
            $stageCount = Value $duration 'count'
            if ($null -eq $stageCount -or $stageCount -le 0) { continue }
            $p95Values += (Value $duration 'p(95)'); $errorValues += ((Value $errors 'rate') * 100); if ($null -ne $timeouts) { $timeoutValues += ((Value $timeouts 'rate') * 100) }
            $count += $stageCount; $rpsValues += ($stageCount / 30.0)
        }
        if ($p95Values.Count -eq 0) { return NoRow $endpoint $profile 'stress metrics unavailable' }
    } else {
        $minVus = if ($profile -eq 'smoke') { 1 } elseif ($profile -eq 'spike') { 3 } else { 0 }; $maxVus = if ($profile -eq 'smoke') { 3 } elseif ($profile -eq 'spike') { 30 } else { 10 }
        $duration = Metric $raw.metrics "fletway_${profile}_$(Safe $endpoint.id)_duration_ms"
        $errors = Metric $raw.metrics "fletway_${profile}_$(Safe $endpoint.id)_error_rate"
        $timeouts = Metric $raw.metrics "fletway_${profile}_$(Safe $endpoint.id)_timeout_rate"
        if ($null -eq $duration -or $null -eq $errors) { return NoRow $endpoint $profile 'required metrics unavailable' }
        $count = Value $duration 'count'
        if ($null -eq $count -or $count -le 0) { return NoRow $endpoint $profile 'no measured samples' }
        $p95Values += (Value $duration 'p(95)'); $errorValues += ((Value $errors 'rate') * 100); if ($null -ne $timeouts) { $timeoutValues += ((Value $timeouts 'rate') * 100) }; $rpsValues += ($count / $durations[$profile])
    }
    $p95 = ($p95Values | Measure-Object -Maximum).Maximum; $error = ($errorValues | Measure-Object -Maximum).Maximum; $timeout = if ($timeoutValues.Count) { ($timeoutValues | Measure-Object -Maximum).Maximum } else { 0 }; $rps = ($rpsValues | Measure-Object -Maximum).Maximum
    $result = if ($p95 -ge 5000 -or $error -ge 20 -or $timeout -ge 10) { 'FALLIDA' } elseif ($p95 -lt $soft[$profile].p95 -and $error -lt $soft[$profile].error -and $timeout -le $soft[$profile].timeout) { 'APROBADA' } else { 'ADVERTENCIA' }
    return [pscustomobject][ordered]@{ endpoint = "$($endpoint.method) $($endpoint.path)"; test = $profile; objetivo = $endpoint.objective; carga_vu_min = $minVus; carga_vu_max = $maxVus; p95_ms = Format-Number $p95; error_pct = Format-Number $error; capacidad_rps = Format-Number $rps; resultado = $result; usuarios = "$minVus→$maxVus VUs" }
}

$rows = [System.Collections.Generic.List[object]]::new()
foreach ($endpoint in @($manifest.endpoints)) { foreach ($profile in $profiles) { if ($profile -in @($endpoint.enabled_profiles)) { $rows.Add((BuildRow $endpoint $profile)) } } }
$columns = @('endpoint','test','objetivo','carga_vu_min','carga_vu_max','p95_ms','error_pct','capacidad_rps','resultado','usuarios')
$parent = [IO.Path]::GetFullPath($CampaignDirectory); New-Item -ItemType Directory -Force -Path $parent | Out-Null
$rows | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $parent 'matrix_general.json') -Encoding utf8NoBOM
$rows | Select-Object $columns | Export-Csv -LiteralPath (Join-Path $parent 'matrix_general.csv') -NoTypeInformation -Encoding utf8
Write-Output "Generated $($rows.Count) matrix rows in $parent"

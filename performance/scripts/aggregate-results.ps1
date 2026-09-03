[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RawPath,
    [Parameter(Mandatory = $true)][string]$ManifestPath,
    [Parameter(Mandatory = $true)][string]$OutputPath
)

$ErrorActionPreference = 'Stop'
$CanonicalColumns = @('endpoint','test','objetivo','carga_vu_min','carga_vu_max','p95_ms','error_pct','capacidad_rps','resultado','usuarios')
$Profiles = @('smoke','load','stress','spike')
$ConfigPath = Join-Path $PSScriptRoot '..\config\thresholds.json'

function Fail([string]$Message) { throw "Malformed performance input: $Message" }

function Has-Property($Object, [string]$Name) {
    return $null -ne $Object -and $null -ne $Object.PSObject.Properties[$Name]
}

function Read-Json([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { Fail "file not found: $Path" }
    try { return (Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json) }
    catch { Fail "invalid JSON in $Path ($($_.Exception.Message))" }
}

function Assert-AllowedProperties($Object, [string[]]$Allowed, [string]$Context) {
    if ($null -eq $Object -or $null -eq $Object.PSObject.Properties) { Fail "$Context must be an object" }
    $unknown = @($Object.PSObject.Properties.Name | Where-Object { $_ -notin $Allowed })
    if ($unknown.Count) { Fail "$Context has unknown field(s): $($unknown -join ', ')" }
}

function Get-Config([string]$Path) {
    $config = Read-Json $Path
    Assert-AllowedProperties $config @('profiles','hard') 'threshold config'
    if (-not (Has-Property $config 'profiles') -or -not (Has-Property $config 'hard')) { Fail 'threshold config requires profiles and hard' }
    foreach ($profile in $Profiles) {
        if (-not (Has-Property $config.profiles $profile)) { Fail "threshold config missing $profile" }
        Assert-AllowedProperties $config.profiles.$profile @('p95_ms','error_pct','timeout_pct') "threshold config $profile"
        foreach ($field in @('p95_ms','error_pct','timeout_pct')) { [void](Number $config.profiles.$profile.$field $field "threshold config $profile") }
    }
    Assert-AllowedProperties $config.hard @('p95_ms','error_pct','timeout_pct') 'threshold config hard'
    foreach ($field in @('p95_ms','error_pct','timeout_pct')) { [void](Number $config.hard.$field $field 'threshold config hard') }
    return $config
}

function Require-Text($Object, [string]$Name, [string]$Context) {
    if (-not (Has-Property $Object $Name) -or [string]::IsNullOrWhiteSpace([string]$Object.$Name)) {
        Fail "$Context requires non-empty $Name"
    }
    return [string]$Object.$Name
}

function Number($Value, [string]$Name, [string]$Context, [double]$Minimum = 0) {
    if ($null -eq $Value -or $Value -is [bool]) { Fail "$Context requires numeric $Name" }
    $parsed = 0.0
    if (-not [double]::TryParse(([string]$Value), [Globalization.NumberStyles]::Float, [Globalization.CultureInfo]::InvariantCulture, [ref]$parsed) -or [double]::IsNaN($parsed) -or [double]::IsInfinity($parsed) -or $parsed -lt $Minimum) {
        Fail "$Context has invalid $Name"
    }
    return $parsed
}

function Format-Number([double]$Value) {
    return $Value.ToString('0.###', [Globalization.CultureInfo]::InvariantCulture)
}

function Get-Manifest([string]$Path) {
    $manifest = Read-Json $Path
    if ($manifest -isnot [array]) { Assert-AllowedProperties $manifest @('endpoints') 'manifest' }
    $items = if ($manifest -is [array]) { @($manifest) } elseif (Has-Property $manifest 'endpoints') { @($manifest.endpoints) } else { Fail 'manifest must contain endpoints' }
    if ($items.Count -eq 0) { Fail 'manifest endpoints cannot be empty' }
    $map = @{}
    foreach ($item in $items) {
        Assert-AllowedProperties $item @('id','module','method','path','objective','priority','traffic_weight','auth_role','mutates_data','enabled_profiles') 'manifest endpoint'
        $id = Require-Text $item 'id' 'manifest endpoint'
        if ($map.ContainsKey($id)) { Fail "duplicate manifest endpoint id: $id" }
        $method = Require-Text $item 'method' "manifest endpoint $id"
        $pathValue = Require-Text $item 'path' "manifest endpoint $id"
        $objective = Require-Text $item 'objective' "manifest endpoint $id"
        $priority = Require-Text $item 'priority' "manifest endpoint $id"
        if ($priority -notin @('P0','P1','P2')) { Fail "invalid priority for $id" }
        $enabled = if (Has-Property $item 'enabled_profiles') { @($item.enabled_profiles | ForEach-Object { [string]$_ }) } else { $Profiles }
        if ($enabled.Count -eq 0 -or @($enabled | Where-Object { $_ -notin $Profiles }).Count -or @($enabled | Group-Object | Where-Object Count -gt 1).Count) { Fail "invalid enabled_profiles for $id" }
        $map[$id] = [pscustomobject]@{ id=$id; endpoint="$($method.ToUpperInvariant()) $pathValue"; objective=$objective; priority=$priority; enabled_profiles=$enabled }
    }
    return $map
}

function Get-RawFiles([string]$Path) {
    if (Test-Path -LiteralPath $Path -PathType Leaf) { return @((Get-Item -LiteralPath $Path)) }
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) { Fail "raw path not found: $Path" }
    $files = @(Get-ChildItem -LiteralPath $Path -File -Filter '*.json' -Recurse | Sort-Object FullName)
    if ($files.Count -eq 0) { Fail 'raw path contains no JSON files' }
    return $files
}

function Get-Profile($Raw, [string]$Path) {
    if ((Has-Property $Raw 'profile') -and (Has-Property $Raw 'requestedProfile')) { Fail "$Path cannot contain both profile and requestedProfile" }
    if (-not (Has-Property $Raw 'profile') -and -not (Has-Property $Raw 'requestedProfile')) { Fail "$Path requires profile" }
    $value = if (Has-Property $Raw 'profile') { [string]$Raw.profile } else { [string]$Raw.requestedProfile }
    if ($value -match '^stress(?:_\d+)?$') { return 'stress' }
    if ($value -notin $Profiles) { Fail "$Path has unsupported profile: $value" }
    return $value
}

function Get-Metric($Metrics, [string]$Name, [string]$Path, [string]$Kind, [string]$EndpointId, [string]$Profile) {
    $suffix = if ($Kind -eq 'duration') { 'duration_ms' } elseif ($Kind -eq 'timeout') { 'timeout_rate' } else { 'error_rate' }
    $specific = @($Metrics.PSObject.Properties | Where-Object { $_.Name -match "(^|_)$suffix$" -and $_.Name -match [regex]::Escape($Profile) -and $_.Name -match [regex]::Escape($EndpointId) } | ForEach-Object Value)
    if ($specific.Count -eq 1) { return $specific[0] }
    if ($specific.Count -gt 1) { Fail "$Path requires exactly one unambiguous $Kind metric" }
    if (Has-Property $Metrics $Name) { return $Metrics.$Name }
    Fail "$Path requires $Kind metric"
}

function Validate-MetricMap($Metrics, [string]$Path) {
    if ($null -eq $Metrics -or $null -eq $Metrics.PSObject.Properties) { Fail "$Path metrics must be an object" }
    foreach ($metricProperty in $Metrics.PSObject.Properties) {
        $metric = $metricProperty.Value
        Assert-AllowedProperties $metric @('type','contains','values','thresholds') "$Path metric $($metricProperty.Name)"
        if (-not (Has-Property $metric 'values')) { Fail "$Path metric $($metricProperty.Name) requires values" }
        Assert-AllowedProperties $metric.values @('avg','min','med','max','p(90)','p(95)','count','rate','passes','fails') "$Path metric $($metricProperty.Name).values"
        if (-not (Has-Property $metric 'type') -or [string]::IsNullOrWhiteSpace([string]$metric.type)) { Fail "$Path metric $($metricProperty.Name) requires type" }
        if (Has-Property $metric.values 'rate') {
            $rate = Number $metric.values.rate 'rate' "$Path metric $($metricProperty.Name)"
            if ($rate -gt 1) { Fail "$Path metric $($metricProperty.Name) rate must be a ratio from 0 to 1" }
        }
        foreach ($valueName in @('count','p(90)','p(95)')) { if (Has-Property $metric.values $valueName) { [void](Number $metric.values.$valueName $valueName "$Path metric $($metricProperty.Name)") } }
    }
}

function Validate-Raw($Raw, [string]$Path) {
    Assert-AllowedProperties $Raw @('endpoint_id','profile','requestedProfile','result','reason','vu_min','vu_max','users','measured_duration_seconds','duration_seconds','duration_ms','timeout_pct','metrics','k6') $Path
    if ((Has-Property $Raw 'metrics') -and (Has-Property $Raw 'k6')) { Fail "$Path cannot contain both metrics and k6" }
    $durationFields = @('measured_duration_seconds','duration_seconds','duration_ms') | Where-Object { Has-Property $Raw $_ }
    if (Has-Property $Raw 'k6' -and Has-Property $Raw.k6 'state' -and Has-Property $Raw.k6.state 'testRunDurationMs') { $durationFields += 'k6.state.testRunDurationMs' }
    if ($durationFields.Count -gt 1) { Fail "$Path has ambiguous duration sources: $($durationFields -join ', ')" }
    if (Has-Property $Raw 'k6') {
        Assert-AllowedProperties $Raw.k6 @('metrics','state') "$Path k6"
        if (-not (Has-Property $Raw.k6 'metrics')) { Fail "$Path k6 requires metrics" }
        if (Has-Property $Raw.k6 'state') { Assert-AllowedProperties $Raw.k6.state @('testRunDurationMs','isStdOutTTY','isStdErrTTY') "$Path k6.state" }
    }
    $metrics = Get-Metrics $Raw
    if ($null -ne $metrics) { Validate-MetricMap $metrics $Path }
}

function Get-OptionalMetric($Metrics, [string]$Path, [string]$Kind, [string]$EndpointId, [string]$Profile) {
    $suffix = if ($Kind -eq 'timeout') { 'timeout_rate' } else { 'error_rate' }
    $specific = @($Metrics.PSObject.Properties | Where-Object { $_.Name -match "(^|_)$suffix$" -and $_.Name -match [regex]::Escape($Profile) -and $_.Name -match [regex]::Escape($EndpointId) } | ForEach-Object Value)
    if ($specific.Count -gt 1) { Fail "$Path requires exactly one unambiguous $Kind metric" }
    if ($specific.Count -eq 1) { return $specific[0] }
    $name = if ($Kind -eq 'timeout') { 'http_req_timeout' } else { '' }
    if ($name -and (Has-Property $Metrics $name)) { return $Metrics.$name }
    return $null
}

function Get-Value($Metric, [string]$ValueName, [string]$Path, [string]$MetricName) {
    if ($null -eq $Metric -or -not (Has-Property $Metric 'values') -or -not (Has-Property $Metric.values $ValueName)) { Fail "$Path metric $MetricName requires values.$ValueName" }
    return Number $Metric.values.$ValueName $ValueName "$Path metric $MetricName"
}

function Get-DurationSeconds($Raw, [string]$Path) {
    $names = @('measured_duration_seconds','duration_seconds')
    foreach ($name in $names) { if (Has-Property $Raw $name) { return Number $Raw.$name $name $Path 0.000001 } }
    if (Has-Property $Raw 'duration_ms') { return ((Number $Raw.duration_ms 'duration_ms' $Path 0.001) / 1000.0) }
    if (Has-Property $Raw 'k6' -and Has-Property $Raw.k6 'state' -and Has-Property $Raw.k6.state 'testRunDurationMs') {
        return ((Number $Raw.k6.state.testRunDurationMs 'k6.state.testRunDurationMs' $Path 0.001) / 1000.0)
    }
    Fail "$Path requires explicit measured duration in seconds or milliseconds"
}

function Get-Metrics($Raw) {
    if ((Has-Property $Raw 'metrics') -and (Has-Property $Raw 'k6')) { Fail 'raw input cannot contain both metrics and k6' }
    if (Has-Property $Raw 'metrics') { return $Raw.metrics }
    if (Has-Property $Raw 'k6' -and Has-Property $Raw.k6 'metrics') { return $Raw.k6.metrics }
    return $null
}

function New-Row($Raw, $Entry, [string]$Profile, [string]$Path, $Config) {
    $result = if (Has-Property $Raw 'result') { [string]$Raw.result } else { '' }
    if ($result -match '^(NOT_EXECUTED|NO_EJECUTADA)$') {
        return [ordered]@{ endpoint=$Entry.endpoint; test=$Profile; objetivo=$Entry.objective; carga_vu_min= if (Has-Property $Raw 'vu_min') { [int](Number $Raw.vu_min 'vu_min' $Path) } else { '' }; carga_vu_max= if (Has-Property $Raw 'vu_max') { [int](Number $Raw.vu_max 'vu_max' $Path) } else { '' }; p95_ms=''; error_pct=''; capacidad_rps=''; resultado='NO_EJECUTADA'; usuarios= if (Has-Property $Raw 'users') { [string]$Raw.users } else { '' } }
    }
    $metrics = Get-Metrics $Raw
    if ($null -eq $metrics) { if ($result -match '^(FAILED|FALLIDA)$') { return [ordered]@{ endpoint=$Entry.endpoint; test=$Profile; objetivo=$Entry.objective; carga_vu_min=''; carga_vu_max=''; p95_ms=''; error_pct=''; capacidad_rps=''; resultado='FALLIDA'; usuarios='' } }; Fail "$Path requires metrics" }
    $durationMetric = Get-Metric $metrics 'http_req_duration' $Path 'duration' $Entry.id $Profile
    $errorMetric = Get-Metric $metrics 'http_req_failed' $Path 'error' $Entry.id $Profile
    $p95 = Get-Value $durationMetric 'p(95)' $Path 'http_req_duration'
    $errorRate = Get-Value $errorMetric 'rate' $Path 'http_req_failed'
    if ($errorRate -gt 1) { Fail "$Path error rate must be a ratio from 0 to 1" }
    $timeoutMetric = Get-OptionalMetric $metrics $Path 'timeout' $Entry.id $Profile
    $timeoutRate = if (Has-Property $Raw 'timeout_pct') { (Number $Raw.timeout_pct 'timeout_pct' $Path) / 100.0 } elseif ($null -ne $timeoutMetric) { Get-Value $timeoutMetric 'rate' $Path 'timeout' } else { 0.0 }
    if ($timeoutRate -gt 1) { Fail "$Path timeout rate must be a ratio from 0 to 1 or timeout_pct" }
    $requestMetric = if (Has-Property $metrics 'http_reqs') { $metrics.http_reqs } elseif (Has-Property $metrics 'http_req_duration') { $metrics.http_req_duration } else { $null }
    if ($null -eq $requestMetric) { Fail "$Path requires http_reqs or http_req_duration count" }
    $requests = Get-Value $requestMetric 'count' $Path 'request count'
    $seconds = Get-DurationSeconds $Raw $Path
    $vuMin = if (Has-Property $Raw 'vu_min') { [int](Number $Raw.vu_min 'vu_min' $Path) } else { 0 }
    $vuMax = if (Has-Property $Raw 'vu_max') { [int](Number $Raw.vu_max 'vu_max' $Path) } else { Fail "$Path requires vu_max" }
    $hardFail = $p95 -ge $Config.hard.p95_ms -or ($errorRate * 100) -ge $Config.hard.error_pct -or ($timeoutRate * 100) -ge $Config.hard.timeout_pct
    $soft = $Config.profiles.$Profile
    $softTimeoutFail = if ($soft.timeout_pct -eq 0) { $timeoutRate -gt 0 } else { ($timeoutRate * 100) -ge $soft.timeout_pct }
    $softFail = $p95 -ge $soft.p95_ms -or ($errorRate * 100) -ge $soft.error_pct -or $softTimeoutFail
    $state = if ($result -match '^(FAILED|FALLIDA)$' -or $hardFail) { 'FALLIDA' } elseif ($softFail) { 'ADVERTENCIA' } else { 'APROBADA' }
    $users = if (Has-Property $Raw 'users') { [string]$Raw.users } else { "$vuMin→$vuMax VUs" }
    return [ordered]@{ endpoint=$Entry.endpoint; test=$Profile; objetivo=$Entry.objective; carga_vu_min=$vuMin; carga_vu_max=$vuMax; p95_ms=(Format-Number ([math]::Round($p95, 3))); error_pct=(Format-Number ([math]::Round($errorRate * 100, 3))); capacidad_rps=(Format-Number ([math]::Round($requests / $seconds, 3))); resultado=$state; usuarios=$users }
}

$config = Get-Config $ConfigPath
$manifest = Get-Manifest $ManifestPath
$rowsByKey = @{}
$seenEndpoints = @{}
foreach ($file in Get-RawFiles $RawPath) {
    $raw = Read-Json $file.FullName
    Validate-Raw $raw $file.Name
    $endpointId = Require-Text $raw 'endpoint_id' $file.Name
    if (-not $manifest.ContainsKey($endpointId)) { Fail "$($file.Name) references unknown endpoint: $endpointId" }
    $entry = $manifest[$endpointId]
    if ($entry.priority -ne 'P0') { continue }
    $profile = Get-Profile $raw $file.Name
    if ($profile -notin $entry.enabled_profiles) { Fail "$($file.Name) profile is not enabled for $endpointId" }
    $seenEndpoints[$endpointId] = $true
    $key = "$endpointId|$profile"
    if ($rowsByKey.ContainsKey($key)) { Fail "duplicate endpoint/profile data: $key" }
    $rowsByKey[$key] = New-Row $raw $entry $profile $file.Name $config
}

if ($rowsByKey.Count -eq 0) { Fail 'no P0 endpoint data found' }
foreach ($endpointId in $seenEndpoints.Keys) {
    $entry = $manifest[$endpointId]
    foreach ($profile in $Profiles) {
        $key = "$endpointId|$profile"
        if (-not $rowsByKey.ContainsKey($key)) {
            $reason = if ($profile -in $entry.enabled_profiles) { "NO_EJECUTADA: no raw result for $profile" } else { "NO_EJECUTADA: $profile disabled in manifest" }
            $rowsByKey[$key] = [ordered]@{ endpoint=$entry.endpoint; test=$profile; objetivo=$entry.objective; carga_vu_min=''; carga_vu_max=''; p95_ms=''; error_pct=''; capacidad_rps=''; resultado='NO_EJECUTADA'; usuarios=$reason }
        }
    }
}
$rows = @($rowsByKey.Values | Sort-Object endpoint, @{ Expression = { $Profiles.IndexOf($_.test) } })
$columnCheck = @($rows[0].Keys)
if (($columnCheck -join ',') -ne ($CanonicalColumns -join ',')) { Fail 'internal output schema mismatch' }
$parent = Split-Path -Parent ([IO.Path]::GetFullPath($OutputPath))
New-Item -ItemType Directory -Force -Path $parent | Out-Null
$rows | ConvertTo-Csv -NoTypeInformation | Set-Content -LiteralPath $OutputPath -Encoding utf8NoBOM
$csvSample = @(Import-Csv -LiteralPath $OutputPath | Select-Object -First 1)
if ($csvSample.Count -ne 1 -or ((@($csvSample[0].PSObject.Properties.Name) -join ',') -ne ($CanonicalColumns -join ','))) { Fail 'output CSV schema mismatch' }
Write-Output ("Aggregated {0} row(s) to {1}" -f $rows.Count, $OutputPath)

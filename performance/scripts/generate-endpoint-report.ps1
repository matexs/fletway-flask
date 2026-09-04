[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$MatrixPath,
    [Parameter(Mandatory = $true)][string]$RawPath,
    [Parameter(Mandatory = $true)][string]$ManifestPath,
    [Parameter(Mandatory = $true)][string]$EndpointId,
    [Parameter(Mandatory = $true)][string]$OutputDirectory,
    [string]$TemplatePath
)

$ErrorActionPreference = 'Stop'
$Profiles = @('smoke','load','stress','spike')
$CanonicalColumns = @('endpoint','test','objetivo','carga_vu_min','carga_vu_max','p95_ms','error_pct','capacidad_rps','resultado','usuarios')

function Fail([string]$Message) { throw "Malformed endpoint report input: $Message" }
function Has-Property($Object, [string]$Name) { return $null -ne $Object -and $null -ne $Object.PSObject.Properties[$Name] }
function Read-Utf8NoBom([string]$Path) {
    $encoding = New-Object System.Text.UTF8Encoding -ArgumentList $false
    return [IO.File]::ReadAllText($Path, $encoding)
}
function Read-Json([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { Fail "file not found: $Path" }
    try { return (Read-Utf8NoBom $Path | ConvertFrom-Json) }
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
function Get-Thresholds([string]$Path) {
    $config = Read-Json $Path
    if (-not (Has-Property $config 'profiles') -or -not (Has-Property $config 'hard')) { Fail 'threshold config requires profiles and hard' }
    foreach ($profile in $Profiles) {
        if (-not (Has-Property $config.profiles $profile)) { Fail "threshold config missing $profile" }
        foreach ($field in @('p95_ms','error_pct','timeout_pct')) {
            if (-not (Has-Property $config.profiles.$profile $field)) { Fail "threshold config $profile requires $field" }
            [void](Number $config.profiles.$profile.$field $field "threshold config $profile")
        }
    }
    foreach ($field in @('p95_ms','error_pct','timeout_pct')) {
        if (-not (Has-Property $config.hard $field)) { Fail "threshold config hard requires $field" }
        [void](Number $config.hard.$field $field 'threshold config hard')
    }
    return $config
}
function Get-ObservedOutcome([string]$Profile, [double]$P95, [double]$ErrorPct, [double]$TimeoutPct) {
    if ($P95 -ge $Thresholds.hard.p95_ms -or $ErrorPct -ge $Thresholds.hard.error_pct -or $TimeoutPct -ge $Thresholds.hard.timeout_pct) { return 'FALLIDA' }
    $softProfile = if ($Profile -like 'stress_*') { 'stress' } else { $Profile }
    $soft = $Thresholds.profiles.$softProfile
    $softTimeoutFail = if ($soft.timeout_pct -eq 0) { $TimeoutPct -gt 0 } else { $TimeoutPct -ge $soft.timeout_pct }
    if ($P95 -ge $soft.p95_ms -or $ErrorPct -ge $soft.error_pct -or $softTimeoutFail) { return 'ADVERTENCIA' }
    return 'APROBADA'
}
function Escape-Md([string]$Value) {
    $punctuation = @('\','`','*','_','{','}','[',']','<','>','(',')','#','+','-','.','!','|','~','&')
    $text = ([string]$Value).Replace("`r",' ').Replace("`n",' ')
    $builder = New-Object System.Text.StringBuilder
    foreach ($character in $text.ToCharArray()) {
        if ($punctuation -contains ([string]$character)) { [void]$builder.Append('\') }
        [void]$builder.Append($character)
    }
    return $builder.ToString()
}
function Escape-Html([string]$Value) { return ([string]$Value).Replace('&','&amp;').Replace('<','&lt;').Replace('>','&gt;').Replace('"','&quot;') }
function Write-Utf8NoBom([string]$Path, [string]$Content) {
    $encoding = New-Object System.Text.UTF8Encoding -ArgumentList $false
    [IO.File]::WriteAllText($Path, $Content, $encoding)
}
function Assert-SafeOutput([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path) -or $Path -match '[*?<>|]' -or $Path -match '(^|[\\/])\.\.([\\/]|$)') { Fail 'output path is not safe' }
    $full = [IO.Path]::GetFullPath($Path)
    if ([IO.Path]::GetPathRoot($full) -eq $full) { Fail 'output path cannot be a filesystem root' }
    return $full
}
function Assert-NoSecrets([string]$Text) {
    $patterns = @(
        '(?i)\b(?:password|passwd|secret)\s*[:=]\s*[^\s,;]+',
        '(?i)\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|secret[_-]?key|private[_-]?key|provider[_-]?(?:api[_-]?)?credential)s?\s*[:=]\s*[^\s,;]+',
        '(?i)\b(?:authorization|x-api-key|x-auth-token)\s*[:=]\s*(?:bearer\s+)?[^\s,;]+',
        '(?i)\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
        '(?i)\bAIza[0-9A-Za-z_-]{20,}\b',
        '(?i)\b(?:sk|pk)_[A-Za-z0-9]{20,}\b',
        '(?i)\b(?:ghp_|github_pat_|xox[baprs]-|glpat-|npm_)[A-Za-z0-9_-]{12,}\b',
        '(?i)\bbearer\s+eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}',
        '(?i)\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'
    )
    foreach ($pattern in $patterns) { if ($Text -match $pattern) { Fail 'generated report contains a secret-like value' } }
}
function Get-ManifestEntry([string]$Path, [string]$Id) {
    $manifest = Read-Json $Path
    $items = if ($manifest -is [array]) { @($manifest) } elseif (Has-Property $manifest 'endpoints') { @($manifest.endpoints) } else { Fail 'manifest must contain endpoints' }
    $entry = @($items | Where-Object { [string]$_.id -eq $Id })
    if ($entry.Count -ne 1) { Fail "manifest must contain exactly one endpoint: $Id" }
    foreach ($field in @('id','method','path','objective')) { [void](Require-Text $entry[0] $field "manifest endpoint $Id") }
    Assert-NoSecrets ([string]$entry[0].path)
    Assert-NoSecrets ([string]$entry[0].objective)
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
    $hasProfile = Has-Property $Raw 'profile'; $hasRequestedProfile = Has-Property $Raw 'requestedProfile'
    if ($hasProfile -and $hasRequestedProfile) { Fail "$Path cannot contain both profile and requestedProfile" }
    $property = if ($hasProfile) { 'profile' } elseif ($hasRequestedProfile) { 'requestedProfile' } else { Fail "$Path requires profile" }
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
    $timeoutMetrics = @($metrics.PSObject.Properties | Where-Object { $_.Name -eq 'http_req_timeout' -or $_.Name -match '(^|_)timeout_rate$' })
    if ($timeoutMetrics.Count -gt 1) { Fail "$Path has ambiguous timeout metrics" }
    $timeoutPct = 0.0
    if ($timeoutMetrics.Count -eq 1) {
        $timeoutMetric = $timeoutMetrics[0].Value
        if (-not (Has-Property $timeoutMetric 'values') -or -not (Has-Property $timeoutMetric.values 'rate')) { Fail "$Path timeout metric requires rate" }
        $timeoutRate = Number $timeoutMetric.values.rate 'timeout rate' $Path
        if ($timeoutRate -gt 1) { Fail "$Path timeout rate must be a ratio from 0 to 1" }
        $timeoutPct = $timeoutRate * 100
    }
    if (Has-Property $Raw 'timeout_pct') {
        if ($timeoutMetrics.Count -gt 0) { Fail "$Path has ambiguous timeout sources" }
        $timeoutPct = Number $Raw.timeout_pct 'timeout_pct' $Path
        if ($timeoutPct -gt 100) { Fail "$Path timeout_pct must be between 0 and 100" }
    }
    return [pscustomobject]@{ p50=$p50; p90=$p90; p95=(Number $duration.'p(95)' 'p(95)' $Path); max=$max; count=(Number $requestValues.count 'count' $Path); error_pct=(Number $failed.rate 'error rate' $Path) * 100; timeout_pct=$timeoutPct }
}
function Get-Vu([object]$Raw, [string]$Name, [string]$Path) {
    if (-not (Has-Property $Raw $Name)) { Fail "$Path requires $Name" }
    $value = Number $Raw.$Name $Name $Path
    if ([math]::Floor($value) -ne $value) { Fail "$Path requires integer $Name" }
    return [int]$value
}
function Get-SpikeParts($Raw, [string]$Path, [double]$SummaryP95, [double]$SummaryErrorPct, [double]$SummaryRps) {
    $parts = @{}
    foreach ($name in @('baseline','peak','recovery')) {
        if (-not (Has-Property $Raw $name)) { Fail "spike requires $name data" }
        $part = $Raw.$name
        foreach ($field in @('vus','p95_ms','error_pct','rps')) { if (-not (Has-Property $part $field)) { Fail "spike $name requires $field" } }
        $errorPct = Number $part.error_pct 'error_pct' "spike $name"
        if ($errorPct -gt 100) { Fail "spike $name error_pct must be between 0 and 100" }
        $parts[$name] = [pscustomobject]@{ vus=(Get-Vu $part 'vus' "spike $name"); p95_ms=(Number $part.p95_ms 'p95_ms' "spike $name"); error_pct=$errorPct; rps=(Number $part.rps 'rps' "spike $name") }
    }
    $recoverySeconds = if (Has-Property $Raw.recovery 'seconds') { Number $Raw.recovery.seconds 'recovery seconds' 'spike' } elseif (Has-Property $Raw 'recovery_seconds') { Number $Raw.recovery_seconds 'recovery seconds' 'spike' } else { Fail 'spike requires recovery seconds' }
    if (Has-Property $Raw.recovery 'seconds' -and Has-Property $Raw 'recovery_seconds') { Assert-NumericMatch $Raw.recovery.seconds $Raw.recovery_seconds 'recovery seconds' 'spike' }
    if ((Has-Property $Raw 'vu_min')) {
        $rawMinVu = Get-Vu $Raw 'vu_min' $Path
        Assert-NumericMatch $parts.baseline.vus $rawMinVu 'baseline vus' 'spike'
        Assert-NumericMatch $parts.recovery.vus $rawMinVu 'recovery vus' 'spike'
    }
    if ((Has-Property $Raw 'vu_max')) {
        $rawMaxVu = Get-Vu $Raw 'vu_max' $Path
        Assert-NumericMatch $parts.peak.vus $rawMaxVu 'peak vus' 'spike'
    }
    Assert-NumericMatch $parts.peak.p95_ms $SummaryP95 'p95_ms' 'spike peak'
    Assert-NumericMatch $parts.peak.error_pct $SummaryErrorPct 'error_pct' 'spike peak'
    Assert-NumericMatch $parts.peak.rps $SummaryRps 'rps' 'spike peak'
    return [pscustomobject]@{ baseline=$parts.baseline; peak=$parts.peak; recovery=$parts.recovery; recovery_seconds=$recoverySeconds }
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
    if (Has-Property $Raw 'users') { Assert-NoSecrets ([string]$Raw.users) }
    $outcome = Get-ObservedOutcome $Profile $values.p95 $values.error_pct $values.timeout_pct
    if ($result -in @('APROBADA','ADVERTENCIA','FALLIDA','NO_EJECUTADA') -and $result -cne $outcome) { Fail "$Path result contradicts raw metrics outcome" }
    $spikeParts = if ($Profile -eq 'spike') { Get-SpikeParts $Raw $Path $values.p95 $values.error_pct $rps } else { $null }
    return [pscustomobject]@{ profile=$Profile; vu_min=$vuMin; vu_max=$vuMax; p95=$values.p95; error_pct=$values.error_pct; timeout_pct=$values.timeout_pct; rps=$rps; duration_seconds=$durationSeconds; outcome=$outcome; result=$result; values=$values; spike_parts=$spikeParts; raw=$Raw }
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
    $rows = @(Read-Utf8NoBom $Path | ConvertFrom-Csv)
    if ($rows.Count -eq 0) { Fail 'matrix cannot be empty' }
    if ((@($rows[0].PSObject.Properties.Name) -join ',') -ne ($CanonicalColumns -join ',')) { Fail 'matrix schema does not match canonical columns' }
    $selected = @($rows | Where-Object { $_.endpoint -eq $Entry.endpoint })
    if ($selected.Count -ne 4) { Fail "matrix must contain exactly four rows for $($Entry.endpoint)" }
    foreach ($profile in $Profiles) { if (@($selected | Where-Object test -eq $profile).Count -ne 1) { Fail "matrix missing profile: $profile" } }
    foreach ($row in $selected) {
        foreach ($field in @('endpoint','test','objetivo','resultado','usuarios')) {
            if (-not (Has-Property $row $field) -or [string]::IsNullOrWhiteSpace([string]$row.$field)) { Fail "matrix row requires non-empty $field" }
        }
        foreach ($field in @('endpoint','objetivo','resultado','usuarios')) { Assert-NoSecrets ([string]$row.$field) }
        if ($row.test -notin $Profiles) { Fail "matrix row has unsupported test: $($row.test)" }
        if ([string]$row.resultado -notin @('APROBADA','ADVERTENCIA','FALLIDA','NO_EJECUTADA')) { Fail "matrix row has invalid resultado: $($row.resultado)" }
        if ([string]$row.objetivo -cne [string]$Entry.objective) { Fail "matrix row objetivo does not match manifest objective" }
        $notExecuted = [string]$row.resultado -eq 'NO_EJECUTADA'
        foreach ($field in @('carga_vu_min','carga_vu_max')) {
            if ($notExecuted) {
                if (-not [string]::IsNullOrWhiteSpace([string]$row.$field)) { Fail "matrix NO_EJECUTADA row requires blank $field" }
            } else {
                if (-not (Has-Property $row $field) -or [string]::IsNullOrWhiteSpace([string]$row.$field)) { Fail "matrix row requires numeric $field" }
                $vu = Number $row.$field $field 'matrix row'
                if ([math]::Floor($vu) -ne $vu) { Fail "matrix row requires integer $field" }
            }
        }
        foreach ($field in @('p95_ms','error_pct','capacidad_rps')) {
            if ($notExecuted) {
                if (-not [string]::IsNullOrWhiteSpace([string]$row.$field)) { Fail "matrix NO_EJECUTADA row requires blank $field" }
            } else {
                if (-not (Has-Property $row $field) -or [string]::IsNullOrWhiteSpace([string]$row.$field)) { Fail "matrix row requires numeric $field" }
                $errorPct = Number $row.$field $field 'matrix row'
                if ($field -eq 'error_pct' -and ($errorPct -lt 0 -or $errorPct -gt 100)) { Fail 'matrix row error_pct must be between 0 and 100' }
            }
        }
        if ((Has-Property $row 'carga_vu_min') -and (Has-Property $row 'carga_vu_max') -and -not [string]::IsNullOrWhiteSpace([string]$row.carga_vu_min) -and -not [string]::IsNullOrWhiteSpace([string]$row.carga_vu_max)) {
            if (([double]$row.carga_vu_min) -gt ([double]$row.carga_vu_max)) { Fail 'matrix row carga_vu_min must be less than or equal to carga_vu_max' }
        }
    }
    return @($selected | Sort-Object @{Expression={ $Profiles.IndexOf($_.test) }})
}
function Assert-NumericMatch([double]$Actual, [double]$Expected, [string]$Field, [string]$Context) {
    $tolerance = [math]::Max(0.001, ([math]::Max([math]::Abs($Actual), [math]::Abs($Expected)) * 0.000001))
    if ([math]::Abs($Actual - $Expected) -gt $tolerance) { Fail "cross-source $Context $Field mismatch: matrix=$Actual raw=$Expected" }
}
function Assert-NumericRange([double]$Value, [double]$Minimum, [double]$Maximum, [string]$Field, [string]$Context) {
    $tolerance = [math]::Max(0.001, ([math]::Max([math]::Abs($Minimum), [math]::Abs($Maximum)) * 0.000001))
    if ($Value -lt ($Minimum - $tolerance) -or $Value -gt ($Maximum + $tolerance)) { Fail "cross-source $Context $Field is outside raw range: matrix=$Value raw=$Minimum..$Maximum" }
}
function Validate-CrossSource($Rows, $RawModels) {
    foreach ($row in $Rows) {
        if ($row.test -eq 'stress') {
            $stressModels = @($RawModels.stress.Keys | ForEach-Object { $RawModels.stress[$_] })
            if ($stressModels.Count -eq 0) { continue }
            if ([string]$row.resultado -eq 'NO_EJECUTADA') { Fail 'cross-source stress row is NO_EJECUTADA but raw stress metrics exist' }
            $minVu = (@($stressModels | ForEach-Object { $_.vu_min } | Measure-Object -Minimum).Minimum)
            $maxVu = (@($stressModels | ForEach-Object { $_.vu_max } | Measure-Object -Maximum).Maximum)
            Assert-NumericMatch (Number $row.carga_vu_min 'carga_vu_min' 'matrix stress row') $minVu 'carga_vu_min' 'stress'
            Assert-NumericMatch (Number $row.carga_vu_max 'carga_vu_max' 'matrix stress row') $maxVu 'carga_vu_max' 'stress'
            foreach ($field in @('p95_ms','error_pct','capacidad_rps')) {
                $rawValues = @($stressModels | ForEach-Object { if ($field -eq 'p95_ms') { $_.p95 } elseif ($field -eq 'error_pct') { $_.error_pct } else { $_.rps } })
                $minimum = (@($rawValues | Measure-Object -Minimum).Minimum)
                $maximum = (@($rawValues | Measure-Object -Maximum).Maximum)
                Assert-NumericRange (Number $row.$field $field 'matrix stress row') $minimum $maximum $field 'stress'
            }
            $rawOutcome = Get-WorstResult (@($stressModels | ForEach-Object { [pscustomobject]@{ resultado=$_.outcome } }))
            if ([string]$row.resultado -cne $rawOutcome) { Fail "cross-source stress resultado mismatch: matrix=$($row.resultado) raw=$rawOutcome" }
            continue
        }
        $profile = $RawModels.profiles[[string]$row.test]
        if ($null -eq $profile) { continue }
        if ([string]$row.resultado -eq 'NO_EJECUTADA') { Fail "cross-source $($row.test) row is NO_EJECUTADA but raw metrics exist" }
        Assert-NumericMatch (Number $row.carga_vu_min 'carga_vu_min' "matrix $($row.test) row") $profile.vu_min 'carga_vu_min' $row.test
        Assert-NumericMatch (Number $row.carga_vu_max 'carga_vu_max' "matrix $($row.test) row") $profile.vu_max 'carga_vu_max' $row.test
        Assert-NumericMatch (Number $row.p95_ms 'p95_ms' "matrix $($row.test) row") $profile.p95 'p95_ms' $row.test
        Assert-NumericMatch (Number $row.error_pct 'error_pct' "matrix $($row.test) row") $profile.error_pct 'error_pct' $row.test
        Assert-NumericMatch (Number $row.capacidad_rps 'capacidad_rps' "matrix $($row.test) row") $profile.rps 'capacidad_rps' "$($row.test) duration/RPS"
        if ([string]$row.resultado -cne $profile.outcome) { Fail "cross-source $($row.test) resultado mismatch: matrix=$($row.resultado) raw=$($profile.outcome)" }
    }
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
    $resultText = if ($p.result) { Escape-Md $p.result } else { $p.outcome }
    return "**Configuración:** $($p.vu_min)→$($p.vu_max) VUs  `n**p95:** $(Value-Or-NA $p.p95) ms  `n**Error:** $(Value-Or-NA $p.error_pct)%  `n**RPS:** $(Value-Or-NA $p.rps)  `n**Resultado:** $resultText"
}
function Render-Stress($Model) {
    if ($Model.stress.Count -eq 0) { return '**Resultado:** NO_EJECUTADA; no hay escalones stress_<VU> disponibles.' }
    $lines = @('| VU | p50 ms | p90 ms | p95 ms | max ms | error % | RPS |','|---:|---:|---:|---:|---:|---:|---:|')
    foreach ($vu in ($Model.stress.Keys | Sort-Object)) { $x=$Model.stress[$vu]; $lines += "| $vu | $(Value-Or-NA $x.values.p50) | $(Value-Or-NA $x.values.p90) | $(Value-Or-NA $x.values.p95) | $(Value-Or-NA $x.values.max) | $(Value-Or-NA $x.values.error_pct) | $(Value-Or-NA ($x.rps)) |" }
    $degraded = @($Model.stress.Keys | Sort-Object | Where-Object { $x=$Model.stress[$_]; $x.values.p95 -ge 3000 -or $x.values.error_pct -ge 10 })
    $first = if ($degraded.Count) { "$($degraded[0]) VU" } else { 'No observado en los escalones disponibles' }
    $outcome = Get-WorstResult (@($Model.stress.Keys | ForEach-Object { [pscustomobject]@{ resultado=$Model.stress[$_].outcome } }))
    return ($lines -join "`n") + "`n`n**Resultado:** $outcome`n`n**Primer punto de degradación:** $first (p95 ≥ 3000 ms o error ≥ 10%)."
}
function Render-Spike($Model) {
    $p = $Model.profiles['spike']
    if ($null -eq $p) { return '**Resultado:** NO_EJECUTADA; no hay datos spike.' }
    $spikeParts=$p.spike_parts
    $resultText = if ($p.result) { Escape-Md $p.result } else { $p.outcome }
    return "**Baseline:** $($spikeParts.baseline.vus) VU, p95 $(Value-Or-NA $spikeParts.baseline.p95_ms) ms, error $(Value-Or-NA $spikeParts.baseline.error_pct)%, RPS $(Value-Or-NA $spikeParts.baseline.rps)`n`n**Peak:** $($spikeParts.peak.vus) VU, p95 $(Value-Or-NA $spikeParts.peak.p95_ms) ms, error $(Value-Or-NA $spikeParts.peak.error_pct)%, RPS $(Value-Or-NA $spikeParts.peak.rps)`n`n**Recovery:** $($spikeParts.recovery.vus) VU, p95 $(Value-Or-NA $spikeParts.recovery.p95_ms) ms, error $(Value-Or-NA $spikeParts.recovery.error_pct)%, RPS $(Value-Or-NA $spikeParts.recovery.rps), $($spikeParts.recovery_seconds) s.`n`n**Resultado:** $resultText"
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

if ([string]::IsNullOrWhiteSpace($TemplatePath)) { $TemplatePath = Join-Path -Path $PSScriptRoot -ChildPath '..\templates\endpoint-report.md' }
if (-not (Test-Path -LiteralPath $TemplatePath -PathType Leaf)) { Fail "template file not found: $TemplatePath" }
$Thresholds = Get-Thresholds (Join-Path $PSScriptRoot '..\config\thresholds.json')
$safeOutput = Assert-SafeOutput $OutputDirectory
$entry = Get-ManifestEntry $ManifestPath $EndpointId
$rows = Read-Matrix $MatrixPath $entry
$rawModels = Read-Models $entry
if ($rawModels.stress.Count -eq 0) { Fail 'stress report requires at least one stress_<VU> raw profile' }
$stressMatrixRow = @($rows | Where-Object test -eq 'stress')[0]
$stressMaxVu = [int]$stressMatrixRow.carga_vu_max
if (-not $rawModels.stress.ContainsKey($stressMaxVu)) { Fail "stress raw profiles are missing the matrix maximum VU: $stressMaxVu" }
$model = [pscustomobject]@{ entry=$entry; profiles=$rawModels.profiles; stress=$rawModels.stress; rows=$rows }
Validate-CrossSource $rows $rawModels
$summary = "- **Score endpoint:** N/D (no calculado hasta Task 10)`n- **Resultado:** $(Get-WorstResult $rows)`n- **Carga máxima:** $((@($rows | ForEach-Object {[int]$_.carga_vu_max} | Measure-Object -Maximum).Maximum)) VU`n- **Capacidad máxima:** $((@($rows | ForEach-Object {[double]$_.capacidad_rps} | Measure-Object -Maximum).Maximum)) RPS"
$template = Read-Utf8NoBom $TemplatePath
foreach ($token in @('{{ENDPOINT}}','{{OBJECTIVE}}','{{SUMMARY}}','{{SMOKE}}','{{LOAD}}','{{STRESS}}','{{SPIKE}}','{{MATRIX}}','{{CONCLUSION}}')) { if (-not $template.Contains($token)) { Fail "template missing token: $token" } }
$markdown = $template.Replace('{{ENDPOINT}}',(Escape-Md $entry.endpoint)).Replace('{{OBJECTIVE}}',(Escape-Md $entry.objective)).Replace('{{SUMMARY}}',$summary).Replace('{{SMOKE}}',(Report-Text $model 'smoke')).Replace('{{LOAD}}',(Report-Text $model 'load')).Replace('{{STRESS}}',(Render-Stress $model)).Replace('{{SPIKE}}',(Render-Spike $model)).Replace('{{MATRIX}}',(Render-Matrix $rows)).Replace('{{CONCLUSION}}',(Render-Conclusion $model $rows))
$html = Render-Html $model $rows
Assert-NoSecrets $markdown; Assert-NoSecrets $html
New-Item -ItemType Directory -Force -Path $safeOutput | Out-Null
$markdownPath=Join-Path $safeOutput 'endpoint-report.md'; $htmlPath=Join-Path $safeOutput 'endpoint-report.html'
Write-Utf8NoBom $markdownPath $markdown
Write-Utf8NoBom $htmlPath $html
Write-Output "Generated endpoint report: $markdownPath and $htmlPath"

[CmdletBinding()]
param(
    [string]$PlanPath = (Join-Path $PSScriptRoot '..\config\coverage-plan.json'),
    [string]$PerformanceRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$RunId = '',
    [string]$PreflightScript = (Join-Path $PSScriptRoot 'preflight.ps1'),
    [string]$EndpointRunnerScript = (Join-Path $PSScriptRoot 'run-endpoint.ps1'),
    [string]$LockPath = '',
    [int]$WarmupSeconds = 0,
    [int]$CooldownSeconds = 0,
    [switch]$WhatIf,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$performanceRoot = [IO.Path]::GetFullPath($PerformanceRoot)
if (-not $LockPath) { $LockPath = Join-Path $performanceRoot 'results\.run-lock' }
$lockPath = [IO.Path]::GetFullPath($LockPath)
$runId = if ($RunId) { $RunId } else { [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH-mm-ssZ') }
$isWhatIf = [bool]$WhatIf
$runRoot = Join-Path $performanceRoot 'results\runs'
$runDirectory = Join-Path $runRoot $runId
$metadataPath = Join-Path $runDirectory 'run.json'
$recordsPath = Join-Path $runDirectory 'results.json'
$logPath = Join-Path $runDirectory 'queue.log'
$lockHandle = $null
$records = [System.Collections.Generic.List[object]]::new()
$startedAt = [DateTime]::UtcNow.ToString('o')

function Write-JsonFile([string]$Path, $Value) {
    $Value | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $Path -Encoding utf8NoBOM
}

function Add-Record($Record) {
    $records.Add([pscustomobject]$Record)
    Write-JsonFile $recordsPath @($records)
}

function Read-Plan([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Coverage plan not found: $Path" }
    $value = Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json
    $items = if ($value -is [array]) { $value } elseif ($value.endpoints) { $value.endpoints } elseif ($value.plan) { $value.plan } elseif ($value.scope) { $value.scope } else { throw 'Coverage plan must contain endpoints, plan, or scope.' }
    $items | ForEach-Object {
        if (-not $_.id) { throw 'Every coverage-plan entry requires an id.' }
        $_
    } | Sort-Object @{ Expression = { if ($null -eq $_.order) { [int]::MaxValue } else { [int]$_.order } } }, @{ Expression = { [string]$_.id } }
}

function Invoke-FixtureOrRunner([string]$Script, [string]$EndpointId, [string]$Profile) {
    if (-not (Test-Path -LiteralPath $Script -PathType Leaf)) {
        return 127
    }
    & pwsh -NoProfile -File $Script -EndpointId $EndpointId -Profile $Profile -RunDirectory $runDirectory
    return [int]$LASTEXITCODE
}

function Resolve-EntryScript($Endpoint, [string]$Fallback) {
    $candidate = if ($Endpoint.script) { [string]$Endpoint.script } elseif ($Endpoint.runner) { [string]$Endpoint.runner } else { $Fallback }
    if ([IO.Path]::IsPathRooted($candidate)) { return [IO.Path]::GetFullPath($candidate) }
    $planDirectory = Split-Path -Parent ([IO.Path]::GetFullPath($PlanPath))
    $fromPlan = Join-Path $planDirectory $candidate
    if (Test-Path -LiteralPath $fromPlan -PathType Leaf) { return [IO.Path]::GetFullPath($fromPlan) }
    return [IO.Path]::GetFullPath((Join-Path $performanceRoot $candidate))
}

function Add-PlannedRecord([string]$EndpointId, [string]$Profile, [string]$Result, [int]$ExitCode, [string]$Reason) {
    Add-Record @{ endpoint_id=$EndpointId; profile=$Profile; run_id=$runId; started_at=$startedAt; finished_at=[DateTime]::UtcNow.ToString('o'); exit_code=$ExitCode; result=$Result; reason=$Reason; result_path=(Join-Path $runDirectory "$EndpointId-$Profile.json") }
}

New-Item -ItemType Directory -Force -Path $runDirectory | Out-Null
$runMetadata = [ordered]@{ run_id=$runId; started_at=$startedAt; finished_at=$null; status='RUNNING'; plan_path=[IO.Path]::GetFullPath($PlanPath); what_if=$isWhatIf; dry_run=[bool]$DryRun }
Write-JsonFile $metadataPath $runMetadata
Write-JsonFile $recordsPath @()

try {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $lockPath) | Out-Null
    try {
        $lockHandle = [IO.File]::Open($lockPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    } catch [IO.IOException] {
        throw "Another performance runner is already active (lock: $lockPath)."
    }
    $lockPayload = @{ run_id=$runId; pid=$PID; started_at=$startedAt } | ConvertTo-Json -Compress
    $lockBytes = [Text.Encoding]::UTF8.GetBytes($lockPayload)
    $lockHandle.Write($lockBytes, 0, $lockBytes.Length)
    $lockHandle.Flush()

    $plan = @(Read-Plan $PlanPath)
    $customScripts = $PSBoundParameters.ContainsKey('PreflightScript') -or $PSBoundParameters.ContainsKey('EndpointRunnerScript')
    $invokeCommands = (-not $isWhatIf -and -not $DryRun) -or ($customScripts -and $isWhatIf -and -not $DryRun)
    $preflightOk = @{}
    foreach ($endpoint in $plan) {
        $endpointId = [string]$endpoint.id
        $exitCode = if ($invokeCommands) { Invoke-FixtureOrRunner $PreflightScript $endpointId 'preflight' } else { 0 }
        $preflightOk[$endpointId] = ($exitCode -eq 0)
        Add-Record @{ endpoint_id=$endpointId; profile='preflight'; run_id=$runId; started_at=$startedAt; finished_at=[DateTime]::UtcNow.ToString('o'); exit_code=$exitCode; result=if ($exitCode -eq 0) { 'APROBADA' } else { 'NO_EJECUTADA' }; result_path=(Join-Path $runDirectory "$endpointId-preflight.json") }
    }

    foreach ($profile in @('smoke','load','stress','spike')) {
        foreach ($endpoint in $plan) {
            $endpointId = [string]$endpoint.id
            if (-not $preflightOk[$endpointId]) {
                Add-PlannedRecord $endpointId $profile 'NO_EJECUTADA' 107 'preflight unavailable'
                continue
            }
            $smoke = @($records | Where-Object { $_.endpoint_id -eq $endpointId -and $_.profile -eq 'smoke' }) | Select-Object -Last 1
            if ($profile -ne 'smoke' -and ($null -eq $smoke -or $smoke.exit_code -ne 0 -or $smoke.result -eq 'NO_EJECUTADA')) {
                Add-PlannedRecord $endpointId $profile 'NO_EJECUTADA' 107 'smoke unavailable or failed'
                continue
            }
            if ($WarmupSeconds -gt 0) { Start-Sleep -Seconds $WarmupSeconds }
            $profileStarted = [DateTime]::UtcNow.ToString('o')
            $endpointScript = Resolve-EntryScript $endpoint $EndpointRunnerScript
            $exitCode = if ($invokeCommands) { Invoke-FixtureOrRunner $endpointScript $endpointId $profile } else { 0 }
            $profileFinished = [DateTime]::UtcNow.ToString('o')
            $result = if ($isWhatIf -or $DryRun) { if ($exitCode -eq 0) { 'PLANIFICADA' } else { 'FALLIDA' } } elseif ($exitCode -eq 0) { 'EJECUTADA' } else { 'FALLIDA' }
            $resultFile = Join-Path $runDirectory "$endpointId-$profile.json"
            Write-JsonFile $resultFile @{ endpoint_id=$endpointId; profile=$profile; run_id=$runId; started_at=$profileStarted; finished_at=$profileFinished; exit_code=$exitCode; result=$result }
            Add-Record @{ endpoint_id=$endpointId; profile=$profile; run_id=$runId; started_at=$profileStarted; finished_at=$profileFinished; exit_code=$exitCode; result=$result; result_path=$resultFile }
            if ($CooldownSeconds -gt 0) { Start-Sleep -Seconds $CooldownSeconds }
        }
    }
    $runMetadata.status = 'COMPLETED'
}
catch {
    $runMetadata.status = 'FAILED'
    $runMetadata.error = $_.Exception.Message
    throw
}
finally {
    $runMetadata.finished_at = [DateTime]::UtcNow.ToString('o')
    Write-JsonFile $metadataPath $runMetadata
    if ($lockHandle) { $lockHandle.Dispose(); Remove-Item -LiteralPath $lockPath -Force -ErrorAction SilentlyContinue }
}

Write-Output ("Run {0} {1}: {2}" -f $runId, $runMetadata.status, $runDirectory)

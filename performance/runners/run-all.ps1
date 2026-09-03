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

$args = @{
    PlanPath=$PlanPath; PerformanceRoot=$PerformanceRoot; PreflightScript=$PreflightScript; EndpointRunnerScript=$EndpointRunnerScript; WarmupSeconds=$WarmupSeconds; CooldownSeconds=$CooldownSeconds
}
if ($RunId) { $args.RunId = $RunId }
if ($LockPath) { $args.LockPath = $LockPath }
if ($WhatIf) { $args.WhatIf = $true }
if ($DryRun) { $args.DryRun = $true }
& (Join-Path $PSScriptRoot 'run-coverage80.ps1') @args
exit $LASTEXITCODE

[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Leaf })]
    [string] $LedgerPath,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('\{id\}')]
    [string] $DeleteUriTemplate,

    [Parameter(Mandatory = $true)]
    [switch] $ConfirmCleanup
)

if (-not $ConfirmCleanup) {
    throw 'Cleanup is disabled unless the explicit -ConfirmCleanup switch is supplied.'
}

$records = @(
    Get-Content -LiteralPath $LedgerPath |
        Where-Object { $_.Trim() } |
        ForEach-Object { $_ | ConvertFrom-Json }
)
if ($records.Count -eq 0) { exit 0 }

$bearerToken = [Environment]::GetEnvironmentVariable('FLETWAY_CLEANUP_BEARER_TOKEN')
if ($bearerToken -and $DeleteUriTemplate -notmatch '^https://') {
    throw 'HTTPS is required when FLETWAY_CLEANUP_BEARER_TOKEN is set.'
}

foreach ($record in $records) {
    foreach ($field in @('run_id', 'agent', 'resource_type', 'created_by_test', 'created_at', 'id')) {
        if ($null -eq $record.PSObject.Properties[$field]) { throw "Ledger record is missing required field: $field" }
    }
    if ($record.run_id -isnot [string] -or [string]::IsNullOrWhiteSpace($record.run_id)) { throw 'Ledger record has an invalid run_id' }
    if ($record.agent -isnot [string] -or [string]::IsNullOrWhiteSpace($record.agent)) { throw 'Ledger record has an invalid agent' }
    if ($record.resource_type -isnot [string] -or [string]::IsNullOrWhiteSpace($record.resource_type)) { throw 'Ledger record has an invalid resource_type' }
    if ($record.created_by_test -isnot [string] -or [string]::IsNullOrWhiteSpace($record.created_by_test)) { throw 'Ledger record has an invalid created_by_test' }
    $createdAt = [string]$record.created_at
    if ([string]::IsNullOrWhiteSpace($createdAt)) { throw 'Ledger record has an invalid created_at' }
    try { [DateTimeOffset]::Parse($createdAt) | Out-Null } catch { throw 'Ledger record has an invalid created_at' }
    if ($record.id -isnot [int] -and $record.id -isnot [long] -and $record.id -isnot [decimal]) {
        throw "Ledger record has a non-numeric ID: $($record.id)"
    }
    $id = [long]$record.id
    if ($id -le 0 -or $id -ne [decimal]$record.id) { throw "Ledger record has an invalid ID: $($record.id)" }
    $uri = $DeleteUriTemplate.Replace('{id}', [uri]::EscapeDataString([string]$id))
    if ($PSCmdlet.ShouldProcess($uri, "DELETE ledger resource ID $id")) {
        $headers = @{}
        if ($bearerToken) { $headers.Authorization = "Bearer $bearerToken" }
        Invoke-RestMethod -Method Delete -Uri $uri -Headers $headers
    }
}

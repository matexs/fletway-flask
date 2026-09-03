[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [Parameter(Mandatory = $true)]
    [ValidateScript({ Test-Path -LiteralPath $_ -PathType Leaf })]
    [string] $LedgerPath,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('\{id\}')]
    [string] $DeleteUriTemplate,

    [Parameter(Mandatory = $true)]
    [switch] $ConfirmCleanup,

    [string] $BearerToken
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

foreach ($record in $records) {
    if ($record.id -isnot [int] -and $record.id -isnot [long] -and $record.id -isnot [decimal]) {
        throw "Ledger record has a non-numeric ID: $($record.id)"
    }
    $id = [long]$record.id
    if ($id -le 0 -or $id -ne [decimal]$record.id) { throw "Ledger record has an invalid ID: $($record.id)" }
    $uri = $DeleteUriTemplate.Replace('{id}', [uri]::EscapeDataString([string]$id))
    if ($PSCmdlet.ShouldProcess($uri, "DELETE ledger resource ID $id")) {
        $headers = @{}
        if ($BearerToken) { $headers.Authorization = "Bearer $BearerToken" }
        Invoke-RestMethod -Method Delete -Uri $uri -Headers $headers
    }
}

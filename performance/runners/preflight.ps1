[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$EndpointId,
    [Parameter(Mandatory = $true)][string]$ManifestPath,
    [Parameter(Mandatory = $true)][string]$OutputPath
)

$ErrorActionPreference = 'Stop'
$manifest = Get-Content -Raw -LiteralPath $ManifestPath | ConvertFrom-Json
$endpoint = @($manifest.endpoints | Where-Object id -eq $EndpointId)[0]
if ($null -eq $endpoint) { throw "Unknown endpoint: $EndpointId" }
$baseUrl = ([string]$env:BASE_URL).TrimEnd('/')
$supabaseUrl = ([string]$env:SUPABASE_URL).TrimEnd('/')
if (-not $baseUrl -or -not $supabaseUrl) { throw 'BASE_URL and SUPABASE_URL are required for preflight' }

function Get-Token([string]$email, [string]$password, [string]$role) {
    $body = @{ email = $email; password = $password } | ConvertTo-Json -Compress
    $response = Invoke-RestMethod -Method Post -Uri "$supabaseUrl/auth/v1/token?grant_type=password" -Headers @{ apikey = $env:SUPABASE_ANON_KEY; Authorization = "Bearer $($env:SUPABASE_ANON_KEY)" } -ContentType 'application/json' -Body $body -TimeoutSec 60
    if (-not $response.access_token) { throw "No token returned for $role" }
    return $response.access_token
}

$health = Invoke-WebRequest -UseBasicParsing -Uri "$baseUrl/" -Method Get -TimeoutSec 60
if ($health.StatusCode -ne 200) { throw "Health preflight returned HTTP $($health.StatusCode)" }
$token = if ($endpoint.auth_role -eq 'driver') { Get-Token $env:DRIVER_EMAIL $env:DRIVER_PASSWORD 'driver' } else { Get-Token $env:CLIENT_EMAIL $env:CLIENT_PASSWORD 'client' }
$targetPath = [string]$endpoint.path
if ($targetPath -notmatch '<[^>]+>') {
    $target = Invoke-WebRequest -UseBasicParsing -Uri "$baseUrl$targetPath" -Headers @{ Authorization = "Bearer $token"; Accept = 'application/json' } -Method Get -TimeoutSec 60
    if ($target.StatusCode -ne 200) { throw "Endpoint preflight returned HTTP $($target.StatusCode)" }
}

$record = [ordered]@{ endpoint_id = $EndpointId; result = 'APROBADA'; checked_at = [DateTime]::UtcNow.ToString('o') }
$parent = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Force -Path $parent | Out-Null
$record | ConvertTo-Json | Set-Content -LiteralPath $OutputPath -Encoding utf8NoBOM

$ErrorActionPreference = 'Stop'

$inspection = k6 inspect performance\k6\scripts\fletway-api.js | ConvertFrom-Json
$thresholdNames = @($inspection.thresholds.PSObject.Properties.Name)
$endpointKeys = Select-String -Path performance\k6\config\performance.config.js -Pattern "key: '([^']+)'" -AllMatches |
    ForEach-Object { $_.Matches } |
    ForEach-Object { $_.Groups[1].Value }

$missing = foreach ($endpointKey in $endpointKeys) {
    foreach ($kind in @('duration_ms', 'success_rate', 'error_rate', 'timeout_rate')) {
        $name = "fletway_smoke_${endpointKey}_${kind}"
        if ($thresholdNames -notcontains $name) { $name }
    }
}

if ($missing) {
    throw "Missing endpoint thresholds: $($missing -join ', ')"
}

Write-Output "Verified $($endpointKeys.Count * 4) endpoint thresholds for smoke."

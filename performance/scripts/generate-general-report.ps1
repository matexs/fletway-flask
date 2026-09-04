[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$CampaignDirectory,
    [Parameter(Mandatory = $true)][string]$ManifestPath
)

$ErrorActionPreference = 'Stop'
$rows = @(Get-Content -Raw -LiteralPath (Join-Path $CampaignDirectory 'matrix_general.json') | ConvertFrom-Json)
$reports = Join-Path $CampaignDirectory 'reports'; New-Item -ItemType Directory -Force -Path $reports | Out-Null
$summary = [ordered]@{ run_id = Split-Path $CampaignDirectory -Leaf; total_rows = $rows.Count; executed_rows = @($rows | Where-Object resultado -ne 'NO_EJECUTADA').Count; outcomes = @{} }
foreach ($outcome in @('APROBADA','ADVERTENCIA','FALLIDA','NO_EJECUTADA')) { $summary.outcomes[$outcome] = @($rows | Where-Object resultado -eq $outcome).Count }
$summary | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $CampaignDirectory 'general-report.json') -Encoding utf8NoBom
$table = @('| endpoint | test | p95_ms | error_pct | capacidad_rps | resultado |','|---|---|---:|---:|---:|---|')
foreach ($row in $rows) { $table += "| $($row.endpoint) | $($row.test) | $($row.p95_ms) | $($row.error_pct) | $($row.capacidad_rps) | $($row.resultado) |" }
$markdown = "# Fletway k6 Performance Campaign`n`n- **Run:** $($summary.run_id)`n- **Rows:** $($summary.total_rows)`n- **Executed:** $($summary.executed_rows)`n- **APROBADA:** $($summary.outcomes.APROBADA)`n- **ADVERTENCIA:** $($summary.outcomes.ADVERTENCIA)`n- **FALLIDA:** $($summary.outcomes.FALLIDA)`n- **NO_EJECUTADA:** $($summary.outcomes.NO_EJECUTADA)`n`n## Matrix`n`n$($table -join "`n")`n"
$markdown | Set-Content -LiteralPath (Join-Path $reports 'general-report.md') -Encoding utf8NoBom
$htmlRows = ($rows | ForEach-Object { "<tr><td>$($_.endpoint)</td><td>$($_.test)</td><td>$($_.p95_ms)</td><td>$($_.error_pct)</td><td>$($_.capacidad_rps)</td><td>$($_.resultado)</td></tr>" }) -join ''
"<!doctype html><html><head><meta charset='utf-8'><title>Fletway k6 campaign</title></head><body><h1>Fletway k6 Performance Campaign</h1><p>Run: $($summary.run_id)</p><table border='1'><tr><th>endpoint</th><th>test</th><th>p95_ms</th><th>error_pct</th><th>RPS</th><th>resultado</th></tr>$htmlRows</table></body></html>" | Set-Content -LiteralPath (Join-Path $reports 'general-report.html') -Encoding utf8NoBom
foreach ($endpoint in @($rows | Group-Object endpoint)) {
    $safeName = $endpoint.Name -replace '[^A-Za-z0-9_-]', '_'; $directory = Join-Path $reports $safeName; New-Item -ItemType Directory -Force -Path $directory | Out-Null
    $endpointTable = @("# $($endpoint.Name)",'', '| test | p95_ms | error_pct | capacidad_rps | resultado |','|---|---:|---:|---:|---|')
    foreach ($row in $endpoint.Group) { $endpointTable += "| $($row.test) | $($row.p95_ms) | $($row.error_pct) | $($row.capacidad_rps) | $($row.resultado) |" }
    $endpointTable -join "`n" | Set-Content -LiteralPath (Join-Path $directory 'endpoint-report.md') -Encoding utf8NoBom
    "<!doctype html><html><body><h1>$($endpoint.Name)</h1><pre>$([System.Net.WebUtility]::HtmlEncode(($endpointTable -join "`n")))</pre></body></html>" | Set-Content -LiteralPath (Join-Path $directory 'endpoint-report.html') -Encoding utf8NoBom
}
Write-Output "Generated reports in $reports"

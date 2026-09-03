Describe 'cleanup-created-data' {
    It 'does not accept a bearer token parameter and requires HTTPS for the environment token' {
        $script = Join-Path $PSScriptRoot '..\runners\cleanup-created-data.ps1'
        (Get-Content -LiteralPath $script -Raw) -cmatch '\$BearerToken\b' | Should Be $false
        $env:FLETWAY_CLEANUP_BEARER_TOKEN = 'test-token'
        $tempDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ('fletway-cleanup-test-' + [guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $tempDirectory | Out-Null
        try {
            $ledger = Join-Path $tempDirectory 'solicitudes.jsonl'
            Set-Content -LiteralPath $ledger -Value '{"run_id":"run-1","agent":"solicitudes","resource_type":"solicitud","id":123,"created_by_test":"test","created_at":"2026-09-03T15:30:00Z"}'
            $failed = $false
            try { & $script -LedgerPath $ledger -DeleteUriTemplate 'http://example.invalid/api/solicitudes/{id}' -WhatIf -ConfirmCleanup 2>&1 | Out-Null } catch { $failed = $_.Exception.Message -match 'HTTPS' }
            $failed | Should Be $true
        } finally {
            Remove-Item Env:FLETWAY_CLEANUP_BEARER_TOKEN -ErrorAction SilentlyContinue
            Remove-Item -LiteralPath $tempDirectory -Recurse -Force
        }
    }

    It 'previews only the ledger ID and preserves the ledger with WhatIf' {
        $ErrorActionPreference = 'Stop'
        $script = Join-Path $PSScriptRoot '..\runners\cleanup-created-data.ps1'
        $tempDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ('fletway-cleanup-test-' + [guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $tempDirectory | Out-Null
        try {
            $ledger = Join-Path $tempDirectory 'solicitudes.jsonl'
            Set-Content -LiteralPath $ledger -Value '{"run_id":"run-1","agent":"solicitudes","resource_type":"solicitud","id":123,"created_by_test":"test","created_at":"2026-09-03T15:30:00Z"}'
            Add-Content -LiteralPath $ledger -Value '{"run_id":"run-1","agent":"solicitudes","resource_type":"solicitud","id":124,"created_by_test":"test","created_at":"2026-09-03T15:30:01Z"}'
            & $script -LedgerPath $ledger -DeleteUriTemplate 'https://example.invalid/api/solicitudes/{id}' -WhatIf -ConfirmCleanup | Out-Null
            Test-Path -LiteralPath $ledger | Should Be $true
        } finally {
            Remove-Item -LiteralPath $tempDirectory -Recurse -Force
        }
    }

    It 'refuses to run without explicit confirmation' {
        $ErrorActionPreference = 'Stop'
        $script = Join-Path $PSScriptRoot '..\runners\cleanup-created-data.ps1'
        $tempDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ('fletway-cleanup-test-' + [guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $tempDirectory | Out-Null
        try {
            $ledger = Join-Path $tempDirectory 'solicitudes.jsonl'
            Set-Content -LiteralPath $ledger -Value '{"id":123}'
            $failed = $false
            try {
                & $script -LedgerPath $ledger -DeleteUriTemplate 'https://example.invalid/api/solicitudes/{id}' 2>&1 | Out-Null
            } catch {
                $failed = $_.Exception.Message -match 'ConfirmCleanup'
            }
            $failed | Should Be $true
        } finally {
            Remove-Item -LiteralPath $tempDirectory -Recurse -Force
        }
    }

    It 'rejects a positive ID without the required resource record envelope' {
        $ErrorActionPreference = 'Stop'
        $script = Join-Path $PSScriptRoot '..\runners\cleanup-created-data.ps1'
        $tempDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ('fletway-cleanup-test-' + [guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $tempDirectory | Out-Null
        try {
            $ledger = Join-Path $tempDirectory 'solicitudes.jsonl'
            Set-Content -LiteralPath $ledger -Value '{"id":123}'
            $failed = $false
            try { & $script -LedgerPath $ledger -DeleteUriTemplate 'https://example.invalid/api/solicitudes/{id}' -ConfirmCleanup -WhatIf 2>&1 | Out-Null } catch { $failed = $_.Exception.Message -match 'run_id' }
            $failed | Should Be $true
        } finally {
            Remove-Item -LiteralPath $tempDirectory -Recurse -Force
        }
    }
}

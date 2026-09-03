# Task 4 report — canonical performance profiles

## Scope

Implemented only the canonical profile configuration and endpoint runner requested by Task 4.

- Updated `performance/config/profiles.js` while preserving existing exports and behavior for smoke, load, and standard stress IDs.
- Added canonical spike configuration with configurable baseline, spike, recovery, and cooldown stages.
- Added configurable extended P0 stress stages with the default 20/40/60/80/100 VU levels.
- Made every stress level a zero-offset, independently runnable scenario with explicit stage and VU metadata.
- Added `performance/runners/run-endpoint.ps1`, which forwards endpoint/profile/stage/VU metadata to k6, supports dry runs, exports raw summaries, and preserves the original k6 payload under `k6`.
- Raw runner output includes `endpoint_id`, `profile`, `stage`, `vu_min`, `vu_max`, and optional spike `recovery` metadata.

## Verification

- `node --experimental-default-type=module --test performance/tests/profiles.test.mjs performance/tests/run-endpoint.test.mjs` — 6 passed.
- `node --test performance/tests/resource-ledger.test.js` — 6 passed.
- `python -m unittest discover -s performance/tests -p 'test_*.py'` — 10 passed.
- `Invoke-Pester -Path performance/tests/cleanup-created-data.test.ps1` — 4 passed.
- PowerShell parser validation — no errors.
- `git diff --check` — clean.

No live load, stress, spike, or endpoint run was executed. The manifest, coverage plan, resource ledger, and aggregators were not modified.

## Concern

The endpoint runner and k6 script now enforce manifest endpoint selection. No live k6 execution was performed, so runtime connectivity/authentication remains unverified by design.

## Review fix round

Addressed all six review findings:

- Stress stages now require and map to one individual profile per invocation (`stress_20` or `stress_p0_40`), so k6 cannot launch the complete stress family from the endpoint runner.
- `ENDPOINT_ID` is validated against the manifest, validated again at k6 module initialization, and selects exactly one manifest endpoint without weighted fallback.
- Runner VU bounds derive from canonical smoke/load/stress values when omitted.
- Runner exposes baseline/spike controls; spike defaults are baseline 1 VU, spike 20 VU, recovery baseline VU, and 30 seconds, and recovery metadata is always recorded.
- Output paths are restricted to sanitized `.json` files under `performance/results`; existing files require `-Force`.

### Exact verification commands and outputs

`node --experimental-default-type=module --test performance/tests/profiles.test.mjs performance/tests/run-endpoint.test.mjs performance/tests/endpoint-selection.test.mjs`

```text
1..14
# tests 14
# pass 14
# fail 0
```

`node --test performance/tests/resource-ledger.test.js`

```text
1..6
# tests 6
# pass 6
# fail 0
```

`python -m unittest discover -s performance/tests -p 'test_*.py'`

```text
..........
----------------------------------------------------------------------
Ran 10 tests in 0.018s

OK
```

`Invoke-Pester -Path performance/tests/cleanup-created-data.test.ps1`

```text
Tests completed in 648ms
Passed: 4 Failed: 0 Skipped: 0 Pending: 0 Inconclusive: 0
```

PowerShell parser validation returned no errors, and `git diff --check` returned clean. No live k6 load was run.

## Follow-up review fix

Removed the duplicate top-level `selectedEndpoint` declaration from `fletway-api.js`. The canonical spike defaults are now baseline 3 VUs and spike 30 VUs; baseline, spike, recovery, and duration controls remain configurable, with recovery metadata retained.

### Exact follow-up verification commands and outputs

`node --experimental-default-type=module --test performance/tests/profiles.test.mjs performance/tests/run-endpoint.test.mjs performance/tests/endpoint-selection.test.mjs`

```text
1..15
# tests 15
# pass 15
# fail 0
```

`node --check performance/config/profiles.js; node --check performance/k6/lib/endpoint-selection.js; node --check performance/k6/config/performance.config.js; node --check performance/k6/scripts/fletway-api.js`

```text
exit=0
```

`k6 inspect performance/k6/scripts/fletway-api.js`

```text
scenarios.smoke.executor = ramping-vus
scenarios.smoke.stages = 10s/1, 20s/3, 10s/0
exit=0
```

`k6 inspect --env ENDPOINT_ID=health --env PROFILE=stress_20 performance/k6/scripts/fletway-api.js`

```text
"stress_20": {
  "executor": "constant-vus",
  "vus": 20,
  "duration": "30s"
}
exit=0
```

`node --test performance/tests/resource-ledger.test.js` → `1..6`, `# pass 6`, `# fail 0`.

`python -m unittest discover -s performance/tests -p 'test_*.py'` → `Ran 10 tests`, `OK`.

`Invoke-Pester -Path performance/tests/cleanup-created-data.test.ps1` → `Passed: 4 Failed: 0 Skipped: 0 Pending: 0 Inconclusive: 0`.

PowerShell parser validation and `git diff --check` both returned clean. No live k6 load was run.

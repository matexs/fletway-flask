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

The existing k6 script does not currently consume `ENDPOINT_ID` to filter its endpoint distribution. The new runner forwards that value and records it in raw metadata; endpoint filtering remains dependent on the k6 script being extended in a later scoped task.

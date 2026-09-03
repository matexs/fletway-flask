# Task 7 — Serialized execution queue report

## Scope

Implemented the performance execution queue in:

- `performance/runners/run-coverage80.ps1`
- `performance/runners/run-all.ps1`
- `performance/tests/run-queue.tests.ps1`

No matrix, scoring, endpoint, or k6 configuration modules were modified.

## Behavior implemented

- Validates the explicit/generated `run_id` and every endpoint id before using either value in a results path. Rooted paths, separators, `..`, spaces, and other unsafe characters are rejected; normal alphanumeric, underscore, and hyphen identifiers remain valid.
- Acquires a global `performance/results/.run-lock` using an atomic `CreateNew` file operation before creating any run directory or metadata. A second runner fails before execution and reports the lock path. The lock payload contains only `run_id`, an owner token, process id, and UTC start time.
- Uses `FileOptions.DeleteOnClose` for ownership-safe release: the OS removes the lock as part of disposing the owner’s still-held handle, and the runner never unconditionally deletes a path that could have been replaced by another run.
- Rejects an existing `performance/results/runs/<run_id>` after lock acquisition, preventing explicit/generated RunId collisions from overwriting metadata or results. The run records UTC `started_at`, `finished_at`, final status, plan path, and dry-run flags.
- Accepts `coverage-plan.json` in the common `endpoints`, `plan`, `scope`, or array shape. Entries are sorted deterministically by numeric `order` and then endpoint id.
- Executes phases in the required order: all preflights, smoke, load, stress, and spike.
- Resolves an endpoint-specific `script` or `runner` path when supplied; otherwise uses the runner default.
- Writes one result JSON file for every preflight, endpoint/profile attempt, and gated `NO_EJECUTADA` profile, then appends every attempt to `results.json`, including start/end timestamps, exit code, result, reason, and result path. Failed child processes do not discard prior or current metadata.
- Prevents load, stress, and spike execution for an endpoint whose preflight or smoke is unavailable/failed, while recording `NO_EJECUTADA` metadata with exit code `107`.
- Supports `-WhatIf` and `-DryRun`. Default dry-run/WhatIf execution plans work without invoking endpoint scripts; explicitly supplied fixture scripts may be used with `-WhatIf` for safe process-boundary tests. `-DryRun` never invokes executors.
- Warm-up and cooldown delays are configurable and default to zero for safe verification.
- Marks aggregate `run.json.status` as `FAILED` when any preflight or child profile returns a nonzero exit code, while preserving all records. A dry-run with no invoked child returns `COMPLETED` with `PLANIFICADA` records; fixture-driven WhatIf failures still produce `FAILED` so simulated failures are visible.
- Does not read or write credential values and does not print the target URL or secrets.

## Verification

Command executed:

```powershell
pwsh -NoProfile -File performance/tests/run-queue.tests.ps1
```

Result: `PASS run-queue.tests.ps1`

The focused test covers deterministic ordering, failed smoke exit-code/result preservation, aggressive-stage gating, lock contention/ownership, metadata timestamps, explicit RunId collision rejection, unsafe RunId/endpoint rejection, preflight and gated-result file existence, aggregate failure status, lock release, dry-run non-invocation, and `run-all.ps1` delegation.

No live smoke, load, stress, spike, mutation traffic, or k6 execution was performed.

## Risks and follow-up

- The current worktree does not yet contain `performance/config/coverage-plan.json`, `preflight.ps1`, or `run-endpoint.ps1`; those are produced by other plan tasks. The default runner therefore fails clearly until those contracts exist or explicit fixture paths are supplied.
- Result status values are orchestration states (`EJECUTADA`, `PLANIFICADA`, `FALLIDA`, `NO_EJECUTADA`); metric normalization into the canonical matrix remains Task 8.
- The lock is intentionally owned by the OS file handle. A manually abandoned lock created by a different process may remain visible and block subsequent runs if that process did not use the runner’s DeleteOnClose handle; operator cleanup should first verify the recorded process/run metadata.

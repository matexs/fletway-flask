# Task 7 — Serialized execution queue report

## Scope

Implemented the performance execution queue in:

- `performance/runners/run-coverage80.ps1`
- `performance/runners/run-all.ps1`
- `performance/tests/run-queue.tests.ps1`

No matrix, scoring, endpoint, or k6 configuration modules were modified.

## Behavior implemented

- Acquires a global `performance/results/.run-lock` using an atomic `CreateNew` file operation. A second runner fails before execution and reports the lock path. The lock payload contains only `run_id`, process id, and UTC start time.
- Creates `performance/results/runs/<run_id>/run.json` and records UTC `started_at`, `finished_at`, final status, plan path, and dry-run flags.
- Accepts `coverage-plan.json` in the common `endpoints`, `plan`, `scope`, or array shape. Entries are sorted deterministically by numeric `order` and then endpoint id.
- Executes phases in the required order: all preflights, smoke, load, stress, and spike.
- Resolves an endpoint-specific `script` or `runner` path when supplied; otherwise uses the runner default.
- Writes one result JSON file per endpoint/profile and appends every attempt to `results.json`, including start/end timestamps, exit code, result, reason, and result path. Failed child processes do not discard prior or current metadata.
- Prevents load, stress, and spike execution for an endpoint whose preflight or smoke is unavailable/failed, while recording `NO_EJECUTADA` metadata with exit code `107`.
- Supports `-WhatIf` and `-DryRun`. Default dry-run/WhatIf execution plans work without invoking endpoint scripts; explicitly supplied fixture scripts may be used with `-WhatIf` for safe process-boundary tests. `-DryRun` never invokes executors.
- Warm-up and cooldown delays are configurable and default to zero for safe verification.
- Does not read or write credential values and does not print the target URL or secrets.

## Verification

Command executed:

```powershell
pwsh -NoProfile -File performance/tests/run-queue.tests.ps1
```

Result: `PASS run-queue.tests.ps1`

The focused test covers deterministic ordering, failed smoke exit-code/result preservation, aggressive-stage gating, lock contention, metadata timestamps, lock release, and dry-run non-invocation.

No live smoke, load, stress, spike, mutation traffic, or k6 execution was performed.

## Risks and follow-up

- The current worktree does not yet contain `performance/config/coverage-plan.json`, `preflight.ps1`, or `run-endpoint.ps1`; those are produced by other plan tasks. The default runner therefore fails clearly until those contracts exist or explicit fixture paths are supplied.
- Result status values are orchestration states (`EJECUTADA`, `PLANIFICADA`, `FALLIDA`, `NO_EJECUTADA`); metric normalization into the canonical matrix remains Task 8.
- A manually abandoned lock remains visible and blocks subsequent runs. This is deliberate: automatic stale-lock deletion could terminate or overlap a legitimate shared-environment run. Operator cleanup should first verify the recorded process/run metadata.

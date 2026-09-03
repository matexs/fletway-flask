# Task 3 report

## Status

Implemented and committed the append-only per-run/module resource ledger and explicit ID-only cleanup flow.

## Files

- `performance/fixtures/resource-ledger.js`
  - Creates isolated `<ledger directory>/<run_id>/<agent>.jsonl` files.
  - Appends normalized records with `run_id`, `agent`, `created_at`, resource type, ID, and test name.
  - Rejects missing, non-integer, and non-positive IDs.
  - Merges agent JSONL files deterministically into an append-once `merged.jsonl` without modifying source ledgers.
- `performance/runners/cleanup-created-data.ps1`
  - Requires `-ConfirmCleanup` explicitly.
  - Reads JSONL records only from the supplied ledger file.
  - Validates positive numeric IDs and substitutes only those IDs into a required `{id}` URI template.
  - Supports `-WhatIf`; no live cleanup was executed.
- `performance/tests/resource-ledger.test.js`
- `performance/tests/cleanup-created-data.test.ps1`

## Tests and exact outputs

### Command

`node --test performance\\tests\\resource-ledger.test.js`

### Output

`1..3`

`# tests 3`

`# pass 3`

`# fail 0`

### Command

`Invoke-Pester -Path performance\\tests\\cleanup-created-data.test.ps1`

### Output

`Describing cleanup-created-data`

`What if: Performing the operation "DELETE ledger resource ID 123" on target "https://example.invalid/api/solicitudes/123".`

`What if: Performing the operation "DELETE ledger resource ID 124" on target "https://example.invalid/api/solicitudes/124".`

`[+] previews only the ledger ID and preserves the ledger with WhatIf`

`[+] refuses to run without explicit confirmation`

`Passed: 2 Failed: 0 Skipped: 0 Pending: 0 Inconclusive: 0`

### Command

`python -m unittest discover -s performance\\tests -p 'test_*.py'`

### Output

`Ran 10 tests in 0.020s`

`OK`

### Command

`git diff --check`

### Output

No output (success).

## Concerns

- Cleanup intentionally requires the caller to provide the endpoint URI template and bearer token; it does not infer or discover targets.
- Merge output uses deterministic agent-name ordering and refuses to overwrite an existing `merged.jsonl`; rerunning a merge requires a new run directory.
- No live load or live cleanup was run.

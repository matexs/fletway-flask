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

## Fix round

Addressed all five review findings:

1. Cleanup reads `FLETWAY_CLEANUP_BEARER_TOKEN` from the environment rather than accepting a token command-line parameter, and requires an HTTPS URI when that token is set.
2. Merge ordering uses explicit UTF-16 code-unit comparison. Concurrent appends by the same agent are append-only but their relative ordering is intentionally unspecified.
3. Run and agent path components are UTF-8 hex encoded, preventing distinct identifiers from colliding after sanitization.
4. Each module ledger has a write-once provenance sidecar; merge ignores unregistered JSONL files and validates metadata plus every record's envelope and run/agent consistency.
5. Cleanup validates run ID, agent, resource type, test name, ISO date, and positive integer ID before any DELETE operation.

### Fix-round tests and exact outputs

`node --test performance\\tests\\resource-ledger.test.js`

`1..6`

`# tests 6`

`# pass 6`

`# fail 0`

`Invoke-Pester -Path performance\\tests\\cleanup-created-data.test.ps1`

`Describing cleanup-created-data`

`[+] does not accept a bearer token parameter and requires HTTPS for the environment token`

`[+] previews only the ledger ID and preserves the ledger with WhatIf`

`[+] refuses to run without explicit confirmation`

`[+] rejects a positive ID without the required resource record envelope`

`Passed: 4 Failed: 0 Skipped: 0 Pending: 0 Inconclusive: 0`

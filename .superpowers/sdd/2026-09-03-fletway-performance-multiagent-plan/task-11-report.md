# Task 11 Report — General Performance Matrix

Implemented an offline PowerShell builder at `performance/scripts/build-general-matrix.ps1` and the canonical empty matrix at `performance/results/matrix/matrix_general.csv`.

The builder discovers endpoint `matrix.csv` artifacts recursively, excludes its output path, validates the exact Task 8/9 ten-column schema and row values, rejects unsafe endpoint/run identifiers, preserves distinct enclosing runs, and sorts deterministically by canonical result severity, canonical-manifest priority, endpoint, test, run, source, and line. Manifest priority is derived from canonical `method + path`; legacy `endpoint` is accepted only as an unambiguous compatibility alias. Empty input emits the canonical header and an explicit CLI message.

When a canonical manifest is supplied, every row must match its method/path and objective. Duplicate canonical method/path declarations, including the real `puede-calificar` declarations, are accepted: an exact objective selects the row contract; otherwise candidates resolve by priority then declaration order. The ambiguity policy is deterministic and documented here rather than inventing rows. Executed rows require finite, nonnegative numeric fields, `error_pct` in 0–100, and `carga_vu_min <= carga_vu_max`; p95, error, RPS, and both VU bounds are required. `NO_EJECUTADA` rows preserve the Task 8/9 all-blank numeric contract. Run identity is extracted only from `results/runs/<run_id>/...` directly below the configured results root; missing or ambiguous/colliding identities are rejected, while distinct run IDs remain valid.

Added focused fixtures for empty input, two endpoint matrices, distinct duplicate runs, malformed headers/rows, unsafe endpoints, equal-severity P0 ordering, canonical manifest reconciliation, the duplicate `puede-calificar` declaration, executed numeric blanks and invalid ranges, strict direct run-layout identity, and deterministic repeated output.

No HTTP requests, k6 execution, credentials, mutations, or generated secrets were used.

## Verification status

- `pwsh -NoProfile -File performance/tests/build-general-matrix.tests.ps1` — **PASS** (`PASS build-general-matrix.tests.ps1`).
- `pwsh -NoProfile -Command "[System.Management.Automation.Language.Parser]::ParseFile('performance/scripts/build-general-matrix.ps1',[ref]$null,[ref]$null) > $null"` — **PASS**.
- `pwsh -NoProfile -Command "[System.Management.Automation.Language.Parser]::ParseFile('performance/tests/build-general-matrix.tests.ps1',[ref]$null,[ref]$null) > $null"` — **PASS**.
- `git diff --check` — **PASS**.

The focused fix corrected manifest/run identity and semantic validation gaps identified in review. No production behavior outside Task 11 was changed.

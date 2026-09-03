# Task 9 — Automatic per-endpoint reports

## Outcome

Implemented a fixture-only PowerShell report generator at `performance/scripts/generate-endpoint-report.ps1` with the Markdown skeleton in `performance/templates/endpoint-report.md`.

The generator accepts the Task 8 canonical endpoint matrix, raw JSON summaries, the endpoint manifest, an endpoint ID, and an output directory. It builds one validated in-memory model and renders both `endpoint-report.md` and `endpoint-report.html` from that model. No k6 command, API request, or live traffic was used.

## Report contract

- Identifies the endpoint as method plus path and copies the manifest objective.
- Reports summary result, maximum observed VUs, and maximum observed RPS. Task 9 does not invent a score; it states that scoring belongs to Task 10.
- Includes Smoke and Load configuration, p95, error percentage, RPS, and result.
- Includes Stress rows for each `stress_<VU>` raw profile with p50, p90, p95, max, error percentage, and RPS.
- Marks the first observed stress degradation as the first VU whose p95 is at least 3000 ms or whose error rate is at least 10%; the statement is limited to observed escalones.
- Includes Spike baseline, peak, recovery, recovery seconds, and result.
- Includes all four canonical matrix rows with the exact Task 8 columns.
- Separates evidence (`Hecho`) from interpretation (`Hipótesis`) and explicitly declines to assign SQL, memory, CPU, or log causes without telemetry.

## Validation and safety

The generator rejects missing files, invalid JSON, missing endpoint/rows/profiles, malformed required metrics, duplicate raw profiles, incomplete stress detail for the matrix maximum VU, unsafe output paths, and secret-like content in generated output. It only emits selected manifest/matrix/metric fields; arbitrary raw JSON fields are not copied into reports.

The review hardening adds strict validation at the report-controller boundary:

- Duplicate `stress_<VU>` keys fail before map assignment; the raw key must also agree with integer `vu_min` and `vu_max`.
- Every stress row requires numeric `p(50)`, `p(90)`, `p(95)`, `max`, error `rate`, and `http_reqs.values.count`; RPS is derived only from that count and a positive measured duration.
- Smoke, Load, Stress, and Spike raw profiles require a positive `measured_duration_seconds`; missing duration can no longer silently produce zero RPS.
- Spike baseline, peak, and recovery each require numeric integer VUs, p95, error percentage, and RPS. Recovery also requires a numeric duration in seconds.
- The score field is present as `N/D (no calculado hasta Task 10)` in both formats; no score value is inferred by Task 9.
- Markdown and HTML consume the same conclusion model facts and hypothesis. Every HTML matrix cell, including `resultado`, is escaped before interpolation.

Absent Smoke/Load/Spike raw profiles are rendered as `NO_EJECUTADA`. Stress detail is required when the matrix claims a stress maximum, because the required per-VU table cannot be fabricated.

## Tests

Added `performance/tests/generate-endpoint-report.tests.ps1` with hand-built fixtures covering:

- Markdown and HTML shared content/section parity.
- Missing stress detail rejection.
- Duplicate stress profile rejection and stress VU/key mismatch rejection.
- Missing/non-numeric stress p50, p90, p95, max, error rate, count, and VU rejection.
- Missing measured duration rejection.
- Missing Smoke, Load, and Spike profile rendering as `NO_EJECUTADA`.
- Missing/non-numeric Spike baseline, peak, recovery fields and recovery duration rejection.
- First stress degradation at the first threshold-breaching VU.
- Spike baseline, peak, and recovery reporting.
- Complete four-row matrix inclusion.
- Explicit score `N/D` until Task 10.
- Shared model-derived Markdown/HTML conclusion facts and escaped HTML matrix values.
- Evidence/hypothesis wording and rejection of unsupported cause claims.
- Unsafe output path rejection.

TDD evidence:

1. The new test was run before the generator existed and failed because the script file was missing.
2. After implementation, it failed on the Task 8 metric shape; the parser was corrected to read request count from `http_reqs` and duration statistics from `http_req_duration`.
3. Review fixtures then failed on the missing score contract and VU mismatch, driving the strict validation/model-rendering fixes.
4. The final fixture test passed.

Verification commands and results:

```text
pwsh -NoProfile -File performance/tests/generate-endpoint-report.tests.ps1  PASS
pwsh -NoProfile -File performance/tests/aggregate-results.tests.ps1        PASS
pwsh -NoProfile -File performance/tests/run-queue.tests.ps1                PASS
git diff --check                                                           PASS
```

## Controller-branch validation and worktree status

The controller branch was checked with `git branch --show-current` and is `main`. The Task 9 fix is kept as one coherent commit, and after commit verification the tracked worktree is clean (`git diff --check` passes with no tracked diff). Pre-existing untracked files remain intentionally preserved and unstaged: `performance/env.performance`, `performance/endpoints/solicitudes/`, and `performance/2026-09-03-fletway-performance-multiagent-plan.md`. The real environment file was not read into or committed by this task.

## Risks and follow-up

- Task 10 scoring is not yet available, so the report intentionally labels the endpoint score as not calculated.
- Stress degradation thresholds are aligned with the Task 8/plan soft stress thresholds; changing central thresholds later should be wired into this generator rather than duplicated.
- The generator requires a raw `stress_<VU>` file for the matrix maximum VU. A future aggregator contract could make those detail files explicit and schema-validated centrally.
- The working directory contained pre-existing untracked files (`performance/env.performance`, `performance/endpoints/solicitudes/`, and the plan file). They were preserved and not staged; only Task 9 files are included in the commit.

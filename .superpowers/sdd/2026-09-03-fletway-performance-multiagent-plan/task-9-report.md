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
- All free-form Markdown values (manifest endpoint/objective and matrix endpoint/objective/result/users, plus raw profile results) use the comprehensive `Escape-Md` helper. It normalizes line breaks and escapes pipes, links, emphasis, backticks, and raw HTML/script punctuation; structural labels remain literal.
- Raw objects containing both `profile` and `requestedProfile` are rejected as ambiguous.
- Canonical matrix rows are validated before rendering: required free-form fields are non-empty, tests are supported, and executed rows have numeric VU bounds, p95, error percentage, and RPS values.
- Matrix semantics are enforced before rendering: `resultado` must be `APROBADA`, `ADVERTENCIA`, `FALLIDA`, or `NO_EJECUTADA`; `error_pct` must be within 0–100; VU minimum cannot exceed VU maximum; and each row’s raw `objetivo` must exactly match the manifest objective before Markdown/HTML escaping.
- UTF-8 input and output use .NET `UTF8Encoding($false)` with `File.ReadAllText`/`File.WriteAllText`, avoiding the PowerShell 7-only `utf8NoBOM` encoding name while preserving UTF-8 without BOM on PowerShell 5.1 and 7.
- Before rendering, canonical rows are reconciled with the raw-derived model: smoke/load/spike p95, VU bounds, error, derived RPS/duration, and metric-derived outcome must match; the stress row must match the observed VU range, remain within raw p95/error/RPS ranges, and match the worst raw stress outcome. Differences are rejected with a cross-source error.
- Endpoint method/path is rendered as escaped Markdown text rather than wrapped in a code span, so backticks in a manifest path cannot terminate Markdown formatting. The fixture harness uses its existing edition-selected PowerShell executable for the unsafe-path check.
- Outcome classification loads `performance/config/thresholds.json`, including hard timeout 10% and per-profile timeout thresholds. Raw timeout rates are validated from the timeout metric or `timeout_pct` and influence `APROBADA`, `ADVERTENCIA`, and `FALLIDA`.
- Missing raw `result` values use metric-derived outcomes in Smoke, Load, Stress, and Spike sections; Stress emits its worst observed outcome explicitly. Spike peak values are reconciled with the raw summary, baseline/recovery VUs with raw bounds, and duplicate recovery durations are rejected when they disagree.
- `NO_EJECUTADA` matrix rows require every numeric field to be blank; fabricated VU, p95, error, or RPS values are rejected before rendering. Credential detection targets assignment-shaped API keys/tokens/secrets and recognizable provider prefixes while allowing ordinary words such as “token budget” or “provider status.”

Absent Smoke/Load/Spike raw profiles are rendered as `NO_EJECUTADA`. A stress row with `NO_EJECUTADA` and blank numeric fields is valid without stress raw profiles; when stress is executed or the matrix claims a stress maximum, validated `stress_<VU>` detail is required because the per-VU table cannot be fabricated. Raw `http_req_failed.values.rate` must be a ratio in `[0,1]` before conversion to `error_pct`.

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
- Markdown/HTML-metacharacter result fixture proving free-form result escaping in Smoke and Spike output.
- Evidence/hypothesis wording and rejection of unsupported cause claims.
- Unsafe output path rejection.
- Hostile manifest/matrix endpoint, objective, result, and users values with pipes, line breaks, links, emphasis, and script-like HTML are escaped in Markdown while structural labels remain unchanged.
- Ambiguous raw `profile` plus `requestedProfile` rejection.
- Malformed canonical matrix numeric and required free-form field rejection.
- Invalid canonical `resultado`, out-of-range `error_pct`, reversed VU bounds, and manifest-objective mismatch rejection.
- Cross-source p95, VU, RPS/duration, error, stress-range/metric, and outcome mismatch rejection; a valid canonical matrix still renders.
- Backtick-containing endpoint rendering and edition-selected unsafe-path subprocess compatibility.
- Timeout threshold/outcome fixtures, absent-result outcome rendering, spike peak/VU/recovery contradiction rejection, blank numeric `NO_EJECUTADA` enforcement, and provider-credential detection with ordinary-word non-regression.

TDD evidence:

1. The new test was run before the generator existed and failed because the script file was missing.
2. After implementation, it failed on the Task 8 metric shape; the parser was corrected to read request count from `http_reqs` and duration statistics from `http_req_duration`.
3. Review fixtures then failed on the missing score contract and VU mismatch, driving the strict validation/model-rendering fixes.
4. The focused P1 fixture failed against the unescaped result renderer, then passed after adding a scoped Markdown-free-form helper at result interpolation sites.
5. The latest review fixtures failed on incomplete escaping and permissive input handling, then passed after making `Escape-Md` comprehensive and adding dual-profile/matrix validation.
6. The canonical matrix semantic fixtures failed on invalid status/range/order/objective cases, then passed after enforcing those checks before rendering.
7. The first Windows PowerShell 5.1 compatibility run failed on the unsupported `utf8NoBOM` encoding and source/output decoding; the harness and generator were then switched to the cross-version .NET UTF-8 helpers and the compatibility run passed.
8. The final fixture tests passed under both PowerShell 7 and Windows PowerShell 5.1.
9. Cross-source mismatch fixtures initially rendered successfully, proving the missing reconciliation; after adding raw-derived semantic checks, all mismatch cases were rejected and the valid fixture continued to render.
10. The latest fixtures failed on absent-result `observado`, ignored timeout classification, un-reconciled spike submetrics, fabricated `NO_EJECUTADA` numerics, and incomplete credential coverage; the focused fixes made those cases pass while preserving ordinary free-form words.
11. The focused edge-case fixtures cover valid stress `NO_EJECUTADA` rendering without stress raw files, rejection of executed stress without raw detail, fabricated stress `NO_EJECUTADA` numerics, and rejection of an out-of-range raw `http_req_failed.values.rate`.

Verification commands and results:

```text
pwsh -NoProfile -File performance/tests/generate-endpoint-report.tests.ps1                                  PASS
powershell.exe -NoProfile -ExecutionPolicy Bypass -File performance/tests/generate-endpoint-report.tests.ps1 PASS
pwsh -NoProfile -File performance/tests/aggregate-results.tests.ps1                                        PASS
pwsh -NoProfile -File performance/tests/run-queue.tests.ps1                                                PASS
git diff --check                                                                                           PASS
```

The current focused edge-case attempt intentionally did not rerun the long Windows PowerShell 5.1 harness after it was interrupted; its result is therefore recorded as **INTERRUPTED / incomplete**, not as a pass. The focused PS7 endpoint run produced the expected fixture report but did not terminate promptly and was stopped with exit code 1; it is likewise **INTERRUPTED / incomplete**, not a pass. `git diff --check` passed; aggregate and queue tests were not rerun.

## Controller-branch validation and worktree status

The controller branch was checked with `git branch --show-current` and is `main`. The Task 9 fix is kept as one coherent commit, and after commit verification the tracked worktree is clean (`git diff --check` passes with no tracked diff). Pre-existing untracked files remain intentionally preserved and unstaged: `performance/env.performance`, `performance/endpoints/solicitudes/`, and `performance/2026-09-03-fletway-performance-multiagent-plan.md`. The real environment file was not read into or committed by this task.

## Risks and follow-up

- Task 10 scoring is not yet available, so the report intentionally labels the endpoint score as not calculated.
- Stress degradation thresholds are aligned with the Task 8/plan soft stress thresholds; changing central thresholds later should be wired into this generator rather than duplicated.
- The generator requires a raw `stress_<VU>` file for the matrix maximum VU when stress was executed; a valid `NO_EJECUTADA` stress row may omit stress detail. A future aggregator contract could make those detail files explicit and schema-validated centrally.
- The working directory contained pre-existing untracked files (`performance/env.performance`, `performance/endpoints/solicitudes/`, and the plan file). They were preserved and not staged; only Task 9 files are included in the commit.

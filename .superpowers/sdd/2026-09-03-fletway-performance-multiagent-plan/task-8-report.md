# Task 8 Report — Raw Result Normalization

## Scope

Implemented the per-endpoint raw k6 summary aggregator in
`performance/scripts/aggregate-results.ps1` and focused fixture coverage in
`performance/tests/aggregate-results.tests.ps1`.

No live traffic, k6 execution, or endpoint calls were performed.

## Contract implemented

The output CSV always uses exactly this ordered schema:

```text
endpoint,test,objetivo,carga_vu_min,carga_vu_max,p95_ms,error_pct,capacidad_rps,resultado,usuarios
```

Only P0 endpoints from the manifest are emitted. Each supplied canonical
profile (`smoke`, `load`, `stress`, `spike`) produces one row per endpoint;
duplicate endpoint/profile inputs and unknown endpoints are rejected.

Endpoint labels are normalized as `METHOD /path`, and the objective comes from
the manifest rather than raw data. CSV numeric values use invariant decimal
notation, avoiding locale-dependent comma decimals.

## Raw input handling

The aggregator accepts a JSON file or recursively discovers `*.json` files in
a raw-results directory. It supports:

- direct raw metrics under `metrics`;
- the existing k6 wrapper under `k6.metrics`;
- endpoint-specific k6 metric names, preferred over global metrics when both
  are present;
- explicit `measured_duration_seconds`, `duration_seconds`, `duration_ms`, or
  `k6.state.testRunDurationMs` for duration.

RPS is calculated as `http_reqs.values.count / measured_duration_seconds`.
When `http_reqs` is absent, the duration metric count is used. The duration
unit is explicit; no k6 counter rate is treated as a substitute.

p95 is read from `values.p(95)` and remains numeric milliseconds. Error and
timeout rates must be ratios in `[0, 1]` and are emitted as numeric
percentages.

Malformed JSON, missing required fields, ambiguous endpoint metrics, invalid
units, invalid ratios, missing p95/count/duration data, duplicate rows, and
schema mismatches fail fast. Explicit `NOT_EXECUTED`/`NO_EJECUTADA` inputs are
preserved as `NO_EJECUTADA`; explicit failed records remain `FALLIDA`.

## Centralized result rules

Soft thresholds:

| Profile | p95 target | Error target | Timeout target |
|---|---:|---:|---:|
| smoke | < 1000 ms | < 1% | 0% |
| load | < 2000 ms | < 5% | < 1% |
| stress | < 3000 ms | < 10% | < 10% |
| spike | < 5000 ms | < 20% | < 20% |

Shared hard limits are p95 ≥ 5000 ms, error ≥ 20%, or timeout ≥ 10%.
Hard-limit violations classify as `FALLIDA`; soft-only violations classify as
`ADVERTENCIA`; otherwise the result is `APROBADA`.

## Verification

Focused command:

```powershell
pwsh -NoProfile -File performance/tests/aggregate-results.tests.ps1
```

Observed result: `PASS aggregate-results.tests.ps1`.

The fixtures verify numeric p95 conversion, ratio-to-percent conversion,
RPS calculation, manifest objective and endpoint normalization, all four
profile rows, `APROBADA`/`ADVERTENCIA`/`FALLIDA` classification,
`NOT_EXECUTED` preservation, malformed schema rejection, and exact CSV
columns.

## Risks and follow-up

- Stress sub-levels such as `stress_20` are normalized to the single
  canonical `stress` row required by Task 8; preserving one row per stress
  level belongs to the later endpoint-reporting task.
- Raw summaries without an explicit measured duration are rejected, even if a
  counter `rate` is present, to prevent ambiguous RPS units.
- Timeout is optional for compact summaries and defaults to zero when absent;
  when present, it participates in centralized status evaluation.
- Existing historical raw artifacts may contain secrets in their own
  `setup_data`; the aggregator does not copy raw secrets into CSV output or
  reports.

# Task 10 report — Weighted performance scoring

Implemented deterministic scoring from the canonical Task 8 matrix and manifest schemas.

## Delivered

- `performance/config/scoring.js`: strict latency, error, test, endpoint, general, traffic-weight, coverage, and classification calculations.
- `performance/scripts/calculate-score.js`: offline CLI that reads matrix CSV, manifest JSON, and thresholds JSON and writes reproducible score JSON.
- `performance/tests/scoring.test.mjs`: fixtures/assertions for normal and boundary scores, missing profiles, zero/invalid denominators, coverage below 80%, malformed/contradictory inputs, classification, and reproducibility.

Missing or `NO_EJECUTADA` profiles never score as successful. Incomplete endpoints are excluded from the general-score denominator, and the representative classification is blocked with machine-readable `representative_reason` when P0 coverage is below 80%. Coverage uses all P0/P1/P2 traffic weights as its denominator and only fully executed P0 endpoints in its numerator. Capacity/RPS is validated as matrix input but is not used in scoring.

Review fixes preserve `error_score = 0` at or above the hard error boundary, including equal target/hard thresholds, and accept observed `p95_ms = 0` end-to-end as a valid 100-point latency result when it is at or below target while retaining finite nonnegative validation.

Threshold normalization now rejects non-finite or out-of-range error percentages outside `[0, 100]`, and rejects any profile target above the hard error percentage before incomplete endpoint data can bypass validation.

## Verification

- `node --test performance/tests/scoring.test.mjs` — PASS, 7 tests.
- `node --check performance/config/scoring.js` — PASS.
- `node --check performance/scripts/calculate-score.js` — PASS.
- `git diff --check` — PASS.

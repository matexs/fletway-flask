# Task 6A — Solicitudes

## Implemented endpoints

Generated the seven Solicitudes P0 endpoint scripts from the existing endpoint generator:

- `mis-pedidos`
- `mis-pedidos-optimizado`
- `dashboard-transportista`
- `historial-transportista`
- `crear-solicitud`
- `actualizar-solicitud`
- `detalle-solicitud`

The scripts use the shared endpoint template, manifest-owned method/path resolution, role-aware setup authentication, endpoint adapters, and the structured ledger hook for mutations. The existing adapters provide the create/update request precondition fields from environment variables; no credentials, concrete resource IDs, or manifest/scoring changes were added. Shared metric-name normalization converts endpoint IDs such as `mis-pedidos` to valid k6 metric components (`mis_pedidos`) while preserving threshold limits and scoring semantics; this is required because the module scripts build endpoint-specific thresholds from manifest IDs.

Mutation response events now carry explicit `resource_action` and boolean `created_by_test` fields. `crear-solicitud` is marked as a created test resource; `actualizar-solicitud` is marked as an update and cannot be interpreted as a newly created cleanup resource.

## Validation

- Module contract test: PASS (canonical manifest-derived P0 set; 7/7 scripts).
- Node syntax checks: PASS (7/7 scripts).
- Direct endpoint contract validation: PASS (7/7 scripts).
- Focused regression suite: PASS (21 tests).
- Manifest validation: PASS (39 endpoints; temporary output used, shared coverage plan unchanged).
- Non-executing `k6 inspect`: PASS for all 7 scripts; standalone scripts declare and record the overall and endpoint-specific Trend/Rate metrics referenced by their thresholds.
- CLI entrypoint contract: PASS; each script exports a default function receiving k6 setup data and delegating to named `runFlow`.
- Live load: NOT RUN, per task instruction.

## Per-endpoint preflight evidence

Preflight policy: only transient read-only requests were allowed; POST/PATCH mutations were safety-blocked. The controller used the ignored original environment file transiently; credentials were not copied, persisted, or committed.

| Endpoint | Method | Evidence status | Reason |
|---|---|---|---|
| `mis-pedidos` | GET | FAIL | Timed out at `https://fletway.onrender.com/api/solicitudes/mis-pedidos` with `REQUEST_TIMEOUT=10s`; k6 exit 99. |
| `mis-pedidos-optimizado` | GET | PASS | One iteration, HTTP success, `REQUEST_TIMEOUT=3s`; k6 exit 0. |
| `dashboard-transportista` | GET | PASS | One iteration, HTTP success, `REQUEST_TIMEOUT=3s`; k6 exit 0. |
| `historial-transportista` | GET | PASS | One iteration, HTTP success, `REQUEST_TIMEOUT=3s`; k6 exit 0. |
| `crear-solicitud` | POST | SAFETY-BLOCKED | Mutation prohibited by task; not executed. |
| `actualizar-solicitud` | PATCH | SAFETY-BLOCKED | Mutation prohibited by task; not executed. |
| `detalle-solicitud` | GET | NOT-RUN | `REQUEST_ID` was not configured. |

## Resources and prerequisites

- Client role: `CLIENT_EMAIL`, `CLIENT_PASSWORD`.
- Driver role: `DRIVER_EMAIL`, `DRIVER_PASSWORD`.
- Common setup: `BASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`.
- Mutation/path data comes from the existing adapter environment variables, including `ORIGIN_ADDRESS`, `DESTINATION_ADDRESS`, `CARGO_DETAILS`, `WEIGHT`, `PICKUP_TIME`, and `REQUEST_ID` as applicable.
- Mutation-created resources are emitted through the existing ledger hook for cleanup integration.

## Concerns

The standalone metric and CLI entrypoint preflight issues are resolved. `mis-pedidos` timed out while the other three configured read-only endpoint preflights passed. Mutation endpoints remain intentionally safety-blocked, and `detalle-solicitud` was not run without `REQUEST_ID`. No load ran; credentials remained transient and uncommitted.

## Files

- `performance/endpoints/solicitudes/*.js` — seven generated endpoint scripts.
- `performance/endpoints/solicitudes/solicitudes.contract.test.mjs` — manifest-derived module contract test.
- `performance/config/thresholds.js` — valid k6 metric-name normalization helper.
- `performance/scripts/generate-endpoint-test.mjs` — explicit create/update event semantics in generated mutation scripts.
- `performance/tests/thresholds.test.mjs` — metric-name regression test.
- `performance/tests/endpoint-generator.test.mjs` — ledger-event, metric-declaration, and CLI-entrypoint regression tests.

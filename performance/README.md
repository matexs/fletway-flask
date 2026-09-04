# Fletway k6 performance campaign

The canonical campaign exercises exactly the ten requested endpoints, including
the `POST /api/solicitudes` and `PATCH /api/solicitudes/<id>` mutation tests.
Mutation notifications remain enabled and generated test records are retained;
cleanup is deliberately a separate, explicit operation.

## Perfiles

| Perfil | Carga | Duración aproximada | Uso |
|---|---|---:|---|
| `smoke` | 1 → 3 VU | 40 s | Validar login, endpoints y configuración |
| `load` | 0 → 10 VU, sostenidos | 90 s | Representar carga normal conservadora |
| `stress` | 10, 20 y 30 VU | 105 s | Observar el primer escalón con degradación |
| `spike` | 3 → 30 VU + recuperación | 60 s | Medir pico y recuperación |

El estrés mide escalones independientes y no pretende encontrar un breakpoint definitivo.

## Configuración

1. Install k6 on Windows:

   ```powershell
   winget install k6 --source winget
   ```

2. Copy `.env.performance.example` to `performance/env.performance` and fill in
   authorized test credentials. The real file is ignored by Git.

3. Run the serialized campaign from `main`:

   ```powershell
   pwsh -NoProfile -File performance/runners/run-campaign.ps1 -RunId 20260904-final
   ```

   Optional overrides are available without changing the environment file:

   ```powershell
   pwsh -NoProfile -File performance/runners/run-campaign.ps1 `
     -BaseUrl http://127.0.0.1:5000 -RunId local-campaign
   ```

The runner preflights all ten endpoints, gates profiles deterministically, runs
endpoints serially in manifest order, continues after failures, and writes the
campaign bundle to `performance/campaigns/<run_id>/`.

The bundle includes raw sanitized k6 JSON, logs, JSONL ledgers, Markdown/HTML
reports, and the exact 34-row `matrix_general.csv` with this schema:

`endpoint,test,objetivo,carga_vu_min,carga_vu_max,p95_ms,error_pct,capacidad_rps,resultado,usuarios`

Do not commit `performance/env.performance`, passwords, JWTs, or tokens.

## Semáforo

- **APROBADA:** p95, éxito, errores y timeouts cumplen los objetivos recomendados.
- **ADVERTENCIA:** existe degradación moderada, pero la API continúa por encima de los límites duros.
- **NO EJECUTADA:** falló la prevalidación de disponibilidad, autenticación o roles; no hay muestras para evaluar.
- **FALLIDA:** durante la prueba, p95 ≥ 5000 ms, éxito ≤ 80%, errores ≥ 20% o timeouts ≥ 10%.

Los objetivos blandos generales son p95 < 2000 ms, éxito > 95%, errores < 5% y timeouts < 1%. Smoke usa p95 < 1000 ms, éxito > 99%, errores < 1% y cero timeouts.

La prevalidación tolera el arranque en frío de Render mediante `SETUP_REQUEST_TIMEOUT=60s`, tres intentos y una pausa de dos segundos. Este margen solo se usa antes de iniciar VUs; las solicitudes medidas conservan `REQUEST_TIMEOUT=10s`.

Los reportes nunca incluyen emails, contraseñas ni JWT. Los archivos generados quedan en `performance/reports/` y los resúmenes objetivos de k6 en `performance/results/`.

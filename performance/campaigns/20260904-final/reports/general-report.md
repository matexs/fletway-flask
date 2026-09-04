# Fletway k6 Performance Campaign

- **Run:** 20260904-final
- **Rows:** 34
- **Executed:** 29
- **APROBADA:** 25
- **ADVERTENCIA:** 2
- **FALLIDA:** 2
- **NO_EJECUTADA:** 5

## Matrix

| endpoint | test | p95_ms | error_pct | capacidad_rps | resultado |
|---|---|---:|---:|---:|---|
| GET /api/presupuestos/completo-batch | load |  |  |  | NO_EJECUTADA |
| GET /api/presupuestos/completo-batch | stress | 2201.024 | 0 | 14.733 | APROBADA |
| GET /api/presupuestos/completo-batch | spike | 1995.43 | 0 | 8.683 | APROBADA |
| GET /api/presupuestos/mis-presupuestos | load |  |  |  | NO_EJECUTADA |
| GET /api/presupuestos/mis-presupuestos | stress | 2401.467 | 0 | 14.133 | APROBADA |
| GET /api/presupuestos/mis-presupuestos | spike | 2198.5 | 0 | 8.367 | APROBADA |
| GET /api/presupuestos/solicitud/<solicitud_id> | smoke | 215.047 | 0 | 1.075 | APROBADA |
| GET /api/presupuestos/solicitud/<solicitud_id> | load | 252.46 | 0 | 6.967 | APROBADA |
| GET /api/presupuestos/solicitud/<solicitud_id> | stress | 1994.746 | 0 | 16.3 | APROBADA |
| GET /api/presupuestos/solicitud/<solicitud_id> | spike | 1990.027 | 0 | 9.317 | APROBADA |
| GET /api/solicitudes/<id> | smoke | 256.575 | 0 | 1.05 | APROBADA |
| GET /api/solicitudes/<id> | load | 252.18 | 0 | 6.922 | APROBADA |
| GET /api/solicitudes/<id> | stress | 1609.563 | 0 | 20.767 | APROBADA |
| GET /api/solicitudes/<id> | spike | 1186.562 | 0 | 12.117 | APROBADA |
| GET /api/solicitudes/mis-pedidos | load | 493.534 | 0 | 6.467 | APROBADA |
| GET /api/solicitudes/mis-pedidos | stress | 3830.067 | 0 | 9.4 | ADVERTENCIA |
| GET /api/solicitudes/mis-pedidos | spike | 3775.263 | 0 | 5.4 | APROBADA |
| GET /api/transportista/dashboard | load | 302.833 | 0 | 6.822 | APROBADA |
| GET /api/transportista/dashboard | stress | 2402.778 | 0 | 12.5 | APROBADA |
| GET /api/transportista/dashboard | spike | 1900.108 | 0 | 7.9 | APROBADA |
| GET /api/transportista/historial | load | 1291.175 | 0 | 4.8 | APROBADA |
| GET /api/transportista/historial | stress | 6621.575 | 0 | 6.133 | FALLIDA |
| GET /api/transportista/historial | spike | 4934.546 | 0 | 4 | APROBADA |
| GET /solicitudes/mis-pedidos-optimizado | load | 511.778 | 0 | 6.311 | APROBADA |
| GET /solicitudes/mis-pedidos-optimizado | stress | 4027.128 | 0 | 8.833 | ADVERTENCIA |
| GET /solicitudes/mis-pedidos-optimizado | spike | 4098.907 | 0 | 4.867 | APROBADA |
| PATCH /api/solicitudes/<id> | smoke | 259.859 | 0 | 1.05 | APROBADA |
| PATCH /api/solicitudes/<id> | load | 366.253 | 0 | 6.678 | APROBADA |
| PATCH /api/solicitudes/<id> | stress | 2197.115 | 0 | 13 | APROBADA |
| PATCH /api/solicitudes/<id> | spike | 2096.626 | 0 | 8.2 | APROBADA |
| POST /api/solicitudes | smoke | 10000.422 | 0 | 0.125 | FALLIDA |
| POST /api/solicitudes | load |  |  |  | NO_EJECUTADA |
| POST /api/solicitudes | stress |  |  |  | NO_EJECUTADA |
| POST /api/solicitudes | spike |  |  |  | NO_EJECUTADA |

## Stress stage details

| endpoint | VU | p95_ms | error_pct | capacidad_rps |
|---|---:|---:|---:|---:|
| GET /api/presupuestos/completo-batch | 10 | 310.488 | 0 | 8.333 |
| GET /api/presupuestos/completo-batch | 20 | 907.865 | 0 | 14.733 |
| GET /api/presupuestos/completo-batch | 30 | 2201.024 | 0 | 14.1 |
| GET /api/presupuestos/mis-presupuestos | 10 | 342.516 | 0 | 8.267 |
| GET /api/presupuestos/mis-presupuestos | 20 | 1402.199 | 0 | 13.1 |
| GET /api/presupuestos/mis-presupuestos | 30 | 2401.467 | 0 | 14.133 |
| GET /api/presupuestos/solicitud/<solicitud_id> | 10 | 290.27 | 0 | 8.333 |
| GET /api/presupuestos/solicitud/<solicitud_id> | 20 | 597.024 | 0 | 15.833 |
| GET /api/presupuestos/solicitud/<solicitud_id> | 30 | 1994.746 | 0 | 16.3 |
| GET /api/solicitudes/<id> | 10 | 246.521 | 0 | 8.4 |
| GET /api/solicitudes/<id> | 20 | 500.663 | 0 | 15.967 |
| GET /api/solicitudes/<id> | 30 | 1609.563 | 0 | 20.767 |
| GET /api/solicitudes/mis-pedidos | 10 | 806.172 | 0 | 7.533 |
| GET /api/solicitudes/mis-pedidos | 20 | 3000.005 | 0 | 8.233 |
| GET /api/solicitudes/mis-pedidos | 30 | 3830.067 | 0 | 9.4 |
| GET /api/transportista/dashboard | 10 | 380.348 | 0 | 8.167 |
| GET /api/transportista/dashboard | 20 | 1794.193 | 0 | 11.433 |
| GET /api/transportista/dashboard | 30 | 2402.778 | 0 | 12.5 |
| GET /api/transportista/historial | 10 | 1810.961 | 0 | 5.233 |
| GET /api/transportista/historial | 20 | 4104.685 | 0 | 5.5 |
| GET /api/transportista/historial | 30 | 6621.575 | 0 | 6.133 |
| GET /solicitudes/mis-pedidos-optimizado | 10 | 609.565 | 0 | 7.467 |
| GET /solicitudes/mis-pedidos-optimizado | 20 | 3549.713 | 0 | 7.8 |
| GET /solicitudes/mis-pedidos-optimizado | 30 | 4027.128 | 0 | 8.833 |
| PATCH /api/solicitudes/<id> | 10 | 362.48 | 0 | 8.1 |
| PATCH /api/solicitudes/<id> | 20 | 1799.936 | 0 | 10.833 |
| PATCH /api/solicitudes/<id> | 30 | 2197.115 | 0 | 13 |

## Spike recovery details

| endpoint | peak_p95_ms | peak_error_pct | peak_rps | recovery_seconds |
|---|---:|---:|---:|---:|
| GET /api/presupuestos/completo-batch | 1995.43 | 0 | 8.683 | 20 |
| GET /api/presupuestos/mis-presupuestos | 2198.5 | 0 | 8.367 | 20 |
| GET /api/presupuestos/solicitud/<solicitud_id> | 1990.027 | 0 | 9.317 | 20 |
| GET /api/solicitudes/<id> | 1186.562 | 0 | 12.117 | 20 |
| GET /api/solicitudes/mis-pedidos | 3775.263 | 0 | 5.4 | 20 |
| GET /api/transportista/dashboard | 1900.108 | 0 | 7.9 | 20 |
| GET /api/transportista/historial | 4934.546 | 0 | 4 | 20 |
| GET /solicitudes/mis-pedidos-optimizado | 4098.907 | 0 | 4.867 | 20 |
| PATCH /api/solicitudes/<id> | 2096.626 | 0 | 8.2 | 20 |


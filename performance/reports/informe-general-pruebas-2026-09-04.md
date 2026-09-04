# Fletway — Informe general de pruebas de rendimiento

**Fecha:** 4 de septiembre de 2026  
**Rama:** `codex/fletway-performance`  
**Estado del plan:** completado hasta la Tarea 11; Tarea 12 pendiente de corrección y validación.

## Resumen ejecutivo

Se completó y revisó la base técnica del plan de rendimiento multiagente: configuración, perfiles, contratos, generación de scripts, selección de endpoints, cola de ejecución, agregación, reportes por endpoint, cálculo ponderado y matriz general.

La matriz canónica incluida en la rama contiene únicamente el encabezado porque no se ejecutó una campaña nueva de tráfico contra la API durante este plan. Por lo tanto, no se inventan valores de p95, errores, RPS ni una clasificación general. La cobertura del manifiesto es de **39 endpoints**, con **13 P0**, pero la cobertura de ejecución medida es **0%**.

La Tarea 12 no se publicó porque su validación detectó inconsistencias reales en el generador del informe general. El fallo inmediato fue que el manifiesto guarda la prioridad como texto (`"P0"`) y una ruta de cálculo la comparaba como número (`0`); eso hacía que la puntuación recalculada no coincidiera con la puntuación suministrada por el fixture. Además, la revisión encontró problemas pendientes en la validación de fuentes, el renderizado de stress/spike, el filtrado de secretos, la exigencia de identidades de matriz y el parseo CSV. Es un fallo del reporte y sus controles, no evidencia de que la API esté caída.

## Matriz general entregada

Archivo: [`performance/results/matrix/matrix_general.csv`](../results/matrix/matrix_general.csv)

```csv
endpoint,test,objetivo,carga_vu_min,carga_vu_max,p95_ms,error_pct,capacidad_rps,resultado,usuarios
```

Estado de la matriz:

| Indicador | Resultado |
|---|---:|
| Endpoints en el manifiesto canónico | 39 |
| Endpoints P0 | 13 |
| Filas de ejecución con métricas | 0 |
| Cobertura estática planificada | 80% |
| Cobertura de ejecución observada en esta rama | 0% |
| Puntuación general representativa | No calculable |
| Clasificación general representativa | No calculable |

La ausencia de filas significa **NO EJECUTADA**, no aprobación. Los scripts y contratos quedaron preparados para poblar la matriz cuando exista una ejecución autorizada y reproducible.

## Tareas terminadas

| Tarea | Alcance | Estado | Evidencia principal |
|---:|---|---|---|
| 1 | Fundaciones, configuración y estructura de la suite | ✅ Completada | Configuración central en `performance/config/` y runners en `performance/runners/` |
| 2 | Perfiles, objetivos y umbrales | ✅ Completada | `profiles.js`, `thresholds.js`, `thresholds.json` |
| 3 | Generación compartida de requests y contratos | ✅ Completada | `performance/templates/`, adaptadores y pruebas de contrato |
| 4 | Runner y cola ejecutable | ✅ Completada | Cola serializada, ownership y ledger de recursos |
| 5 | Generación de pruebas por endpoint | ✅ Completada | `generate-endpoint-test.mjs`, template y pruebas de paridad |
| 6A | Solicitudes | ⚠️ Condicional | Prevalidaciones GET ejecutadas; mutaciones bloqueadas por seguridad; no se escribió tráfico destructivo |
| 6B | Presupuestos | ✅ Completada | Scripts, adapters, contratos y validaciones finales aprobados |
| 6C | Localidades y health | ✅ Completada | Scripts, adapters, contratos y validaciones finales aprobados |
| 7 | Cola y ejecución controlada | ✅ Completada | `run-queue.tests.ps1` y control de recursos |
| 8 | Agregación de métricas por endpoint | ✅ Completada | `aggregate-results.ps1` y `aggregate-results.tests.ps1` |
| 9 | Reportes legibles por endpoint | ✅ Completada | `generate-endpoint-report.ps1` y sus pruebas |
| 10 | Puntuación ponderada | ✅ Completada | `calculate-score.js`, `scoring.js` y 7 casos aprobados |
| 11 | Matriz general canónica | ✅ Completada | `build-general-matrix.ps1` y contrato de identidad de filas |
| 12 | Informe general consolidado y endurecimiento | ⏸ Pendiente | Bloqueada por inconsistencias de score y hallazgos de revisión; no se empujó código incompleto |

## Pruebas y verificaciones realizadas

Se verificaron, según la tarea correspondiente:

- sintaxis y contratos de scripts Node.js y PowerShell;
- paridad entre el template y los scripts generados;
- selección de endpoints y cobertura explícita del manifiesto;
- validación de perfiles smoke, load, stress y spike;
- ownership de la cola y ledger de recursos creados;
- limpieza segura y bloqueo de operaciones mutantes;
- agregación de métricas incluyendo escenarios sin ejecución;
- generación de reportes por endpoint para resultados vacíos y con resultados;
- cálculo de score: **7/7 casos de la suite de scoring aprobados**;
- construcción y validación de la matriz general, incluyendo encabezado y orden canónico.

Comandos representativos verificados:

```powershell
pwsh -NoProfile -File performance/tests/aggregate-results.tests.ps1
pwsh -NoProfile -File performance/tests/generate-endpoint-report.tests.ps1
node --test performance/tests/scoring.test.mjs
pwsh -NoProfile -File performance/tests/build-general-matrix.tests.ps1
```

No se ejecutaron k6, smoke, load, stress o spike nuevos como parte de esta consolidación. Tampoco se ejecutaron mutaciones contra datos reales.

## Campaña k6 histórica ya disponible

El repositorio conserva [`performance/informe-rendimiento-general-k6.md`](../informe-rendimiento-general-k6.md), correspondiente a una campaña anterior, realizada el 23 de agosto de 2026 sobre Render. Esa campaña sí tuvo tráfico real y reportó:

| Perfil | Requests | p95 | Éxito | Errores | Timeouts | Estado |
|---|---:|---:|---:|---:|---:|---|
| Smoke 1–3 VU | 39 | 928 ms | 100% | 0% | 0% | ✅ Aprobada |
| Load 10 VU | 428 | 1.752 ms | 100% | 0% | 0% | ✅ Aprobada |
| Stress 10 VU | 164 | 1.815 ms | 100% | 0% | 0% | ✅ Aprobada |
| Stress 20 VU | 216 | 4.192 ms | 100% | 0% | 0% | ⚠️ Advertencia |
| Stress 30 VU | 240 | 6.811 ms | 100% | 0% | 0% | ❌ Fallida por latencia |

Estos números son evidencia histórica separada: no deben mezclarse con la matriz canónica actual, que está vacía y no permite comparar campañas, herramientas, fechas o entornos distintos como si fueran una misma ejecución.

## Seguridad y límites

- No se versionaron contraseñas, JWT ni secretos.
- El archivo local `performance/.env.performance` permanece fuera del control de versiones.
- Las operaciones mutantes de Solicitudes quedaron bloqueadas por seguridad.
- No se hicieron afirmaciones de causa raíz sin métricas de aplicación, base de datos o infraestructura.
- Sin filas ejecutadas no es válido declarar capacidad, score o semáforo general.

## Conclusión

El trabajo terminado deja una suite reproducible y con controles para producir la matriz y el informe general. Las Tareas 1–11 están terminadas y sus cambios están en la rama remota. La Tarea 12 queda correctamente pendiente porque sus pruebas descubrieron inconsistencias que deben corregirse antes de presentar un informe consolidado como válido.

La siguiente acción técnica es corregir el contrato de prioridad (`P0`), completar las validaciones pendientes y volver a ejecutar las pruebas de regresión de la Tarea 12. Luego se podrá generar una matriz con métricas reales, siempre que se autorice una campaña segura de ejecución.

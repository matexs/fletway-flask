# FLETWAY — Informe General de Rendimiento de la API

## Resumen del documento

| Campo | Valor |
|---|---|
| **Sistema evaluado** | API backend de Fletway |
| **Entorno objetivo** | Producción — Render |
| **URL evaluada** | `https://fletway.onrender.com` |
| **Herramienta** | Grafana k6 v2.2.0 |
| **Fecha de ejecución** | 23 de agosto de 2026, zona horaria America/Buenos_Aires |
| **Ventana UTC** | 24 de agosto de 2026, 01:54–01:58 UTC |
| **Tipos de prueba** | Smoke, carga y estrés escalonado |
| **Operaciones ejecutadas** | Exclusivamente HTTP GET de solo lectura |
| **Estado gerencial** | **⚠️ ADVERTENCIA** |
| **Versión del informe** | 1.0 |

> Este documento consolida exclusivamente las ejecuciones definitivas realizadas con k6. El informe anterior de Artillery se conserva como antecedente histórico, pero sus resultados no se mezclan ni se comparan directamente porque corresponden a otra herramienta, otra fecha y otro entorno de despliegue.

---

## 1. Informe gerencial

La API de Fletway se mantuvo disponible y funcional durante todas las pruebas realizadas. Se procesaron **1.087 requests**, con **100% de respuestas HTTP exitosas**, **0% de errores** y **0 timeouts**. Esto representa una mejora operacional importante respecto del antecedente histórico, aunque no permite atribuir la diferencia a una optimización concreta porque cambiaron el entorno, la herramienta y el perfil de carga.

La carga normal conservadora de **10 usuarios virtuales concurrentes (VU)** fue aprobada: procesó 428 requests con p95 global de **1.752 ms**, por debajo del objetivo general de 2.000 ms. El smoke test también fue aprobado y validó los nueve endpoints, la autenticación y ambos roles antes de aplicar mayor concurrencia.

La principal limitación observada no fue la disponibilidad, sino la **latencia bajo concurrencia creciente**. En estrés, el p95 global aumentó desde **1.815 ms con 10 VU**, a **4.192 ms con 20 VU** y **6.811 ms con 30 VU**. Por este motivo, 20 VU se clasifica como `ADVERTENCIA` y 30 VU como `FALLIDA` por superar el límite duro de 5.000 ms.

Desde una perspectiva gerencial, el estado general se clasifica como **ADVERTENCIA**: la API es estable y no pierde requests en la carga normal probada, pero necesita optimización antes de considerar validados niveles sostenidos de 20 VU o superiores. Los endpoints prioritarios son el historial del transportista y el catálogo completo de localidades.

### Decisión recomendada

- Considerar **10 VU** como carga concurrente validada por esta campaña.
- No adoptar **20 VU o más** como capacidad estable hasta reducir la latencia y repetir las mediciones.
- Priorizar `/api/transportista/historial` y `/api/localidades` para análisis de consultas, volumen de respuesta y paginación/caché.
- Incorporar métricas de aplicación, base de datos y recursos antes de afirmar una causa raíz.

---

## 2. Objetivos de la evaluación

Las pruebas buscaron responder las siguientes preguntas:

1. ¿La API y las credenciales funcionan con una carga mínima?
2. ¿Los endpoints principales soportan una carga normal conservadora?
3. ¿En qué nivel comienza a degradarse la latencia?
4. ¿Qué endpoints se degradan primero?
5. ¿La degradación provoca errores HTTP o timeouts?

No se ejecutaron pruebas spike, soak, navegador ni un breakpoint abierto. El objetivo fue obtener un reporte sencillo, reproducible y fácil de explicar.

---

## 3. Entorno y autenticación

### 3.1 Entorno probado

| Componente | Configuración |
|---|---|
| Backend | Flask desplegado en Render |
| URL base | `https://fletway.onrender.com` |
| Autenticación | Supabase Auth con JWT Bearer |
| Generador de carga | k6 local en Windows |
| Tiempo de espera por request | 10 segundos |
| Pausa de usuario | 1 segundo entre iteraciones |
| Modelo de carga | Usuarios virtuales concurrentes, modelo cerrado |

### 3.2 Usuarios de prueba

| Rol | Cuenta utilizada | Uso |
|---|---|---|
| Cliente | `mateoreyx@gmail.com` | Pedidos, localidades y presupuestos del cliente |
| Fletero/transportista | `fletero@gmail.com.ar` | Dashboard, historial y presupuestos del transportista |

Las contraseñas y los JWT no forman parte de este informe. k6 realizó el login una sola vez por rol durante `setup()`, obtuvo tokens temporales desde Supabase y validó cada rol antes de iniciar la carga. Las métricas de autenticación y prevalidación se excluyeron de las métricas de negocio.

### 3.3 Precauciones

- Todas las operaciones medidas fueron GET.
- No se crearon, actualizaron ni eliminaron datos.
- No se usaron IDs fijos de solicitudes o presupuestos.
- Las credenciales se mantienen en un archivo local ignorado por Git.
- Ningún reporte generado contiene contraseñas, claves o JWT.

---

## 4. Endpoints evaluados

| Peso | Endpoint | Rol | Propósito |
|---:|---|---|---|
| 5% | `GET /` | Público | Health check del backend |
| 10% | `GET /api/localidades` | Cliente | Catálogo completo de localidades |
| 10% | `GET /api/localidades/buscar?q=Cordoba` | Cliente | Búsqueda limitada de localidades |
| 20% | `GET /api/solicitudes/mis-pedidos` | Cliente | Pedidos asociados al cliente autenticado |
| 15% | `GET /solicitudes/mis-pedidos-optimizado` | Cliente | Versión optimizada de pedidos |
| 15% | `GET /api/transportista/dashboard` | Fletero | Solicitudes y datos del dashboard |
| 10% | `GET /api/transportista/historial` | Fletero | Historial de viajes del transportista |
| 10% | `GET /api/presupuestos/mis-presupuestos` | Fletero | Presupuestos del transportista |
| 5% | `GET /api/presupuestos/completo-batch` | Cliente | Presupuestos agrupados de solicitudes propias |

La selección se distribuyó de forma ponderada durante cada perfil. Cada response fue validado mediante un `check` de HTTP 200 y registrado en métricas separadas por perfil y endpoint.

---

## 5. Perfiles de prueba

### 5.1 Smoke test

| Fase | Duración | Carga |
|---|---:|---:|
| Inicio | 10 s | 0 → 1 VU |
| Validación | 20 s | 1 → 3 VU |
| Descenso | 10 s | 3 → 0 VU |

Objetivo: validar disponibilidad, autenticación, roles, rutas y respuestas antes de ejecutar carga adicional.

### 5.2 Load test

| Fase | Duración | Carga |
|---|---:|---:|
| Rampa | 15 s | 0 → 10 VU |
| Carga sostenida | 60 s | 10 VU |
| Descenso | 15 s | 10 → 0 VU |

Objetivo: validar una carga normal conservadora de 10 usuarios virtuales concurrentes.

### 5.3 Stress test

| Escalón | Duración | Carga |
|---|---:|---:|
| Nivel 1 | 30 s | 10 VU |
| Pausa | 5 s | Sin carga |
| Nivel 2 | 30 s | 20 VU |
| Pausa | 5 s | Sin carga |
| Nivel 3 | 30 s | 30 VU |

Objetivo: observar la degradación en tres escalones independientes. Esta prueba identifica capacidad dentro del rango evaluado, pero **no constituye una prueba de breakpoint definitiva**.

---

## 6. Criterios y estados

### 6.1 Objetivos recomendados

| Indicador | Smoke | Carga y estrés |
|---|---:|---:|
| p95 | < 1.000 ms | < 2.000 ms |
| Success rate | > 99% | > 95% |
| Error rate | < 1% | < 5% |
| Timeout rate | 0% | < 1% |

### 6.2 Límites duros

| Indicador | Se considera FALLIDA cuando |
|---|---:|
| p95 | ≥ 5.000 ms |
| Success rate | ≤ 80% |
| Error rate | ≥ 20% |
| Timeout rate | ≥ 10% |
| Muestras | No existe ninguna respuesta válida |

### 6.3 Interpretación del semáforo

- **✅ APROBADA:** cumple todos los objetivos recomendados.
- **⚠️ ADVERTENCIA:** supera al menos un objetivo recomendado, pero no alcanza un límite duro.
- **❌ FALLIDA:** alcanza un límite duro o no produce muestras válidas.

---

## 7. Resultados globales

| Prueba | Requests | p95 | Éxito | Errores | Timeouts | Estado |
|---|---:|---:|---:|---:|---:|---|
| Smoke 1–3 VU | 39 | 928 ms | 100,00% | 0,00% | 0,00% | ✅ APROBADA |
| Carga 10 VU | 428 | 1.752 ms | 100,00% | 0,00% | 0,00% | ✅ APROBADA |
| Estrés 10 VU | 164 | 1.815 ms | 100,00% | 0,00% | 0,00% | ✅ APROBADA |
| Estrés 20 VU | 216 | 4.192 ms | 100,00% | 0,00% | 0,00% | ⚠️ ADVERTENCIA |
| Estrés 30 VU | 240 | 6.811 ms | 100,00% | 0,00% | 0,00% | ❌ FALLIDA |
| **Total** | **1.087** | No agregable | **100,00%** | **0,00%** | **0,00%** | **⚠️ ADVERTENCIA gerencial** |

> Los percentiles p95 no se suman ni se promedian entre ejecuciones. Cada valor representa la distribución de su perfil específico.

### 7.1 Capacidad observada

| Concepto | Resultado |
|---|---|
| Carga normal validada | 10 VU durante 60 segundos sostenidos |
| Máxima carga estable observada | 10 VU |
| Primer nivel con degradación | 20 VU |
| Primer nivel con fallo duro | 30 VU |
| Motivo de degradación | Latencia p95 |
| Errores o timeouts observados | Ninguno |

El sistema mantuvo disponibilidad y respuestas correctas hasta 30 VU, pero la experiencia de usuario esperada deja de ser aceptable antes de ese nivel debido al crecimiento de la latencia.

---

## 8. Consolidado por endpoint

La tabla reúne todas las ejecuciones definitivas. El estado final de cada endpoint representa el peor estado observado dentro de los niveles probados.

| Endpoint | Requests totales | Smoke p95 | Carga p95 | Estrés 10 p95 | Estrés 20 p95 | Estrés 30 p95 | Estado final |
|---|---:|---:|---:|---:|---:|---:|---|
| `/` | 55 | 197 ms ✅ | 568 ms ✅ | 380 ms ✅ | 1.095 ms ✅ | 944 ms ✅ | ✅ APROBADA |
| `/api/localidades` | 112 | 1.347 ms ⚠️ | 1.763 ms ✅ | 2.122 ms ⚠️ | 4.500 ms ⚠️ | 7.471 ms ❌ | ❌ FALLIDA |
| `/api/localidades/buscar` | 106 | 243 ms ✅ | 1.327 ms ✅ | 1.026 ms ✅ | 2.198 ms ⚠️ | 2.818 ms ⚠️ | ⚠️ ADVERTENCIA |
| `/api/solicitudes/mis-pedidos` | 219 | 434 ms ✅ | 1.675 ms ✅ | 1.380 ms ✅ | 2.482 ms ⚠️ | 3.598 ms ⚠️ | ⚠️ ADVERTENCIA |
| `/solicitudes/mis-pedidos-optimizado` | 164 | 411 ms ✅ | 1.416 ms ✅ | 1.574 ms ✅ | 2.692 ms ⚠️ | 3.468 ms ⚠️ | ⚠️ ADVERTENCIA |
| `/api/transportista/dashboard` | 162 | 217 ms ✅ | 1.774 ms ✅ | 2.308 ms ⚠️ | 2.421 ms ⚠️ | 4.825 ms ⚠️ | ⚠️ ADVERTENCIA |
| `/api/transportista/historial` | 105 | 437 ms ✅ | 2.467 ms ⚠️ | 2.136 ms ⚠️ | 5.196 ms ❌ | 7.975 ms ❌ | ❌ FALLIDA |
| `/api/presupuestos/mis-presupuestos` | 106 | 221 ms ✅ | 1.504 ms ✅ | 1.174 ms ✅ | 2.494 ms ⚠️ | 3.677 ms ⚠️ | ⚠️ ADVERTENCIA |
| `/api/presupuestos/completo-batch` | 58 | 218 ms ✅ | 1.922 ms ✅ | 1.909 ms ✅ | 2.226 ms ⚠️ | 4.619 ms ⚠️ | ⚠️ ADVERTENCIA |

### 8.1 Endpoints prioritarios

#### `/api/transportista/historial`

- Ya presenta advertencia con la carga normal: p95 de 2.467 ms.
- Supera el límite duro a 20 VU: p95 de 5.196 ms.
- Es el endpoint más lento a 30 VU: p95 de 7.975 ms.
- Debe ser el primer endpoint analizado para paginación, volumen de datos y costo de consulta/serialización.

#### `/api/localidades`

- Supera el objetivo estricto del smoke: p95 de 1.347 ms.
- Alcanza 4.500 ms con 20 VU y 7.471 ms con 30 VU.
- Devuelve un catálogo completo relativamente grande; conviene evaluar caché, compresión y paginación o descarga segmentada.

#### `/api/transportista/dashboard`

- Se mantiene aprobado durante carga normal, pero entra en advertencia desde estrés 10 VU.
- Llega a p95 de 4.825 ms con 30 VU, muy cerca del límite duro.

### 8.2 Endpoint con mejor estabilidad

El health check `/` permaneció aprobado en todos los niveles, incluso con 30 VU. Esto confirma que el servicio siguió aceptando conexiones mientras los endpoints con acceso y serialización de datos aumentaban su latencia.

---

## 9. Interpretación técnica

### 9.1 Hechos comprobados

- Los nueve endpoints respondieron HTTP 200 durante las ejecuciones definitivas.
- No se registraron errores HTTP ni timeouts.
- La carga normal de 10 VU cumplió el objetivo global de p95 < 2.000 ms.
- El p95 global aumentó a 4.192 ms con 20 VU y a 6.811 ms con 30 VU.
- Historial del transportista y localidades fueron los endpoints con mayor p95.
- El health check no mostró la misma degradación que los endpoints con datos.

### 9.2 Interpretación

La API conserva disponibilidad, pero su tiempo de respuesta se degrada al aumentar la concurrencia. El contraste entre el health check y los endpoints de datos indica que la mayor demora ocurre en el procesamiento de las operaciones de negocio, acceso a datos, construcción de respuestas o transferencia de payloads, no en la mera capacidad de aceptar una petición HTTP.

### 9.3 Hipótesis que requieren evidencia adicional

Las siguientes posibilidades son razonables, pero **no están demostradas por k6**:

- consultas SQL costosas o falta de índices;
- espera por conexiones de base de datos;
- serialización de colecciones grandes;
- falta de paginación;
- límites de CPU, memoria, workers o concurrencia del despliegue;
- cold starts o escalado de Render.

Para confirmar cualquiera de ellas se necesitan métricas de Render, logs de Flask, tiempos de queries, métricas de PostgreSQL y consumo de CPU/memoria durante una nueva ejecución.

---

## 10. Recomendaciones priorizadas

| Prioridad | Acción | Resultado esperado |
|---|---|---|
| Alta | Instrumentar tiempos de consulta, serialización y tamaño de respuesta por endpoint | Diferenciar demora de BD, aplicación y transferencia |
| Alta | Revisar y paginar `/api/transportista/historial` | Reducir el endpoint más lento desde carga normal |
| Alta | Cachear o segmentar `/api/localidades` | Evitar reconstruir y transferir el catálogo completo en cada request |
| Alta | Repetir cada perfil al menos tres veces después de los cambios | Confirmar que el resultado no depende de una ejecución aislada |
| Media | Analizar queries con `EXPLAIN ANALYZE` y revisar índices | Identificar scans y joins costosos |
| Media | Correlacionar k6 con CPU, RAM, workers y conexiones de BD | Confirmar o descartar agotamiento de recursos |
| Media | Revisar compresión HTTP y tamaño de payloads | Reducir tiempo de transferencia y serialización |
| Baja | Agregar spike y soak después de estabilizar 20–30 VU | Evaluar recuperación y estabilidad prolongada |

### Criterio sugerido para una nueva validación

La siguiente campaña debería considerarse exitosa si:

- mantiene 100% de disponibilidad o al menos 99% de éxito;
- conserva error rate < 1% y timeout rate < 1%;
- logra p95 global < 2.000 ms con 20 VU;
- mantiene cada endpoint por debajo de 5.000 ms con 30 VU;
- reduce especialmente el p95 de historial y localidades.

---

## 11. Limitaciones

- Se realizó una ejecución definitiva por perfil; no hay intervalos de confianza ni análisis de variabilidad.
- Los perfiles fueron cortos y conservadores.
- Se usó un modelo cerrado de VU; no se determinó throughput máximo con arrival rate.
- No se monitoreó CPU, RAM, workers, conexiones de BD ni logs durante las pruebas.
- No se ejecutaron spike, soak ni browser tests.
- La capacidad estimada solo aplica a los niveles 10, 20 y 30 VU evaluados.
- Los resultados dependen del volumen de datos asociado a las dos cuentas utilizadas.
- La prueba se ejecutó desde una única máquina generadora de carga.

---

## 12. Reproducción y evidencias

### Comandos

```powershell
.\performance\run.ps1 -Profile smoke
.\performance\run.ps1 -Profile load
.\performance\run.ps1 -Profile stress
```

### Evidencias utilizadas

| Perfil | Resumen objetivo | Informe legible |
|---|---|---|
| Smoke | `performance/results/2026-08-24T01-53-18Z-smoke-summary.json` | `performance/reports/2026-08-24T01-53-18Z-smoke-report.md` |
| Carga | `performance/results/2026-08-24T01-55-01Z-load-summary.json` | `performance/reports/2026-08-24T01-55-01Z-load-report.md` |
| Estrés | `performance/results/2026-08-24T01-56-35Z-stress-summary.json` | `performance/reports/2026-08-24T01-56-35Z-stress-report.md` |

El script reproducible se encuentra en `performance/k6/scripts/fletway-api.js`, con configuración central en `performance/k6/config/performance.config.js`.

---

## 13. Conclusión

Fletway superó satisfactoriamente la validación funcional y la carga normal conservadora. La API entregó respuestas correctas sin errores ni timeouts en toda la campaña. Sin embargo, la latencia aumenta de forma relevante a partir de 20 VU y supera el límite duro con 30 VU.

La recomendación es mantener el estado general en **ADVERTENCIA**, considerar **10 VU como capacidad estable observada** y optimizar los endpoints de historial y localidades antes de validar una capacidad superior. Una nueva campaña, repetida y acompañada por telemetría del backend, permitirá convertir estas observaciones en decisiones de capacidad y causas técnicas confirmadas.

**Fin del Informe General de Rendimiento — Fletway API**

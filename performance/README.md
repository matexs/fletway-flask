# Pruebas de rendimiento de Fletway

Suite k6 de solo lectura para validar la API con perfiles sencillos y reportes HTML, Markdown y JSON.

## Perfiles

| Perfil | Carga | Duración aproximada | Uso |
|---|---|---:|---|
| `smoke` | 1 → 3 VU | 40 s | Validar login, endpoints y configuración |
| `load` | 0 → 10 VU, sostenidos | 90 s | Representar carga normal conservadora |
| `stress` | 10, 20 y 30 VU | 105 s | Observar el primer escalón con degradación |
| `all` | Ejecuta los tres anteriores | 4 min | Generar el conjunto completo de reportes |

El estrés mide escalones independientes y no pretende encontrar un breakpoint definitivo.

## Configuración

1. Instale k6 en Windows:

   ```powershell
   winget install k6 --source winget
   ```

2. Copie `.env.performance.example` como `.env.performance` y complete las credenciales de prueba. El archivo real está ignorado por Git.

3. Ejecute primero el smoke:

   ```powershell
   .\performance\run.ps1 -Profile smoke
   ```

4. Si el smoke funciona, ejecute los demás perfiles:

   ```powershell
   .\performance\run.ps1 -Profile load
   .\performance\run.ps1 -Profile stress
   # o todos en secuencia
   .\performance\run.ps1 -Profile all
   ```

Puede cambiar el destino sin editar archivos:

```powershell
.\performance\run.ps1 -Profile smoke -BaseUrl http://127.0.0.1:5000
```

## Semáforo

- **APROBADA:** p95, éxito, errores y timeouts cumplen los objetivos recomendados.
- **ADVERTENCIA:** existe degradación moderada, pero la API continúa por encima de los límites duros.
- **NO EJECUTADA:** falló la prevalidación de disponibilidad, autenticación o roles; no hay muestras para evaluar.
- **FALLIDA:** durante la prueba, p95 ≥ 5000 ms, éxito ≤ 80%, errores ≥ 20% o timeouts ≥ 10%.

Los objetivos blandos generales son p95 < 2000 ms, éxito > 95%, errores < 5% y timeouts < 1%. Smoke usa p95 < 1000 ms, éxito > 99%, errores < 1% y cero timeouts.

La prevalidación tolera el arranque en frío de Render mediante `SETUP_REQUEST_TIMEOUT=60s`, tres intentos y una pausa de dos segundos. Este margen solo se usa antes de iniciar VUs; las solicitudes medidas conservan `REQUEST_TIMEOUT=10s`.

Los reportes nunca incluyen emails, contraseñas ni JWT. Los archivos generados quedan en `performance/reports/` y los resúmenes objetivos de k6 en `performance/results/`.

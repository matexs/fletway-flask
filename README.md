# fletway-flask

## Comandos

```bash
.\venv\Scripts\Activate.ps1
pip install flask_cors flask_sqlalchemy psycopg2-binary
python app.py
```

## Variables de Entorno Requeridas

Crear un archivo `.env` en la raíz del proyecto con las siguientes variables:

```env
# Base de datos
DATABASE_URL=postgresql://usuario:password@host:puerto/database

# Autenticación Supabase
SUPABASE_JWT_SECRET=tu_jwt_secret
JWT_AUD=authenticated

# Email (para notificaciones y reportes)
EMAIL_PASSWORD=tu_password_de_aplicacion_gmail

# Entorno
ENV=development  # o 'production' en producción
```

### Configuración de EMAIL_PASSWORD

Para obtener una contraseña de aplicación de Gmail:

1. Ir a tu cuenta de Google > Seguridad
2. Activar verificación en dos pasos
3. Ir a "Contraseñas de aplicaciones"
4. Generar una nueva contraseña para "Correo"
5. Copiar la contraseña generada en `EMAIL_PASSWORD`

**Nota**: El sistema envía correos automáticos al cliente cuando:

- Se crea una nueva solicitud
- Se acepta un presupuesto
- Comienza el viaje
- Se completa el viaje
- Se cancela la solicitud

## Entorno de pruebas de rendimiento

El directorio `performance/` contiene una suite de rendimiento de solo lectura
para la API, construida con Grafana k6. Incluye perfiles smoke, carga y estrés,
autenticación de los roles cliente/fletero y reportes Markdown, HTML y JSON.

### 1. Instalar k6

En Windows:

```powershell
winget install k6 --source winget
k6 version
```

### 2. Configurar el entorno

Copiar el archivo de ejemplo y completar valores exclusivos para pruebas:

```powershell
Copy-Item performance/.env.performance.example performance/.env.performance
```

Variables requeridas:

| Variable | Descripción |
|---|---|
| `BASE_URL` | Backend objetivo. El valor usado actualmente es `https://fletway.onrender.com` |
| `SUPABASE_URL` | URL del proyecto Supabase que autentica a Fletway |
| `SUPABASE_ANON_KEY` | Clave pública anon de Supabase |
| `CLIENT_EMAIL` / `CLIENT_PASSWORD` | Cuenta de prueba con datos de cliente |
| `DRIVER_EMAIL` / `DRIVER_PASSWORD` | Cuenta de prueba asociada a un transportista |
| `SEARCH_QUERY` | Texto utilizado en la búsqueda de localidades |
| `REQUEST_TIMEOUT` | Timeout de cada request; valor recomendado: `10s` |
| `SETUP_REQUEST_TIMEOUT` | Timeout exclusivo de preparación/cold start; recomendado: `60s` |
| `SETUP_MAX_ATTEMPTS` | Intentos de disponibilidad antes de cancelar; recomendado: `3` |
| `SETUP_RETRY_DELAY_SECONDS` | Pausa entre intentos de preparación; recomendado: `2` |
| `THINK_TIME_SECONDS` | Pausa entre requests por VU; valor recomendado: `1` |

`performance/.env.performance` está ignorado por Git. No se deben agregar
contraseñas, JWT ni claves privadas al README, scripts o reportes.

### 3. Perfiles disponibles

| Perfil | Carga | Duración aproximada | Objetivo |
|---|---|---:|---|
| `smoke` | 1 → 3 VU | 40 s | Validar backend, login, roles y endpoints |
| `load` | Hasta 10 VU | 90 s | Validar la carga normal conservadora |
| `stress` | 10, 20 y 30 VU | 105 s | Detectar el primer escalón con degradación |
| `all` | Ejecuta los tres perfiles | 4 min | Obtener el conjunto completo de resultados |

### 4. Ejecutar las pruebas

Ejecutar siempre smoke antes de aplicar carga adicional:

```powershell
.\performance\run.ps1 -Profile smoke
```

Si smoke finaliza correctamente:

```powershell
.\performance\run.ps1 -Profile load
.\performance\run.ps1 -Profile stress

# Ejecutar todos los perfiles en secuencia
.\performance\run.ps1 -Profile all
```

Para probar otro backend sin modificar el archivo de entorno:

```powershell
.\performance\run.ps1 -Profile smoke -BaseUrl http://127.0.0.1:5000
```

No ejecutar `load`, `stress` o `all` contra un entorno remoto sin autorización
del responsable del servicio.

### 5. Resultados y estados

La suite genera:

- `performance/reports/`: informes Markdown y HTML;
- `performance/results/`: resúmenes JSON objetivos de k6;
- `performance/informe-rendimiento-general-k6.md`: informe consolidado de la
  campaña validada.

Los archivos generados por cada ejecución están ignorados por Git. El informe
general y la configuración de la suite sí son versionables.

Estados utilizados:

- **APROBADA**: cumple los objetivos recomendados;
- **ADVERTENCIA**: existe degradación moderada, sin alcanzar el límite duro;
- **NO EJECUTADA**: falló la prevalidación de disponibilidad, autenticación o
  roles y no existen muestras para evaluar;
- **FALLIDA**: se alcanza un límite severo de latencia, errores, timeouts o
  respuestas inválidas durante la prueba.

La preparación usa un timeout independiente y reintentos para tolerar el arranque
en frío de Render. Esas solicitudes no forman parte de las métricas de negocio:
`REQUEST_TIMEOUT` continúa limitando cada request medido a 10 segundos.

La documentación completa de perfiles, thresholds y estructura está en
[`performance/README.md`](performance/README.md).

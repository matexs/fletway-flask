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

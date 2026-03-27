# Usa imagen oficial de Python 3.12 slim (liviana)
FROM python:3.12-slim

# Evita que Python escriba archivos .pyc y activa logs sin buffer
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Variables de entorno para producción
ENV ENV=production

# Directorio de trabajo dentro del contenedor
WORKDIR /app

# Instalar dependencias del sistema necesarias para eventlet y compilación
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias de Python primero (mejor uso de caché de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código fuente
COPY . .

# Crear carpeta uploads si no existe
RUN mkdir -p uploads

# Cloud Run inyecta el puerto via la variable PORT (por defecto 8080)
# gunicorn con worker eventlet para Flask-SocketIO
CMD exec gunicorn \
    --bind "0.0.0.0:${PORT:-8080}" \
    --worker-class eventlet \
    --workers 1 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    "app:socketio"

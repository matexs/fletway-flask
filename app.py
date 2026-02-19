"""
Módulo principal de la aplicación Flask.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env SOLO en desarrollo
if os.getenv("ENV") != "production":
    env_path = Path(__file__).parent / '.env'
    load_dotenv(dotenv_path=env_path)

from flask import Flask
from flask_cors import CORS
from extensions import socketio
from config import Config, db
from routes.solicitud_routes import solicitudes_bp
from routes.presupuesto_routes import presupuestos_bp
from routes.calificacion_routes import calificaciones_bp
from routes.localidad_routes import localidad_bp
from routes.reporte_routes import reporte_bp
from routes.fotos_routes import fotos_bp
# extensions.py (o donde tengas tu 'db')


# cors_allowed_origins="*" es crucial para desarrollo con Angular en otro puerto


app = Flask(__name__)
app.config.from_object(Config)
socketio.init_app(app)


base_dir = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(base_dir, 'uploads')

# 2. Crear la carpeta si no existe (En una sola línea)
# 'exist_ok=True' hace lo mismo que tu 'if not exists' pero más limpio
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 3. Configuración de Flask (Solo una vez)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB

# [CORS] Configuración CORS para rutas HTTP (Socket.IO tiene su propia configuración en extensions.py)
CORS(
    app,
    resources={
        r"/*": {
            "origins": [
                "http://localhost:4200",
                "http://127.0.0.1:4200",
                "https://fletway-api-533654897399.us-central1.run.app",
                "https://fletway.netlify.app",
            ],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
            "allow_headers": ["Content-Type", "Authorization"],
            "supports_credentials": True,
        }
    },
)

db.init_app(app)

# Blueprints
app.register_blueprint(solicitudes_bp)
app.register_blueprint(presupuestos_bp)
app.register_blueprint(calificaciones_bp)
app.register_blueprint(localidad_bp)
app.register_blueprint(reporte_bp)
app.register_blueprint(fotos_bp)


@app.route("/")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    print("[INIT] Iniciando servidor...")
    port = int(os.environ.get("PORT", 5000))
    print(f"[INIT] Ejecutando en puerto: {port}")
    print("[INIT] Servidor iniciado correctamente")
    socketio.run(app, host="127.0.0.1", port=port, debug=True)

    #app.run(debug=True, host="127.0.0.1", port=5000)
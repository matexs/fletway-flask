"""
Módulo principal de la aplicación Flask.
"""

import os

# Cargar .env SOLO en desarrollo
if os.getenv("ENV") != "production":
    from dotenv import load_dotenv
    load_dotenv()

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

CORS(
    app,
    resources={
        r"/*": {
            "origins": [
                "http://localhost:4200",
                "http://localhost:4200/",
                "https://fletway-api-533654897399.us-central1.run.app/",
                "https://fletway.netlify.app",  # opcional
            ],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
            "allow_headers": ["Content-Type", "Authorization"],
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
    socketio.run(app, debug=True)
    app.run(debug=True, host="127.0.0.1", port=5000)
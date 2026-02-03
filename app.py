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

from config import Config, db
from routes.usuario_routes import usuario_bp
from routes.solicitud_routes import solicitud_bp
from routes.transportista_routes import transportista_bp
from routes.presupuesto_routes import presupuesto_bp
from routes.calificacion_routes import calificacion_bp
from routes.localidad_routes import localidad_bp
from routes.reporte_routes import reporte_bp


UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config.from_object(Config)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5MB

CORS(
    app,
    resources={
        r"/*": {
            "origins": [
                "http://localhost:4200",
                "https://fletway-api-533654897399.us-central1.run.app/",  # opcional
            ],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
        }
    },
)

db.init_app(app)

# Blueprints
app.register_blueprint(usuario_bp)
app.register_blueprint(solicitud_bp)
app.register_blueprint(transportista_bp)
app.register_blueprint(presupuesto_bp)
app.register_blueprint(calificacion_bp)
app.register_blueprint(localidad_bp)
app.register_blueprint(reporte_bp)


@app.route("/")
def health():
    return {"status": "ok"}


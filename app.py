"""Módulo principal de la aplicación Flask. Aquí se inicializa la app y se definen las rutas."""
import os
from flask import Flask
from flask_cors import CORS
from config import Config, db
from routes.usuario_routes import usuario_bp
from routes.solicitud_routes import solicitud_bp
from routes.transportista_routes import transportista_bp
from routes.presupuesto_routes import presupuesto_bp
from routes.calificacion_routes import calificacion_bp
from routes.localidad_routes import localidad_bp

# Configuración de la carpeta de uploads
UPLOAD_FOLDER = 'uploads'

# CRÍTICO: Crear carpeta ANTES de inicializar Flask
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    print(f"✓ Carpeta '{UPLOAD_FOLDER}' creada exitosamente")

app = Flask(__name__)
app.config.from_object(Config)

# Agregar configuración de uploads a la app
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB máximo

# Habilitar CORS con configuración específica
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:4200"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

db.init_app(app)

# Registrar blueprints
app.register_blueprint(usuario_bp)
app.register_blueprint(solicitud_bp)
app.register_blueprint(transportista_bp)
app.register_blueprint(presupuesto_bp)
app.register_blueprint(calificacion_bp)
app.register_blueprint(localidad_bp)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    
    print("=" * 50)
    print("🚀 Servidor Flask iniciado")
    print(f"📁 Carpeta uploads: {os.path.abspath(UPLOAD_FOLDER)}")
    print("🌐 CORS habilitado para: http://localhost:4200")
    print("=" * 50)
    
    app.run(debug=True)
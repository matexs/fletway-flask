"""Módulo principal de la aplicación Flask. Aquí se inicializa la app y se definen las rutas."""

from flask import Flask
from config import Config, db
from models import Usuario, Solicitud, Transportista, Presupuesto, Calificacion, Localidad
from routes.usuario_routes import usuario_bp
from routes.solicitud_routes import solicitud_bp
from routes.transportista_routes import transportista_bp
from routes.presupuesto_routes import presupuesto_bp
from routes.calificacion_routes import calificacion_bp
from routes.localidad_routes import localidad_bp


app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

app.register_blueprint(usuario_bp)
app.register_blueprint(solicitud_bp)
app.register_blueprint(transportista_bp)
app.register_blueprint(presupuesto_bp)
app.register_blueprint(calificacion_bp)
app.register_blueprint(localidad_bp)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)

from flask import Blueprint, jsonify, request
from models import db, Usuario
from services import usuario_service

usuario_bp = Blueprint('usuario_bp', __name__)


# endpoints solo manejan request/response

@usuario_bp.route("/usuarios", methods=["GET"])
def obtener_usuarios():
    usuarios = Usuario.query.all()
    return jsonify([u.to_dict() for u in usuarios])


@usuario_bp.route("/usuarios/<int:id>", methods=["GET"])
def obtener_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    return jsonify(usuario.to_dict())

@usuario_bp.route("/usuarios", methods=["POST"])
def crear_usuario():
    data = request.get_json()
    nuevo = Usuario(nombre=data["nombre"], email=data["email"])
    db.session.add(nuevo)
    db.session.commit()
    return jsonify(nuevo.to_dict()), 201
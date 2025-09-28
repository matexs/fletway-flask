"""Rutas relacionadas con usuarios."""

from flask import Blueprint, jsonify, request
from services import usuario_service

usuario_bp = Blueprint("usuario_bp", __name__)

# Endpoints solo manejan request/response

@usuario_bp.route("/usuarios", methods=["GET"])
def obtener_usuarios():
    """Obtiene todos los usuarios."""
    usuarios = usuario_service.obtener_todos()
    return jsonify([u.to_dict() for u in usuarios])

@usuario_bp.route("/usuarios/<int:id_>", methods=["GET"])
def obtener_usuario(id_):
    """Obtiene un usuario por su ID."""
    usuario = usuario_service.obtener_por_id(id_)
    if not usuario:
        return jsonify({"error": "Usuario no encontrado"}), 404
    return jsonify(usuario.to_dict())

@usuario_bp.route("/usuarios", methods=["POST"])
def crear_usuario():
    """Crea un nuevo usuario."""
    data = request.get_json()
    try:
        nuevo_usuario = usuario_service.crear(data)
        return jsonify(nuevo_usuario.to_dict()), 201
    except KeyError as e:
        return jsonify({"error": f"Falta el campo {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

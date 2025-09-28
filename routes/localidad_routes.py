"""Rutas para los endpoints de las localidades."""

from flask import Blueprint, jsonify, request
from services import localidad_service

localidad_bp = Blueprint("localidad_bp", __name__)

# Endpoints solo manejan request/response

@localidad_bp.route("/localidades", methods=["GET"])
def obtener_localidades():
    """Obtiene todas las localidades."""
    localidades = localidad_service.obtener_todas()
    return jsonify([l.to_dict() for l in localidades])

@localidad_bp.route("/localidades/<int:id_>", methods=["GET"])
def obtener_localidad(id_):
    """Obtiene una localidad por su ID."""
    localidad = localidad_service.obtener_por_id(id_)
    if not localidad:
        return jsonify({"error": "Localidad no encontrada"}), 404
    return jsonify(localidad.to_dict())

@localidad_bp.route("/localidades", methods=["POST"])
def crear_localidad():
    """Crea una nueva localidad."""
    data = request.get_json()
    try:
        nueva_localidad = localidad_service.crear(data)
        return jsonify(nueva_localidad.to_dict()), 201
    except KeyError as e:
        return jsonify({"error": f"Falta el campo {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

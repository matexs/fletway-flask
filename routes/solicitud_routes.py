"""Rutas para los endpoints de las solicitudes."""

from flask import Blueprint, jsonify, request
from services import solicitud_service

solicitud_bp = Blueprint("solicitud_bp", __name__)

# Endpoints solo manejan request/response

@solicitud_bp.route("/solicitudes", methods=["GET"])
def obtener_solicitudes():
    """Obtiene todas las solicitudes."""
    solicitudes = solicitud_service.obtener_todas()
    return jsonify([s.to_dict() for s in solicitudes])

@solicitud_bp.route("/solicitudes/<int:id_>", methods=["GET"])
def obtener_solicitud(id_):
    """Obtiene una solicitud por su ID."""
    solicitud = solicitud_service.obtener_por_id(id_)
    if not solicitud:
        return jsonify({"error": "Solicitud no encontrada"}), 404
    return jsonify(solicitud.to_dict())

@solicitud_bp.route("/solicitudes", methods=["POST"])
def crear_solicitud():
    """Crea una nueva solicitud."""
    data = request.get_json()
    try:
        nueva_solicitud = solicitud_service.crear(data)
        return jsonify(nueva_solicitud.to_dict()), 201
    except KeyError as e:
        return jsonify({"error": f"Falta el campo {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

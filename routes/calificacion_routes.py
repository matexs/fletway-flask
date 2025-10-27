"""Rutas para los endpoints de las calificaciones."""

from flask import Blueprint, jsonify, request
from services import calificacion_service, solicitud_service

calificacion_bp = Blueprint("calificacion_bp", __name__)

# Endpoints solo manejan request/response

@calificacion_bp.route("/calificaciones", methods=["GET"])
def obtener_calificaciones():
    """Obtiene todas las calificaciones."""
    calificaciones = calificacion_service.obtener_todas()
    return jsonify([c.to_dict() for c in calificaciones])

@calificacion_bp.route("/calificaciones/<int:id_>", methods=["GET"])
def obtener_calificacion(id_):
    """Obtiene una calificación por su ID."""
    calificacion = calificacion_service.obtener_por_id(id_)
    if not calificacion:
        return jsonify({"error": "Calificación no encontrada"}), 404
    return jsonify(calificacion.to_dict())

@calificacion_bp.route("/calificaciones", methods=["POST"])
def crear_calificacion():
    """Crea una nueva calificación."""
    data = request.get_json()
    try:
        nueva = calificacion_service.crear(data)
        return jsonify(nueva.to_dict()), 201
    except KeyError as e:
        return jsonify({"error": f"Falta el campo {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@calificacion_bp.route("/solicitudes/sin-transportista/<int:id_localidad>", methods=["GET"])
def obtener_solicitudes_sin_transportista(id_localidad):
    """Obtiene todas las solicitudes sin transportista asignado para una localidad específica."""
    solicitudes = solicitud_service.obtener_solicitudes_sin_transportista(id_localidad)
    return jsonify([s.to_dict() for s in solicitudes])

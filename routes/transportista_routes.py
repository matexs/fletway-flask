"""Rutas para los endpoints de los transportistas."""

from flask import Blueprint, jsonify, request
from services import transportista_service

transportista_bp = Blueprint("transportista_bp", __name__)

# Endpoints solo manejan request/response

@transportista_bp.route("/transportistas", methods=["GET"])
def obtener_transportistas():
    """Obtiene todos los transportistas."""
    transportistas = transportista_service.obtener_todos()
    return jsonify([t.to_dict() for t in transportistas])

#@transportista_bp.route("/transportistas/<int:id>", methods=["GET"])
#def obtener_transportista(id):
#    transportista = transportista_service.obtener_por_id(id)
#    if not transportista:
#        return jsonify({"error": "Transportista no encontrado"}), 404
#    return jsonify(transportista.to_dict())

@transportista_bp.route("/transportistas", methods=["POST"])
def crear_transportista():
    """Crea un nuevo transportista."""
    data = request.get_json()
    try:
        nuevo_transportista = transportista_service.crear(data)
        return jsonify(nuevo_transportista.to_dict()), 201
    except KeyError as e:
        return jsonify({"error": f"Falta el campo {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@transportista_bp.route("/transportistas/<int:transportista_id>", methods=["GET"])
def obtener_transportista(transportista_id):
    """Obtiene un transportista por su ID."""
    transportista = transportista_service.obtener_transportista_by_id(transportista_id)
    if transportista:
        return jsonify(transportista), 200
    return jsonify({"error": "Transportista no encontrado"}), 404

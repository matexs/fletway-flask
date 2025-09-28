"""Rutas para los endpoints de los presupuestoss."""

from flask import Blueprint, jsonify, request
from services import presupuesto_service

presupuesto_bp = Blueprint("presupuesto_bp", __name__)

# Endpoints solo manejan request/response

@presupuesto_bp.route("/presupuestos", methods=["GET"])
def obtener_presupuestos():
    """Obtiene todos los presupuestos."""
    presupuestos = presupuesto_service.obtener_todos()
    return jsonify([p.to_dict() for p in presupuestos])

@presupuesto_bp.route("/presupuestos/<int:id>", methods=["GET"])
def obtener_presupuesto(id_):
    """Obtiene un presupuesto por su ID."""
    presupuesto = presupuesto_service.obtener_por_id(id_)
    if not presupuesto:
        return jsonify({"error": "Presupuesto no encontrado"}), 404
    return jsonify(presupuesto.to_dict())

@presupuesto_bp.route("/presupuestos", methods=["POST"])
def crear_presupuesto():
    """Crea un nuevo presupuesto."""
    data = request.get_json()
    try:
        nuevo_presupuesto = presupuesto_service.crear(data)
        return jsonify(nuevo_presupuesto.to_dict()), 201
    except KeyError as e:
        return jsonify({"error": f"Falta el campo {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# para obtener presupuestos por solicitud y estado pendiente
@presupuesto_bp.route("/presupuestos/solicitud", methods=["GET"])
def obtener_presupuestos_por_solicitud():
    """Obtiene presupuestos por ID de solicitud y estado."""
    solicitud_id = request.args.get("solicitud_id", type=int)
    estado = request.args.get("estado",default="pendiente", type=str)

    try:
        presupuestos = presupuesto_service.obtener_por_solicitud(solicitud_id, estado)
        return jsonify([p.to_dict() for p in presupuestos]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


#aceptar un presupuesto
@presupuesto_bp.route("/presupuestos/aceptar", methods=["PUT"])
def aceptar_presupuesto():
    """Acepta un presupuesto y rechaza los demás de la misma solicitud."""
    data = request.get_json()
    presupuesto_id = data.get("presupuesto_id")
    solicitud_id = data.get("solicitud_id")

    exito = presupuesto_service.aceptar_presupuesto(presupuesto_id, solicitud_id)
    if exito:
        return jsonify({"mensaje": "Presupuesto aceptado correctamente"}), 200
    return jsonify({"error": "Error al aceptar el presupuesto"}), 500

@presupuesto_bp.route("/presupuestos/rechazar", methods=["PUT"])
def rechazar_presupuesto():
    """Rechaza un presupuesto."""
    data = request.get_json()
    presupuesto_id = data.get("presupuesto_id")
    exito = presupuesto_service.rechazar_presupuesto(presupuesto_id)
    if exito:
        return jsonify({"mensaje": "Presupuesto rechazado correctamente"}), 200
    return jsonify({"error": "Error al rechazar el presupuesto"}), 500

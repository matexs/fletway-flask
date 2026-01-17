"""
Rutas para los endpoints de solicitudes.
"""
import os
from flask import Blueprint, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from services.solicitud_service import SolicitudService
from services.auth import require_auth

solicitud_bp = Blueprint("solicitud_bp", __name__)
solicitud_service = SolicitudService()

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


# =========================
# HELPERS
# =========================

def allowed_file(filename: str) -> bool:
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


# =========================
# SOLICITUDES
# =========================

@solicitud_bp.route("/solicitudes", methods=["GET"])
@require_auth
def obtener_solicitudes():
    """
    Obtiene solicitudes.
    Opcional: ?estado=pendiente | sin transportista | en viaje | completado
    """
    estado = request.args.get("estado")
    solicitudes = solicitud_service.obtener_todas(estado=estado)
    return jsonify([s.to_dict() for s in solicitudes]), 200


@solicitud_bp.route("/solicitudes/mias", methods=["GET"])
@require_auth
def obtener_solicitudes_mias():
    """
    Obtiene las solicitudes del usuario autenticado
    """
    solicitudes = solicitud_service.obtener_por_uid(request.uid)
    return jsonify([s.to_dict() for s in solicitudes]), 200


@solicitud_bp.route("/solicitudes/<int:solicitud_id>", methods=["GET"])
@require_auth
def obtener_solicitud(solicitud_id):
    solicitud = solicitud_service.obtener_por_id(solicitud_id, request.uid)
    if not solicitud:
        return jsonify({"error": "Solicitud no encontrada"}), 404
    return jsonify(solicitud.to_dict()), 200


@solicitud_bp.route("/solicitudes", methods=["POST"])
@require_auth
def crear_solicitud():
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON requerido"}), 400

    solicitud = solicitud_service.crear(data, request.uid)
    return jsonify(solicitud.to_dict()), 201


@solicitud_bp.route("/solicitudes/<int:solicitud_id>", methods=["PUT"])
@require_auth
def actualizar_solicitud(solicitud_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON requerido"}), 400

    solicitud = solicitud_service.actualizar(solicitud_id, data, request.uid)
    if not solicitud:
        return jsonify({"error": "Solicitud no encontrada"}), 404

    return jsonify(solicitud.to_dict()), 200


@solicitud_bp.route("/solicitudes/<int:solicitud_id>", methods=["DELETE"])
@require_auth
def eliminar_solicitud(solicitud_id):
    ok = solicitud_service.eliminar(solicitud_id, request.uid)
    if not ok:
        return jsonify({"error": "Solicitud no encontrada"}), 404
    return jsonify({"mensaje": "Solicitud eliminada correctamente"}), 200


# =========================
# ESTADO
# =========================

@solicitud_bp.route("/solicitudes/<int:solicitud_id>/estado", methods=["PUT"])
@require_auth
def cambiar_estado(solicitud_id):
    data = request.get_json()
    if not data or "estado" not in data:
        return jsonify({"error": "Campo 'estado' requerido"}), 400

    solicitud = solicitud_service.cambiar_estado(
        solicitud_id,
        data["estado"],
        request.uid
    )

    if not solicitud:
        return jsonify({"error": "Solicitud no encontrada"}), 404

    return jsonify(solicitud.to_dict()), 200


# =========================
# FOTOS
# =========================

@solicitud_bp.route("/solicitudes/<int:solicitud_id>/foto", methods=["POST"])
@require_auth
def subir_foto(solicitud_id):
    if "foto" not in request.files:
        return jsonify({"error": "Archivo 'foto' requerido"}), 400

    archivo = request.files["foto"]

    if archivo.filename == "":
        return jsonify({"error": "Nombre de archivo vacío"}), 400

    if not allowed_file(archivo.filename):
        return jsonify({
            "error": f"Tipo de archivo no permitido ({', '.join(ALLOWED_EXTENSIONS)})"
        }), 400

    filename = secure_filename(archivo.filename)

    solicitud = solicitud_service.guardar_foto(
        solicitud_id,
        archivo,
        filename,
        request.uid
    )

    if not solicitud:
        return jsonify({"error": "Solicitud no encontrada"}), 404

    return jsonify(solicitud.to_dict()), 200


@solicitud_bp.route("/uploads/<filename>", methods=["GET"])
def obtener_foto(filename):
    """
    Servir imágenes subidas.
    NO requiere auth (mejor cache y rendimiento)
    """
    return send_from_directory(UPLOAD_FOLDER, filename)

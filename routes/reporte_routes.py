from flask import Blueprint, request, jsonify
from services.auth import require_auth
from services import reporte_service
import traceback

reporte_bp = Blueprint("reporte_bp", __name__)

@reporte_bp.route('/enviar-reporte', methods=['POST'])
@require_auth
def enviar_reporte():
    data = request.json

    # 1. Extracción de datos
    usuario_id = data.get('usuario_id')
    solicitud_id = data.get('solicitud_id')
    motivo = data.get('motivo')
    mensaje = data.get('mensaje')

    # 2. Validación básica
    if not all([usuario_id, solicitud_id, motivo, mensaje]):
        return jsonify({"error": "Faltan datos obligatorios (usuario_id, solicitud_id, motivo, mensaje)"}), 400

    try:
        # 3. Llamada al Servicio
        resultado = reporte_service.crear_nuevo_reporte(
            usuario_id=usuario_id,
            solicitud_id=solicitud_id,
            motivo=motivo,
            mensaje_usuario=mensaje
        )

        reporte = resultado['reporte']
        email_status = "enviado" if resultado['email_enviado'] else "fallido"

        return jsonify({
            "message": "Reporte creado con éxito",
            "reporte_id": reporte.reporte_id,
            "estado_email": email_status
        }), 201

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Error interno al procesar el reporte: {str(e)}"}), 500


@reporte_bp.route('/mis-viajes-fletero', methods=['GET'])
@require_auth
def mis_viajes_fletero():
    try:
        supabase_uuid = request.uid
        viajes = reporte_service.obtener_viajes_fletero_por_uuid(supabase_uuid)
        # ✅ El servicio ya devuelve diccionarios serializados correctamente
        return jsonify(viajes), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@reporte_bp.route('/mis-pedidos-cliente', methods=['GET'])
@require_auth
def mis_pedidos_cliente():
    try:
        supabase_uuid = request.uid
        pedidos = reporte_service.obtener_pedidos_cliente_por_uuid(supabase_uuid)
        # ✅ El servicio ya devuelve diccionarios serializados correctamente
        return jsonify(pedidos), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
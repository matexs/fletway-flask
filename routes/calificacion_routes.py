"""Rutas para los endpoints de las calificaciones."""
from flask import Blueprint, jsonify, request
from sqlalchemy.orm import joinedload
from models import db, Usuario, Transportista, Solicitud, Calificacion
from services.auth import require_auth
from datetime import datetime
from extensions import socketio
import uuid
from sqlalchemy.dialects.postgresql import UUID

calificaciones_bp = Blueprint('calificaciones', __name__)

# ============================================
# 🔥 HELPER: EMITIR EVENTO DE ACTUALIZACIÓN
# ============================================
def emitir_evento_calificacion(evento='calificacion_creada', data=None):
    """
    Emite un evento de Socket.IO para notificar cambios relacionados con calificaciones
    """
    try:
        if data is None:
            data = {}

        print(f"📤 [Socket.IO-Calificaciones] Emitiendo evento: {evento}")
        print(f"   📦 Data: {data}")

        # Emitir a TODOS los clientes conectados
        socketio.emit(evento, data, broadcast=True)

        print(f"✅ [Socket.IO-Calificaciones] Evento {evento} emitido correctamente")
    except Exception as e:
        print(f"❌ [Socket.IO-Calificaciones] Error al emitir evento {evento}: {e}")


# ============================================
# ENDPOINT: CREAR CALIFICACIÓN
# ============================================
@calificaciones_bp.route('/api/calificaciones', methods=['POST'])
@require_auth
def crear_calificacion():
    """
    Crea una nueva calificación para un transportista.

    Body JSON:
    {
        "solicitud_id": 123,
        "transportista_id": 45,
        "puntuacion": 5,
        "comentario": "Excelente servicio" (opcional)
    }
    """
    current_uid = request.uid

    try:
        # 1. Obtener usuario actual (cliente)
        usuario = Usuario.query.filter_by(u_id=current_uid).first()
        if not usuario:
            return jsonify({"error": "Usuario no encontrado"}), 404

        print(f"⭐ [crear_calificacion] Usuario: {usuario.nombre} (ID: {usuario.usuario_id})")

        # 2. Validar datos de entrada
        data = request.get_json()

        solicitud_id = data.get('solicitud_id')
        transportista_id = data.get('transportista_id')
        puntuacion = data.get('puntuacion')
        comentario = data.get('comentario', '')

        if not all([solicitud_id, transportista_id, puntuacion]):
            return jsonify({"error": "Faltan datos requeridos"}), 400

        # Validar rango de puntuación
        if not (1 <= puntuacion <= 5):
            return jsonify({"error": "La puntuación debe estar entre 1 y 5"}), 400

        print(f"📝 [crear_calificacion] Datos: solicitud={solicitud_id}, transportista={transportista_id}, puntuacion={puntuacion}")

        # 3. Verificar que la solicitud existe y pertenece al usuario
        solicitud = Solicitud.query.get(solicitud_id)
        if not solicitud:
            return jsonify({"error": "Solicitud no encontrada"}), 404

        if solicitud.cliente_id != usuario.usuario_id:
            return jsonify({"error": "No tienes permiso para calificar esta solicitud"}), 403

        estado_valor = solicitud.estado.value if hasattr(solicitud.estado, 'value') else solicitud.estado
        # 4. Verificar que la solicitud está completada
        if estado_valor != 'completado':
            return jsonify({"error": "Solo puedes calificar solicitudes completadas"}), 400

        # 5. Verificar que no existe ya una calificación para esta solicitud
        calificacion_existente = Calificacion.query.filter_by(
            solicitud_id=solicitud_id,
            borrado_logico=False
        ).first()

        if calificacion_existente:
            return jsonify({"error": "Ya has calificado esta solicitud"}), 400

        # 6. Verificar que el transportista existe
        transportista = Transportista.query.get(transportista_id)
        if not transportista:
            return jsonify({"error": "Transportista no encontrado"}), 404

        print(f"✅ [crear_calificacion] Validaciones completadas")

        # 7. Crear la calificación
        nueva_calificacion = Calificacion(
            solicitud_id=solicitud_id,
            cliente_id=usuario.usuario_id,
            transportista_id=transportista_id,
            puntuacion=puntuacion,
            comentario=comentario,
            borrado_logico=False,
            creado_en=datetime.now(),
            actualizado_en=datetime.now()
        )

        db.session.add(nueva_calificacion)
        db.session.commit()

        print(f"✅ [crear_calificacion] Calificación creada: ID {nueva_calificacion.calificacion_id}")

        # 8. Obtener estadísticas actualizadas del transportista
        # El trigger de la base de datos ya actualizó calificacion_promedio y total_calificaciones
        db.session.refresh(transportista)

        estadisticas = {
            'calificacion_promedio': float(transportista.calificacion_promedio or 0),
            'total_calificaciones': transportista.total_calificaciones or 0,
        }

        print(f"📊 [crear_calificacion] Estadísticas actualizadas: {estadisticas}")

        # 9. Emitir eventos Socket.IO
        emitir_evento_calificacion('calificacion_creada', {
            'calificacion_id': nueva_calificacion.calificacion_id,
            'solicitud_id': solicitud_id,
            'transportista_id': transportista_id,
            'puntuacion': puntuacion,
            'cliente_id': usuario.usuario_id
        })

        emitir_evento_calificacion('transportista_actualizado', {
            'transportista_id': transportista_id,
            'estadisticas': estadisticas
        })

        # 10. Respuesta
        response = nueva_calificacion.to_dict()
        response['estadisticas_transportista'] = estadisticas

        return jsonify(response), 201

    except Exception as e:
        db.session.rollback()
        print(f"❌ [crear_calificacion] Error: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


# ============================================
# ENDPOINT: OBTENER ESTADÍSTICAS DE TRANSPORTISTA
# ============================================
@calificaciones_bp.route('/api/calificaciones/transportista/<int:transportista_id>/estadisticas', methods=['GET'])
def get_estadisticas_transportista(transportista_id):
    """
    Obtiene las estadísticas de calificación de un transportista.

    Retorna:
    {
        "transportista_id": 45,
        "calificacion_promedio": 4.5,
        "total_calificaciones": 10
    }
    """
    try:
        print(f"📊 [get_estadisticas] Transportista ID: {transportista_id}")

        # Obtener transportista
        transportista = Transportista.query.get(transportista_id)
        if not transportista:
            return jsonify({"error": "Transportista no encontrado"}), 404

        # Retornar estadísticas
        estadisticas = {
            'transportista_id': transportista_id,
            'calificacion_promedio': float(transportista.calificacion_promedio or 0),
            'total_calificaciones': transportista.total_calificaciones or 0,
        }

        print(f"✅ [get_estadisticas] Estadísticas: {estadisticas}")

        return jsonify(estadisticas), 200

    except Exception as e:
        print(f"❌ [get_estadisticas] Error: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


# ============================================
# ENDPOINT: OBTENER CALIFICACIONES DE UN TRANSPORTISTA
# ============================================
@calificaciones_bp.route('/api/calificaciones/transportista/<int:transportista_id>', methods=['GET'])
def get_calificaciones_transportista(transportista_id):
    """
    Obtiene todas las calificaciones de un transportista.

    Retorna lista de calificaciones con información del cliente.
    """
    try:
        print(f"📋 [get_calificaciones] Transportista ID: {transportista_id}")

        # Obtener calificaciones con joins
        calificaciones = Calificacion.query.options(
            joinedload(Calificacion.cliente),
            joinedload(Calificacion.solicitud)
        ).filter_by(
            transportista_id=transportista_id,
            borrado_logico=False
        ).order_by(Calificacion.creado_en.desc()).all()

        print(f"📊 [get_calificaciones] Calificaciones encontradas: {len(calificaciones)}")

        # Serializar con información del cliente
        resultado = []
        for cal in calificaciones:
            cal_dict = cal.to_dict()

            # Agregar información del cliente
            if cal.cliente:
                cal_dict['cliente'] = {
                    'usuario_id': cal.cliente.usuario_id,
                    'nombre': cal.cliente.nombre,
                    'apellido': cal.cliente.apellido,
                }

            resultado.append(cal_dict)

        print(f"✅ [get_calificaciones] Retornando {len(resultado)} calificaciones")

        return jsonify(resultado), 200

    except Exception as e:
        print(f"❌ [get_calificaciones] Error: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


# ============================================
# ENDPOINT: OBTENER CALIFICACIÓN DE UNA SOLICITUD
# ============================================
@calificaciones_bp.route('/api/calificaciones/solicitud/<int:solicitud_id>', methods=['GET'])
@require_auth
def get_calificacion_solicitud(solicitud_id):
    """
    Obtiene la calificación de una solicitud específica (si existe).
    """
    current_uid = request.uid

    try:
        print(f"📋 [get_calificacion_solicitud] Solicitud ID: {solicitud_id}")

        # Obtener usuario actual
        usuario = Usuario.query.filter_by(u_id=current_uid).first()
        if not usuario:
            return jsonify({"error": "Usuario no encontrado"}), 404

        # Obtener calificación
        calificacion = Calificacion.query.filter_by(
            solicitud_id=solicitud_id,
            borrado_logico=False
        ).first()

        if not calificacion:
            return jsonify({"error": "No hay calificación para esta solicitud"}), 404

        print(f"✅ [get_calificacion_solicitud] Calificación encontrada: ID {calificacion.calificacion_id}")

        return jsonify(calificacion.to_dict()), 200

    except Exception as e:
        print(f"❌ [get_calificacion_solicitud] Error: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


# ============================================
# ENDPOINT: VERIFICAR SI PUEDE CALIFICAR
# ============================================
"""
@calificaciones_bp.route('/api/calificaciones/puede-calificar/<int:solicitud_id>', methods=['GET'])
@require_auth
def puede_calificar(solicitud_id):


    current_uid = request.uid

    try:
        # Obtener usuario
        usuario = Usuario.query.filter_by(u_id=current_uid).first()
        if not usuario:
            return jsonify({"error": "Usuario no encontrado"}), 404

        # Obtener solicitud
        solicitud = Solicitud.query.get(solicitud_id)
        if not solicitud:
            return jsonify({
                "puede_calificar": False,
                "motivo": "Solicitud no encontrada"
            }), 404

        # Verificar que sea el cliente de la solicitud
        if solicitud.cliente_id != usuario.usuario_id:
            return jsonify({
                "puede_calificar": False,
                "motivo": "No eres el cliente de esta solicitud"
            }), 200

        # Verificar que esté completada
        if solicitud.estado != 'completado':
            return jsonify({
                "puede_calificar": False,
                "motivo": "La solicitud no está completada"
            }), 200

        # Verificar que no tenga ya una calificación
        calificacion_existente = Calificacion.query.filter_by(
            solicitud_id=solicitud_id,
            borrado_logico=False
        ).first()

        if calificacion_existente:
            return jsonify({
                "puede_calificar": False,
                "motivo": "Ya has calificado esta solicitud"
            }), 200

        # Todo OK, puede calificar
        return jsonify({
            "puede_calificar": True,
            "motivo": None
        }), 200

    except Exception as e:
        print(f"❌ [puede_calificar] Error: {e}")
        return jsonify({"error": str(e)}), 500

"""

@calificaciones_bp.route('/api/calificaciones/puede-calificar/<int:solicitud_id>', methods=['GET'])
@require_auth
def puede_calificar(solicitud_id):
    """
    Verifica si un usuario puede calificar una solicitud.
    """
    # 1. Obtenemos el UUID seguro desde el token (ej: "a54b-...")
    current_uid_auth = request.uid

    try:
        # 2. "Traducimos" el UUID de Auth al ID numérico de nuestra tabla Usuario
        usuario = Usuario.query.filter_by(u_id=current_uid_auth).first()

        if not usuario:
            return jsonify({"error": "Usuario no encontrado en la base de datos"}), 404

        # Ahora ya tenemos 'usuario.usuario_id' (ej: 1)

        # 3. Obtener solicitud
        solicitud = Solicitud.query.get(solicitud_id)
        if not solicitud:
            return jsonify({
                "puede_calificar": False,
                "motivo": "Solicitud no encontrada"
            }), 404

        # 4. Verificar que sea el cliente (Comparamos ID numérico con ID numérico)
        # solicitud.cliente_id es int (FK) | usuario.usuario_id es int (PK)
        if solicitud.cliente_id != usuario.usuario_id:
            return jsonify({
                "puede_calificar": False,
                "motivo": "No eres el cliente de esta solicitud"
            }), 200

        # 5. Verificar que esté completada (IGNORANDO MAYÚSCULAS Y ESPACIOS)
        # Esto soluciona el error "Solo puedes calificar solicitudes completadas"
        estado_actual = str(solicitud.estado or '').strip().lower()

        if estado_actual != 'completado':
            # Debug para ver qué está pasando si falla
            print(f"⚠️ Rechazado por estado. Estado actual en BD: '{solicitud.estado}'")
            return jsonify({
                "puede_calificar": False,
                "motivo": f"La solicitud no está completada (Estado actual: {solicitud.estado})"
            }), 200

        # 6. Verificar que no tenga ya una calificación activa
        calificacion_existente = Calificacion.query.filter_by(
            solicitud_id=solicitud_id,
            borrado_logico=False
        ).first()

        if calificacion_existente:
            return jsonify({
                "puede_calificar": False,
                "motivo": "Ya has calificado esta solicitud"
            }), 200

        # Todo OK, puede calificar
        return jsonify({
            "puede_calificar": True,
            "motivo": None
        }), 200

    except Exception as e:
        print(f"❌ [puede_calificar] Error crítico: {e}")
        return jsonify({"error": str(e)}), 500
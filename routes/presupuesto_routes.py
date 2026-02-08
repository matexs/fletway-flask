import os
from flask import Blueprint, jsonify, request, send_from_directory, current_app
from sqlalchemy import or_, text
from werkzeug.utils import secure_filename
from models import db, Usuario, Transportista, Solicitud, Presupuesto, EstadoPresupuesto, EstadoSolicitud
from services.auth import require_auth
from datetime import datetime
from sqlalchemy.orm import joinedload
from extensions import socketio


presupuestos_bp = Blueprint('presupuestos', __name__)

# ============================================
# 🔥 HELPER: EMITIR EVENTO DE ACTUALIZACIÓN
# ============================================
def emitir_actualizacion_presupuesto(evento='presupuestos_actualizados', data=None):
    """
    Emite un evento de Socket.IO para notificar cambios en presupuestos
    """
    try:
        if data is None:
            data = {}

        print(f"📤 [Socket.IO-Presupuestos] Emitiendo evento: {evento}")
        print(f"   📦 Data: {data}")

        # Emitir a TODOS los clientes conectados
        socketio.emit(evento, data, broadcast=True)

        print(f"✅ [Socket.IO-Presupuestos] Evento {evento} emitido correctamente")
    except Exception as e:
        print(f"❌ [Socket.IO-Presupuestos] Error al emitir evento {evento}: {e}")


# ============================================
# ENDPOINT: CREAR PRESUPUESTO
# ============================================
@presupuestos_bp.route('/api/presupuestos', methods=['POST'])
@require_auth
def crear_presupuesto():
    """
    Crear un nuevo presupuesto para una solicitud
    Body: { solicitud_id, precio_estimado, comentario }
    """
    current_uid = request.uid

    try:
        # 1. Obtener usuario actual
        usuario = Usuario.query.filter_by(u_id=current_uid).first()
        if not usuario:
            return jsonify({"error": "Usuario no encontrado"}), 404

        # 2. Verificar que es transportista
        transportista = Transportista.query.filter_by(usuario_id=usuario.usuario_id).first()
        if not transportista:
            return jsonify({"error": "No tienes permiso de transportista"}), 403

        print(f"💰 [crear_presupuesto] Transportista: {usuario.nombre} (ID: {transportista.transportista_id})")

        # 3. Obtener datos del request
        data = request.get_json()
        solicitud_id = data.get('solicitud_id')
        precio_estimado = data.get('precio_estimado')
        comentario = data.get('comentario', '')

        if not solicitud_id or precio_estimado is None:
            return jsonify({"error": "solicitud_id y precio_estimado son requeridos"}), 400

        # 4. Verificar que la solicitud existe
        solicitud = Solicitud.query.get(solicitud_id)
        if not solicitud:
            return jsonify({"error": "Solicitud no encontrada"}), 404

        # 5. Verificar que la solicitud está sin transportista
        # ✅ FIX: Comparar con ENUM
        if solicitud.estado != EstadoSolicitud.SIN_TRANSPORTISTA:
            return jsonify({"error": f"La solicitud ya tiene estado: {solicitud.estado.value}"}), 400

        # 6. Verificar que no haya presupuesto duplicado del mismo transportista
        # ✅ FIX: Comparar con ENUM
        presupuesto_existente = Presupuesto.query.filter_by(
            solicitud_id=solicitud_id,
            transportista_id=transportista.transportista_id,
            estado=EstadoPresupuesto.PENDIENTE
        ).first()

        if presupuesto_existente:
            return jsonify({"error": "Ya enviaste un presupuesto para esta solicitud"}), 400

        # 7. Crear nuevo presupuesto
        nuevo_presupuesto = Presupuesto(
            solicitud_id=solicitud_id,
            transportista_id=transportista.transportista_id,
            precio_estimado=precio_estimado,
            comentario=comentario,
            estado=EstadoPresupuesto.PENDIENTE,
            fecha_creacion=datetime.utcnow()
        )

        db.session.add(nuevo_presupuesto)
        db.session.commit()

        print(f"✅ [crear_presupuesto] Presupuesto creado: ID {nuevo_presupuesto.presupuesto_id}")

        # 8. 🔥 EMITIR EVENTO SOCKET.IO
        emitir_actualizacion_presupuesto('presupuesto_creado', {
            'presupuesto_id': nuevo_presupuesto.presupuesto_id,
            'solicitud_id': solicitud_id,
            'transportista_id': transportista.transportista_id
        })

        # 9. Retornar presupuesto creado con datos del transportista
        presupuesto_dict = nuevo_presupuesto.to_dict()

        return jsonify(presupuesto_dict), 201

    except Exception as e:
        db.session.rollback()
        print(f"❌ [crear_presupuesto] Error: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": "Error interno del servidor"}), 500


# ============================================
# ENDPOINT: OBTENER PRESUPUESTOS POR SOLICITUD
# ============================================
@presupuestos_bp.route('/api/presupuestos/solicitud/<int:solicitud_id>', methods=['GET'])
@require_auth
def get_presupuestos_by_solicitud(solicitud_id):
    """
    Obtener todos los presupuestos de una solicitud específica
    """
    current_uid = request.uid

    try:
        # 1. Verificar que el usuario tiene acceso a esta solicitud
        usuario = Usuario.query.filter_by(u_id=current_uid).first()
        if not usuario:
            return jsonify({"error": "Usuario no encontrado"}), 404

        # 2. Verificar que la solicitud existe
        solicitud = Solicitud.query.get(solicitud_id)
        if not solicitud:
            return jsonify({"error": "Solicitud no encontrada"}), 404

        # 3. Verificar permisos (solo el cliente o transportistas pueden ver)
        es_cliente = solicitud.cliente_id == usuario.usuario_id
        transportista = Transportista.query.filter_by(usuario_id=usuario.usuario_id).first()
        es_transportista = transportista is not None

        if not (es_cliente or es_transportista):
            return jsonify({"error": "No tienes permiso para ver estos presupuestos"}), 403

        print(f"🔍 [get_presupuestos] Solicitud: {solicitud_id}, Usuario: {usuario.nombre}")

        # 4. Obtener presupuestos con eager loading
        presupuestos = Presupuesto.query.options(
            joinedload(Presupuesto.transportista).joinedload(Transportista.usuario)
        ).filter_by(
            solicitud_id=solicitud_id
        ).order_by(Presupuesto.fecha_creacion.desc()).all()

        print(f"📦 [get_presupuestos] Presupuestos encontrados: {len(presupuestos)}")

        # 5. Serializar con datos del transportista
        resultado = []
        for p in presupuestos:
            p_dict = p.to_dict()
            print(f"   💰 Presupuesto {p.presupuesto_id}: estado={p.estado}, precio=${p.precio_estimado}")
            resultado.append(p_dict)

        print(f"✅ [get_presupuestos] Retornando {len(resultado)} presupuestos")
        return jsonify(resultado), 200

    except Exception as e:
        print(f"❌ [get_presupuestos] Error: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": "Error interno del servidor"}), 500


# ============================================
# ENDPOINT: RESUMEN DE PRESUPUESTOS
# ============================================
@presupuestos_bp.route('/api/presupuestos/resumen/<int:solicitud_id>', methods=['GET'])
@require_auth
def get_resumen_presupuestos(solicitud_id):
    """
    Obtener resumen de presupuestos (conteos por estado)
    """
    try:
        presupuestos = Presupuesto.query.filter_by(solicitud_id=solicitud_id).all()

        total = len(presupuestos)

        # ✅ FIX: Comparar con ENUM correctamente
        pendientes = sum(1 for p in presupuestos if p.estado == EstadoPresupuesto.PENDIENTE)
        aceptados = sum(1 for p in presupuestos if p.estado == EstadoPresupuesto.ACEPTADO)
        rechazados = sum(1 for p in presupuestos if p.estado == EstadoPresupuesto.RECHAZADO)

        print(f"📊 [resumen] Solicitud {solicitud_id}: Total={total}, Pendientes={pendientes}, Aceptados={aceptados}, Rechazados={rechazados}")

        return jsonify({
            'total': total,
            'pendientes': pendientes,
            'aceptados': aceptados,
            'rechazados': rechazados
        }), 200

    except Exception as e:
        print(f"❌ [get_resumen_presupuestos] Error: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": "Error interno del servidor"}), 500


# ============================================
# ENDPOINT: ACEPTAR PRESUPUESTO
# ============================================
@presupuestos_bp.route('/api/presupuestos/<int:presupuesto_id>/aceptar', methods=['POST'])
@require_auth
def aceptar_presupuesto(presupuesto_id):
    """
    Aceptar un presupuesto (solo el cliente puede hacerlo)
    """
    current_uid = request.uid

    try:
        # 1. Obtener usuario actual
        usuario = Usuario.query.filter_by(u_id=current_uid).first()
        if not usuario:
            return jsonify({"error": "Usuario no encontrado"}), 404

        # 2. Obtener presupuesto
        presupuesto = Presupuesto.query.get(presupuesto_id)
        if not presupuesto:
            return jsonify({"error": "Presupuesto no encontrado"}), 404

        # 3. Obtener solicitud
        solicitud = Solicitud.query.get(presupuesto.solicitud_id)
        if not solicitud:
            return jsonify({"error": "Solicitud no encontrada"}), 404

        # 4. Verificar que el usuario es el cliente de la solicitud
        if solicitud.cliente_id != usuario.usuario_id:
            return jsonify({"error": "Solo el cliente puede aceptar presupuestos"}), 403

        # 5. Verificar que la solicitud está sin transportista
        # ✅ FIX: Comparar con ENUM
        if solicitud.estado != EstadoSolicitud.SIN_TRANSPORTISTA:
            return jsonify({"error": f"La solicitud ya tiene estado: {solicitud.estado.value}"}), 400

        print(f"✅ [aceptar_presupuesto] Usuario: {usuario.nombre}, Presupuesto: {presupuesto_id}")

        # 6. Rechazar todos los otros presupuestos de esta solicitud
        # ✅ FIX: Usar ENUM para actualizar
        Presupuesto.query.filter(
            Presupuesto.solicitud_id == presupuesto.solicitud_id,
            Presupuesto.presupuesto_id != presupuesto_id
        ).update({'estado': EstadoPresupuesto.RECHAZADO}, synchronize_session=False)

        # 7. Aceptar el presupuesto seleccionado
        presupuesto.estado = EstadoPresupuesto.ACEPTADO

        # 8. Actualizar solicitud: asignar presupuesto aceptado y cambiar estado
        solicitud.presupuesto_aceptado = presupuesto_id
        solicitud.estado = EstadoSolicitud.PENDIENTE

        db.session.commit()

        print(f"✅ [aceptar_presupuesto] Presupuesto {presupuesto_id} aceptado para solicitud {solicitud.solicitud_id}")

        # 9. 🔥 EMITIR EVENTO SOCKET.IO
        emitir_actualizacion_presupuesto('presupuesto_aceptado', {
            'presupuesto_id': presupuesto_id,
            'solicitud_id': presupuesto.solicitud_id,
            'transportista_id': presupuesto.transportista_id
        })

        # También emitir evento de solicitud actualizada (para sincronizar con otros componentes)
        try:
            from solicitud_routes import emitir_actualizacion
            emitir_actualizacion('solicitud_actualizada', {
                'solicitud_id': solicitud.solicitud_id
            })
        except ImportError:
            print("⚠️ No se pudo importar emitir_actualizacion de solicitud_routes")

        return jsonify({
            "message": "Presupuesto aceptado correctamente",
            "presupuesto": presupuesto.to_dict(),
            "solicitud": solicitud.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"❌ [aceptar_presupuesto] Error: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": "Error interno del servidor"}), 500


# ============================================
# ENDPOINT: RECHAZAR PRESUPUESTO
# ============================================
@presupuestos_bp.route('/api/presupuestos/<int:presupuesto_id>/rechazar', methods=['POST'])
@require_auth
def rechazar_presupuesto(presupuesto_id):
    """
    Rechazar un presupuesto (solo el cliente puede hacerlo)
    """
    current_uid = request.uid

    try:
        # 1. Obtener usuario actual
        usuario = Usuario.query.filter_by(u_id=current_uid).first()
        if not usuario:
            return jsonify({"error": "Usuario no encontrado"}), 404

        # 2. Obtener presupuesto
        presupuesto = Presupuesto.query.get(presupuesto_id)
        if not presupuesto:
            return jsonify({"error": "Presupuesto no encontrado"}), 404

        # 3. Obtener solicitud
        solicitud = Solicitud.query.get(presupuesto.solicitud_id)
        if not solicitud:
            return jsonify({"error": "Solicitud no encontrada"}), 404

        # 4. Verificar que el usuario es el cliente de la solicitud
        if solicitud.cliente_id != usuario.usuario_id:
            return jsonify({"error": "Solo el cliente puede rechazar presupuestos"}), 403

        print(f"❌ [rechazar_presupuesto] Usuario: {usuario.nombre}, Presupuesto: {presupuesto_id}")

        # 5. Rechazar el presupuesto
        # ✅ FIX: Usar ENUM
        presupuesto.estado = EstadoPresupuesto.RECHAZADO
        db.session.commit()

        print(f"✅ [rechazar_presupuesto] Presupuesto {presupuesto_id} rechazado")

        # 6. 🔥 EMITIR EVENTO SOCKET.IO
        emitir_actualizacion_presupuesto('presupuesto_rechazado', {
            'presupuesto_id': presupuesto_id,
            'solicitud_id': presupuesto.solicitud_id,
            'transportista_id': presupuesto.transportista_id
        })

        return jsonify({
            "message": "Presupuesto rechazado correctamente",
            "presupuesto": presupuesto.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"❌ [rechazar_presupuesto] Error: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": "Error interno del servidor"}), 500


# ============================================
# ENDPOINT: OBTENER INFORMACIÓN DEL TRANSPORTISTA
# ============================================
@presupuestos_bp.route('/api/transportistas/<int:transportista_id>', methods=['GET'])
@require_auth
def get_transportista_by_id(transportista_id):
    """
    Obtener información completa de un transportista
    """
    try:
        # 1. Obtener transportista con eager loading
        transportista = Transportista.query.options(
            joinedload(Transportista.usuario),
            joinedload(Transportista.localidades)
        ).get(transportista_id)

        if not transportista:
            return jsonify({"error": "Transportista no encontrado"}), 404

        # 2. Serializar
        transportista_dict = transportista.to_dict()

        return jsonify(transportista_dict), 200

    except Exception as e:
        print(f"❌ [get_transportista_by_id] Error: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": "Error interno del servidor"}), 500


# ============================================
# ENDPOINT: MIS PRESUPUESTOS (TRANSPORTISTA)
# ============================================
@presupuestos_bp.route('/api/presupuestos/mis-presupuestos', methods=['GET'])
@require_auth
def get_mis_presupuestos():
    """
    Obtener todos los presupuestos del transportista actual
    """
    current_uid = request.uid

    try:
        # 1. Obtener usuario actual
        usuario = Usuario.query.filter_by(u_id=current_uid).first()
        if not usuario:
            return jsonify({"error": "Usuario no encontrado"}), 404

        # 2. Verificar que es transportista
        transportista = Transportista.query.filter_by(usuario_id=usuario.usuario_id).first()
        if not transportista:
            return jsonify({"error": "No tienes permiso de transportista"}), 403

        print(f"📋 [get_mis_presupuestos] Transportista: {usuario.nombre} (ID: {transportista.transportista_id})")

        # 3. Obtener presupuestos del transportista
        presupuestos = Presupuesto.query.filter_by(
            transportista_id=transportista.transportista_id
        ).order_by(Presupuesto.fecha_creacion.desc()).all()

        print(f"📦 [get_mis_presupuestos] Presupuestos encontrados: {len(presupuestos)}")

        # 4. Serializar
        resultado = [p.to_dict() for p in presupuestos]

        return jsonify(resultado), 200

    except Exception as e:
        print(f"❌ [get_mis_presupuestos] Error: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": "Error interno del servidor"}), 500


# ============================================
# ENDPOINT: ELIMINAR PRESUPUESTO (TRANSPORTISTA)
# ============================================
@presupuestos_bp.route('/api/presupuestos/<int:presupuesto_id>', methods=['DELETE'])
@require_auth
def eliminar_presupuesto(presupuesto_id):
    """
    Eliminar un presupuesto propio (solo si está pendiente)
    """
    current_uid = request.uid

    try:
        # 1. Obtener usuario actual
        usuario = Usuario.query.filter_by(u_id=current_uid).first()
        if not usuario:
            return jsonify({"error": "Usuario no encontrado"}), 404

        # 2. Verificar que es transportista
        transportista = Transportista.query.filter_by(usuario_id=usuario.usuario_id).first()
        if not transportista:
            return jsonify({"error": "No tienes permiso de transportista"}), 403

        # 3. Obtener presupuesto
        presupuesto = Presupuesto.query.get(presupuesto_id)
        if not presupuesto:
            return jsonify({"error": "Presupuesto no encontrado"}), 404

        # 4. Verificar que el presupuesto pertenece al transportista
        if presupuesto.transportista_id != transportista.transportista_id:
            return jsonify({"error": "No tienes permiso para eliminar este presupuesto"}), 403

        # 5. Verificar que está pendiente
        # ✅ FIX: Comparar con ENUM
        if presupuesto.estado != EstadoPresupuesto.PENDIENTE:
            return jsonify({"error": f"No se puede eliminar un presupuesto {presupuesto.estado.value}"}), 400

        solicitud_id = presupuesto.solicitud_id

        # 6. Eliminar presupuesto
        db.session.delete(presupuesto)
        db.session.commit()

        print(f"✅ [eliminar_presupuesto] Presupuesto {presupuesto_id} eliminado")

        # 7. 🔥 EMITIR EVENTO SOCKET.IO
        emitir_actualizacion_presupuesto('presupuesto_eliminado', {
            'presupuesto_id': presupuesto_id,
            'solicitud_id': solicitud_id,
            'transportista_id': transportista.transportista_id
        })

        return jsonify({"message": "Presupuesto eliminado correctamente"}), 200

    except Exception as e:
        db.session.rollback()
        print(f"❌ [eliminar_presupuesto] Error: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": "Error interno del servidor"}), 500


# ============================================
# ENDPOINT: ACTUALIZAR PRESUPUESTO (TRANSPORTISTA)
# ============================================
@presupuestos_bp.route('/api/presupuestos/<int:presupuesto_id>', methods=['PUT'])
@require_auth
def actualizar_presupuesto(presupuesto_id):
    """
    Actualizar precio o comentario de un presupuesto propio (solo si está pendiente)
    """
    current_uid = request.uid

    try:
        # 1. Obtener usuario actual
        usuario = Usuario.query.filter_by(u_id=current_uid).first()
        if not usuario:
            return jsonify({"error": "Usuario no encontrado"}), 404

        # 2. Verificar que es transportista
        transportista = Transportista.query.filter_by(usuario_id=usuario.usuario_id).first()
        if not transportista:
            return jsonify({"error": "No tienes permiso de transportista"}), 403

        # 3. Obtener presupuesto
        presupuesto = Presupuesto.query.get(presupuesto_id)
        if not presupuesto:
            return jsonify({"error": "Presupuesto no encontrado"}), 404

        # 4. Verificar que el presupuesto pertenece al transportista
        if presupuesto.transportista_id != transportista.transportista_id:
            return jsonify({"error": "No tienes permiso para editar este presupuesto"}), 403

        # 5. Verificar que está pendiente
        # ✅ FIX: Comparar con ENUM
        if presupuesto.estado != EstadoPresupuesto.PENDIENTE:
            return jsonify({"error": f"No se puede editar un presupuesto {presupuesto.estado.value}"}), 400

        # 6. Obtener datos del request
        data = request.get_json()

        if 'precio_estimado' in data:
            presupuesto.precio_estimado = data['precio_estimado']

        if 'comentario' in data:
            presupuesto.comentario = data['comentario']

        db.session.commit()

        print(f"✅ [actualizar_presupuesto] Presupuesto {presupuesto_id} actualizado")

        # 7. 🔥 EMITIR EVENTO SOCKET.IO
        emitir_actualizacion_presupuesto('presupuesto_actualizado', {
            'presupuesto_id': presupuesto_id,
            'solicitud_id': presupuesto.solicitud_id,
            'transportista_id': transportista.transportista_id
        })

        return jsonify({
            "message": "Presupuesto actualizado correctamente",
            "presupuesto": presupuesto.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"❌ [actualizar_presupuesto] Error: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": "Error interno del servidor"}), 500

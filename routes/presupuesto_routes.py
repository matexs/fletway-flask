import os
from flask import Blueprint, jsonify, request, send_from_directory, current_app
from sqlalchemy import or_, text,func,case
from werkzeug.utils import secure_filename
from models import db, Usuario, Transportista, Solicitud, Presupuesto, EstadoPresupuesto, EstadoSolicitud
from services.auth import require_auth
from datetime import datetime
from sqlalchemy.orm import joinedload
from extensions import socketio


presupuestos_bp = Blueprint('presupuestos', __name__)



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

        ##### OBTENER DATOS COMPLETOS DEL PRESUPUESTO CON TRANSPORTISTA PARA EMITIR EN EL EVENTO
        presupuesto_completo = nuevo_presupuesto.to_dict()
        presupuesto_completo['transportista'] = {
            'transportista_id': transportista.transportista_id,
            'calificacion_promedio': float(transportista.calificacion_promedio or 0),
            'total_calificaciones': transportista.total_calificaciones or 0,
            'usuario': {
                'usuario_id': transportista.usuario.usuario_id,
                'nombre': transportista.usuario.nombre,
                'apellido': transportista.usuario.apellido,
                'telefono': transportista.usuario.telefono,
                'email': transportista.usuario.email,
            } if transportista.usuario else None
        }

        # 8. 🔥 EMITIR EVENTO SOCKET.IO
        socketio.emit('nuevo_presupuesto', presupuesto_completo)

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
        if solicitud.estado != EstadoSolicitud.SIN_TRANSPORTISTA:
            return jsonify({"error": f"La solicitud ya tiene estado: {solicitud.estado.value}"}), 400

        print(f"✅ [aceptar_presupuesto] Usuario: {usuario.nombre}, Presupuesto: {presupuesto_id}")

        # 6. Rechazar todos los otros presupuestos de esta solicitud
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

        # ========================================
        # ✅ NUEVO: Cargar presupuesto con transportista para el socket
        # ========================================

        # Refrescar el presupuesto desde la BD con sus relaciones cargadas
        presupuesto_ganador = Presupuesto.query.options(
            joinedload(Presupuesto.transportista).joinedload(Transportista.usuario)
        ).get(presupuesto_id)

        # Construir objeto completo para el socket
        solicitud_data = solicitud.to_dict()

        # ✅ AGREGAR: Presupuesto ganador completo con transportista
        solicitud_data['presupuesto'] = {
            'presupuesto_id': presupuesto_ganador.presupuesto_id,
            'transportista_id': presupuesto_ganador.transportista_id,
            'precio_estimado': presupuesto_ganador.precio_estimado,
            'comentario': presupuesto_ganador.comentario,
            'estado': 'aceptado',
            'fecha_creacion': presupuesto_ganador.fecha_creacion.isoformat() if presupuesto_ganador.fecha_creacion else None,
            'transportista': {
                'transportista_id': presupuesto_ganador.transportista.transportista_id,
                'calificacion_promedio': float(presupuesto_ganador.transportista.calificacion_promedio or 0),
                'total_calificaciones': presupuesto_ganador.transportista.total_calificaciones or 0,
                'usuario': {
                    'usuario_id': presupuesto_ganador.transportista.usuario.usuario_id,
                    'nombre': presupuesto_ganador.transportista.usuario.nombre,
                    'apellido': presupuesto_ganador.transportista.usuario.apellido,
                    'telefono': presupuesto_ganador.transportista.usuario.telefono,
                    'email': presupuesto_ganador.transportista.usuario.email,
                } if presupuesto_ganador.transportista.usuario else None
            } if presupuesto_ganador.transportista else None
        }

        # 9. 🔥 EMITIR EVENTO SOCKET.IO CON DATOS COMPLETOS
        print(f"🔥 [Socket] Emitiendo 'aceptar_solicitud' con presupuesto completo")
        socketio.emit('aceptar_solicitud', solicitud_data)

        # 10. También emitir evento de solicitud actualizada (para el SolicitudService)
        try:
            from solicitud_routes import emitir_actualizacion
            emitir_actualizacion('solicitud_actualizada', {
                'solicitud_id': solicitud.solicitud_id
            })
        except ImportError:
            print("⚠️ No se pudo importar emitir_actualizacion de solicitud_routes")

        return jsonify({
            "message": "Presupuesto aceptado correctamente",
            "presupuesto": presupuesto_ganador.to_dict(),
            "solicitud": solicitud_data  # ✅ Retornar con datos completos
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



@presupuestos_bp.route('/api/presupuestos/resumenes-batch', methods=['POST'])
@require_auth
def get_resumenes_batch():
    """
    Obtiene resúmenes de MÚLTIPLES solicitudes en UNA SOLA consulta.

    Body: {"solicitud_ids": [60, 61, 62, ...]}

    Returns: {
        "60": {"total": 1, "pendientes": 0, "aceptados": 1, "rechazados": 0},
        "61": {"total": 1, "pendientes": 0, "aceptados": 1, "rechazados": 0},
        ...
    }

    Reduce: 19 requests → 1 request ✅
    """
    current_uid = request.uid

    try:
        usuario = Usuario.query.filter_by(u_id=current_uid).first()
        if not usuario:
            return jsonify({"error": "Usuario no encontrado"}), 404

        data = request.get_json()
        solicitud_ids = data.get('solicitud_ids', [])

        if not solicitud_ids:
            return jsonify({}), 200

        print(f"📦 [batch_resumenes] Procesando {len(solicitud_ids)} solicitudes en UNA consulta")

        # ✅ UNA SOLA CONSULTA con GROUP BY
        resumenes = db.session.query(
            Presupuesto.solicitud_id,
            func.count(Presupuesto.presupuesto_id).label('total'),
            func.sum(case((Presupuesto.estado == EstadoPresupuesto.PENDIENTE, 1), else_=0)).label('pendientes'),
            func.sum(case((Presupuesto.estado == EstadoPresupuesto.ACEPTADO, 1), else_=0)).label('aceptados'),
            func.sum(case((Presupuesto.estado == EstadoPresupuesto.RECHAZADO, 1), else_=0)).label('rechazados')
        ).filter(
            Presupuesto.solicitud_id.in_(solicitud_ids),
            Presupuesto.borrado_logico == False
        ).group_by(Presupuesto.solicitud_id).all()

        # Inicializar todos con 0
        resultado = {str(sid): {'total': 0, 'pendientes': 0, 'aceptados': 0, 'rechazados': 0}
                    for sid in solicitud_ids}

        # Llenar con datos reales
        for row in resumenes:
            resultado[str(row.solicitud_id)] = {
                'total': int(row.total or 0),
                'pendientes': int(row.pendientes or 0),
                'aceptados': int(row.aceptados or 0),
                'rechazados': int(row.rechazados or 0)
            }

        print(f"✅ [batch_resumenes] Retornando {len(resultado)} resúmenes")
        return jsonify(resultado), 200

    except Exception as e:
        print(f"❌ [batch_resumenes] Error: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


# Necesito listar los presupuestos
# dasdas
@presupuestos_bp.route('/api/presupuestos/completo-batch', methods=['GET'])
@require_auth
def get_presupuestos_completo_batch():

    current_uid = request.uid

    try:
        usuario = Usuario.query.filter_by(u_id=current_uid).first()
        if not usuario:
            return jsonify({"error": "Usuario no encontrado"}), 404

        interna_user_id = usuario.usuario_id


        mis_solicitudes = Solicitud.query.with_entities(Solicitud.solicitud_id)\
            .filter_by(cliente_id=interna_user_id, borrado_logico=False)\
            .all()

        # Esto devuelve una lista de tuplas [(1,), (2,), (5,)] -> Lo pasamos a lista simple [1, 2, 5]
        solicitud_ids = [s.solicitud_id for s in mis_solicitudes]

        if not solicitud_ids:
            return jsonify({}), 200

        print(f"📦 [mis_presupuestos] Usuario {current_uid} tiene {len(solicitud_ids)} solicitudes. Buscando presupuestos...")


        presupuestos = Presupuesto.query.options(
            joinedload(Presupuesto.transportista).joinedload(Transportista.usuario)
        ).filter(
            Presupuesto.solicitud_id.in_(solicitud_ids),
           # Presupuesto.borrado_logico == False
        ).order_by(
            Presupuesto.solicitud_id,
            Presupuesto.fecha_creacion.desc()
        ).all()

        # Agrupar por solicitud_id
        resultado = {str(sid): [] for sid in solicitud_ids}

        for p in presupuestos:
            sol_id = str(p.solicitud_id)
            if sol_id in resultado:
                presupuesto_dict = p.to_dict()

                # Incluir transportista
                if p.transportista:
                    presupuesto_dict['transportista'] = {
                        'transportista_id': p.transportista.transportista_id,
                        'calificacion_promedio': float(p.transportista.calificacion_promedio or 0),
                        'total_calificaciones': p.transportista.total_calificaciones or 0,
                        'usuario': {
                            'usuario_id': p.transportista.usuario.usuario_id,
                            'nombre': p.transportista.usuario.nombre,
                            'apellido': p.transportista.usuario.apellido,
                            'telefono': p.transportista.usuario.telefono,
                            'email': p.transportista.usuario.email,
                        } if p.transportista.usuario else None
                    }

                resultado[sol_id].append(presupuesto_dict)

        print(f"✅ [batch_completo] Retornando {len(presupuestos)} presupuestos agrupados")
        return jsonify(resultado), 200

    except Exception as e:
        print(f"❌ [batch_completo] Error: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500
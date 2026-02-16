import os
from flask import Blueprint, jsonify, request, send_from_directory, current_app
from sqlalchemy import or_, text
from werkzeug.utils import secure_filename
from models import db, Usuario,EstadoPresupuesto, Calificacion,Transportista, Solicitud, Foto, Presupuesto, EstadoSolicitud, transportista_localidad
from services.auth import require_auth
from datetime import datetime
from sqlalchemy.orm import joinedload
from extensions import socketio

solicitudes_bp = Blueprint('solicitudes', __name__)




# ============================================
# ENDPOINT: MIS PEDIDOS (CLIENTE)
# ============================================
@solicitudes_bp.route('/api/solicitudes/mis-pedidos', methods=['GET'])
@require_auth
def get_solicitudes_usuario():
    current_uid = request.uid

    print(f"🔍 [mis-pedidos] Usuario UID: {current_uid}")

    try:
        # 1. Obtener usuario
        usuario = Usuario.query.filter_by(u_id=current_uid).first()
        if not usuario:
            print(f"⚠️ [mis-pedidos] Usuario no encontrado: {current_uid}")
            return jsonify([]), 200

        print(f"✅ [mis-pedidos] Usuario: {usuario.nombre} (ID: {usuario.usuario_id})")

        # 2. Consultar solicitudes con eager loading
        solicitudes = Solicitud.query.options(
            joinedload(Solicitud.localidad_origen),
            joinedload(Solicitud.localidad_destino),
            joinedload(Solicitud.presupuesto)
                .joinedload(Presupuesto.transportista)
                .joinedload(Transportista.usuario)
        ).filter_by(
            cliente_id=usuario.usuario_id
        ).order_by(Solicitud.fecha_creacion.desc()).all()

        print(f"📊 [mis-pedidos] Solicitudes encontradas: {len(solicitudes)}")

        # 3. Serialización
        response_data = []
        for s in solicitudes:
            data = s.to_dict()

            # Localidades
            if s.localidad_origen:
                data['localidad_origen'] = s.localidad_origen.to_dict()
            else:
                data['localidad_origen'] = None

            if s.localidad_destino:
                data['localidad_destino'] = s.localidad_destino.to_dict()
            else:
                data['localidad_destino'] = None

            # Presupuesto aceptado
            data['presupuesto'] = None

            if s.presupuesto_aceptado:
                presupuesto = None

                # Buscar el presupuesto
                if s.presupuesto and s.presupuesto.presupuesto_id == s.presupuesto_aceptado:
                    presupuesto = s.presupuesto
                else:
                    presupuesto = Presupuesto.query.options(
                        joinedload(Presupuesto.transportista).joinedload(Transportista.usuario)
                    ).get(s.presupuesto_aceptado)

                if presupuesto:
                    p_data = presupuesto.to_dict()

                    if presupuesto.transportista:
                        t_data = presupuesto.transportista.to_dict()

                        if presupuesto.transportista.usuario:
                            u_trans = presupuesto.transportista.usuario
                            t_data['usuario'] = {
                                'nombre': u_trans.nombre,
                                'apellido': u_trans.apellido,
                                'telefono': u_trans.telefono
                            }

                        p_data['transportista'] = t_data

                    data['presupuesto'] = p_data

            response_data.append(data)

        print(f"✨ [mis-pedidos] Respuesta: {len(response_data)} solicitudes")
        return jsonify(response_data), 200

    except Exception as e:
        print(f"❌ [mis-pedidos] Error: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": "Error interno del servidor"}), 500


# ============================================
# ENDPOINT: DASHBOARD TRANSPORTISTA
# ============================================
@solicitudes_bp.route('/api/transportista/dashboard', methods=['GET'])
@require_auth
def get_dashboard_transportista():
    current_uid = request.uid

    print(f"🔍 [dashboard] Transportista UID: {current_uid}")

    try:
        # 1. Identificar transportista
        usuario = Usuario.query.filter_by(u_id=current_uid).first()
        if not usuario:
            return jsonify({"error": "Usuario no encontrado"}), 404

        transportista = Transportista.query.filter_by(usuario_id=usuario.usuario_id).first()
        if not transportista:
            return jsonify({"error": "No es transportista"}), 403

        print(f"✅ [dashboard] Transportista: {usuario.nombre} (ID: {transportista.transportista_id})")

        # 2. Obtener zonas de cobertura
        zonas_query = db.session.query(transportista_localidad.c.localidad_id)\
            .filter(transportista_localidad.c.transportista_id == transportista.transportista_id).all()

        ids_zonas = [z[0] for z in zonas_query]
        print(f"📍 [dashboard] Zonas: {ids_zonas}")

        # 3. Solicitudes disponibles
        disponibles = []
        if ids_zonas:
            disponibles = Solicitud.query.options(
                joinedload(Solicitud.cliente),
                joinedload(Solicitud.localidad_origen),
                joinedload(Solicitud.localidad_destino)
            ).filter(
                text("estado = CAST('sin transportista' AS estado_solicitud)"),
                or_(
                    Solicitud.localidad_origen_id.in_(ids_zonas),
                    Solicitud.localidad_destino_id.in_(ids_zonas)
                )
            ).all()

        # 4. Mis viajes (pendientes o en viaje)
        mis_viajes = Solicitud.query.join(
            Presupuesto, Solicitud.presupuesto_aceptado == Presupuesto.presupuesto_id
        ).options(
            joinedload(Solicitud.cliente),
            joinedload(Solicitud.localidad_origen),
            joinedload(Solicitud.localidad_destino),
            joinedload(Solicitud.presupuesto)
        ).filter(
            Presupuesto.transportista_id == transportista.transportista_id,
            text("solicitud.estado IN (CAST('pendiente' AS estado_solicitud), CAST('en viaje' AS estado_solicitud))")
        ).all()

        print(f"📦 [dashboard] Disponibles: {len(disponibles)}, Mis viajes: {len(mis_viajes)}")

        # 5. Serialización
        def serializar_full(solicitud):
            data = solicitud.to_dict()
            if solicitud.cliente:
                data['cliente'] = solicitud.cliente.to_dict()
            if solicitud.localidad_origen:
                data['localidad_origen'] = solicitud.localidad_origen.to_dict()
            if solicitud.localidad_destino:
                data['localidad_destino'] = solicitud.localidad_destino.to_dict()
            return data

        return jsonify({
            "disponibles": [serializar_full(s) for s in disponibles],
            "pendientes": [serializar_full(s) for s in mis_viajes]
        }), 200

    except Exception as e:
        print(f"❌ [dashboard] Error: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": "Error interno del servidor"}), 500


# ============================================
# ENDPOINT: CREAR SOLICITUD
# ============================================
@solicitudes_bp.route('/api/solicitudes', methods=['POST'])
@require_auth
def crear_solicitud():
    current_uid = request.uid

    try:
        usuario = Usuario.query.filter_by(u_id=current_uid).first()
        if not usuario:
            return jsonify({"error": "Usuario no encontrado"}), 404

        data = request.get_json()

        nueva_solicitud = Solicitud(
            cliente_id=usuario.usuario_id,
            direccion_origen=data.get('direccion_origen'),
            direccion_destino=data.get('direccion_destino'),
            localidad_origen_id=data.get('localidad_origen_id'),
            localidad_destino_id=data.get('localidad_destino_id'),
            detalles_carga=data.get('detalles_carga'),
            medidas=data.get('medidas'),
            peso=data.get('peso'),
            hora_recogida=data.get('hora_recogida'),
            estado='sin transportista',
            fecha_creacion=datetime.now()
        )

        db.session.add(nueva_solicitud)
        db.session.commit()

        print(f"✅ [crear_solicitud] Solicitud creada: ID {nueva_solicitud.solicitud_id}")

        #Incompleto
        solicitud_completa = nueva_solicitud.to_dict()
        solicitud_completa['localidad_origen'] = nueva_solicitud.localidad_origen.to_dict() if nueva_solicitud.localidad_origen else None
        solicitud_completa['localidad_destino'] = nueva_solicitud.localidad_destino.to_dict() if nueva_solicitud.localidad_destino else None


    # Agregar después de las localidades
        if nueva_solicitud.cliente:
            solicitud_completa['cliente'] = {
                'usuario_id': nueva_solicitud.cliente.usuario_id,
                'nombre': nueva_solicitud.cliente.nombre,
                'apellido': nueva_solicitud.cliente.apellido,
                'telefono': nueva_solicitud.cliente.telefono,
                'email': nueva_solicitud.cliente.email
            }

        socketio.emit('nueva_solicitud', solicitud_completa)

        return jsonify(nueva_solicitud.to_dict()), 201

    except Exception as e:
        db.session.rollback()
        print(f"❌ [crear_solicitud] Error: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================
# ENDPOINT: ACTUALIZAR SOLICITUD
# ============================================
@solicitudes_bp.route('/api/solicitudes/<int:id>', methods=['PATCH'])
@require_auth
def actualizar_solicitud(id):
    current_uid = request.uid

    try:
        usuario = Usuario.query.filter_by(u_id=current_uid).first()
        solicitud = Solicitud.query.get(id)

        if not solicitud:
            return jsonify({"error": "Solicitud no encontrada"}), 404

        if solicitud.cliente_id != usuario.usuario_id:
            return jsonify({"error": "No tienes permiso"}), 403

        # Solo se puede editar si aún no tiene transportista asignado
        if solicitud.estado != EstadoSolicitud.SIN_TRANSPORTISTA:
            return jsonify({"error": f"No se puede editar, estado actual: {solicitud.estado.value}"}), 400

        data = request.get_json()

        # Actualizar solo los campos presentes en el body
        if 'direccion_origen' in data:
            solicitud.direccion_origen = data['direccion_origen']
        if 'direccion_destino' in data:
            solicitud.direccion_destino = data['direccion_destino']
        if 'detalles_carga' in data:
            solicitud.detalles_carga = data['detalles_carga']
        if 'medidas' in data:
            solicitud.medidas = data['medidas']
        if 'peso' in data:
            solicitud.peso = data['peso']
        if 'hora_recogida' in data:
            solicitud.hora_recogida = data['hora_recogida']
        if 'localidad_origen_id' in data:
            solicitud.localidad_origen_id = data['localidad_origen_id']
        if 'localidad_destino_id' in data:
            solicitud.localidad_destino_id = data['localidad_destino_id']

        db.session.commit()
        print(f"✅ [actualizar_solicitud] Solicitud {id} actualizada")

        # Re-fetch con relaciones frescas (localidades pueden haber cambiado)
        solicitud = Solicitud.query.options(
            joinedload(Solicitud.localidad_origen),
            joinedload(Solicitud.localidad_destino),
            joinedload(Solicitud.cliente),
        ).get(id)

        # Construir respuesta completa (igual para HTTP response y socket)
        solicitud_data = solicitud.to_dict()
        solicitud_data['localidad_origen']  = solicitud.localidad_origen.to_dict()  if solicitud.localidad_origen  else None
        solicitud_data['localidad_destino'] = solicitud.localidad_destino.to_dict() if solicitud.localidad_destino else None
        if solicitud.cliente:
            solicitud_data['cliente'] = {
                'usuario_id': solicitud.cliente.usuario_id,
                'nombre':     solicitud.cliente.nombre,
                'apellido':   solicitud.cliente.apellido,
                'telefono':   solicitud.cliente.telefono,
                'email':      solicitud.cliente.email,
            }

        # Notificar a fleteros que tienen esta zona para que vean los cambios
        socketio.emit('solicitud_actualizada', solicitud_data)

        return jsonify(solicitud_data), 200

    except Exception as e:
        db.session.rollback()
        print(f"❌ [actualizar_solicitud] Error: {e}")
        return jsonify({"error": str(e)}), 500



# ============================================
# ENDPOINT: CANCELAR SOLICITUD
# ============================================
# ============================================
# ENDPOINT: CANCELAR POR CLIENTE (sin transportista)
# Solo cuando estado = 'sin transportista'
# Rechaza todos los presupuestos existentes
# ============================================
@solicitudes_bp.route('/api/solicitudes/<int:id>/cancelar', methods=['PATCH'])
@require_auth
def cancelar_solicitud(id):
    current_uid = request.uid

    try:
        usuario = Usuario.query.filter_by(u_id=current_uid).first()
        if not usuario:
            return jsonify({"error": "Usuario no encontrado"}), 404

        solicitud = Solicitud.query.get(id)
        if not solicitud:
            return jsonify({"error": "Solicitud no encontrada"}), 404

        # Solo el cliente puede usar este endpoint
        if solicitud.cliente_id != usuario.usuario_id:
            return jsonify({"error": "Solo el cliente puede cancelar con este endpoint"}), 403

        # Solo se puede cancelar si aún no tiene transportista asignado
        if solicitud.estado != EstadoSolicitud.SIN_TRANSPORTISTA:
            return jsonify({"error": f"Solo puedes cancelar en estado 'sin transportista'. Estado actual: {solicitud.estado.value}"}), 400

        # Rechazar todos los presupuestos pendientes de esta solicitud
        presupuestos_rechazados = Presupuesto.query.filter(
            Presupuesto.solicitud_id == id,
            Presupuesto.estado == EstadoPresupuesto.PENDIENTE
        ).all()

        ids_presupuestos_rechazados = [p.presupuesto_id for p in presupuestos_rechazados]

        Presupuesto.query.filter(
            Presupuesto.solicitud_id == id,
            Presupuesto.estado == EstadoPresupuesto.PENDIENTE
        ).update({'estado': EstadoPresupuesto.RECHAZADO}, synchronize_session=False)

        # Cancelar la solicitud
        solicitud.estado = EstadoSolicitud.CANCELADO
        db.session.commit()

        print(f"✅ [cancelar_solicitud] Solicitud {id} cancelada por el cliente. Presupuestos rechazados: {ids_presupuestos_rechazados}")

        # Emitir a todos los fleteros: la solicitud desaparece de "disponibles"
        socketio.emit('solicitud_cancelada', {
            'solicitud_id': id,
            'cancelado_por': 'cliente',
            'presupuestos_rechazados': ids_presupuestos_rechazados
        })

        return jsonify({"message": "Solicitud cancelada correctamente"}), 200

    except Exception as e:
        db.session.rollback()
        print(f"❌ [cancelar_solicitud] Error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ============================================
# ENDPOINT: CANCELAR POR FLETERO (pendiente o en viaje)
# Solo el transportista asignado puede usar este endpoint
# Notifica al cliente por socket
# ============================================
@solicitudes_bp.route('/api/solicitudes/<int:id>/cancelar-fletero', methods=['PATCH'])
@require_auth
def cancelar_solicitud_fletero(id):
    current_uid = request.uid

    try:
        usuario = Usuario.query.filter_by(u_id=current_uid).first()
        if not usuario:
            return jsonify({"error": "Usuario no encontrado"}), 404

        transportista = Transportista.query.filter_by(usuario_id=usuario.usuario_id).first()
        if not transportista:
            return jsonify({"error": "No eres transportista"}), 403

        solicitud = Solicitud.query.options(
            joinedload(Solicitud.cliente),
            joinedload(Solicitud.localidad_origen),
            joinedload(Solicitud.localidad_destino),
            joinedload(Solicitud.presupuesto).joinedload(Presupuesto.transportista).joinedload(Transportista.usuario)
        ).get(id)

        if not solicitud:
            return jsonify({"error": "Solicitud no encontrada"}), 404

        # Verificar que sea el transportista asignado
        if not solicitud.presupuesto or solicitud.presupuesto.transportista_id != transportista.transportista_id:
            return jsonify({"error": "No eres el transportista asignado a esta solicitud"}), 403

        # Solo se puede cancelar en estado pendiente o en viaje
        if solicitud.estado not in [EstadoSolicitud.PENDIENTE, EstadoSolicitud.EN_VIAJE]:
            return jsonify({"error": f"Solo puedes cancelar en estado 'pendiente' o 'en viaje'. Estado actual: {solicitud.estado.value}"}), 400

        # Cancelar la solicitud
        solicitud.estado = EstadoSolicitud.CANCELADO
        db.session.commit()

        print(f"✅ [cancelar_solicitud_fletero] Solicitud {id} cancelada por el fletero (transportista_id={transportista.transportista_id})")

        # Construir payload completo para notificar al cliente
        solicitud_data = solicitud.to_dict()
        solicitud_data['localidad_origen']  = solicitud.localidad_origen.to_dict()  if solicitud.localidad_origen  else None
        solicitud_data['localidad_destino'] = solicitud.localidad_destino.to_dict() if solicitud.localidad_destino else None
        if solicitud.cliente:
            solicitud_data['cliente'] = {
                'usuario_id': solicitud.cliente.usuario_id,
                'nombre':     solicitud.cliente.nombre,
                'apellido':   solicitud.cliente.apellido,
                'telefono':   solicitud.cliente.telefono,
                'email':      solicitud.cliente.email,
            }

        # Emitir al cliente: su solicitud fue cancelada por el fletero
        socketio.emit('solicitud_cancelada', {
            'solicitud_id': id,
            'cancelado_por': 'fletero',
            'solicitud': solicitud_data
        })

        return jsonify({"message": "Solicitud cancelada correctamente"}), 200

    except Exception as e:
        db.session.rollback()
        print(f"❌ [cancelar_solicitud_fletero] Error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# ============================================
# ENDPOINT: ACEPTAR PRESUPUESTO
# ============================================
@solicitudes_bp.route('/api/solicitudes/<int:id>/aceptar-presupuesto', methods=['POST'])
@require_auth
def aceptar_presupuesto_solicitud(id):
    current_uid = request.uid

    try:
        usuario = Usuario.query.filter_by(u_id=current_uid).first()
        solicitud = Solicitud.query.get(id)

        if not solicitud:
            return jsonify({"error": "Solicitud no encontrada"}), 404

        if solicitud.cliente_id != usuario.usuario_id:
            return jsonify({"error": "No tienes permiso"}), 403

        data = request.get_json()
        presupuesto_id = data.get('presupuesto_id')

        if not presupuesto_id:
            return jsonify({"error": "presupuesto_id requerido"}), 400

        # Verificar que el presupuesto existe
        presupuesto = Presupuesto.query.get(presupuesto_id)
        if not presupuesto:
            return jsonify({"error": "Presupuesto no encontrado"}), 404

        # Actualizar solicitud
        solicitud.presupuesto_aceptado = presupuesto_id
        solicitud.estado = 'pendiente'

        db.session.commit()

        print(f"✅ [aceptar_presupuesto] Presupuesto {presupuesto_id} aceptado para solicitud {id}")

        # 🔥 EMITIR EVENTO

                # Cargar relaciones
        presupuesto = Presupuesto.query.options(
            joinedload(Presupuesto.transportista).joinedload(Transportista.usuario)
        ).get(presupuesto_id)

        # Construir datos completos del presupuesto
        presupuesto_completo = presupuesto.to_dict()

        # Agregar datos del transportista
        if presupuesto.transportista:
            presupuesto_completo['transportista'] = {
                'transportista_id': presupuesto.transportista.transportista_id,
                'calificacion_promedio': float(presupuesto.transportista.calificacion_promedio or 0),
                'total_calificaciones': presupuesto.transportista.total_calificaciones or 0,
                'usuario': {
                    'usuario_id': presupuesto.transportista.usuario.usuario_id,
                    'nombre': presupuesto.transportista.usuario.nombre,
                    'apellido': presupuesto.transportista.usuario.apellido,
                    'telefono': presupuesto.transportista.usuario.telefono,
                    'email': presupuesto.transportista.usuario.email
                } if presupuesto.transportista.usuario else None
            }

        # Emitir evento completo
        socketio.emit('presupuesto_aceptado', {
            'solicitud_id': id,
            'presupuesto_id': presupuesto_id,
            'transportista_id': presupuesto.transportista_id,
            'presupuesto': presupuesto_completo  # ✅ Datos completos del presupuesto
        })

        return jsonify(solicitud.to_dict()), 200

    except Exception as e:
        db.session.rollback()
        print(f"❌ [aceptar_presupuesto] Error: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================
# ENDPOINT: COMENZAR VIAJE
# ============================================
@solicitudes_bp.route('/api/solicitudes/<int:id>/comenzar-viaje', methods=['POST'])
@require_auth
def comenzar_viaje(id):
    current_uid = request.uid

    try:
        usuario = Usuario.query.filter_by(u_id=current_uid).first()
        transportista = Transportista.query.filter_by(usuario_id=usuario.usuario_id).first()

        if not transportista:
            return jsonify({"error": "No tienes permiso de transportista"}), 403

        solicitud = Solicitud.query.get(id)
        if not solicitud:
            return jsonify({"error": "Solicitud no encontrada"}), 404

        # Validaciones
        if not solicitud.presupuesto or not solicitud.presupuesto.transportista:
            return jsonify({"error": "Sin transportista asignado"}), 400

        if solicitud.presupuesto.transportista.transportista_id != transportista.transportista_id:
            return jsonify({"error": "No eres el transportista asignado"}), 403

       # if solicitud.estado != 'pendiente':
        if solicitud.estado != EstadoSolicitud.PENDIENTE:
            return jsonify({"error": f"Estado actual: {solicitud.estado}"}), 400

        # Actualizar estado
        solicitud.estado = EstadoSolicitud.EN_VIAJE
        db.session.commit()

        print(f"✅ [comenzar_viaje] Viaje iniciado: solicitud {id}")

        # 🔥 podria enviar el viaje ya iniciado

            # Cargar con eager loading
        solicitud = Solicitud.query.options(
            joinedload(Solicitud.localidad_origen),
            joinedload(Solicitud.localidad_destino),
            joinedload(Solicitud.cliente),
            joinedload(Solicitud.presupuesto).joinedload(Presupuesto.transportista).joinedload(Transportista.usuario)
        ).get(id)

        # Construir objeto completo
        solicitud_completa = solicitud.to_dict()

        # Agregar localidades
        solicitud_completa['localidad_origen'] = solicitud.localidad_origen.to_dict() if solicitud.localidad_origen else None
        solicitud_completa['localidad_destino'] = solicitud.localidad_destino.to_dict() if solicitud.localidad_destino else None

        # Agregar cliente
        if solicitud.cliente:
            solicitud_completa['cliente'] = {
                'usuario_id': solicitud.cliente.usuario_id,
                'nombre': solicitud.cliente.nombre,
                'apellido': solicitud.cliente.apellido,
                'telefono': solicitud.cliente.telefono,
                'email': solicitud.cliente.email
            }

        # Agregar presupuesto con transportista
        if solicitud.presupuesto:
            presupuesto_dict = solicitud.presupuesto.to_dict()
            if solicitud.presupuesto.transportista:
                presupuesto_dict['transportista'] = {
                    'transportista_id': solicitud.presupuesto.transportista.transportista_id,
                    'calificacion_promedio': float(solicitud.presupuesto.transportista.calificacion_promedio or 0),
                    'total_calificaciones': solicitud.presupuesto.transportista.total_calificaciones or 0,
                    'usuario': {
                        'usuario_id': solicitud.presupuesto.transportista.usuario.usuario_id,
                        'nombre': solicitud.presupuesto.transportista.usuario.nombre,
                        'apellido': solicitud.presupuesto.transportista.usuario.apellido,
                        'telefono': solicitud.presupuesto.transportista.usuario.telefono,
                        'email': solicitud.presupuesto.transportista.usuario.email
                    } if solicitud.presupuesto.transportista.usuario else None
                }
            solicitud_completa['presupuesto'] = presupuesto_dict

        socketio.emit('viaje_iniciado', solicitud_completa)

        return jsonify({
            "message": "Viaje iniciado correctamente",
            "solicitud": solicitud.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"❌ [comenzar_viaje] Error: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500


# ============================================
# ENDPOINT: COMPLETAR VIAJE
# ============================================
@solicitudes_bp.route('/api/solicitudes/<int:id>/completar', methods=['POST'])
@require_auth
def completar_viaje(id):
    current_uid = request.uid

    try:
        usuario = Usuario.query.filter_by(u_id=current_uid).first()
        transportista = Transportista.query.filter_by(usuario_id=usuario.usuario_id).first()

        if not transportista:
            return jsonify({"error": "No tienes permiso de transportista"}), 403

        solicitud = Solicitud.query.get(id)
        if not solicitud:
            return jsonify({"error": "Solicitud no encontrada"}), 404

        # Validaciones
        if not solicitud.presupuesto or solicitud.presupuesto.transportista_id != transportista.transportista_id:
            return jsonify({"error": "No eres el transportista de esta solicitud"}), 403

        if solicitud.estado != EstadoSolicitud.EN_VIAJE:
            return jsonify({"error": f"Estado actual: {solicitud.estado}"}), 400

        # Actualizar estado
        solicitud.estado = EstadoSolicitud.COMPLETADO
        db.session.commit()

        print(f"✅ [completar_viaje] Viaje completado: solicitud {id}")

        # ... cargar todas las relaciones igual que viaje_iniciado ...
        # Cargar con eager loading
        solicitud = Solicitud.query.options(
            joinedload(Solicitud.localidad_origen),
            joinedload(Solicitud.localidad_destino),
            joinedload(Solicitud.cliente),
            joinedload(Solicitud.presupuesto).joinedload(Presupuesto.transportista).joinedload(Transportista.usuario)
        ).get(id)

        # Construir objeto completo
        solicitud_completa = solicitud.to_dict()

        # Agregar localidades
        solicitud_completa['localidad_origen'] = solicitud.localidad_origen.to_dict() if solicitud.localidad_origen else None
        solicitud_completa['localidad_destino'] = solicitud.localidad_destino.to_dict() if solicitud.localidad_destino else None

        # Agregar cliente
        if solicitud.cliente:
            solicitud_completa['cliente'] = {
                'usuario_id': solicitud.cliente.usuario_id,
                'nombre': solicitud.cliente.nombre,
                'apellido': solicitud.cliente.apellido,
                'telefono': solicitud.cliente.telefono,
                'email': solicitud.cliente.email
            }

        # Agregar presupuesto con transportista
        if solicitud.presupuesto:
            presupuesto_dict = solicitud.presupuesto.to_dict()
            if solicitud.presupuesto.transportista:
                presupuesto_dict['transportista'] = {
                    'transportista_id': solicitud.presupuesto.transportista.transportista_id,
                    'calificacion_promedio': float(solicitud.presupuesto.transportista.calificacion_promedio or 0),
                    'total_calificaciones': solicitud.presupuesto.transportista.total_calificaciones or 0,
                    'usuario': {
                        'usuario_id': solicitud.presupuesto.transportista.usuario.usuario_id,
                        'nombre': solicitud.presupuesto.transportista.usuario.nombre,
                        'apellido': solicitud.presupuesto.transportista.usuario.apellido,
                        'telefono': solicitud.presupuesto.transportista.usuario.telefono,
                        'email': solicitud.presupuesto.transportista.usuario.email
                    } if solicitud.presupuesto.transportista.usuario else None
                }
            solicitud_completa['presupuesto'] = presupuesto_dict

        # ✅ IMPORTANTE: Agregar flag de que puede calificar
        solicitud_completa['puede_calificar'] = True

        socketio.emit('viaje_completado', solicitud_completa)

        return jsonify({
            "message": "Viaje completado exitosamente",
            "solicitud": solicitud.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"❌ [completar_viaje] Error: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500


# ============================================
# ENDPOINT: OBTENER SOLICITUD POR ID
# ============================================
@solicitudes_bp.route('/api/solicitudes/<int:id>', methods=['GET'])
@require_auth
def get_pedido_by_id(id):
    try:
        solicitud = Solicitud.query.get(id)

        if not solicitud:
            return jsonify({"error": "Solicitud no encontrada"}), 404

        data = solicitud.to_dict()

        if solicitud.cliente:
            data['cliente'] = solicitud.cliente.to_dict()
        else:
            data['cliente'] = None

        if solicitud.localidad_origen:
            data['localidad_origen'] = solicitud.localidad_origen.to_dict()
        else:
            data['localidad_origen'] = None

        if solicitud.localidad_destino:
            data['localidad_destino'] = solicitud.localidad_destino.to_dict()
        else:
            data['localidad_destino'] = None

        return jsonify(data), 200

    except Exception as e:
        print(f"❌ [get_pedido_by_id] Error: {e}")
        return jsonify({"error": "Error interno"}), 500



@solicitudes_bp.route('/api/transportista/historial', methods=['GET'])
@require_auth
def get_historial_fletero():
    current_uid = request.uid

    # 1. Identificar al Transportista
    usuario = Usuario.query.filter_by(u_id=current_uid).first()
    if not usuario:
        return jsonify({"error": "Usuario no encontrado"}), 404

    transportista = Transportista.query.filter_by(usuario_id=usuario.usuario_id).first()
    if not transportista:
        return jsonify({"error": "El usuario no es transportista"}), 403

    # 2. Consulta con JOIN (Reemplazo de la vista SQL)
    # Filtramos por el ID del transportista en la tabla Presupuesto
    # Ordenamos por ID descendente (o fecha) para ver lo último primero
    solicitudes = db.session.query(Solicitud).join(
        Presupuesto, Solicitud.presupuesto_aceptado == Presupuesto.presupuesto_id
    ).filter(
        Presupuesto.transportista_id == transportista.transportista_id
    ).order_by(Solicitud.solicitud_id.desc()).all()

    # 3. Serialización (Misma estructura que el Frontend espera)
    response_data = []
    for s in solicitudes:
        data = s.to_dict()

        # Localidades
        if s.localidad_origen:
            data['localidad_origen'] = s.localidad_origen.to_dict()
        if s.localidad_destino:
            data['localidad_destino'] = s.localidad_destino.to_dict()

        # Presupuesto -> Transportista -> Usuario
        if s.presupuesto:
            p_data = s.presupuesto.to_dict()
            t_data = transportista.to_dict() # Ya tenemos al transportista

            if transportista.usuario:
                t_data['usuario'] = {
                    'usuario_id': transportista.usuario.usuario_id,
                    'nombre': transportista.usuario.nombre,
                    'apellido': transportista.usuario.apellido
                }

            p_data['transportista'] = t_data
            data['presupuesto'] = p_data

        response_data.append(data)

    return jsonify(response_data), 200



@solicitudes_bp.route('/solicitudes/mis-pedidos-optimizadov', methods=['GET'])
@require_auth
def get_mis_pedidos_optimizadov():
    """
    🚀 ENDPOINT ULTRA-OPTIMIZADO
    - Sin conteos innecesarios.
    - 1 sola consulta a la DB para traer todo.
    """
    try:
        # 1. Obtener usuario
        user_uid = request.uid
        usuario = db.session.query(Usuario).filter_by(u_id=user_uid).first()
        if not usuario:
            return jsonify({"error": "Usuario no encontrado"}), 404

        # 2. Obtener todas las solicitudes con eager loading (TRAE TODO DE UNA VEZ)
        solicitudes = (
            db.session.query(Solicitud)
            .options(
                joinedload(Solicitud.localidad_origen),
                joinedload(Solicitud.localidad_destino),
                # Carga el presupuesto activo y su transportista en la misma query
                joinedload(Solicitud.presupuesto)
                .joinedload(Presupuesto.transportista)
                .joinedload(Transportista.usuario),
            )
            .filter_by(cliente_id=usuario.usuario_id)
            .order_by(Solicitud.fecha_creacion.desc())
            .all()
        )

        # 3. Cache y construcción de respuesta
        transportistas_cache = {}
        resultado = []

        for solicitud in solicitudes:
            # Convierte datos básicos
            sol_dict = solicitud.to_dict()

            # 4. Datos del presupuesto ACTIVO y Transportista
            # Como usamos joinedload arriba, acceder a .presupuesto NO hace otra query
            if solicitud.presupuesto:
                sol_dict['presupuesto'] = solicitud.presupuesto.to_dict()

                # Datos del Transportista (optimizados con caché simple)
                if solicitud.presupuesto.transportista:
                    transportista = solicitud.presupuesto.transportista
                    t_id = transportista.transportista_id

                    if t_id not in transportistas_cache:
                        transportistas_cache[t_id] = {
                            'transportista_id': transportista.transportista_id,
                            'descripcion': transportista.descripcion,
                            #'calificacion_promedio': float(transportista.calificacion_promedio or 0),
                            #'total_calificaciones': transportista.total_calificaciones or 0,
                            'usuario': {
                                'usuario_id': transportista.usuario.usuario_id,
                                'nombre': transportista.usuario.nombre,
                                'apellido': transportista.usuario.apellido,
                                'telefono': transportista.usuario.telefono,
                                'email': transportista.usuario.email,
                            }
                        }

                    # Asignamos del caché
                    sol_dict['presupuesto']['transportista'] = transportistas_cache[t_id]
            else:
                sol_dict['presupuesto'] = None

            resultado.append(sol_dict)

        print(f"✨ Respuesta optimizada: {len(resultado)} solicitudes")
        return jsonify(resultado), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500



@solicitudes_bp.route('/solicitudes/mis-pedidos-optimizado', methods=['GET'])
@require_auth
def get_mis_pedidos_optimizado():
    """
    🚀 ENDPOINT ULTRA-OPTIMIZADO — 2 queries totales.

    Query 1 (joinedload): solicitudes + localidades + presupuesto + transportista + usuario
    Query 2 (IN):         todas las calificaciones del cliente de una sola vez

    El frontend ya NO necesita llamar a:
      - getEstadisticasTransportista() → calificacion_promedio y total_calificaciones vienen aquí
      - getCalificacionSolicitud()     → _calificacion viene aquí
    """
    try:
        # ── 1. Usuario ──────────────────────────────────────────────────────
        user_uid = request.uid
        usuario = db.session.query(Usuario).filter_by(u_id=user_uid).first()
        if not usuario:
            return jsonify({"error": "Usuario no encontrado"}), 404

        # ── 2. Query principal: todo en una sola query SQL ───────────────────
        solicitudes = (
            db.session.query(Solicitud)
            .options(
                joinedload(Solicitud.localidad_origen),
                joinedload(Solicitud.localidad_destino),
                joinedload(Solicitud.presupuesto)
                    .joinedload(Presupuesto.transportista)
                    .joinedload(Transportista.usuario),
            )
            .filter_by(cliente_id=usuario.usuario_id)
            .order_by(Solicitud.fecha_creacion.desc())
            .all()
        )

        # ── 3. Query de calificaciones: 1 sola query con IN ─────────────────
        # En vez de N queries (una por solicitud completada), traemos todas juntas
        # y armamos un dict para lookup O(1) por solicitud_id
        ids_solicitudes = [s.solicitud_id for s in solicitudes]
        calificaciones_map = {}

        if ids_solicitudes:
            calificaciones = (
                db.session.query(Calificacion)
                .filter(Calificacion.solicitud_id.in_(ids_solicitudes))
                .all()
            )
            calificaciones_map = {
                c.solicitud_id: {
                    'calificacion_id': c.calificacion_id,
                    'puntuacion':      c.puntuacion,
                    'comentario':      c.comentario,
                    'creado_en':  c.creado_en.isoformat() if c.creado_en else None,
                }
                for c in calificaciones
            }

        # ── 4. Serialización ────────────────────────────────────────────────
        transportistas_cache = {}
        resultado = []

        for solicitud in solicitudes:
            sol_dict = solicitud.to_dict()

            # Localidades (ya en memoria por joinedload, sin query extra)
            sol_dict['localidad_origen']  = solicitud.localidad_origen.to_dict()  if solicitud.localidad_origen  else None
            sol_dict['localidad_destino'] = solicitud.localidad_destino.to_dict() if solicitud.localidad_destino else None

            # Presupuesto activo + transportista
            if solicitud.presupuesto:
                sol_dict['presupuesto'] = solicitud.presupuesto.to_dict()

                if solicitud.presupuesto.transportista:
                    transportista = solicitud.presupuesto.transportista
                    t_id = transportista.transportista_id

                    # Cache: si el mismo transportista tiene varias solicitudes, no repetimos el dict
                    if t_id not in transportistas_cache:
                        transportistas_cache[t_id] = {
                            'transportista_id':      transportista.transportista_id,
                            'descripcion':           transportista.descripcion,
                            'calificacion_promedio': float(transportista.calificacion_promedio or 0),
                            'total_calificaciones':  transportista.total_calificaciones or 0,
                            'usuario': {
                                'usuario_id': transportista.usuario.usuario_id,
                                'nombre':     transportista.usuario.nombre,
                                'apellido':   transportista.usuario.apellido,
                                'telefono':   transportista.usuario.telefono,
                                'email':      transportista.usuario.email,
                            } if transportista.usuario else None,
                        }

                    sol_dict['presupuesto']['transportista'] = transportistas_cache[t_id]
            else:
                sol_dict['presupuesto'] = None

            # Calificación de esta solicitud (lookup O(1), sin query extra)
            sol_dict['_calificacion'] = calificaciones_map.get(solicitud.solicitud_id)

            resultado.append(sol_dict)

        print(f"✨ [mis-pedidos-optimizado] {len(resultado)} solicitudes, {len(calificaciones_map)} calificaciones")
        return jsonify(resultado), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500




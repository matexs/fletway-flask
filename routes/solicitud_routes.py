import os
from flask import Blueprint, jsonify, request, send_from_directory, current_app
from sqlalchemy import or_, text
from werkzeug.utils import secure_filename
from models import db, Usuario, Transportista, Solicitud, Foto, Presupuesto, EstadoSolicitud, transportista_localidad
from services.auth import require_auth
from datetime import datetime
from sqlalchemy.orm import joinedload
from extensions import socketio

solicitudes_bp = Blueprint('solicitudes', __name__)

# ============================================
# 🔥 HELPER: EMITIR EVENTO DE ACTUALIZACIÓN
# ============================================
def emitir_actualizacion(evento='lista_actualizada', data=None):
    """
    Emite un evento de Socket.IO para notificar cambios a todos los clientes conectados
    """
    try:
        if data is None:
            data = {}

        print(f"📤 [Socket.IO] Emitiendo evento: {evento}")
        print(f"   📦 Data: {data}")

        # Emitir a TODOS los clientes conectados
        socketio.emit(evento, data)

        print(f"✅ [Socket.IO] Evento {evento} emitido correctamente")
    except Exception as e:
        print(f"❌ [Socket.IO] Error al emitir evento {evento}: {e}")


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

        # 🔥 EMITIR EVENTO
        emitir_actualizacion('solicitud_creada', {
            'solicitud_id': nueva_solicitud.solicitud_id,
            'cliente_id': usuario.usuario_id
        })

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

        data = request.get_json()

        # Actualizar campos
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

        # 🔥 EMITIR EVENTO
        emitir_actualizacion('solicitud_actualizada', {
            'solicitud_id': id,
            'cliente_id': usuario.usuario_id
        })

        return jsonify(solicitud.to_dict()), 200

    except Exception as e:
        db.session.rollback()
        print(f"❌ [actualizar_solicitud] Error: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================
# ENDPOINT: ELIMINAR SOLICITUD
# ============================================
@solicitudes_bp.route('/api/solicitudes/<int:id>', methods=['DELETE'])
@require_auth
def eliminar_solicitud(id):
    current_uid = request.uid

    try:
        usuario = Usuario.query.filter_by(u_id=current_uid).first()
        solicitud = Solicitud.query.get(id)

        if not solicitud:
            return jsonify({"error": "Solicitud no encontrada"}), 404

        if solicitud.cliente_id != usuario.usuario_id:
            return jsonify({"error": "No tienes permiso"}), 403

        db.session.delete(solicitud)
        db.session.commit()

        print(f"✅ [eliminar_solicitud] Solicitud {id} eliminada")

        # 🔥 EMITIR EVENTO
        emitir_actualizacion('solicitud_eliminada', {
            'solicitud_id': id,
            'cliente_id': usuario.usuario_id
        })

        return jsonify({"message": "Solicitud eliminada"}), 200

    except Exception as e:
        db.session.rollback()
        print(f"❌ [eliminar_solicitud] Error: {e}")
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
        emitir_actualizacion('presupuesto_aceptado', {
            'solicitud_id': id,
            'presupuesto_id': presupuesto_id,
            'transportista_id': presupuesto.transportista_id
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

        if solicitud.estado != 'pendiente':
            return jsonify({"error": f"Estado actual: {solicitud.estado}"}), 400

        # Actualizar estado
        solicitud.estado = 'en viaje'
        db.session.commit()

        print(f"✅ [comenzar_viaje] Viaje iniciado: solicitud {id}")

        # 🔥 EMITIR EVENTO
        emitir_actualizacion('viaje_iniciado', {
            'solicitud_id': id,
            'transportista_id': transportista.transportista_id
        })

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

        if solicitud.estado != 'en viaje':
            return jsonify({"error": f"Estado actual: {solicitud.estado}"}), 400

        # Actualizar estado
        solicitud.estado = 'completada'
        db.session.commit()

        print(f"✅ [completar_viaje] Viaje completado: solicitud {id}")

        # 🔥 EMITIR EVENTO
        emitir_actualizacion('viaje_completado', {
            'solicitud_id': id,
            'transportista_id': transportista.transportista_id
        })

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
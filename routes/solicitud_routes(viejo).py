import os
from flask import Blueprint, jsonify, request, send_from_directory, current_app
from sqlalchemy import or_,text
from werkzeug.utils import secure_filename
from models import db, Usuario, Transportista, Solicitud, Foto,Presupuesto, EstadoSolicitud,transportista_localidad
from services.auth import require_auth
from datetime import datetime
from sqlalchemy.orm import joinedload
from extensions import socketio


solicitudes_bp = Blueprint('solicitudes', __name__)

@solicitudes_bp.route('/api/solicitudes/recomendadas', methods=['GET'])
@require_auth
def get_solicitudes_recomendadas():
    current_user_uuid = request.uid # El UUID de Supabase

    # 1. Obtener el usuario y verificar que sea transportista
    usuario = Usuario.query.filter_by(u_id=current_user_uuid).first()
    if not usuario:
        return jsonify({"error": "Usuario no encontrado"}), 404

    transportista = Transportista.query.filter_by(usuario_id=usuario.usuario_id).first()
    if not transportista:
        return jsonify({"error": "El usuario no es transportista"}), 403

    # 2. Obtener los IDs de las localidades que cubre el transportista
    # (Equivalente a consultar 'vw_transportista_localidades')
    # Asumiendo una relación en tus modelos, o consultando la tabla intermedia:
    # Opción Recomendada (Más segura y clara)
    zonas = db.session.query(transportista_localidad.c.localidad_id)\
    .filter(transportista_localidad.c.transportista_id == transportista.transportista_id)\
    .all()
    # Tu código actual:

    ids_localidades = [z[0] for z in zonas] # Convierte [(1,), (5,)] a [1, 5]

    if not ids_localidades:
        return jsonify([]) # No cubre ninguna zona, devuelve array vacío

    # 3. La consulta principal (El filtro complejo)
    # estado = 'sin transportista' AND (origen IN zonas OR destino IN zonas)
    solicitudes = Solicitud.query.filter(
        # CORRECCIÓN: Usamos text() con CAST para que PostgreSQL entienda el ENUM
        text("estado = CAST('sin transportista' AS estado_solicitud)"),

        # Mantenemos el filtro de localidades original
        or_(
            Solicitud.localidad_origen_id.in_(ids_localidades),
            Solicitud.localidad_destino_id.in_(ids_localidades)
        )
    ).all()

    # 4. Serialización manual para igualar la estructura de Supabase
    # Supabase devuelve objetos anidados: cliente: {...}, localidad_origen: {...}
    # Flask debe devolver EXACTAMENTE lo mismo para no romper el Angular.
    response_data = []
    for s in solicitudes:
        # Asegúrate de acceder a las relaciones (relationship) de tu modelo
        s_dict = s.to_dict() # Tu método base de conversión

        # Agregamos los anidados manualmente
        s_dict['cliente'] = s.cliente.to_dict() if s.cliente else None
        s_dict['localidad_origen'] = s.localidad_origen.to_dict() if s.localidad_origen else None
        s_dict['localidad_destino'] = s.localidad_destino.to_dict() if s.localidad_destino else None

        response_data.append(s_dict)

    return jsonify(response_data), 200



@solicitudes_bp.route('/api/solicitudes/<int:id>', methods=['GET'])
@require_auth
def get_pedido_by_id(id):
    # 1. Buscar solicitud
    solicitud = Solicitud.query.get(id)

    if not solicitud:
        return jsonify({"error": "Solicitud no encontrada"}), 404

    # 2. Serialización
    data = solicitud.to_dict()

    # A. Relación Cliente (Con todos los campos extra que pide tu frontend)
    if solicitud.cliente:
        cliente_data = solicitud.cliente.to_dict()
        # Asegúrate de que tu modelo Usuario tenga estos campos en su to_dict()
        # O agrégalos manualmente aquí si faltan:
        # cliente_data['fecha_nacimiento'] = solicitud.cliente.fecha_nacimiento
        # cliente_data['fecha_registro'] = solicitud.cliente.fecha_registro
        data['cliente'] = cliente_data
    else:
        data['cliente'] = None

    # B. Localidades
    if solicitud.localidad_origen:
        data['localidad_origen'] = solicitud.localidad_origen.to_dict()
    else:
        data['localidad_origen'] = None

    if solicitud.localidad_destino:
        data['localidad_destino'] = solicitud.localidad_destino.to_dict()
    else:
        data['localidad_destino'] = None

    # C. Presupuesto (Si lo necesitas para mostrar detalles del transportista)
    if solicitud.presupuesto:
         # ... lógica de serialización de presupuesto vista anteriormente ...
         pass

    return jsonify(data), 200

@solicitudes_bp.route('/api/solicitudes/estado/<string:estado>', methods=['GET'])
@require_auth
def get_solicitudes_por_estado(estado):
    # 1. Validar input básico (seguridad)
    estados_validos = ['pendiente', 'sin transportista', 'en viaje', 'completado', 'cancelado']

    # Decodificar URL (por si viene "sin%20transportista")
    estado_limpio = estado.replace('%20', ' ')

    if estado_limpio not in estados_validos:
        # Opcional: Si quieres ser estricto. Si no, quita este if.
        pass

    # 2. Consultar base de datos
    try:
        # CORRECCIÓN: Usamos CAST(... AS ...) para evitar el error de sintaxis con los dos puntos
        solicitudes = Solicitud.query.filter(
            text("estado = CAST(:val AS estado_solicitud)")
        ).params(val=estado_limpio).all()

    except Exception as e:
        print(f"Error DB Estado: {e}")
        return jsonify({"error": "Error al filtrar por estado"}), 500

    # 3. Serialización
    response_data = []
    for s in solicitudes:
        data = s.to_dict()

        # Hidratar relaciones (Igual que en los endpoints anteriores)
        # Esto es vital para que Angular muestre nombre, apellido y localidades
        if s.cliente:
            data['cliente'] = s.cliente.to_dict()
        else:
            data['cliente'] = None

        if s.localidad_origen:
            data['localidad_origen'] = s.localidad_origen.to_dict()
        else:
            data['localidad_origen'] = None

        if s.localidad_destino:
            data['localidad_destino'] = s.localidad_destino.to_dict()
        else:
            data['localidad_destino'] = None

        response_data.append(data)

    return jsonify(response_data), 200

# En solicitud_routes.py

@solicitudes_bp.route('/api/solicitudess/mis-pedidoss', methods=['GET'])
@require_auth
def get_solicitudes_usuario():
    current_uid = request.uid

    try:
        # 1. Obtener el usuario (Cliente) desde el token
        usuario = Usuario.query.filter_by(u_id=current_uid).first()
        if not usuario:
            # Si no existe, retornamos lista vacía para no romper el front
            return jsonify([]), 200

        # 2. Consultar Solicitudes con Eager Loading (Optimización)
        # Traemos todas las relaciones necesarias de un solo golpe
        solicitudes = Solicitud.query.options(
            joinedload(Solicitud.localidad_origen),
            joinedload(Solicitud.localidad_destino),
            # Cargamos la cadena completa: Solicitud -> Presupuesto -> Transportista -> Usuario
            joinedload(Solicitud.presupuesto)
                .joinedload(Presupuesto.transportista)
                .joinedload(Transportista.usuario)
        ).filter_by(
            cliente_id=usuario.usuario_id
        ).order_by(Solicitud.fecha_creacion.desc()).all()

        # 3. Serialización Manual para coincidir con la interfaz de Angular
        response_data = []

        for s in solicitudes:
            data = s.to_dict() # Tu base (id, estado, fecha, etc.)

            # A. Localidades
            if s.localidad_origen:
                data['localidad_origen'] = s.localidad_origen.to_dict()
            if s.localidad_destino:
                data['localidad_destino'] = s.localidad_destino.to_dict()

            # B. Presupuesto Aceptado (La parte compleja)
            # Angular espera: presupuesto: { transportista: { ..., usuario: {...} } }
            if s.presupuesto:
                p_data = s.presupuesto.to_dict()

                if s.presupuesto.transportista:
                    transp = s.presupuesto.transportista
                    t_data = transp.to_dict()

                    # -- Adaptación de campos para Angular --
                    # Angular pide 'total_calificaciones' y 'cantidad_calificaciones'.
                    # Tu modelo tiene 'calificacion_promedio'.
                    # Mapeamos lo que tenemos para que no falle el TS.
                    t_data['total_calificaciones'] = transp.calificacion_promedio or 0
                    t_data['cantidad_calificaciones'] = 0 # O el campo real si lo agregas al modelo después

                    # Datos del conductor (Usuario dentro de Transportista)
                    if transp.usuario:
                        t_data['usuario'] = {
                            'usuario_id': transp.usuario.usuario_id,
                            'nombre': transp.usuario.nombre,
                            'apellido': transp.usuario.apellido
                        }

                    p_data['transportista'] = t_data

                data['presupuesto'] = p_data
            else:
                data['presupuesto'] = None

            response_data.append(data)

        return jsonify(response_data), 200

    except Exception as e:
        print(f"Error en mis-pedidos: {e}")
        return jsonify({"error": "Error al obtener pedidos"}), 500


@solicitudes_bp.route('/api/solicitudes', methods=['POST'])
@require_auth
def create_solicitud():
    try:
        data = request.json
        current_uid = request.uid # Obtenido del token

        # 1. Obtener el usuario (Cliente)
        usuario = Usuario.query.filter_by(u_id=current_uid).first()
        if not usuario:
            return jsonify({"error": "Usuario no encontrado"}), 404

        # 2. Validaciones básicas (puedes agregar más)
        required_fields = ['direccion_origen', 'direccion_destino', 'localidad_origen_id', 'localidad_destino_id']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Falta el campo requerido: {field}"}), 400

        # 3. Procesar Fecha y Hora
        # Angular enviará un string ISO completo en 'hora_recogida'
        hora_recogida_dt = None
        if data.get('hora_recogida'):
            try:
                # Python < 3.11 prefiere que le quites la 'Z' o manejes el timezone explícitamente
                # Si angular manda "2023-10-10T15:30:00.000Z", strptime lo maneja así:
                date_str = data['hora_recogida'].replace('Z', '+00:00')
                hora_recogida_dt = datetime.fromisoformat(date_str)
            except ValueError:
                return jsonify({"error": "Formato de fecha inválido. Se espera ISO 8601"}), 400

        # 4. Crear el objeto Solicitud
        nueva_solicitud = Solicitud(
            cliente_id=usuario.usuario_id,
            direccion_origen=data['direccion_origen'],
            direccion_destino=data['direccion_destino'],
            localidad_origen_id=data['localidad_origen_id'],
            localidad_destino_id=data['localidad_destino_id'],
            detalles_carga=data.get('detalles_carga'),
            medidas=data.get('medidas'),
            peso=data.get('peso'),
            hora_recogida=hora_recogida_dt,
           # estado='sin transportista'
           # estado=EstadoSolicitud.SIN_TRANSPORTISTA # Estado inicial por defecto
        )

        db.session.add(nueva_solicitud)
        db.session.commit()


        socketio.emit('lista_actualizada', {'action': 'crear'})
        # --- AQUÍ PODRÍAS DISPARAR LA NOTIFICACIÓN PUSH A TRANSPORTISTAS ---
        # buscar_y_notificar_transportistas(nueva_solicitud.localidad_origen_id)
        # -------------------------------------------------------------------

        # 5. Devolver el objeto creado (usando to_dict)
        return jsonify(nueva_solicitud.to_dict()), 201

    except Exception as e:
        db.session.rollback()
        print(f"Error creando solicitud: {e}")
        return jsonify({"error": "Error interno al crear la solicitud"}), 500

@solicitudes_bp.route('/api/solicitudes/<int:id>', methods=['DELETE'])
@require_auth
def eliminar_solicitud(id):
    try:
        current_uid = request.uid

        # 1. Buscar la solicitud
        solicitud = Solicitud.query.get(id)

        if not solicitud:
            return jsonify({"error": "Solicitud no encontrada"}), 404

        # 2. Validar Propiedad (Seguridad Crítica)
        # Verificamos que el usuario del token sea el dueño de la solicitud
        # Asumiendo que solicitud.cliente es la relación con Usuario
        if not solicitud.cliente or solicitud.cliente.u_id != current_uid:
            return jsonify({"error": "No tienes permiso para eliminar esta solicitud"}), 403

        # 3. Validar Estado de Negocio
        # No permitimos borrar si ya hay un compromiso serio (ej: en viaje)
        if solicitud.estado in ['en viaje', 'completado']:
            return jsonify({"error": "No se puede eliminar una solicitud en curso o finalizada"}), 400

        # 4. (Opcional) Borrar fotos físicas del servidor
        # Si tienes configurado CASCADE en la base de datos, las filas se borran solas,
        # pero los archivos quedan en disco. Esto los limpia:
        fotos = Foto.query.filter_by(solc_id=id).all()
        for foto in fotos:
            try:
                # Construir ruta completa
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], foto.url)
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"Error borrando archivo físico {foto.url}: {e}")

        # 5. Eliminar registro de la DB
        db.session.delete(solicitud)
        db.session.commit()

        return jsonify({"message": "Solicitud eliminada correctamente"}), 200

    except Exception as e:
        db.session.rollback()
        print(f"Error al eliminar solicitud: {e}")
        return jsonify({"error": "Error interno al eliminar"}), 500


@solicitudes_bp.route('/api/solicitudes/<int:id>', methods=['PATCH'])
@require_auth
def update_solicitud(id):
    try:
        data = request.json
        current_uid = request.uid

        # 1. Buscar la solicitud
        solicitud = Solicitud.query.get(id)

        if not solicitud:
            return jsonify({"error": "Solicitud no encontrada"}), 404

        # 2. Validar Propiedad (Seguridad)
        # Solo el dueño puede editar los detalles de la carga
        if not solicitud.cliente or solicitud.cliente.u_id != current_uid:
            return jsonify({"error": "No tienes permiso para editar esta solicitud"}), 403

        # 3. Validar Estado
        # Generalmente no se debería editar una solicitud que ya se completó
        if solicitud.estado == 'completado':
             return jsonify({"error": "No se puede editar una solicitud completada"}), 400

        # 4. Actualización Dinámica de Campos
        # Solo actualizamos si el campo viene en el JSON

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

        if 'localidad_origen_id' in data:
            solicitud.localidad_origen_id = data['localidad_origen_id']

        if 'localidad_destino_id' in data:
            solicitud.localidad_destino_id = data['localidad_destino_id']

        # Manejo especial de fechas
        if 'hora_recogida' in data:
            fecha_str = data['hora_recogida']
            if fecha_str:
                try:
                    # Ajuste para compatibilidad ISO (quita la Z o maneja timezone)
                    if fecha_str.endswith('Z'):
                         fecha_str = fecha_str.replace('Z', '+00:00')
                    solicitud.hora_recogida = datetime.fromisoformat(fecha_str)
                except ValueError:
                    return jsonify({"error": "Formato de fecha inválido"}), 400
            else:
                solicitud.hora_recogida = None

        # Nota: 'estado' y 'foto' se suelen manejar en endpoints separados o con lógica especial,
        # pero si tu app permite editarlos directamente aquí, puedes agregarlos:
        # if 'estado' in data: solicitud.estado = data['estado']
        # if 'foto' in data: solicitud.foto = data['foto'] # (Si guardas la URL aqui)

        db.session.commit()

        # 5. Devolver el objeto actualizado
        # Es importante devolverlo serializado para actualizar la UI
        return jsonify(solicitud.to_dict()), 200

    except Exception as e:
        db.session.rollback()
        print(f"Error actualizando solicitud: {e}")
        return jsonify({"error": "Error interno al actualizar"}), 500

@solicitudes_bp.route('/api/transportista/viajes-pendientes', methods=['GET'])
@require_auth
def get_viajes_pendientes_transportista():
    current_uid = request.uid

    # 1. Identificar al Transportista desde el Token
    # Buscamos al usuario y luego su perfil de transportista
    usuario = Usuario.query.filter_by(u_id=current_uid).first()
    if not usuario:
        return jsonify({"error": "Usuario no encontrado"}), 404

    transportista = Transportista.query.filter_by(usuario_id=usuario.usuario_id).first()
    if not transportista:
        return jsonify({"error": "El usuario no es transportista"}), 403

    # 2. Consulta con JOINS (Reemplaza a la vista 'v_solicitudes_transportista')
    # Queremos: Solicitudes donde (estado='pendiente') Y (el presupuesto aceptado es MÍO)
    solicitudes = db.session.query(Solicitud).join(
        Presupuesto, Solicitud.presupuesto_aceptado == Presupuesto.presupuesto_id
    ).filter(
        Solicitud.estado == 'pendiente',
        Presupuesto.transportista_id == transportista.transportista_id
    ).all()

    # 3. Serialización Profunda (Deep Nested)
    # Debemos construir exactamente la estructura que tu Frontend espera
    response_data = []
    for s in solicitudes:
        data = s.to_dict()

        # A. Localidades
        if s.localidad_origen:
            data['localidad_origen'] = s.localidad_origen.to_dict()
        if s.localidad_destino:
            data['localidad_destino'] = s.localidad_destino.to_dict()

        # B. Presupuesto -> Transportista -> Usuario
        # Esto es vital para que tu tarjeta muestre los datos del viaje correctamente
        if s.presupuesto:
            p_data = s.presupuesto.to_dict()

            # Como ya sabemos que el transportista es el usuario actual,
            # podemos usar los datos que ya tenemos o sacarlos de la relación.
            t_data = transportista.to_dict() # o s.presupuesto.transportista.to_dict()

            # Datos del Usuario (Nombre/Apellido del transportista)
            if transportista.usuario:
                t_data['usuario'] = {
                    'usuario_id': transportista.usuario.usuario_id,
                    'nombre': transportista.usuario.nombre,
                    'apellido': transportista.usuario.apellido
                }

            p_data['transportista'] = t_data
            data['presupuesto'] = p_data

        # C. Cliente (Opcional, si necesitas ver a quién le llevas la carga)
        if s.cliente:
             data['cliente'] = s.cliente.to_dict()

        response_data.append(data)

    return jsonify(response_data), 200


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

@solicitudes_bp.route('/api/solicitudes/general/todas', methods=['GET'])
@require_auth
def get_all_solicitudes_system():
    """
    Obtiene TODAS las solicitudes registradas en el sistema.
    Ideal para paneles de administración o debugging.
    """
    try:
        # 1. Consulta optimizada con 'joinedload' para traer relaciones en una sola query
        # Ordenamos por las más recientes primero
        solicitudes = Solicitud.query.options(
            joinedload(Solicitud.cliente),
            joinedload(Solicitud.localidad_origen),
            joinedload(Solicitud.localidad_destino),
            joinedload(Solicitud.presupuesto).joinedload(Presupuesto.transportista)
        ).order_by(Solicitud.solicitud_id.desc()).all()

        # 2. Serialización Manual (Vital para que Angular no rompa)
        response_data = []
        for s in solicitudes:
            data = s.to_dict()

            # A. Datos del Cliente (Usuario)
            if s.cliente:
                data['cliente'] = s.cliente.to_dict()

            # B. Localidades
            if s.localidad_origen:
                data['localidad_origen'] = s.localidad_origen.to_dict()
            if s.localidad_destino:
                data['localidad_destino'] = s.localidad_destino.to_dict()

            # C. Presupuesto Aceptado (si existe)
            if s.presupuesto:
                p_data = s.presupuesto.to_dict()

                # Datos del Transportista asociado al presupuesto
                if s.presupuesto.transportista:
                    t_data = s.presupuesto.transportista.to_dict()

                    # Nombre del Chofer (Usuario dentro de Transportista)
                    if s.presupuesto.transportista.usuario:
                        u_trans = s.presupuesto.transportista.usuario
                        t_data['usuario'] = {
                            'usuario_id': u_trans.usuario_id,
                            'nombre': u_trans.nombre,
                            'apellido': u_trans.apellido
                        }
                    p_data['transportista'] = t_data

                data['presupuesto'] = p_data

            response_data.append(data)

        return jsonify(response_data), 200

    except Exception as e:
        print(f"Error obteniendo todas las solicitudes: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500



#nuevos endpoints



@solicitudes_bp.route('/api/transportista/dashboard', methods=['GET'])
@require_auth
def get_dashboard_transportista():
    current_uid = request.uid

    try:
        # 1. Identificar al Transportista usando el Token
        usuario = Usuario.query.filter_by(u_id=current_uid).first()
        if not usuario:
            return jsonify({"error": "Usuario no encontrado"}), 404

        transportista = Transportista.query.filter_by(usuario_id=usuario.usuario_id).first()
        if not transportista:
            return jsonify({"error": "El usuario actual no es un transportista registrado"}), 403

        # 2. Obtener IDs de sus Localidades (Zonas de cobertura)
        # Nota: Usamos .c. porque es una tabla de asociación sin modelo de clase
        zonas_query = db.session.query(transportista_localidad.c.localidad_id)\
            .filter(transportista_localidad.c.transportista_id == transportista.transportista_id).all()

        # Convertimos lista de tuplas [(1,), (5,)] a lista plana [1, 5]
        ids_zonas = [z[0] for z in zonas_query]

        # 3. CONSULTA A (Disponibles): Solicitudes 'sin transportista' en sus zonas
        disponibles = []
        if ids_zonas:
            disponibles = Solicitud.query.options(
                joinedload(Solicitud.cliente),
                joinedload(Solicitud.localidad_origen),
                joinedload(Solicitud.localidad_destino)
            ).filter(
                # Usamos CAST para evitar el error de tipos ENUM de PostgreSQL
                text("estado = CAST('sin transportista' AS estado_solicitud)"),
                or_(
                    Solicitud.localidad_origen_id.in_(ids_zonas),
                    Solicitud.localidad_destino_id.in_(ids_zonas)
                )
            ).all()

        # 4. CONSULTA B (Mis Viajes): Pendientes o En Viaje asignados a mí
        # Hacemos JOIN con Presupuesto para asegurar que es MI viaje aceptado
        mis_viajes = Solicitud.query.join(
            Presupuesto, Solicitud.presupuesto_aceptado == Presupuesto.presupuesto_id
        ).options(
            joinedload(Solicitud.cliente),
            joinedload(Solicitud.localidad_origen),
            joinedload(Solicitud.localidad_destino),
            joinedload(Solicitud.presupuesto)
        ).filter(
            Presupuesto.transportista_id == transportista.transportista_id,
            # Filtramos estados activos (Pendiente o En Viaje)
            text("solicitud.estado IN (CAST('pendiente' AS estado_solicitud), CAST('en viaje' AS estado_solicitud))")
        ).all()

        # 5. Serialización Manual (Para incluir objetos anidados como Cliente y Localidad)
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
        print(f"Error en dashboard transportista: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500


@solicitudes_bp.route('/api/solicitudes/<int:id>/comenzar-viaje', methods=['POST'])
@require_auth
def comenzar_viaje(id):
    """
    Cambia el estado de la solicitud de 'pendiente' a 'en viaje'.
    Solo el transportista asignado puede hacer esto.
    """
    current_uid = request.uid

    try:
        # 1. Identificar al Transportista
        usuario = Usuario.query.filter_by(u_id=current_uid).first()
        transportista = Transportista.query.filter_by(usuario_id=usuario.usuario_id).first()

        if not transportista:
            return jsonify({"error": "No tienes permiso de transportista"}), 403

        # 2. Obtener la solicitud
        solicitud = Solicitud.query.get(id)
        if not solicitud:
            return jsonify({"error": "Solicitud no encontrada"}), 404

        # 3. Validaciones de Seguridad
        # A. Que la solicitud tenga presupuesto aceptado
        if not solicitud.presupuesto or not solicitud.presupuesto.transportista:
             return jsonify({"error": "Esta solicitud no tiene transportista asignado"}), 400

        # B. Que el transportista sea EL MISMO que el del presupuesto aceptado
        if solicitud.presupuesto.transportista.transportista_id != transportista.transportista_id:
            return jsonify({"error": "No eres el transportista asignado a este viaje"}), 403

        # C. Que el estado sea correcto (Solo se puede iniciar si está 'pendiente')
        if solicitud.estado != 'pendiente':
            return jsonify({"error": f"No se puede iniciar. Estado actual: {solicitud.estado}"}), 400

        # 4. Actualizar Estado
        # Usamos el string exacto que espera tu ENUM en Postgres
        solicitud.estado = 'en viaje'

        db.session.commit()

        socketio.emit('lista_actualizada', {'action': 'comenzar_viaje', 'id': id})

        return jsonify({
            "message": "Viaje iniciado correctamente",
            "solicitud": solicitud.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"Error al iniciar viaje: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500

@solicitudes_bp.route('/api/solicitudes/<int:id>/completar', methods=['POST'])
@require_auth
def completar_viaje(id):
    """
    Finaliza el viaje. Cambia estado de 'en viaje' a 'completada'.
    """
    current_uid = request.uid

    try:
        # 1. Validar Transportista
        usuario = Usuario.query.filter_by(u_id=current_uid).first()
        transportista = Transportista.query.filter_by(usuario_id=usuario.usuario_id).first()

        if not transportista:
            return jsonify({"error": "No tienes permiso de transportista"}), 403

        # 2. Obtener solicitud
        solicitud = Solicitud.query.get(id)
        if not solicitud:
            return jsonify({"error": "Solicitud no encontrada"}), 404

        # 3. Validar Propiedad (Que sea su viaje)
        if not solicitud.presupuesto or solicitud.presupuesto.transportista_id != transportista.transportista_id:
             return jsonify({"error": "No eres el transportista de esta solicitud"}), 403

        # 4. Validar Estado (Debe estar 'en viaje')
        if solicitud.estado != 'en viaje':
            return jsonify({"error": f"No se puede completar. Estado actual: {solicitud.estado}"}), 400

        # 5. Actualizar Estado
        solicitud.estado = 'completada'

        # Opcional: Podrías guardar la fecha de finalización aquí si tienes una columna para eso
        # solicitud.fecha_fin = datetime.now()

        db.session.commit()

        socketio.emit('lista_actualizada', {'action': 'completar_viaje', 'id': id})

        return jsonify({
            "message": "Viaje completado exitosamente",
            "solicitud": solicitud.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"Error al completar viaje: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500



@solicitudes_bp.route('/api/solicitudes/mis-pedidos', methods=['GET'])
@require_auth
def get_solicitudess_usuario():
    current_uid = request.uid

    print(f"🔍 [mis-pedidos] Usuario solicitante UID: {current_uid}")

    try:
        # 1. Obtener el usuario (Cliente) desde el token
        usuario = Usuario.query.filter_by(u_id=current_uid).first()

        if not usuario:
            print(f"⚠️ [mis-pedidos] Usuario no encontrado con UID: {current_uid}")
            return jsonify([]), 200

        print(f"✅ [mis-pedidos] Usuario encontrado: ID={usuario.usuario_id}, Nombre={usuario.nombre}")

        # 2. Consultar Solicitudes con Eager Loading
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

        # 3. Serialización Manual
        response_data = []

        for idx, s in enumerate(solicitudes):
            print(f"🔧 [mis-pedidos] Procesando solicitud {idx + 1}/{len(solicitudes)} - ID: {s.solicitud_id}")

            data = s.to_dict()

            # A. Localidades
            if s.localidad_origen:
                data['localidad_origen'] = s.localidad_origen.to_dict()
                print(f"  ✓ Localidad origen: {s.localidad_origen.nombre}")
            else:
                data['localidad_origen'] = None
                print(f"  ⚠️ Sin localidad origen")

            if s.localidad_destino:
                data['localidad_destino'] = s.localidad_destino.to_dict()
                print(f"  ✓ Localidad destino: {s.localidad_destino.nombre}")
            else:
                data['localidad_destino'] = None
                print(f"  ⚠️ Sin localidad destino")

            # B. Presupuesto Aceptado
            data['presupuesto'] = None

            if s.presupuesto_aceptado:
                print(f"  💰 Tiene presupuesto aceptado ID: {s.presupuesto_aceptado}")

                # Buscar el presupuesto (debería estar ya cargado por joinedload)
                if s.presupuesto and s.presupuesto.presupuesto_id == s.presupuesto_aceptado:
                    presupuesto = s.presupuesto
                else:
                    # Fallback: buscarlo manualmente si no está en la relación
                    presupuesto = Presupuesto.query.options(
                        joinedload(Presupuesto.transportista).joinedload(Transportista.usuario)
                    ).get(s.presupuesto_aceptado)

                if presupuesto:
                    p_data = presupuesto.to_dict()

                    # Agregar info del transportista
                    if presupuesto.transportista:
                        t_data = presupuesto.transportista.to_dict()

                        if presupuesto.transportista.usuario:
                            u_trans = presupuesto.transportista.usuario
                            t_data['usuario'] = {
                                'nombre': u_trans.nombre,
                                'apellido': u_trans.apellido,
                                'telefono': u_trans.telefono
                            }
                            print(f"  ✓ Transportista: {u_trans.nombre} {u_trans.apellido}")

                        p_data['transportista'] = t_data

                    data['presupuesto'] = p_data
                else:
                    print(f"  ⚠️ Presupuesto {s.presupuesto_aceptado} no encontrado")
            else:
                print(f"  ℹ️ Sin presupuesto aceptado")

            response_data.append(data)

        print(f"✨ [mis-pedidos] Respuesta final: {len(response_data)} solicitudes")

        # Log del primer elemento para debugging
        if response_data:
            print(f"📦 [mis-pedidos] Ejemplo de solicitud a enviar:")
            print(f"   - ID: {response_data[0].get('solicitud_id')}")
            print(f"   - Estado: {response_data[0].get('estado')}")
            print(f"   - Tiene localidad_origen: {response_data[0].get('localidad_origen') is not None}")
            print(f"   - Tiene localidad_destino: {response_data[0].get('localidad_destino') is not None}")
            print(f"   - Tiene presupuesto: {response_data[0].get('presupuesto') is not None}")

        return jsonify(response_data), 200

    except Exception as e:
        print(f"❌ [mis-pedidos] Error crítico: {e}")
        import traceback
        print(f"🔥 Traceback completo:")
        print(traceback.format_exc())
        return jsonify({"error": "Error interno del servidor"}), 500


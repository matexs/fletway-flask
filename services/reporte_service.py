import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import uuid

# Importamos SQLAlchemy y los Modelos necesarios
from config import db
from models import Reporte, Transportista, Solicitud, Usuario, Presupuesto
from sqlalchemy.orm import joinedload

# Configuración Email
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_SENDER = "soporte.fletway01@gmail.com"
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_ADMIN = "franrojas331@gmail.com"

# --- CREACIÓN ---
def crear_nuevo_reporte(usuario_id, solicitud_id, motivo, mensaje_usuario):
    """
    Crea el reporte.
    NOTA: 'usuario_id' llega desde el frontend como un UUID string (ej: "a7ec..."),
    así que debemos buscar el ID numérico real en la BD.
    """
    try:
        # --- PASO 1: RESOLVER QUIÉN ES EL USUARIO (UUID -> INT) ---
        real_id_numerico = None

        # Intentamos tratarlo como UUID primero
        try:
            validador_uuid = uuid.UUID(str(usuario_id))
            # Buscamos en la tabla Usuario usando la columna u_id (que es el UUID)
            usuario_encontrado = Usuario.query.filter_by(u_id=validador_uuid).first()

            if usuario_encontrado:
                real_id_numerico = usuario_encontrado.usuario_id
        except ValueError:
            # Si falla la conversión a UUID, quizás ya enviaron un número
            # (esto es por seguridad, por si cambias la lógica luego)
            real_id_numerico = int(usuario_id)

        if not real_id_numerico:
            raise Exception(f"No se encontró un usuario registrado con el ID/UUID: {usuario_id}")

        # --- PASO 2: GUARDAR EL REPORTE ---
        nuevo_reporte = Reporte(
            usuario_id=real_id_numerico, # ¡Ahora sí usamos el entero!
            solicitud_id=solicitud_id,
            motivo=motivo,
            descripcion=mensaje_usuario,
            estado="pendiente",
            creado_en=datetime.now()
        )

        db.session.add(nuevo_reporte)
        db.session.commit()

        # Enviar correo (no bloqueante)
        email_ok = _enviar_correo_admin(nuevo_reporte)  # capturar resultado

        return {
            "success": True,
            "reporte": nuevo_reporte,
            "email_enviado": email_ok  # ← ahora refleja la realidad
        }

    except Exception as e:
        db.session.rollback()
        # Es bueno imprimir el error en consola de Cloud Run para depurar
        print(f"Error creando reporte: {e}")
        raise e

def obtener_viajes_fletero_por_uuid(supabase_uuid):
    try:
        # 1. Validar y convertir UUID
        try:
            uuid_obj = uuid.UUID(str(supabase_uuid))
        except (ValueError, AttributeError):
            return []

        # 2. Obtener Usuario
        usuario = Usuario.query.filter_by(u_id=uuid_obj).first()
        if not usuario:
            return []

        # 3. Obtener Transportista
        transportista = Transportista.query.filter_by(usuario_id=usuario.usuario_id).first()
        if not transportista:
            return []

        # 4. Consulta con JOIN (Corregida la sintaxis de multilínea con paréntesis)
        viajes = (
            db.session.query(Solicitud)
            .join(Presupuesto, Solicitud.presupuesto_aceptado == Presupuesto.presupuesto_id)
            .options(
                joinedload(Solicitud.localidad_origen),
                joinedload(Solicitud.localidad_destino),
                joinedload(Solicitud.cliente),
                joinedload(Solicitud.presupuesto)
                    .joinedload(Presupuesto.transportista)
                    .joinedload(Transportista.usuario)
            )
            .filter(Presupuesto.transportista_id == transportista.transportista_id)
            .order_by(Solicitud.fecha_creacion.desc())
            .all()
        )

        return [_serializar_solicitud(v) for v in viajes]

    except Exception as e:
        print(f"Error en obtener_viajes_fletero: {str(e)}")
        # Es mejor relanzar o manejar el error según tu flujo de Flask
        return []

def obtener_pedidos_cliente_por_uuid(supabase_uuid):
    try:
        # 1. Obtener Usuario
        try:
            uuid_obj = uuid.UUID(str(supabase_uuid))
        except ValueError:
            return []

        usuario = Usuario.query.filter_by(u_id=uuid_obj).first()
        if not usuario:
            return []

        usuario_int_id = usuario.usuario_id

        # 2. LÓGICA CORREGIDA: Verificar si tiene presupuesto aceptado
        # Buscamos solicitudes del usuario donde 'presupuesto_aceptado' NO SEA NULL

        pedidos = Solicitud.query.options(
            joinedload(Solicitud.localidad_origen),
            joinedload(Solicitud.localidad_destino),
            joinedload(Solicitud.cliente),
            joinedload(Solicitud.presupuesto).joinedload(Presupuesto.transportista).joinedload(Transportista.usuario)
        ).filter(
            Solicitud.cliente_id == usuario_int_id,
            Solicitud.presupuesto_aceptado != None
        ).order_by(Solicitud.fecha_creacion.desc()).all()

        return [_serializar_solicitud(p) for p in pedidos]

    except Exception as e:
        print(f"Error cliente: {e}")
        raise e

# --- HELPERS ---

def _serializar_solicitud(solicitud):
    # Validamos fechas para evitar errores si son None
    fecha_iso = solicitud.fecha_creacion.isoformat() if hasattr(solicitud, 'fecha_creacion') and solicitud.fecha_creacion else None

    # ✅ FIX CRÍTICO: Convertir enum EstadoSolicitud a string
    estado_str = solicitud.estado.value if hasattr(solicitud.estado, 'value') else str(solicitud.estado)

    # Serializar localidades si existen (evita N+1 queries con joinedload)
    localidad_origen = None
    if solicitud.localidad_origen:
        localidad_origen = {
            'localidad_id': solicitud.localidad_origen.localidad_id,
            'nombre': solicitud.localidad_origen.nombre,
            'provincia': solicitud.localidad_origen.provincia
        }

    localidad_destino = None
    if solicitud.localidad_destino:
        localidad_destino = {
            'localidad_id': solicitud.localidad_destino.localidad_id,
            'nombre': solicitud.localidad_destino.nombre,
            'provincia': solicitud.localidad_destino.provincia
        }

    # Serializar cliente si existe
    cliente = None
    if solicitud.cliente:
        cliente = {
            'usuario_id': solicitud.cliente.usuario_id,
            'nombre': solicitud.cliente.nombre,
            'apellido': solicitud.cliente.apellido,
            'email': solicitud.cliente.email,
            'telefono': solicitud.cliente.telefono
        }

    # Serializar transportista si existe
    transportista = None
    if solicitud.presupuesto and solicitud.presupuesto.transportista:
        transp = solicitud.presupuesto.transportista
        transportista = {
            'transportista_id': transp.transportista_id,
            'nombre': transp.usuario.nombre if transp.usuario else None,
            'apellido': transp.usuario.apellido if transp.usuario else None,
            'telefono': transp.usuario.telefono if transp.usuario else None,
            'calificacion_promedio': float(transp.calificacion_promedio) if transp.calificacion_promedio else None,
            'total_calificaciones': transp.total_calificaciones or 0
        }

    # Presupuesto si existe
    presupuesto_info = None
    if solicitud.presupuesto:
        presupuesto_info = {
            'presupuesto_id': solicitud.presupuesto.presupuesto_id,

        }

    return {
        "solicitud_id": solicitud.solicitud_id,
        "detalles_carga": solicitud.detalles_carga,
        "direccion_origen": solicitud.direccion_origen,
        "direccion_destino": solicitud.direccion_destino,
        "localidad_origen": localidad_origen,
        "localidad_destino": localidad_destino,
        "fecha_creacion": fecha_iso,
        "estado": estado_str,  # ✅ Ahora es string, no enum
        "cliente": cliente,
        "transportista": transportista,
        "presupuesto": presupuesto_info,

    }

def _enviar_correo_admin(reporte):
    try:
        usuario = Usuario.query.get(reporte.usuario_id)

        # Obtenemos el email (si por alguna razón no existe el usuario, ponemos un texto default)
        email_usuario = usuario.email if usuario else "Email no encontrado"
        nombre_completo = f"{usuario.nombre} {usuario.apellido}" if usuario else "Usuario Desconocido"
        cuerpo = f"""
        NUEVO REPORTE #{reporte.reporte_id}
        --------------------------------
        Usuario ID (Int): {reporte.usuario_id}
        Nombre: {nombre_completo}
        Email: {email_usuario}
        Motivo: {reporte.motivo}
        Solicitud: {reporte.solicitud_id}

        Mensaje:
        {reporte.descripcion}
        """

        msg = MIMEText(cuerpo)
        msg['Subject'] = f"Reporte #{reporte.reporte_id}: {reporte.motivo}"
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_ADMIN

        if usuario:
            msg.add_header('Reply-To', email_usuario)

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_ADMIN, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Error mail: {e}")
        return False
import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import uuid

# Importamos SQLAlchemy y los Modelos necesarios
from config import db
from models import Reporte, Transportista, Solicitud, Usuario, Presupuesto

# Configuración Email
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_SENDER = "soporte.fletway@gmail.com"
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_ADMIN = "mateoreyx@gmail.com"

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
        _enviar_correo_admin(nuevo_reporte)

        return {
            "success": True,
            "reporte": nuevo_reporte,
            "email_enviado": True
        }

    except Exception as e:
        db.session.rollback()
        # Es bueno imprimir el error en consola de Cloud Run para depurar
        print(f"Error creando reporte: {e}")
        raise e

# --- CONSULTAS ---

def obtener_viajes_fletero_por_uuid(supabase_uuid):
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

        # 2. Obtener Transportista
        transportista = Transportista.query.filter_by(usuario_id=usuario_int_id).first()
        if not transportista:
            return []

        # 3. LÓGICA CORREGIDA: JOIN entre Solicitud y Presupuesto
        # Buscamos solicitudes cuyo 'presupuesto_aceptado' coincida con un presupuesto de ESTE transportista.

        # SQL equivalente:
        # SELECT s.* FROM solicitud s
        # JOIN presupuesto p ON s.presupuesto_aceptado = p.presupuesto_id
        # WHERE p.transportista_id = MI_ID

        viajes = db.session.query(Solicitud)\
            .join(Presupuesto, Solicitud.presupuesto_aceptado == Presupuesto.presupuesto_id)\
            .filter(Presupuesto.transportista_id == transportista.transportista_id)\
            .order_by(Solicitud.fecha_creacion.desc())\
            .all()

        return [_serializar_solicitud(v) for v in viajes]

    except Exception as e:
        print(f"Error fletero: {e}")
        raise e

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

        pedidos = Solicitud.query.filter(
            Solicitud.cliente_id == usuario_int_id, # Asegúrate que en tu modelo se llame 'usuario_id' (o 'cliente_id' si no lo cambiaste)
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
    # Si usas 'fecha_hora' en lugar de 'fecha_creacion', ajusta aquí.
    # En tu modelo Solicitud vi 'fecha_creacion', por eso lo usé.

    return {
        "solicitud_id": solicitud.solicitud_id,
        "descripcion": solicitud.detalles_carga, # Ajustado a 'detalles_carga' según tu modelo
        "direccion_origen": solicitud.direccion_origen,
        "direccion_destino": solicitud.direccion_destino,
        "fecha_hora": fecha_iso,
        "estado": solicitud.estado
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
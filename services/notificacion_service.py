"""
Servicio de notificaciones por email.
Envía correos al cliente cuando el estado de su solicitud cambia.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configuración SMTP (reutilizamos las mismas credenciales que reporte_service)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
# EMAIL_SENDER = "soporte.fletway@gmail.com"
EMAIL_SENDER = "soporte.fletway01@gmail.com"
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")


def enviar_notificacion_presupuesto(solicitud, presupuesto, transportista):
    """
    Envía un correo al cliente cuando recibe un nuevo presupuesto.
    
    Args:
        solicitud: Objeto Solicitud con relaciones cargadas (cliente, localidades)
        presupuesto: Objeto Presupuesto recién creado
        transportista: Objeto Transportista con usuario cargado
    
    Returns:
        bool: True si el correo se envió correctamente, False en caso contrario
    """
    try:
        # Validar que tenemos un cliente con email
        if not solicitud.cliente or not solicitud.cliente.email:
            print(f"⚠️ [notificacion_service] Solicitud {solicitud.solicitud_id} sin cliente o email")
            return False

        cliente = solicitud.cliente
        email_destino = cliente.email
        nombre_cliente = f"{cliente.nombre} {cliente.apellido}"

        # Información del transportista
        transportista_nombre = "Transportista"
        if transportista.usuario:
            transportista_nombre = f"{transportista.usuario.nombre} {transportista.usuario.apellido}"

        # Información de la solicitud
        solicitud_id = solicitud.solicitud_id
        origen = solicitud.direccion_origen or "Origen no especificado"
        destino = solicitud.direccion_destino or "Destino no especificado"

        if solicitud.localidad_origen:
            origen += f" ({solicitud.localidad_origen.nombre}, {solicitud.localidad_origen.provincia})"
        if solicitud.localidad_destino:
            destino += f" ({solicitud.localidad_destino.nombre}, {solicitud.localidad_destino.provincia})"

        # Construir mensaje
        asunto = f"Fletway - Nuevo presupuesto para tu solicitud #{solicitud_id}"
        cuerpo = f"""
Hola {nombre_cliente},

Has recibido un nuevo presupuesto para tu solicitud de flete.

Detalles de la solicitud:
- Solicitud ID: #{solicitud_id}
- Origen: {origen}
- Destino: {destino}

Presupuesto recibido:
- Transportista: {transportista_nombre}
- Precio estimado: ${presupuesto.precio_estimado:,.2f}
- Comentario: {presupuesto.comentario or 'Sin comentarios'}

Ingresa a tu cuenta para revisar el presupuesto completo y aceptarlo si te interesa.

Saludos,
Equipo Fletway
"""

        # Crear mensaje MIME
        msg = MIMEMultipart('alternative')
        msg['Subject'] = asunto
        msg['From'] = EMAIL_SENDER
        msg['To'] = email_destino

        # Agregar cuerpo en texto plano
        parte_texto = MIMEText(cuerpo, 'plain')
        msg.attach(parte_texto)

        # Enviar correo
        print(f"📧 [notificacion_service] Enviando email de presupuesto a {email_destino}")
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, email_destino, msg.as_string())
        server.quit()

        print(f"✅ [notificacion_service] Email de presupuesto enviado correctamente a {email_destino}")
        return True

    except Exception as e:
        print(f"❌ [notificacion_service] Error enviando email de presupuesto: {e}")
        return False


def enviar_notificacion_presupuesto_aceptado(solicitud, presupuesto, transportista):
    """
    Envía un correo al fletero cuando su presupuesto es aceptado por el cliente.
    
    Args:
        solicitud: Objeto Solicitud con relaciones cargadas (cliente, localidades)
        presupuesto: Objeto Presupuesto aceptado
        transportista: Objeto Transportista con usuario cargado
    
    Returns:
        bool: True si el correo se envió correctamente, False en caso contrario
    """
    try:
        # Validar que tenemos un transportista con email
        if not transportista.usuario or not transportista.usuario.email:
            print(f"⚠️ [notificacion_service] Transportista sin email")
            return False

        email_destino = transportista.usuario.email
        nombre_fletero = f"{transportista.usuario.nombre} {transportista.usuario.apellido}"

        # Información del cliente
        nombre_cliente = "Cliente"
        if solicitud.cliente:
            nombre_cliente = f"{solicitud.cliente.nombre} {solicitud.cliente.apellido}"

        # Información de la solicitud
        solicitud_id = solicitud.solicitud_id
        origen = solicitud.direccion_origen or "Origen no especificado"
        destino = solicitud.direccion_destino or "Destino no especificado"

        asunto = f"🎉 ¡Tu presupuesto fue aceptado! - Solicitud #{solicitud_id}"
        cuerpo = f"""¡Hola {nombre_fletero}!

¡Buenas noticias! Tu presupuesto para la solicitud #{solicitud_id} fue aceptado por {nombre_cliente}.

📋 Detalles de la solicitud:
   - Origen: {origen}
   - Destino: {destino}
   - Precio aceptado: ${presupuesto.precio_estimado:,.2f}

Ingresá a Fletway para coordinar el viaje con el cliente.

¡Gracias por usar Fletway!
Equipo Fletway"""

        # Crear mensaje MIME
        msg = MIMEMultipart('alternative')
        msg['Subject'] = asunto
        msg['From'] = EMAIL_SENDER
        msg['To'] = email_destino

        parte_texto = MIMEText(cuerpo, 'plain')
        msg.attach(parte_texto)

        # Enviar correo
        print(f"📧 [notificacion_service] Enviando email al fletero {email_destino} - Presupuesto aceptado")
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, email_destino, msg.as_string())
        server.quit()

        print(f"✅ [notificacion_service] Email enviado correctamente al fletero {email_destino}")
        return True

    except Exception as e:
        print(f"❌ [notificacion_service] Error enviando email de presupuesto aceptado al fletero: {e}")
        return False


def enviar_notificacion_estado(solicitud, estado_nuevo):
    """
    Envía un correo al cliente cuando cambia el estado de su solicitud.
    
    Args:
        solicitud: Objeto Solicitud con relaciones cargadas (cliente, localidades, presupuesto)
        estado_nuevo: String con el nuevo estado ('sin transportista', 'pendiente', 'en viaje', 'completada', 'cancelado')
    
    Returns:
        bool: True si el correo se envió correctamente, False en caso contrario
    """
    try:
        # Validar que tenemos un cliente con email
        if not solicitud.cliente or not solicitud.cliente.email:
            print(f"⚠️ [notificacion_service] Solicitud {solicitud.solicitud_id} sin cliente o email")
            return False

        cliente = solicitud.cliente
        email_destino = cliente.email
        nombre_cliente = f"{cliente.nombre} {cliente.apellido}"

        # Construir asunto y cuerpo según el estado
        asunto, cuerpo = _construir_mensaje(solicitud, estado_nuevo, nombre_cliente)

        # Crear mensaje MIME
        msg = MIMEMultipart('alternative')
        msg['Subject'] = asunto
        msg['From'] = EMAIL_SENDER
        msg['To'] = email_destino

        # Agregar cuerpo en texto plano
        parte_texto = MIMEText(cuerpo, 'plain')
        msg.attach(parte_texto)

        # Enviar correo
        print(f"📧 [notificacion_service] Enviando email a {email_destino} - Estado: {estado_nuevo}")
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, email_destino, msg.as_string())
        server.quit()

        print(f"✅ [notificacion_service] Email enviado correctamente a {email_destino}")
        return True

    except Exception as e:
        print(f"❌ [notificacion_service] Error enviando email: {e}")
        return False


def _construir_mensaje(solicitud,estado_nuevo, nombre_cliente):
    """
    Construye el asunto y cuerpo del correo según el estado.
    
    Returns:
        tuple: (asunto, cuerpo)
    """
    solicitud_id = solicitud.solicitud_id
    origen = solicitud.direccion_origen or "Origen no especificado"
    destino = solicitud.direccion_destino or "Destino no especificado"

    # Información de localidades si está disponible
    if solicitud.localidad_origen:
        origen += f" ({solicitud.localidad_origen.nombre}, {solicitud.localidad_origen.provincia})"
    if solicitud.localidad_destino:
        destino += f" ({solicitud.localidad_destino.nombre}, {solicitud.localidad_destino.provincia})"

    # Plantillas según estado
    if estado_nuevo == 'sin transportista':
        asunto = f"Fletway - Solicitud #{solicitud_id} creada"
        cuerpo = f"""
Hola {nombre_cliente},

Tu solicitud de flete ha sido creada exitosamente.

Detalles de la solicitud:
- Solicitud ID: #{solicitud_id}
- Origen: {origen}
- Destino: {destino}
- Carga: {solicitud.detalles_carga or 'No especificado'}

Los transportistas de tu zona recibirán tu solicitud y podrán enviarte presupuestos.
Te notificaremos cuando recibas ofertas.

Saludos,
Equipo Fletway
"""

    elif estado_nuevo == 'pendiente':
        # Estado pendiente = presupuesto aceptado, esperando inicio de viaje
        transportista_info = "Transportista asignado"
        if solicitud.presupuesto and solicitud.presupuesto.transportista and solicitud.presupuesto.transportista.usuario:
            trans_usuario = solicitud.presupuesto.transportista.usuario
            transportista_info = f"{trans_usuario.nombre} {trans_usuario.apellido} - Tel: {trans_usuario.telefono}"
        
        asunto = f"Fletway - Presupuesto aceptado para solicitud #{solicitud_id}"
        cuerpo = f"""
Hola {nombre_cliente},

Has aceptado un presupuesto para tu solicitud de flete.

Detalles de la solicitud:
- Solicitud ID: #{solicitud_id}
- Origen: {origen}
- Destino: {destino}
- Transportista: {transportista_info}

El transportista se pondrá en contacto contigo para coordinar la recogida.

Saludos,
Equipo Fletway
"""

    elif estado_nuevo == 'en viaje':
        asunto = f"Fletway - Tu flete está en camino (Solicitud #{solicitud_id})"
        cuerpo = f"""
Hola {nombre_cliente},

Tu flete ha comenzado el viaje.

Detalles:
- Solicitud ID: #{solicitud_id}
- Origen: {origen}
- Destino: {destino}

El transportista está en camino. Te notificaremos cuando el viaje se complete.

Saludos,
Equipo Fletway
"""

    elif estado_nuevo == 'completada':
        asunto = f"Fletway - Flete completado (Solicitud #{solicitud_id})"
        cuerpo = f"""
Hola {nombre_cliente},

Tu flete ha sido completado exitosamente.

Detalles:
- Solicitud ID: #{solicitud_id}
- Origen: {origen}
- Destino: {destino}

Por favor, califica tu experiencia con el transportista para ayudar a otros usuarios.

Saludos,
Equipo Fletway
"""

    elif estado_nuevo == 'cancelado':
        asunto = f"Fletway - Solicitud cancelada (#{solicitud_id})"
        cuerpo = f"""
Hola {nombre_cliente},

Tu solicitud de flete ha sido cancelada.

Detalles:
- Solicitud ID: #{solicitud_id}
- Origen: {origen}
- Destino: {destino}

Si tienes alguna duda, no dudes en contactarnos.

Saludos,
Equipo Fletway
"""

    else:
        # Estado desconocido - mensaje genérico
        asunto = f"Fletway - Actualización de solicitud #{solicitud_id}"
        cuerpo = f"""
Hola {nombre_cliente},

Tu solicitud de flete ha sido actualizada.

Detalles:
- Solicitud ID: #{solicitud_id}
- Estado: {estado_nuevo}
- Origen: {origen}
- Destino: {destino}

Saludos,
Equipo Fletway
"""

    return asunto, cuerpo



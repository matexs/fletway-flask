"""Servicio para manejar operaciones CRUD de Solicitud."""

from config import db
from models import Solicitud

def obtener_todas():
    """Obtiene todas las solicitudes."""
    return Solicitud.query.all()

def obtener_por_id(id_):
    """Obtiene una solicitud por su ID."""
    return Solicitud.query.get(id_)

def crear(data):
    """Crea una nueva solicitud."""
    nueva = Solicitud(**data)
    db.session.add(nueva)
    db.session.commit()
    return nueva

def obtener_solicitudes_sin_transportista(id_localidad):
    """Obtiene todas las solicitudes que no tienen un transportista asignado y son de una localidad específica."""
    return Solicitud.query.filter(
        (Solicitud.presupuesto_aceptado == None) & 
        (Solicitud.localidad_origen_id == id_localidad)
    ).all()

def actualizar(id_, data):
    """Actualiza una solicitud existente."""
    solicitud = Solicitud.query.get(id_)
    if not solicitud:
        return None  # No se encontró la solicitud

    # Actualiza los campos que vienen en 'data'
    # .get(clave, valor_por_defecto) se usa para no fallar si un dato no viene
    solicitud.cliente_id = data.get("cliente_id", solicitud.cliente_id)
    solicitud.presupuesto_aceptado = data.get("presupuesto_aceptado", solicitud.presupuesto_aceptado)
    solicitud.localidad_origen_id = data.get("localidad_origen_id", solicitud.localidad_origen_id)
    solicitud.direccion_origen = data.get("direccion_origen", solicitud.direccion_origen)
    solicitud.direccion_destino = data.get("direccion_destino", solicitud.direccion_destino)
    solicitud.detalles_carga = data.get("detalles_carga", solicitud.detalles_carga)
    solicitud.estado = data.get("estado", solicitud.estado)
    solicitud.hora_recogida = data.get("hora_recogida", solicitud.hora_recogida)

    db.session.commit()  # Guarda los cambios en la base de datos
    return solicitud

def eliminar(id_):
    """Elimina una solicitud por su ID."""
    solicitud = Solicitud.query.get(id_)
    if not solicitud:
        return False  # No se encontró la solicitud

    db.session.delete(solicitud)
    db.session.commit()
    return True
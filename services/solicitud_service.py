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
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

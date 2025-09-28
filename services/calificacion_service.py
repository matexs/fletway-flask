"""Servicio para manejar operaciones relacionadas con calificaciones."""

from config import db
from models import Calificacion

def obtener_todas():
    """Obtiene todas las calificaciones."""
    return Calificacion.query.all()

def obtener_por_id(id_):
    """Obtiene una calificación por su ID."""
    return Calificacion.query.get(id_)

def crear(data):
    """Crea una nueva calificación."""
    nueva = Calificacion(
        solicitud_id=data["solicitud_id"],
        cliente_id=data["cliente_id"],
        transportista_id=data["transportista_id"],
        puntuacion=data["puntuacion"],
        comentario=data.get("comentario"),
        fecha_creacion=data.get("fecha_creacion")
    )
    db.session.add(nueva)
    db.session.commit()
    return nueva

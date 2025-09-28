"""Servicio para manejar operaciones CRUD de Localidad."""

from config import db
from models import Localidad

def obtener_todas():
    """Obtiene todas las localidades."""
    return Localidad.query.all()

def obtener_por_id(id_):
    """Obtiene una localidad por su ID."""
    return Localidad.query.get(id_)

def crear(data):
    """Crea una nueva localidad."""
    nueva = Localidad(
        nombre=data["nombre"],
        provincia=data["provincia"],
        codigo_postal=data.get("codigo_postal")
    )
    db.session.add(nueva)
    db.session.commit()
    return nueva

"""Servicio para manejar operaciones relacionadas con usuarios."""

from config import db
from models import Usuario

def obtener_todos():
    """Obtiene todos los usuarios."""
    return Usuario.query.all()

def obtener_por_id(id_):
    """Obtiene un usuario por su ID."""
    return Usuario.query.get(id_)

def crear(data):
    """Crea un nuevo usuario."""
    nuevo = Usuario(
        nombre=data["nombre"],
        apellido=data.get("apellido"),
        email=data["email"],
        contrasena=data.get("contrasena"),
        telefono=data.get("telefono"),
        fecha_registro=data.get("fecha_registro"),
        fecha_nacimiento=data.get("fecha_nacimiento")
    )
    db.session.add(nuevo)
    db.session.commit()
    return nuevo

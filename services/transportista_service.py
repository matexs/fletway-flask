"""Servicio para manejar operaciones relacionadas con Transportista."""

from config import db
from models import Transportista,Usuario

def obtener_todos():
    """Obtiene todos los transportistas."""
    return Transportista.query.all()

def obtener_por_id(id_):
    """Obtiene un transportista por su ID."""
    return Transportista.query.get(id_)

def crear(data):
    """Crea un nuevo transportista."""
    nuevo = Transportista(
        descripcion=data.get("descripcion"),
        tipo_vehiculo=data["tipo_vehiculo"],
        capacidad_kg=data.get("capacidad_kg"),
        calificacion_promedio=data.get("calificacion_promedio"),
        usuario_id=data["usuario_id"],
        patente_vehiculo=data["patente_vehiculo"],
        modelo_vehiculo=data.get("modelo_vehiculo")
    )
    db.session.add(nuevo)
    db.session.commit()
    return nuevo

def obtener_transportista_by_id(transportista_id: int):
    """Obtiene un transportista junto con los datos del usuario asociado."""
    try:
        # 1️⃣ Buscar transportista
        transportista = Transportista.query.get(transportista_id)
        if not transportista:
            return None

        # 2️⃣ Buscar usuario asociado
        usuario = Usuario.query.get(transportista.usuario_id)
        if not usuario:
            return None

        # 3️⃣ Combinar datos
        transportista_completo = {
            "transportista_id": transportista.transportista_id,
            "descripcion": transportista.descripcion,
            "capacidad_kg": transportista.capacidad_kg,
            "calificacion_promedio": transportista.calificacion_promedio,
            "patente_vehiculo": transportista.patente_vehiculo,
            "modelo_vehiculo": transportista.modelo_vehiculo,
            "usuario": {
                "usuario_id": usuario.usuario_id,
                "nombre": usuario.nombre,
                "apellido": usuario.apellido,
                "email": usuario.email,
                "telefono": usuario.telefono,
                "fecha_registro": usuario.fecha_registro,
                "fecha_nacimiento": usuario.fecha_nacimiento
            }
        }

        return transportista_completo

    except Exception as e:
        db.session.rollback()
        print(f"Error al obtener el transportista: {e}")
        return None

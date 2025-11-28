"""Servicio para manejar operaciones relacionadas con Presupuesto."""

from config import db
from models import Presupuesto

def obtener_todos():
    """Obtiene todos los presupuestos."""
    return Presupuesto.query.all()

def obtener_por_id(id_):
    """Obtiene un presupuesto por su ID."""
    return Presupuesto.query.get(id_)

def crear(data):
    """Crea un nuevo presupuesto."""
    nuevo = Presupuesto(
        solicitud_id=data["solicitud_id"],
        transportista_id=data["transportista_id"],
        precio_estimado=data["precio_estimado"],
        comentario=data.get("comentario"),
        estado=data.get("estado", "pendiente")
    )
    db.session.add(nuevo)
    db.session.commit()
    return nuevo


def obtener_por_solicitud(solicitud_id=None, estado="pendiente"):
    """Obtiene presupuestos por ID de solicitud y estado."""
    if solicitud_id is None:
        raise ValueError("El parámetro 'solicitud_id' es obligatorio.")
    return Presupuesto.query.filter_by(solicitud_id=solicitud_id, estado=estado).all()


def aceptar_presupuesto(presupuesto_id,solicitud_id):
    """Acepta un presupuesto y rechaza los demás asociados a la misma solicitud."""
    try:
        Presupuesto.query.filter_by(solicitud_id=solicitud_id).update({"estado": "rechazado"})

        presupuesto = Presupuesto.query.get_or_404(presupuesto_id)

        presupuesto.estado = "aceptado"

        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        print(f"Error al aceptar el presupuesto: {e}")
        return False

def rechazar_presupuesto(presupuesto_id: int):
    """Rechaza un presupuesto específico."""
    try:
        presupuesto = Presupuesto.query.get_or_404(presupuesto_id)
        if not presupuesto:
            return False
        presupuesto.estado = "rechazado"
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        print(f"Error al rechazar el presupuesto: {e}")
        return False

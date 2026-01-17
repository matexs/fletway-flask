"""Servicio para manejar operaciones relacionadas con Presupuesto."""

from config import db
from models import Presupuesto,Usuario,Transportista

def obtener_todos():
    """Obtiene todos los presupuestos."""
    return Presupuesto.query.all()

def obtener_por_id(id_):
    """Obtiene un presupuesto por su ID."""
    return Presupuesto.query.get(id_)

def crear(data, uid: str):
    """Crea un nuevo presupuesto usando el usuario autenticado (Supabase uid)."""

    usuario = Usuario.query.filter_by(u_id=uid).first()
    if not usuario:
        raise ValueError("No existe usuario para este uid")

    transportista = Transportista.query.filter_by(usuario_id=usuario.usuario_id).first()
    if not transportista:
        raise ValueError("El usuario no es transportista")

    nuevo = Presupuesto(
        solicitud_id=data["solicitud_id"],
        transportista_id=transportista.transportista_id,
        precio_estimado=data["precio_estimado"],
        comentario=data.get("comentario"),
        estado=data.get("estado", "pendiente"),
    )
    db.session.add(nuevo)
    db.session.commit()
    return nuevo


def obtener_por_solicitud(solicitud_id: int, estado: str | None = None):
    if solicitud_id is None:
        raise ValueError("El parámetro 'solicitud_id' es obligatorio.")
    q = Presupuesto.query.filter_by(solicitud_id=solicitud_id)
    if estado:
        q = q.filter_by(estado=estado)
    return q.all()


def aceptar_presupuesto(presupuesto_id: int, solicitud_id: int) -> bool:
    try:
        Presupuesto.query.filter_by(solicitud_id=solicitud_id).update({"estado": "rechazado"})
        presupuesto = Presupuesto.query.filter_by(
            presupuesto_id=presupuesto_id,
            solicitud_id=solicitud_id
        ).first()
        if not presupuesto:
            db.session.rollback()
            return False
        presupuesto.estado = "aceptado"
        db.session.commit()
        return True
    except Exception:
        db.session.rollback()
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

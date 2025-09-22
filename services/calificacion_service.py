from config import db
from models import Calificacion

def obtener_todas():
    return Calificacion.query.all()

def obtener_por_id(id):
    return Calificacion.query.get(id)

def crear(data):
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

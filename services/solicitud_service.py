from config import db
from models import Solicitud

def obtener_todas():
    return Solicitud.query.all()

def obtener_por_id(id):
    return Solicitud.query.get(id)

def crear(data):
    nueva = Solicitud(**data)  # usa **data si las claves coinciden con los nombres de columna
    db.session.add(nueva)
    db.session.commit()
    return nueva

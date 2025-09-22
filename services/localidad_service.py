from config import db
from models import Localidad

def obtener_todas():
    return Localidad.query.all()

def obtener_por_id(id):
    return Localidad.query.get(id)

def crear(data):
    nueva = Localidad(
        nombre=data["nombre"],
        provincia=data["provincia"],
        codigo_postal=data.get("codigo_postal")
    )
    db.session.add(nueva)
    db.session.commit()
    return nueva

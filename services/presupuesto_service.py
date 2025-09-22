from config import db
from models import Presupuesto,Transportista,Usuario

def obtener_todos():
    return Presupuesto.query.all()

def obtener_por_id(id):
    return Presupuesto.query.get(id)

def crear(data):
    # Ajustar los campos según tu modelo Presupuesto
    nuevo = Presupuesto(
        solicitud_id=data["solicitud_id"],
        transportista_id=data["transportista_id"],
        precio_estimado=data["precio_estimado"],
        comentario=data.get("comentario"),
        fecha_creacion=data["fecha_creacion"],
        estado=data.get("estado", "sin transportista")
    )
    db.session.add(nuevo)
    db.session.commit()
    return nuevo


def obtener_por_solicitud(solicitud_id=None, estado=None):
    query = Presupuesto.query
    if solicitud_id is not None:
        query = query.filter_by(solicitud_id=solicitud_id)
    if estado is not None:
        query = query.filter_by(estado=estado)
    return query.all()

def aceptar_presupuesto(presupuesto_id,solicitud_id):
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
    

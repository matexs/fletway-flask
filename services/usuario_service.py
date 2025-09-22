from config import db
from models import Usuario

def obtener_todos():
    return Usuario.query.all()

def obtener_por_id(id):
    return Usuario.query.get(id)

def crear(data):
    # Ajustar los campos según tu modelo Usuario
    nuevo = Usuario(
        nombre=data["nombre"],
        apellido=data.get("apellido"),
        email=data["email"],
        contraseña=data.get("contraseña"),
        telefono=data.get("telefono"),
        fecha_registro=data.get("fecha_registro"),
        fecha_nacimiento=data.get("fecha_nacimiento")
    )
    db.session.add(nuevo)
    db.session.commit()
    return nuevo

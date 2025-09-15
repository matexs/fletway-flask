from models import db, Usuario


# servicios manejan la logica de negocio, validaciones,regla,calculos

def listar_usuarios():
    return Usuario.query.all()

def crear_usuario(nombre, email):
    nuevo = Usuario(nombre=nombre, email=email)
    db.session.add(nuevo)
    db.session.commit()
    return nuevo


def obtener_usuario_por_id(user_id):
    return Usuario.query.get(user_id)

def actualizar_usuario(user_id, nombre=None, email=None):
    usuario = Usuario.query.get(user_id)
    if usuario:
        if nombre:
            usuario.nombre = nombre
        if email:
            usuario.email = email
        db.session.commit()
    return usuario

def eliminar_usuario(user_id):
    usuario = Usuario.query.get(user_id)
    if usuario:
        db.session.delete(usuario)
        db.session.commit()
        return True
    return False
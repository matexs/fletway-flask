"""Servicio para manejar operaciones CRUD de Solicitud."""

from config import db
from models import Solicitud

def obtener_todas():
    """Obtiene todas las solicitudes."""
    return Solicitud.query.all()

def obtener_por_id(id_):
    """Obtiene una solicitud por su ID."""
    return Solicitud.query.get(id_)

def crear(data):
    """Crea una nueva solicitud."""
    nueva = Solicitud(**data)
    db.session.add(nueva)
    db.session.commit()
    return nueva

def obtener_solicitudes_sin_transportista(id_localidad):
    """Obtiene todas las solicitudes que no tienen un transportista asignado y son de una localidad específica."""
    return Solicitud.query.filter(
        (Solicitud.presupuesto_aceptado == None) & 
        (Solicitud.localidad_origen_id == id_localidad)
    ).all()

def actualizar(id_, data):
    """Actualiza una solicitud existente."""
    solicitud = Solicitud.query.get(id_)
    if not solicitud:
        return None  # No se encontró la solicitud

    # Actualiza los campos que vienen en 'data'
    # .get(clave, valor_por_defecto) se usa para no fallar si un dato no viene
    solicitud.cliente_id = data.get("cliente_id", solicitud.cliente_id)
    solicitud.presupuesto_aceptado = data.get("presupuesto_aceptado", solicitud.presupuesto_aceptado)
    solicitud.localidad_origen_id = data.get("localidad_origen_id", solicitud.localidad_origen_id)
    solicitud.direccion_origen = data.get("direccion_origen", solicitud.direccion_origen)
    solicitud.direccion_destino = data.get("direccion_destino", solicitud.direccion_destino)
    solicitud.detalles_carga = data.get("detalles_carga", solicitud.detalles_carga)
    solicitud.estado = data.get("estado", solicitud.estado)
    solicitud.hora_recogida = data.get("hora_recogida", solicitud.hora_recogida)

    db.session.commit()  # Guarda los cambios en la base de datos
    return solicitud

def eliminar(id_):
    """Elimina una solicitud por su ID."""
    solicitud = Solicitud.query.get(id_)
    if not solicitud:
        return False  # No se encontró la solicitud

    db.session.delete(solicitud)
    db.session.commit()
    return True
def actualizar(solicitud_id, data):
    """
    Actualiza una solicitud existente.
    data puede contener cualquier campo a actualizar: foto, estado, etc.
    """
    solicitud = obtener_por_id(solicitud_id)
    if not solicitud:
        return None
    
    # Actualizar solo los campos que vienen en data
    if 'direccion_origen' in data:
        solicitud.direccion_origen = data['direccion_origen']
    if 'direccion_destino' in data:
        solicitud.direccion_destino = data['direccion_destino']
    if 'detalles_carga' in data:
        solicitud.detalles_carga = data['detalles_carga']
    if 'estado' in data:
        solicitud.estado = data['estado']
    if 'hora_recogida' in data:
        solicitud.hora_recogida = data['hora_recogida']
    if 'medidas' in data:
        solicitud.medidas = data['medidas']
    if 'peso' in data:
        solicitud.peso = data['peso']
    if 'localidad_origen_id' in data:
        solicitud.localidad_origen_id = data['localidad_origen_id']
    if 'localidad_destino_id' in data:
        solicitud.localidad_destino_id = data['localidad_destino_id']
    if 'presupuesto_aceptado' in data:
        solicitud.presupuesto_aceptado = data['presupuesto_aceptado']
    
    # IMPORTANTE: Actualizar el campo foto
    if 'foto' in data:
        solicitud.foto = data['foto']
    
    try:
        db.session.commit()
        print(f"✓ Solicitud {solicitud_id} actualizada correctamente en la BD")
        return solicitud
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error actualizando solicitud {solicitud_id}: {str(e)}")
        raise e

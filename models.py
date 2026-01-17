"""Módulo para los modelos. aca se definen las tablas de la base de datos."""

from config import db
from sqlalchemy.sql import func
#tabla intermedia sin modelo propio
transportista_localidad = db.Table('transportista_localidad',
    db.Column('transportista_id', db.Integer, db.ForeignKey('transportista.transportista_id'), primary_key=True),
    db.Column('localidad_id', db.Integer, db.ForeignKey('localidad.localidad_id'), primary_key=True))

#estructura de la base de datos
class Usuario(db.Model):
    __tablename__ = 'usuario'
    usuario_id = db.Column(db.Integer, primary_key=True)
    u_id = db.Column(db.String(36), unique=True, nullable=False)  # ID de autenticación externa
    nombre = db.Column(db.String(80), nullable=False)
    apellido = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    contrasena_hash = db.Column(db.String(200), nullable=False)
    telefono = db.Column(db.String(20), unique=True, nullable=True)
    fecha_registro = db.Column(db.DateTime, nullable=False)
    fecha_nacimiento = db.Column(db.Date, nullable=True)
    def to_dict(self):
        return {"usuario_id": self.usuario_id, "nombre": self.nombre,"apellido":self.apellido,
                 "email": self.email, "telefono": self.telefono,
                 "fecha_registro": self.fecha_registro, "fecha_nacimiento": self.fecha_nacimiento}

class Transportista(db.Model):
    __tablename__ = 'transportista'
    transportista_id = db.Column(db.Integer, primary_key=True)
    descripcion = db.Column(db.String(200), nullable=True)
    tipo_vehiculo = db.Column(db.String(50), nullable=False)
    capacidad_kg = db.Column(db.Integer, nullable=True)
    calificacion_promedio = db.Column(db.Float, nullable=True)
    usuario_id = db.Column(db.Integer,db.ForeignKey('usuario.usuario_id') ,nullable=False)
    patente_vehiculo = db.Column(db.String(20), unique=True, nullable=False)
    modelo_vehiculo = db.Column(db.String(50), nullable=True)

    usuario = db.relationship("Usuario", backref="transportista")
    #many to many
    localidades = db.relationship('Localidad', secondary='transportista_localidad',
                                  back_populates='transportistas')

    def to_dict(self):
        return {"transportista_id": self.transportista_id, "usuario_id": self.usuario_id,
                "descripcion": self.descripcion,"capacidad_kg": self.capacidad_kg,
                "calificacion_promedio": self.calificacion_promedio,"patente_vehiculo": self.patente_vehiculo,
                "modelo_vehiculo": self.modelo_vehiculo,"localidades": [loc.to_dict() for loc in self.localidades]
                ,"usuario": self.usuario.to_dict() if self.usuario else None,"tipo_vehiculo": self.tipo_vehiculo}


from config import db
from sqlalchemy.sql import func

class Solicitud(db.Model):
    __tablename__ = 'solicitud'

    # Campos que SÍ existen en tu Supabase según el schema que compartiste
    solicitud_id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('usuario.usuario_id'), nullable=False)
    presupuesto_aceptado = db.Column(db.Integer, db.ForeignKey('presupuesto.presupuesto_id'), nullable=True)

    localidad_origen_id = db.Column(db.Integer, db.ForeignKey('localidad.localidad_id'), nullable=False)
    localidad_destino_id = db.Column(db.Integer, db.ForeignKey('localidad.localidad_id'), nullable=True)

    direccion_origen = db.Column(db.Text, nullable=False)
    direccion_destino = db.Column(db.Text, nullable=False)
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=func.now())
    detalles_carga = db.Column(db.Text, nullable=False)
    estado = db.Column(db.String(50), nullable=False, default='sin transportista')

    # IMPORTANTE: En Supabase se llama hora_recogida pero es TIMESTAMP WITH TIME ZONE
    hora_recogida = db.Column(db.DateTime(timezone=True), nullable=True)

    # Campos adicionales que SÍ existen en Supabase
    medidas = db.Column(db.Text, nullable=True)
    peso = db.Column(db.Integer, nullable=True)
    foto = db.Column(db.Text, nullable=True)

    borrado_logico = db.Column(db.Boolean, nullable=False, default=False)
    creado_en = db.Column(db.DateTime, nullable=False, default=func.now())
    actualizado_en = db.Column(db.DateTime, nullable=False, default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            "solicitud_id": self.solicitud_id,
            "cliente_id": self.cliente_id,
            "presupuesto_aceptado": self.presupuesto_aceptado,
            "localidad_origen_id": self.localidad_origen_id,
            "localidad_destino_id": self.localidad_destino_id,
            "direccion_origen": self.direccion_origen,
            "direccion_destino": self.direccion_destino,
            "fecha_creacion": self.fecha_creacion.isoformat() if self.fecha_creacion else None,
            "detalles_carga": self.detalles_carga,
            "estado": self.estado,
            "hora_recogida": self.hora_recogida.isoformat() if self.hora_recogida else None,
            "medidas": self.medidas,
            "peso": self.peso,
            "foto": self.foto,
            "borrado_logico": self.borrado_logico,
            "creado_en": self.creado_en.isoformat() if self.creado_en else None,
            "actualizado_en": self.actualizado_en.isoformat() if self.actualizado_en else None
        }
class Presupuesto(db.Model):
    __tablename__ = 'presupuesto'
    presupuesto_id = db.Column(db.Integer, primary_key=True)
    solicitud_id = db.Column(db.Integer, db.ForeignKey('solicitud.solicitud_id'), nullable=False)
    transportista_id = db.Column(db.Integer, db.ForeignKey('transportista.transportista_id'), nullable=False)
    precio_estimado = db.Column(db.Float, nullable=False)
    comentario = db.Column(db.String(200), nullable=True)
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=func.now())
    estado = db.Column(db.String(50), nullable=False, default='sin transportista')

    transportista = db.relationship("Transportista", backref="presupuestos")

    def to_dict(self):
        return {
            "presupuesto_id": self.presupuesto_id,
            "solicitud_id": self.solicitud_id,
            "transportista_id": self.transportista_id,
            "precio_estimado": self.precio_estimado,
            "comentario": self.comentario,
            "fecha_creacion": self.fecha_creacion.isoformat() if self.fecha_creacion else None,
            "estado": self.estado,
            "transportista": self.transportista.to_dict() if self.transportista else None
        }


class Calificacion(db.Model):
    __tablename__ = 'calificacion'
    calificacion_id = db.Column(db.Integer, primary_key=True)
    solicitud_id = db.Column(db.Integer, db.ForeignKey('solicitud.solicitud_id'), nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('usuario.usuario_id'), nullable=False)
    transportista_id = db.Column(db.Integer, db.ForeignKey('transportista.transportista_id'), nullable=False)
    puntuacion = db.Column(db.Integer, nullable=False)
    comentario = db.Column(db.String(200), nullable=True)
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=func.now())

    def to_dict(self):
        return {"calificacion_id": self.calificacion_id, "solicitud_id": self.solicitud_id,
                 "cliente_id": self.cliente_id,   "transportista_id": self.transportista_id,
                 "puntuacion": self.puntuacion, "comentario": self.comentario,
               "fecha_creacion": self.fecha_creacion}

class Localidad(db.Model):
    __tablename__ = 'localidad'
    localidad_id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    provincia = db.Column(db.String(100), nullable=False)
    codigo_postal = db.Column(db.String(20), nullable=True)

    transportistas = db.relationship('Transportista', secondary= 'transportista_localidad',
                                     back_populates='localidades')

    def to_dict(self):
        return {"localidad_id": self.localidad_id, "nombre": self.nombre,
                 "provincia": self.provincia,"codigo_postal": self.codigo_postal}

from flask_sqlalchemy import SQLAlchemy
from config import db


#tabla intermedia sin modelo propio
transportista_localidad = db.Table('transportista_localidad',
    db.Column('transportista_id', db.Integer, db.ForeignKey('transportista.transportista_id'), primary_key=True),
    db.Column('localidad_id', db.Integer, db.ForeignKey('localidad.localidad_id'), primary_key=True))

#estructura de la base de datos
class Usuario(db.Model):
    __tablename__ = 'usuario'
    usuario_id = db.Column(db.Integer, primary_key=True)
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

    #many to many
    localidades = db.relationship('Localidad', secondary='transportista_localidad', 
                                  back_populates='transportistas')

    def to_dict(self):
        return {"fletero_id": self.transportista_id, "usuario_id": self.usuario_id,"descripcion": self.descripcion,
                 "capacidad_kg": self.capacidad_kg, "calificacion_promedio": self.calificacion_promedio,
                "patente_vehiculo": self.patente_vehiculo, "modelo_vehiculo": self.modelo_vehiculo,
                "localidades": [loc.to_dict() for loc in self.localidades]}
    


class Solicitud(db.Model):
    __tablename__ = 'solicitud'
    solicitud_id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('usuario.usuario_id'), nullable=False)
    presupuesto_aceptado = db.Column(db.Integer, db.ForeignKey('presupuesto.presupuesto_id'),nullable=True)
    localidad_origen_id = db.Column(db.Integer, nullable=False)
    direccion_origen = db.Column(db.String(200), nullable=False)
    direccion_destino = db.Column(db.String(200), nullable=False)
    fecha_creacion = db.Column(db.DateTime, nullable=False)
    detalles_carga = db.Column(db.String(200), nullable=False)
    estado = db.Column(db.String(50), nullable=False, default='pendiente')
    hora_recogida = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {"solicitud_id": self.solicitud_id, "cliente_id": self.cliente_id, "presupuesto_aceptado":self.presupuesto_aceptado,
                "localidad_origen_id": self.localidad_origen_id, "direccion_origen": self.direccion_origen,
                "direccion_destino": self.direccion_destino, "fecha_creacion": self.fecha_creacion,
                "detalles_carga": self.detalles_carga, "estado": self.estado, "hora_recogida": self.hora_recogida   }
    
class Presupuesto(db.Model):
    __tablename__ = 'presupuesto'
    presupuesto_id = db.Column(db.Integer, primary_key=True)
    solicitud_id = db.Column(db.Integer, db.ForeignKey('solicitud.solicitud_id'), nullable=False)
    transportista_id = db.Column(db.Integer, db.ForeignKey('transportista.transportista_id'), nullable=False)
    precio_estimado = db.Column(db.Float, nullable=False)
    comentario = db.Column(db.String(200), nullable=True)
    fecha_creacion = db.Column(db.DateTime, nullable=False)
    estado = db.Column(db.String(50), nullable=False, default='sin transportista')

    def to_dict(self):
        return {"presupuesto_id": self.presupuesto_id, "solicitud_id": self.solicitud_id, "transportista_id": self.transportista_id, 
                "precio_estimado": self.precio_estimado,"comentario":self.comentario,"fecha_creacion":self.fecha_creacion,
                "estado": self.estado}
    
class Calificacion(db.Model):
    __tablename__ = 'calificacion'
    calificacion_id = db.Column(db.Integer, primary_key=True)
    solicitud_id = db.Column(db.Integer, db.ForeignKey('solicitud.solicitud_id'), nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('usuario.usuario_id'), nullable=False)
    transportista_id = db.Column(db.Integer, db.ForeignKey('transportista.transportista_id'), nullable=False)
    puntuacion = db.Column(db.Integer, nullable=False)
    comentario = db.Column(db.String(200), nullable=True)
    fecha_creacion = db.Column(db.DateTime, nullable=False)

    def to_dict(self):
        return {"calificacion_id": self.calificacion_id, "solicitud_id": self.solicitud_id, "cliente_id": self.cliente_id, 
                "transporitsta_id": self.transportista_id,"puntuacion": self.puntuacion, "comentario": self.comentario,
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
        return {"localidad_id": self.localidad_id, "nombre": self.nombre, "provincia": self.provincia,"codigo_postal": self.codigo_postal}



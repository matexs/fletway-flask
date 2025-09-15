from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()


#estructura de la base de datos
class Usuario(db.Model):
    __tablename__ = 'usuario'
    usuario_id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), nullable=False)
    apellido = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    contraseña = db.Column(db.String(200), nullable=False)
    telefono = db.Column(db.String(20), unique=True, nullable=True)
    fecha_registro = db.Column(db.DateTime, nullable=False)
    fecha_nacimiento = db.Column(db.Date, nullable=True)
    def to_dict(self):
        return {"usuario_id": self.usuario_id, "nombre": self.nombre, "email": self.email}
    
class Transportista(db.Model):
    __tablename__ = 'transportista'
    transportista_id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.String(80),db.ForeignKey('usuario.usuario_id') ,nullable=False)
    telefono = db.Column(db.String(20), unique=True, nullable=False)
    descripcion = db.Column(db.String(200), nullable=True)
    capacidad_kg = db.Column(db.Integer, nullable=True)
    calificacion_promedio = db.Column(db.Float, nullable=True)
    patente_vehiculo = db.Column(db.String(20), unique=True, nullable=False)
    modelo_vehiculo = db.Column(db.String(50), nullable=True)

    #many to many
    localidades = db.relationship('Localidad', secondary='transportista_localidad', 
                                  backpopulates='transportistas')

    def to_dict(self):
        return {"fletero_id": self.fletero_id, "nombre": self.nombre, "telefono": self.telefono}
    


class Solicitud(db.Model):
    __tablename__ = 'solicitud'
    solicitud_id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('usuario.usuario_id'), nullable=False)
    presupuesto_aceptado = db.Column(db.Integer, db.ForeignKey('presupuesto.presupuesto_id'),nullable=True)
    local_origen_id = db.Column(db.Integer, nullable=False)
    direccion_origen = db.Column(db.String(200), nullable=False)
    direccion_destino = db.Column(db.String(200), nullable=False)
    fecha_creacion = db.Column(db.DateTime, nullable=False)
    detalles_carga = db.Column(db.String(200), nullable=False)
    estado = db.Column(db.String(50), nullable=False, default='pendiente')
    hora_recogida = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {"solicitud_id": self.solicitud_id, "usuario_id": self.usuario_id, "descripcion": self.descripcion, "estado": self.estado}
    
class Presupuesto(db.Model):
    __tablename__ = 'presupuesto'
    presupuesto_id = db.Column(db.Integer, primary_key=True)
    solicitud_id = db.Column(db.Integer, db.ForeignKey('solicitud.solicitud_id'), nullable=False)
    transportista_id = db.Column(db.Integer, db.ForeignKey('transportista.fletero_id'), nullable=False)
    precio_estimado = db.Column(db.Float, nullable=False)
    comentario = db.Column(db.String(200), nullable=True)
    fecha_creacion = db.Column(db.DateTime, nullable=False)
    estado = db.Column(db.String(50), nullable=False, default='sin transportista')

    def to_dict(self):
        return {"presupuesto_id": self.presupuesto_id, "solicitud_id": self.solicitud_id, "transportista_id": self.transportista_id, "monto": self.monto, "estado": self.estado}
    
class Calificacion(db.Model):
    __tablename__ = 'calificacion'
    calificacion_id = db.Column(db.Integer, primary_key=True)
    solicitud_id = db.Column(db.Integer, db.ForeignKey('solicitud.solicitud_id'), nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('usuario.usuario_id'), nullable=False)
    transportista_id = db.Column(db.Integer, db.ForeignKey('transportista.fletero_id'), nullable=False)
    puntuacion = db.Column(db.Integer, nullable=False)
    comentario = db.Column(db.String(200), nullable=True)
    fecha_creacion = db.Column(db.DateTime, nullable=False)

    def to_dict(self):
        return {"calificacion_id": self.calificacion_id, "solicitud_id": self.solicitud_id, "usuario_id": self.usuario_id, "puntaje": self.puntaje, "comentario": self.comentario}
    
class Localidad(db.Model):
    __tablename__ = 'localidad'
    localidad_id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    provincia = db.Column(db.String(100), nullable=False)
    codigo_postal = db.Column(db.String(20), nullable=True)

    transportistas = db.relationship('Transportista', secondary='transportista_localidad', 
                                     backpopulates='localidades')

    def to_dict(self):
        return {"localidad_id": self.localidad_id, "nombre": self.nombre, "provincia": self.provincia}

#tabla intermedia sin modelo propio
transportista_localidad = db.Table('transportista_localidad',
    db.Column('transportista_id', db.Integer, db.ForeignKey('transportista_id'), primary_key=True),
    db.Column('localidad_id', db.Integer, db.ForeignKey('localidad_id'), primary_key=True))

"""
Lógica de negocio para solicitudes
"""
import os
import uuid
from config import db
from models import Solicitud, Usuario
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

ESTADOS_VALIDOS = {
    "sin transportista",
    "pendiente",
    "en viaje",
    "completado",
}


class SolicitudService:

    # =====================
    # HELPERS
    # =====================

    def _usuario_por_uid(self, uid: str) -> Usuario | None:
        return Usuario.query.filter_by(u_id=uid).first()

    def _allowed_file(self, filename: str) -> bool:
        return (
            "." in filename
            and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
        )

    # =====================
    # CONSULTAS
    # =====================

    def obtener_todas(self, estado: str | None = None):
        query = Solicitud.query
        if estado:
            query = query.filter_by(estado=estado)
        return query.all()

    def obtener_por_uid(self, uid: str):
        usuario = self._usuario_por_uid(uid)
        if not usuario:
            return []
        return Solicitud.query.filter_by(
            cliente_id=usuario.usuario_id
        ).all()

    def obtener_por_id(self, solicitud_id: int, uid: str):
        usuario = self._usuario_por_uid(uid)
        if not usuario:
            return None

        return Solicitud.query.filter_by(
            solicitud_id=solicitud_id,
            cliente_id=usuario.usuario_id
        ).first()

    # =====================
    # CREAR / ACTUALIZAR
    # =====================

    def crear(self, data: dict, uid: str) -> Solicitud:
        usuario = self._usuario_por_uid(uid)
        if not usuario:
            raise ValueError("Usuario no encontrado")

        solicitud = Solicitud(
            cliente_id=usuario.usuario_id,
            direccion_origen=data["direccion_origen"],
            direccion_destino=data["direccion_destino"],
            localidad_origen_id=data["localidad_origen_id"],
            localidad_destino_id=data["localidad_destino_id"],
            detalles_carga=data.get("detalles_carga"),
            medidas=data.get("medidas"),
            peso=data.get("peso"),
            estado="sin transportista",
            hora_recogida=data.get("hora_recogida"),
        )

        db.session.add(solicitud)
        db.session.commit()
        return solicitud

    def actualizar(self, solicitud_id: int, data: dict, uid: str):
        solicitud = self.obtener_por_id(solicitud_id, uid)
        if not solicitud:
            return None

        CAMPOS_EDITABLES = {
            "direccion_origen",
            "direccion_destino",
            "detalles_carga",
            "medidas",
            "peso",
            "hora_recogida",
            "localidad_origen_id",
            "localidad_destino_id",
            "presupuesto_aceptado",
        }

        # 🔥 Si se pide eliminar la foto desde Angular
        if "foto" in data and data["foto"] is None and solicitud.foto:
            path = os.path.join(UPLOAD_FOLDER, solicitud.foto)
            if os.path.exists(path):
                os.remove(path)
            solicitud.foto = None

        # actualizar campos permitidos
        for campo in CAMPOS_EDITABLES:
            if campo in data:
                setattr(solicitud, campo, data[campo])

        db.session.commit()
        return solicitud

    def eliminar(self, solicitud_id: int, uid: str) -> bool:
        solicitud = self.obtener_por_id(solicitud_id, uid)
        if not solicitud:
            return False

        # eliminar foto asociada si existe
        if solicitud.foto:
            path = os.path.join(UPLOAD_FOLDER, solicitud.foto)
            if os.path.exists(path):
                os.remove(path)

        db.session.delete(solicitud)
        db.session.commit()
        return True

    # =====================
    # ESTADO
    # =====================

    def cambiar_estado(self, solicitud_id: int, estado: str, uid: str):
        if estado not in ESTADOS_VALIDOS:
            raise ValueError("Estado inválido")

        solicitud = self.obtener_por_id(solicitud_id, uid)
        if not solicitud:
            return None

        solicitud.estado = estado
        db.session.commit()
        return solicitud

    # =====================
    # FOTO
    # =====================

    def guardar_foto(
        self,
        solicitud_id: int,
        archivo,
        filename: str,
        uid: str
    ):
        solicitud = self.obtener_por_id(solicitud_id, uid)
        if not solicitud:
            return None

        if not self._allowed_file(filename):
            raise ValueError("Tipo de archivo no permitido")

        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        # borrar foto previa si existe
        if solicitud.foto:
            old_path = os.path.join(UPLOAD_FOLDER, solicitud.foto)
            if os.path.exists(old_path):
                os.remove(old_path)

        ext = filename.rsplit(".", 1)[1].lower()
        nombre = f"solicitud_{solicitud_id}_{uuid.uuid4().hex}.{ext}"
        path = os.path.join(UPLOAD_FOLDER, secure_filename(nombre))

        archivo.save(path)

        solicitud.foto = nombre
        db.session.commit()
        return solicitud

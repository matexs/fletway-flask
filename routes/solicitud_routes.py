"""Rutas para los endpoints de las solicitudes."""
from flask import Blueprint, jsonify, request, send_from_directory, current_app
from services import solicitud_service
from werkzeug.utils import secure_filename
import os
import uuid

solicitud_bp = Blueprint("solicitud_bp", __name__)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    """Verifica si la extensión del archivo es permitida."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# === ENDPOINTS CRUD ===

@solicitud_bp.route("/solicitudes", methods=["GET"])
def obtener_solicitudes():
    """Obtiene todas las solicitudes."""
    solicitudes = solicitud_service.obtener_todas()
    return jsonify([s.to_dict() for s in solicitudes])

@solicitud_bp.route("/solicitudes/<int:id_>", methods=["GET"])
def obtener_solicitud(id_):
    """Obtiene una solicitud por su ID."""
    solicitud = solicitud_service.obtener_por_id(id_)
    if not solicitud:
        return jsonify({"error": "Solicitud no encontrada"}), 404
    return jsonify(solicitud.to_dict())

@solicitud_bp.route("/solicitudes", methods=["POST"])
def crear_solicitud():
    """Crea una nueva solicitud."""
    data = request.get_json()
    try:
        nueva_solicitud = solicitud_service.crear(data)
        return jsonify(nueva_solicitud.to_dict()), 201
    except KeyError as e:
        return jsonify({"error": f"Falta el campo {str(e)}"}), 400
    except Exception as e:
        print(f"Error creando solicitud: {str(e)}")
        return jsonify({"error": str(e)}), 500

@solicitud_bp.route("/solicitudes/<int:id_>", methods=["PUT"])
def actualizar_solicitud(id_):
    """Actualiza una solicitud existente."""
    data = request.get_json()
    try:
        solicitud_actualizada = solicitud_service.actualizar(id_, data)
        if not solicitud_actualizada:
            return jsonify({"error": "Solicitud no encontrada"}), 404
        return jsonify(solicitud_actualizada.to_dict()), 200
    except Exception as e:
        print(f"Error actualizando solicitud: {str(e)}")
        return jsonify({"error": str(e)}), 500

@solicitud_bp.route("/solicitudes/<int:id_>", methods=["DELETE"])
def eliminar_solicitud(id_):
    """Elimina una solicitud."""
    try:
        exito = solicitud_service.eliminar(id_)
        if not exito:
            return jsonify({"error": "Solicitud no encontrada"}), 404
        return jsonify({"mensaje": "Solicitud eliminada correctamente"}), 200
    except Exception as e:
        return jsonify({"error": f"Error al eliminar la solicitud: {str(e)}"}), 500

# === ENDPOINTS DE FOTOS ===

@solicitud_bp.route("/solicitudes/<int:id_>/foto", methods=["POST"])
def subir_foto_solicitud(id_):
    """Sube una foto para una solicitud específica."""
    try:
        # 1. Verificar que la solicitud existe
        solicitud = solicitud_service.obtener_por_id(id_)
        if not solicitud:
            return jsonify({"error": "Solicitud no encontrada"}), 404
        
        # 2. Verificar que se envió un archivo
        if 'foto' not in request.files:
            return jsonify({"error": "No se envió ningún archivo"}), 400
        
        file = request.files['foto']
        
        # 3. Validar nombre de archivo
        if file.filename == '':
            return jsonify({"error": "Nombre de archivo vacío"}), 400
        
        # 4. Validar extensión
        if not allowed_file(file.filename):
            return jsonify({
                "error": f"Tipo de archivo no permitido. Use: {', '.join(ALLOWED_EXTENSIONS)}"
            }), 400
        
        # 5. Verificar que la carpeta uploads existe
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)
            print(f"⚠️  Carpeta '{UPLOAD_FOLDER}' creada durante la subida")
        
        # 6. Generar nombre único y seguro
        extension = file.filename.rsplit('.', 1)[1].lower()
        nombre_unico = f"solicitud_{id_}_{uuid.uuid4().hex[:8]}.{extension}"
        
        # 7. Crear ruta completa del archivo
        filepath = os.path.join(UPLOAD_FOLDER, nombre_unico)
        
        # 8. Guardar archivo
        file.save(filepath)
        print(f"✓ Foto guardada: {filepath}")
        print(f"✓ Nombre de archivo: {nombre_unico}")
        
        # 9. Actualizar la solicitud en la base de datos con el nombre de la foto
        try:
            solicitud_actualizada = solicitud_service.actualizar(id_, {"foto": nombre_unico})
            
            if not solicitud_actualizada:
                # Si falla la actualización, eliminar la foto guardada
                if os.path.exists(filepath):
                    os.remove(filepath)
                    print(f"⚠️  Foto eliminada debido a error en actualización")
                return jsonify({"error": "Error actualizando la solicitud con el nombre de la foto"}), 500
            
            print(f"✓ Solicitud {id_} actualizada con foto: {nombre_unico}")
            
            return jsonify({
                "mensaje": "Foto subida correctamente",
                "foto": nombre_unico,
                "solicitud_id": id_,
                "url": f"/uploads/{nombre_unico}",
                "solicitud": solicitud_actualizada.to_dict()
            }), 200
            
        except Exception as update_error:
            # Si falla la actualización, eliminar la foto
            if os.path.exists(filepath):
                os.remove(filepath)
                print(f"⚠️  Foto eliminada debido a error: {str(update_error)}")
            raise update_error
        
    except Exception as e:
        print(f"❌ Error subiendo foto: {str(e)}")
        return jsonify({"error": f"Error al subir la foto: {str(e)}"}), 500

@solicitud_bp.route("/uploads/<filename>", methods=["GET"])
def obtener_foto(filename):
    """Sirve una foto desde la carpeta uploads."""
    try:
        # Verificar que el archivo existe
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if not os.path.exists(filepath):
            return jsonify({"error": "Foto no encontrada"}), 404
        
        return send_from_directory(UPLOAD_FOLDER, filename)
    except Exception as e:
        print(f"Error obteniendo foto: {str(e)}")
        return jsonify({"error": "Error al obtener la foto"}), 500

@solicitud_bp.route("/solicitudes/<int:id_>/foto", methods=["DELETE"])
def eliminar_foto_solicitud(id_):
    """Elimina la foto de una solicitud."""
    try:
        solicitud = solicitud_service.obtener_por_id(id_)
        if not solicitud:
            return jsonify({"error": "Solicitud no encontrada"}), 404
        
        if not solicitud.foto:
            return jsonify({"error": "La solicitud no tiene foto"}), 400
        
        # Eliminar archivo físico
        filepath = os.path.join(UPLOAD_FOLDER, solicitud.foto)
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"✓ Foto eliminada: {filepath}")
        
        # Actualizar solicitud
        solicitud_actualizada = solicitud_service.actualizar(id_, {"foto": None})
        
        return jsonify({
            "mensaje": "Foto eliminada correctamente",
            "solicitud": solicitud_actualizada.to_dict()
        }), 200
        
    except Exception as e:
        print(f"Error eliminando foto: {str(e)}")
        return jsonify({"error": f"Error al eliminar la foto: {str(e)}"}), 500
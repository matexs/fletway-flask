import os
from werkzeug.utils import secure_filename
from flask import Blueprint, jsonify, request, send_from_directory, current_app
from models import db, Foto, Solicitud # Asumo que tienes un modelo Foto
from services.auth import require_auth

fotos_bp = Blueprint('fotos', __name__)
# Configuración de extensiones permitidas
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@fotos_bp.route('/api/solicitudes/<int:id>/foto', methods=['POST'])
@require_auth
def subir_foto(id):
    # 1. Verificar si la solicitud existe
    solicitud = Solicitud.query.get(id)
    if not solicitud:
        return jsonify({"error": "Solicitud no encontrada"}), 404

    # 2. Verificar si viene el archivo en la petición
    if 'foto' not in request.files:
        return jsonify({"error": "No se encontró el archivo 'foto'"}), 400

    file = request.files['foto']

    if file.filename == '':
        return jsonify({"error": "No se seleccionó ningún archivo"}), 400

    if file and allowed_file(file.filename):
        try:
            # 3. Sanitizar nombre y guardar archivo físico
            filename = secure_filename(file.filename)
            # Para evitar duplicados, podrias agregar el ID o timestamp al nombre
            # ej: filename = f"{id}_{int(time.time())}_{filename}"

            save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

            file.save(save_path)

            file.seek(0, os.SEEK_END)
            file_size = file.tell()

            # 4. Calcular el "orden" (para que salga al final de la lista)
            # Buscamos cuántas fotos tiene ya esta solicitud
            count = Foto.query.filter_by(solc_id=id).count()
            nuevo_orden = count + 1

            # 5. Guardar registro en Base de Datos
            nueva_foto = Foto(
                solc_id=id,
                url=filename,               # O la URL completa si usas S3/Cloud
                archivo_nombre=filename,    # Nombre original
                archivo_tamano=file_size,   # Tamaño en bytes
                mime_type=file.mimetype,    # ej: image/png
                orden=nuevo_orden,
                descripcion=""              # Opcional
            )

            db.session.add(nueva_foto)
            db.session.commit()

            return jsonify({
                "message": "Foto subida exitosamente",
                "foto": nueva_foto.to_dict() # Asegúrate que tu modelo Foto tenga to_dict
            }), 201

        except Exception as e:
            db.session.rollback()
            print(f"Error subiendo foto: {e}")
            return jsonify({"error": "Error interno al guardar la imagen"}), 500

    return jsonify({"error": "Tipo de archivo no permitido"}), 400


# ---------------------------------------------------------
# ENDPOINT 2: SERVIR FOTO (Para poder verla)
# ---------------------------------------------------------
# Esto reemplaza a Supabase Storage para visualizar
@fotos_bp.route('/uploads/<path:filename>', methods=['GET'])
@require_auth
def get_uploaded_file(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)


@fotos_bp.route('/api/solicitudes/<int:id>/fotos', methods=['GET'])
@require_auth
def get_fotos_solicitud(id):
    try:
        # 1. Consultar fotos filtrando por la solicitud y ordenando
        fotos = Foto.query.filter_by(solc_id=id).order_by(Foto.orden.asc()).all()

        # 2. Serializar la lista
        response_data = [f.to_dict() for f in fotos]

        return jsonify(response_data), 200

    except Exception as e:
        print(f"Error obteniendo fotos: {e}")
        return jsonify([]), 500 # En caso de error, devolvemos lista vacía para no romper la UI
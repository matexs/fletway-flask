"""Rutas para los endpoints de las localidades."""

from flask import Blueprint, jsonify, request
from services import localidad_service
from models import Localidad
from services.auth import require_auth

localidad_bp = Blueprint("localidad_bp", __name__)

@localidad_bp.route('/api/localidades', methods=['GET'])
@require_auth
def get_all_localidades():
    # 1. Consultar todas las localidades
    # Si son muchísimas (ej: +5000), considera usar paginación en el futuro.
    localidades = Localidad.query.order_by(Localidad.nombre.asc()).all()

    # 2. Serialización
    response_data = []
    for loc in localidades:
        # Usamos to_dict() si lo tienes definido en el modelo,
        # o lo construimos manualmente si quieres ser explícito.
        response_data.append({
            "localidad_id": loc.localidad_id,
            "nombre": loc.nombre,
            "provincia": loc.provincia,
            "codigo_postal": loc.codigo_postal
        })

    return jsonify(response_data), 200


@localidad_bp.route('/api/localidades/buscar', methods=['GET'])
@require_auth
def search_localidades():
    # 1. Obtener el parámetro de búsqueda 'q' de la URL
    # Ejemplo: /api/localidades/buscar?q=Cordoba
    query = request.args.get('q', '').strip()

    # Si la búsqueda está vacía, devolvemos array vacío para no sobrecargar la DB
    if not query:
        return jsonify([]), 200

    try:
        # 2. Consulta con filtro ILIKE (Case insensitive)
        # Busca coincidencias en el nombre que contengan el texto (wildcards %)
        resultados = Localidad.query.filter(
            Localidad.nombre.ilike(f'%{query}%')
        ).limit(10).all() # Limitamos a 10 para autocompletado rápido

        # 3. Serialización
        response_data = []
        for loc in resultados:
            response_data.append({
                "localidad_id": loc.localidad_id,
                "nombre": loc.nombre,
                "provincia": loc.provincia,
                "codigo_postal": loc.codigo_postal
            })

        return jsonify(response_data), 200

    except Exception as e:
        print(f"Error en búsqueda de localidades: {e}")
        return jsonify([]), 200 # En búsqueda, mejor devolver vacío que error 500
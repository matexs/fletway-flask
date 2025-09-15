from flask import Blueprint, jsonify, request
from models import db, Calificacion


calificacion_bp = Blueprint('calificacion_bp', __name__)

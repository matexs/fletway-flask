from flask import Blueprint, jsonify, request
from models import db, Localidad

localidad_bp = Blueprint('localidad_bp', __name__)

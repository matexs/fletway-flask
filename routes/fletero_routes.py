from flask import Blueprint, jsonify, request
from models import db, Transportista
from services import fletero_service

transportista_bp = Blueprint('transportista_bp', __name__)

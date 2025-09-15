from flask import Blueprint, jsonify, request
from models import db, Presupuesto
from services import presupuesto_service

presupuesto_bp = Blueprint('presupuesto_bp', __name__)

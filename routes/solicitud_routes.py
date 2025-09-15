from flask import Blueprint, jsonify, request
from models import db, Solicitud
from services import solicitud_service

solicitud_bp = Blueprint('solicitud_bp', __name__)

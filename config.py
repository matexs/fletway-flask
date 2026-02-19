"""Módulo configuracion.Aca se configuran los parametros para acceder a la base de datos."""

import os
from flask_sqlalchemy import SQLAlchemy

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # [DEBUG] Verificar configuración de base de datos
    if not SQLALCHEMY_DATABASE_URI:
        print("[CONFIG] ⚠️ ADVERTENCIA: DATABASE_URI no está configurado en .env")
        print("[CONFIG] Asegúrate de tener DATABASE_URI en tu archivo .env")
    else:
        print(f"[CONFIG] ✅ DATABASE_URI configurado correctamente")

db = SQLAlchemy()

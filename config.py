"""Módulo configuracion.Aca se configuran los parametros para acceder a la base de datos."""

import os
from flask_sqlalchemy import SQLAlchemy

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI")

    SQLALCHEMY_TRACK_MODIFICATIONS = False

db = SQLAlchemy()

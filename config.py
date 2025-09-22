import os

from flask_sqlalchemy import SQLAlchemy

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URI', 
        'postgresql://postgres.cscsodzphvosifgduqtc:9sT5AL2J7NvTEp53@aws-0-us-east-2.pooler.supabase.com:5432/postgres'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

db = SQLAlchemy()

"""
Servicio de autenticación.
Valida JWT emitidos por Supabase Auth.
"""

import os
import jwt
from functools import wraps
from flask import request, jsonify
from jwt import PyJWTError


def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Missing Bearer token"}), 401

        token = auth.split(" ", 1)[1].strip()

        secret = os.getenv("SUPABASE_JWT_SECRET")
        if not secret:
            return jsonify({"error": "Missing SUPABASE_JWT_SECRET env var"}), 500

        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"],
                audience=os.getenv("JWT_AUD", "authenticated"),
                options={"require": ["exp", "sub"]},
            )
        except PyJWTError as e:
            return jsonify({"error": "Invalid token", "detail": str(e)}), 401

        # UID del usuario Supabase
        request.uid = payload["sub"]

        return f(*args, **kwargs)

    return wrapper

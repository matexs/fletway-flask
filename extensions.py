from flask_socketio import SocketIO
from flask_socketio import join_room

# [SOCKETIO] Configuración de SocketIO con CORS habilitado para desarrollo
socketio = SocketIO(
    cors_allowed_origins=[
        "http://localhost:4200",
        "http://127.0.0.1:4200",
        "https://fletway-api-533654897399.us-central1.run.app",
        "https://fletway.netlify.app"
    ],
    async_mode="eventlet",
    ping_timeout=60,
    ping_interval=25
)


"""
@socketio.on('connect')
def handle_connect():

    # Aquí deberías validar quién es el usuario (usando el token, por ejemplo)
    # Supongamos que verificaste que el usuario es un 'transportista'
    es_transportista = True # Lógica tuya de validación

    if es_transportista:
        join_room('transportistas')
        print("🚚 Transportista unido a la sala de notificaciones")
"""
from flask_socketio import SocketIO
from flask_socketio import join_room

#socketio = SocketIO(cors_allowed_origins="*")
socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode="eventlet"
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
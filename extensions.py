from flask_socketio import SocketIO
from flask_socketio import join_room

# [SOCKETIO] Configuración de SocketIO con CORS habilitado para desarrollo
socketio = SocketIO(
    cors_allowed_origins=[
        "http://localhost:4200",
        "http://127.0.0.1:4200",
        "https://fletway-api-568207456643.us-central1.run.app",
        "https://fletway.netlify.app"
    ],
    async_mode="eventlet",
    ping_timeout=60,
    ping_interval=25
)


@socketio.on('join_room')
def on_join_room(data):
    room = data.get('room')
    # Acepta: 'fleteros', 'clientes', 'cliente_123', 'fletero_45'
    if room and (room in ['fleteros', 'clientes'] or
                 room.startswith('cliente_') or
                 room.startswith('fletero_')):
        join_room(room)
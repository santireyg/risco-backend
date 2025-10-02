# path: app/api/endpoints/websocket.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, status
import jwt
from jwt import ExpiredSignatureError, PyJWTError
from app.core.config import SECRET_KEY_AUTH, ALGORITHM
from app.core.database import users_collection
from app.models.users import User
from app.websockets.manager import manager
import time

# Diccionario simple en memoria para rate limiting de handshakes por IP
WS_RATE_LIMIT = 10  # conexiones por 60 segundos
WS_RATE_WINDOW = 60  # segundos
ws_conn_attempts = {}  # {ip: [timestamps]}

MAX_WS_MESSAGES = 1000  # máximo de mensajes por conexión
MESSAGE_WINDOW_SECONDS = 3600  # ventana de 1 hora

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Endpoint de WebSocket centralizado para notificaciones.
    El token se extrae de la cookie 'token' en el handshake.
    Aplica rate limiting por IP para el handshake.
    """
    # Rate limiting handshake por IP
    client_ip = websocket.client.host
    now = time.time()
    attempts = ws_conn_attempts.get(client_ip, [])
    # Filtra intentos fuera de la ventana
    attempts = [t for t in attempts if now - t < WS_RATE_WINDOW]
    if len(attempts) >= WS_RATE_LIMIT:
        await websocket.close(code=1013)  # Try again later
        return
    attempts.append(now)
    ws_conn_attempts[client_ip] = attempts

    # Extraemos la cookie antes de aceptar la conexión
    token = websocket.cookies.get("token")
    if not token:
        # No hay token: rechazamos la conexión
        await websocket.close(code=1008)
        return

    # Validamos y decodificamos el JWT
    try:
        payload = jwt.decode(token, SECRET_KEY_AUTH, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    except ExpiredSignatureError:
        # Token expirado
        await websocket.close(code=1008)
        return
    except (PyJWTError, HTTPException):
        # Token inválido
        await websocket.close(code=1008)
        return

    # Buscamos al usuario en la base de datos
    user_data = await users_collection.find_one({"username": username})
    if not user_data:
        await websocket.close(code=1008)
        return

    user = User(**user_data)
    user_id = str(user.id)  # Convertir ObjectId a string para usar como key

    # Aceptamos la conexión y registramos al usuario
    await websocket.accept()
    await manager.connect(websocket, user_id)

    # --- Límite de mensajes por conexión ---
    msg_timestamps = []
    try:
        # Mantenemos vivo el WebSocket
        while True:
            # Limita la cantidad de mensajes por ventana de tiempo
            now = time.time()
            msg_timestamps = [t for t in msg_timestamps if now - t < MESSAGE_WINDOW_SECONDS]
            if len(msg_timestamps) >= MAX_WS_MESSAGES:
                await websocket.close(code=1013)  # Try again later
                break
            await websocket.receive_text()
            msg_timestamps.append(now)
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
    except Exception:
        manager.disconnect(websocket, user_id)

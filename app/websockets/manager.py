# app/websockets/manager.py

import json
from fastapi import WebSocket
from typing import Dict, List

class ConnectionManager:
    def __init__(self):
        # Usamos un diccionario para mapear el identificador del usuario (puede ser su username o id)
        # a una lista de conexiones WebSocket.
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        """Registra la conexión del usuario (debe estar ya aceptada)."""
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)


    def disconnect(self, websocket: WebSocket, user_id: str):
        """Elimina una conexión al detectar su cierre."""
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Envía un mensaje a una conexión individual."""
        await websocket.send_text(message)

    async def broadcast(self, user_id: str, message: str):
        """Envía un mensaje a todas las conexiones abiertas de un usuario."""
        if user_id in self.active_connections:
            # Usamos una lista de conexiones para realizar el envío.  
            # Si alguna falla, se elimina del listado.
            for connection in self.active_connections[user_id].copy():
                try:
                    await connection.send_text(message)
                except Exception:
                    self.disconnect(connection, user_id)

# Instancia única para toda la aplicación.
manager = ConnectionManager()

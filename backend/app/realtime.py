from collections import defaultdict
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.connections: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, user_id: int, socket: WebSocket):
        await socket.accept()
        self.connections[user_id].add(socket)

    def disconnect(self, user_id: int, socket: WebSocket):
        self.connections[user_id].discard(socket)
        if not self.connections[user_id]:
            self.connections.pop(user_id, None)

    async def send(self, user_id: int, payload: dict):
        dead = []
        for socket in list(self.connections.get(user_id, ())):
            try:
                await socket.send_json(payload)
            except Exception:
                dead.append(socket)
        for socket in dead:
            self.disconnect(user_id, socket)

    async def broadcast(self, payload: dict, exclude: int | None = None):
        for user_id in list(self.connections):
            if user_id != exclude:
                await self.send(user_id, payload)


manager = ConnectionManager()


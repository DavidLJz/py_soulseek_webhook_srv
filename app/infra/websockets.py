from typing import Callable
from asyncio import iscoroutinefunction
from starlette.websockets import WebSocket

# https://fastapi.tiangolo.com/advanced/websockets/#handling-disconnections-and-multiple-clients

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        
        self._event_handlers : dict[str, list[Callable]] = {
            'connection': []
        }

    async def _emit_events(self, event:str, *args, **kwargs):
        listeners = self._event_handlers.get(event, None)

        for listener in listeners:
            try:
                if iscoroutinefunction(listener):
                    await listener(*args, **kwargs)
                else:
                    listener(*args, **kwargs)

            except Exception:
                print(
                    "exception notifying listener %r of event %r" % listener, event
                )

    async def register_connection_event_listener(self, listener: Callable[ [str, WebSocket], None ]):
        self._event_handlers.setdefault('connection', [])

        self._event_handlers['connection'].append(listener)

    async def connect(self, client_id:str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket

        self._emit_events('connection', client_id, websocket)

    async def disconnect(self, client_id:str, websocket: WebSocket):
        self.active_connections.pop(client_id)
        await websocket.close()

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

    async def disconnect_all(self):
        for connection in self.active_connections.values():
            await connection.close()

        self.active_connections.clear()
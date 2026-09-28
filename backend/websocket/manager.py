"""Concurrency-safe WebSocket connection management."""

import asyncio

from fastapi import WebSocket, WebSocketDisconnect


class ConnectionManager:
    """Track clients and serialize writes per WebSocket connection."""

    def __init__(self) -> None:
        self._connections: dict[WebSocket, asyncio.Lock] = {}
        self._manager_lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new client."""
        await websocket.accept()
        async with self._manager_lock:
            self._connections[websocket] = asyncio.Lock()

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a client if it is still registered."""
        async with self._manager_lock:
            self._connections.pop(websocket, None)

    async def send(self, websocket: WebSocket, message: dict[str, object]) -> None:
        """Send one message to a connected client."""
        async with self._manager_lock:
            lock = self._connections.get(websocket)
        if lock is None:
            raise WebSocketDisconnect()
        async with lock:
            await websocket.send_json(message)

    async def broadcast(self, message: dict[str, object]) -> None:
        """Broadcast concurrently and evict connections that fail."""
        async with self._manager_lock:
            connections = list(self._connections.items())
        results = await asyncio.gather(
            *(self._send_locked(websocket, lock, message) for websocket, lock in connections),
            return_exceptions=True,
        )
        for (websocket, _), result in zip(connections, results):
            if isinstance(result, Exception):
                await self.disconnect(websocket)

    @staticmethod
    async def _send_locked(
        websocket: WebSocket,
        lock: asyncio.Lock,
        message: dict[str, object],
    ) -> None:
        async with lock:
            await websocket.send_json(message)


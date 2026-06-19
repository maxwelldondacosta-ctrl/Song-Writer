from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._conns: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, slug: str, ws: WebSocket) -> None:
        await ws.accept()
        self._conns[slug].add(ws)

    def disconnect(self, slug: str, ws: WebSocket) -> None:
        self._conns[slug].discard(ws)

    async def broadcast(self, slug: str, payload: Any) -> None:
        dead = []
        for ws in list(self._conns.get(slug, ())):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._conns[slug].discard(ws)


manager = ConnectionManager()

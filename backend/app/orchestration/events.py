"""Async SSE event bus broadcasting live stage & advisor progress to connected clients."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


class ProgressBroker:
    """In-memory pub/sub supporting multiple concurrent SSE subscribers per investigation."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)

    def subscribe(self, investigation_id: str) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        self._subscribers[investigation_id].add(q)
        return q

    def unsubscribe(self, investigation_id: str, q: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers[investigation_id].discard(q)

    def publish(
        self,
        investigation_id: str,
        *,
        status: str,
        stage: str,
        progress_percent: int,
        message: str,
        advisor_statuses: dict[str, str] | None = None,
    ) -> None:
        payload = {
            "investigation_id": investigation_id,
            "status": status,
            "stage": stage,
            "progress_percent": progress_percent,
            "message": message,
            "advisor_statuses": advisor_statuses or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for q in list(self._subscribers.get(investigation_id, ())):
            if q.full():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                pass


progress_broker = ProgressBroker()

from __future__ import annotations

import asyncio
from typing import Callable

from loguru import logger
from pydantic import BaseModel, Field

from .models import utc_now_iso_z


class MemoryEvent(BaseModel):
    event_type: str
    source_agent_id: str
    data: dict
    timestamp: str = Field(default_factory=utc_now_iso_z)


class MemoryEventBus:

    def __init__(self):
        self._subscribers: dict[str, set[str]] = {}
        self._queue: asyncio.Queue[MemoryEvent] = asyncio.Queue()
        self._pending: dict[str, list[MemoryEvent]] = {}
        self._running: bool = False
        self._callbacks: dict[str, list[Callable]] = {}
        self._consume_task: asyncio.Task | None = None

    async def start(self):
        if self._running:
            return
        self._running = True
        self._consume_task = asyncio.create_task(self._consume_loop())
        logger.info("[MemoryEventBus] Started")

    async def stop(self):
        self._running = False
        if self._consume_task:
            self._consume_task.cancel()
            try:
                await self._consume_task
            except asyncio.CancelledError:
                pass
            self._consume_task = None
        logger.info("[MemoryEventBus] Stopped")

    def subscribe(self, subscriber_agent_id: str, source_agent_id: str):
        if subscriber_agent_id not in self._subscribers:
            self._subscribers[subscriber_agent_id] = set()
        self._subscribers[subscriber_agent_id].add(source_agent_id)

    def unsubscribe(self, subscriber_agent_id: str, source_agent_id: str):
        if subscriber_agent_id in self._subscribers:
            self._subscribers[subscriber_agent_id].discard(source_agent_id)
            if not self._subscribers[subscriber_agent_id]:
                del self._subscribers[subscriber_agent_id]

    async def publish(self, event_type: str, agent_id: str, data: dict):
        event = MemoryEvent(
            event_type=event_type,
            source_agent_id=agent_id,
            data=data,
        )
        for subscriber_id, sources in self._subscribers.items():
            if agent_id in sources:
                if subscriber_id not in self._pending:
                    self._pending[subscriber_id] = []
                self._pending[subscriber_id].append(event)
                await self._queue.put(event)

    def get_pending(self, agent_id: str) -> list[MemoryEvent]:
        events = self._pending.get(agent_id, []).copy()
        self._pending[agent_id] = []
        return events

    def has_pending(self, agent_id: str) -> bool:
        return len(self._pending.get(agent_id, [])) > 0

    def format_pending_for_injection(self, agent_id: str) -> str:
        events = self.get_pending(agent_id)
        if not events:
            return ""
        labels = {"fact_added": "新增", "fact_updated": "更新", "fact_deleted": "删除"}
        lines = ["【来自其他 Agent 的记忆更新】"]
        for e in events:
            action = labels.get(e.event_type, e.event_type)
            layer = e.data.get("layer", "")
            count = e.data.get("count", 1)
            lines.append(f"- [{action}] 来自 {e.source_agent_id}: {count}条{layer}层记忆")
        return "\n".join(lines)

    async def _consume_loop(self):
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            callbacks = self._callbacks.get(event.event_type, [])
            for callback in callbacks:
                try:
                    result = callback(event)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.warning(f"[MemoryEventBus] Callback error for {event.event_type}: {e}")

    def on(self, event_type: str, callback: Callable):
        if event_type not in self._callbacks:
            self._callbacks[event_type] = []
        self._callbacks[event_type].append(callback)

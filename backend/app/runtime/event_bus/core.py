import asyncio
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable
from loguru import logger


class EventType(str, Enum):
    USER_MESSAGE = "user.message"
    AGENT_RESPONSE = "agent.response"
    DEVICE_STATUS = "device.status"
    DEVICE_COMMAND = "device.command"
    PLUGIN_EVENT = "plugin.event"
    SYSTEM_BROADCAST = "system.broadcast"
    LOCATION_UPDATE = "location.update"
    AUDIO_STREAM = "audio.stream"


@dataclass
class Event:
    type: EventType
    payload: dict[str, Any]
    source: str = ""
    target: str = ""
    tenant_id: str = "default"
    metadata: dict[str, Any] = field(default_factory=dict)


EventHandler = Callable[[Event], Awaitable[None]]


class EventBus:
    def __init__(self):
        self._handlers: dict[EventType, list[EventHandler]] = {}
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._running = False

    def on(self, event_type: EventType) -> Callable[[EventHandler], EventHandler]:
        def decorator(handler: EventHandler) -> EventHandler:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(handler)
            return handler
        return decorator

    async def emit(self, event: Event) -> None:
        await self._queue.put(event)
        handlers = self._handlers.get(event.type, [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Event handler error [{event.type}]: {e}")

    async def start(self) -> None:
        self._running = True
        logger.info("EventBus started")

    async def stop(self) -> None:
        self._running = False
        logger.info("EventBus stopped")

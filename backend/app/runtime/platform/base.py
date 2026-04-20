from abc import ABC, abstractmethod
from typing import Any
from dataclasses import dataclass


@dataclass
class PlatformMessage:
    platform: str
    user_id: str
    content: str
    message_id: str = ""
    group_id: str = ""
    raw: Any = None


@dataclass
class PlatformResponse:
    content: str
    message_type: str = "text"
    reply_to: str = ""
    extra: dict[str, Any] = None


class BasePlatformAdapter(ABC):
    platform_name: str = "base"

    @abstractmethod
    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        pass

    @abstractmethod
    async def handle_event(self, event: dict[str, Any]) -> PlatformMessage | None:
        pass

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

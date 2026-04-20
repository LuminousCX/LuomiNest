from abc import ABC, abstractmethod
from typing import AsyncGenerator
from app.runtime.context import PipelineContext
from loguru import logger


class PipelineStage(ABC):
    @abstractmethod
    async def process(self, ctx: PipelineContext) -> PipelineContext | None:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    def order(self) -> int:
        return 0


class StopPropagation(Exception):
    pass

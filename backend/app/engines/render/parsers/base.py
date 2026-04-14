from abc import ABC, abstractmethod
from pathlib import Path

from app.schemas.model_asset import ModelParseResult, ModelType


class BaseParser(ABC):
    @property
    @abstractmethod
    def model_type(self) -> ModelType:
        pass

    @property
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        pass

    @abstractmethod
    async def parse(self, file_path: Path) -> ModelParseResult:
        pass

    @abstractmethod
    async def validate(self, file_path: Path) -> bool:
        pass

    def can_parse(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.supported_extensions

    def _safe_read_json(self, file_path: Path) -> dict | None:
        import orjson
        try:
            return orjson.loads(file_path.read_bytes())
        except Exception:
            return None

    def _safe_read_binary(self, file_path: Path) -> bytes | None:
        try:
            return file_path.read_bytes()
        except Exception:
            return None

from pathlib import Path
from typing import Optional

from loguru import logger

from app.schemas.model_asset import ModelParseResult, ModelType
from .base import BaseParser
from .live2d_parser import Live2DParser
from .blender_parser import BlenderParser
from .vam_parser import VAMParser
from .vrm_parser import VRMParser


class ParserRegistry:
    def __init__(self):
        self._parsers: dict[ModelType, BaseParser] = {}
        self._register_defaults()

    def _register_defaults(self):
        self.register(Live2DParser())
        self.register(BlenderParser())
        self.register(VAMParser())
        self.register(VRMParser())

    def register(self, parser: BaseParser) -> None:
        self._parsers[parser.model_type] = parser

    def get_parser(self, model_type: ModelType) -> Optional[BaseParser]:
        return self._parsers.get(model_type)

    def detect_type(self, file_path: Path) -> Optional[ModelType]:
        ext = file_path.suffix.lower()
        ext_map: dict[str, ModelType] = {
            ".moc3": ModelType.LIVE2D,
            ".json": ModelType.LIVE2D,
            ".zip": ModelType.LIVE2D,
            ".glb": ModelType.BLENDER,
            ".gltf": ModelType.BLENDER,
            ".blend": ModelType.BLENDER,
            ".var": ModelType.VAM,
            ".vam": ModelType.VAM,
            ".vrm": ModelType.VRM,
        }
        return ext_map.get(ext)

    async def parse(self, file_path: Path, model_type: Optional[ModelType] = None) -> ModelParseResult:
        if model_type is None:
            model_type = self.detect_type(file_path)

        if model_type is None:
            return ModelParseResult(
                model_type=ModelType.LIVE2D,
                metadata={},
                warnings=[f"Cannot detect model type for: {file_path.name}"],
            )

        parser = self.get_parser(model_type)
        if parser is None:
            return ModelParseResult(
                model_type=model_type,
                metadata={},
                warnings=[f"No parser registered for type: {model_type}"],
            )

        if not parser.can_parse(file_path):
            return ModelParseResult(
                model_type=model_type,
                metadata={},
                warnings=[f"Parser {model_type} cannot handle file: {file_path.name}"],
            )

        is_valid = await parser.validate(file_path)
        if not is_valid:
            return ModelParseResult(
                model_type=model_type,
                metadata={},
                warnings=[f"File validation failed: {file_path.name}"],
            )

        try:
            result = await parser.parse(file_path)
            logger.info(f"Parsed {model_type} model: {file_path.name} -> {result.name}")
            return result
        except Exception as e:
            logger.error(f"Parse error for {file_path.name}: {e}")
            return ModelParseResult(
                model_type=model_type,
                metadata={},
                warnings=[f"Parse exception: {str(e)}"],
            )

    async def validate(self, file_path: Path, model_type: Optional[ModelType] = None) -> bool:
        if model_type is None:
            model_type = self.detect_type(file_path)
        if model_type is None:
            return False

        parser = self.get_parser(model_type)
        if parser is None:
            return False

        return await parser.validate(file_path)


registry = ParserRegistry()

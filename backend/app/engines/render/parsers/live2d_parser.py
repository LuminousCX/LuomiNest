import zipfile
from pathlib import Path

import orjson
from loguru import logger

from app.schemas.model_asset import ModelParseResult, ModelType
from .base import BaseParser


class Live2DParser(BaseParser):
    @property
    def model_type(self) -> ModelType:
        return ModelType.LIVE2D

    @property
    def supported_extensions(self) -> list[str]:
        return [".moc3", ".json", ".zip"]

    async def validate(self, file_path: Path) -> bool:
        ext = file_path.suffix.lower()
        if ext == ".zip":
            return await self._validate_zip(file_path)
        if ext == ".moc3":
            return await self._validate_moc3(file_path)
        if ext == ".json":
            data = self._safe_read_json(file_path)
            return data is not None and "Version" in data or "FileReferences" in data
        return False

    async def _validate_zip(self, file_path: Path) -> bool:
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                names = zf.namelist()
                has_moc3 = any(n.endswith(".moc3") for n in names)
                has_model_json = any(
                    n.endswith(".model3.json") or n.endswith(".model.json")
                    for n in names
                )
                return has_moc3 or has_model_json
        except zipfile.BadZipFile:
            return False

    async def _validate_moc3(self, file_path: Path) -> bool:
        data = self._safe_read_binary(file_path)
        if data is None:
            return False
        return len(data) > 4 and data[:4] == b"MOC3"

    async def parse(self, file_path: Path) -> ModelParseResult:
        ext = file_path.suffix.lower()
        warnings: list[str] = []

        if ext == ".zip":
            return await self._parse_zip(file_path)
        if ext == ".moc3":
            return await self._parse_moc3(file_path)
        if ext == ".json":
            return await self._parse_model_json(file_path)

        return ModelParseResult(
            model_type=self.model_type,
            metadata={},
            warnings=["Unsupported file extension"],
        )

    async def _parse_zip(self, file_path: Path) -> ModelParseResult:
        warnings: list[str] = []
        metadata: dict = {}
        animations: list[dict] = []
        expressions: list[dict] = []
        parameters: list[dict] = []
        physics_groups: list[dict] = []
        model_name: str | None = None

        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                names = zf.namelist()

                model_json_files = [
                    n for n in names
                    if n.endswith(".model3.json") or n.endswith(".model.json")
                ]

                if model_json_files:
                    model_json_path = model_json_files[0]
                    model_name = Path(model_json_path).stem.replace(".model3", "").replace(".model", "")
                    data = orjson.loads(zf.read(model_json_path))

                    metadata["version"] = data.get("Version", 3)
                    metadata["model_name"] = model_name

                    file_refs = data.get("FileReferences", {})
                    textures = file_refs.get("Textures", [])
                    metadata["texture_count"] = len(textures)

                    motion_groups = file_refs.get("Motions", {})
                    metadata["motion_groups"] = list(motion_groups.keys())

                    for group_name, motion_list in motion_groups.items():
                        for motion in motion_list:
                            animations.append({
                                "name": motion.get("Name", motion.get("File", "")),
                                "group": group_name,
                                "file": motion.get("File", ""),
                                "sound": motion.get("Sound"),
                                "fade_in": motion.get("FadeInTime"),
                                "fade_out": motion.get("FadeOutTime"),
                            })

                    expression_files = file_refs.get("Expressions", [])
                    metadata["expression_count"] = len(expression_files)
                    for expr in expression_files:
                        expressions.append({
                            "name": expr.get("Name", ""),
                            "file": expr.get("File", ""),
                        })

                    physics_file = file_refs.get("Physics")
                    metadata["physics_enabled"] = physics_file is not None
                    if physics_file:
                        physics_groups.append({"file": physics_file})

                    groups = data.get("Groups", [])
                    for group in groups:
                        group_id = group.get("Id", "")
                        parameters.append({
                            "group_id": group_id,
                            "name": group.get("Name", group_id),
                        })

                moc3_files = [n for n in names if n.endswith(".moc3")]
                if moc3_files:
                    moc3_data = zf.read(moc3_files[0])
                    metadata["moc3_size"] = len(moc3_data)

                metadata["total_files"] = len(names)
                metadata["file_list"] = names

        except Exception as e:
            logger.error(f"Live2D zip parse error: {e}")
            warnings.append(f"Parse error: {str(e)}")

        return ModelParseResult(
            model_type=self.model_type,
            name=model_name,
            metadata=metadata,
            animations=animations,
            parameters=parameters,
            expressions=expressions,
            physics_groups=physics_groups,
            warnings=warnings,
        )

    async def _parse_moc3(self, file_path: Path) -> ModelParseResult:
        data = self._safe_read_binary(file_path)
        if data is None:
            return ModelParseResult(
                model_type=self.model_type,
                metadata={},
                warnings=["Cannot read moc3 file"],
            )

        metadata: dict = {
            "moc3_size": len(data),
            "version": int.from_bytes(data[4:5], "little") if len(data) > 5 else None,
        }

        return ModelParseResult(
            model_type=self.model_type,
            name=file_path.stem,
            metadata=metadata,
            warnings=[],
        )

    async def _parse_model_json(self, file_path: Path) -> ModelParseResult:
        data = self._safe_read_json(file_path)
        if data is None:
            return ModelParseResult(
                model_type=self.model_type,
                metadata={},
                warnings=["Invalid JSON"],
            )

        metadata: dict = {"version": data.get("Version", 3)}
        animations: list[dict] = []
        expressions: list[dict] = []

        file_refs = data.get("FileReferences", {})
        metadata["texture_count"] = len(file_refs.get("Textures", []))
        metadata["motion_groups"] = list(file_refs.get("Motions", {}).keys())
        metadata["expression_count"] = len(file_refs.get("Expressions", []))
        metadata["physics_enabled"] = file_refs.get("Physics") is not None

        for group_name, motion_list in file_refs.get("Motions", {}).items():
            for motion in motion_list:
                animations.append({
                    "name": motion.get("Name", ""),
                    "group": group_name,
                    "file": motion.get("File", ""),
                })

        for expr in file_refs.get("Expressions", []):
            expressions.append({
                "name": expr.get("Name", ""),
                "file": expr.get("File", ""),
            })

        return ModelParseResult(
            model_type=self.model_type,
            name=data.get("Name", file_path.stem),
            metadata=metadata,
            animations=animations,
            expressions=expressions,
        )

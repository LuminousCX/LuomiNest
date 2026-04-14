import zipfile
from pathlib import Path

from loguru import logger

from app.schemas.model_asset import ModelParseResult, ModelType
from .base import BaseParser


class VAMParser(BaseParser):
    @property
    def model_type(self) -> ModelType:
        return ModelType.VAM

    @property
    def supported_extensions(self) -> list[str]:
        return [".var", ".vam", ".json"]

    async def validate(self, file_path: Path) -> bool:
        ext = file_path.suffix.lower()
        if ext == ".var":
            return await self._validate_var(file_path)
        if ext == ".vam":
            return await self._validate_vam(file_path)
        if ext == ".json":
            data = self._safe_read_json(file_path)
            return data is not None and (
                "vamVersion" in data
                or "pluginId" in data
                or "customAssetId" in data
                or "morphs" in data
            )
        return False

    async def _validate_var(self, file_path: Path) -> bool:
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                names = zf.namelist()
                has_meta = any(
                    n.endswith(".json") and "meta" in n.lower() for n in names
                )
                has_vam = any(n.endswith(".vam") for n in names)
                return has_meta or has_vam
        except zipfile.BadZipFile:
            return False

    async def _validate_vam(self, file_path: Path) -> bool:
        data = self._safe_read_json(file_path)
        return data is not None

    async def parse(self, file_path: Path) -> ModelParseResult:
        ext = file_path.suffix.lower()
        if ext == ".var":
            return await self._parse_var(file_path)
        if ext == ".vam":
            return await self._parse_vam(file_path)
        if ext == ".json":
            return await self._parse_vam(file_path)
        return ModelParseResult(
            model_type=self.model_type,
            metadata={},
            warnings=["Unsupported extension"],
        )

    async def _parse_var(self, file_path: Path) -> ModelParseResult:
        warnings: list[str] = []
        metadata: dict = {}
        animations: list[dict] = []
        parameters: list[dict] = []
        model_name: str | None = None

        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                names = zf.namelist()
                metadata["total_files"] = len(names)

                meta_files = [
                    n for n in names
                    if n.endswith(".json") and ("meta" in n.lower() or "package" in n.lower())
                ]

                if meta_files:
                    import orjson
                    meta_data = orjson.loads(zf.read(meta_files[0]))
                    model_name = meta_data.get("name", meta_data.get("displayName"))
                    metadata["vam_version"] = meta_data.get("vamVersion")
                    metadata["author"] = meta_data.get("creatorName", meta_data.get("author"))
                    metadata["category"] = meta_data.get("category")
                    metadata["description"] = meta_data.get("description")
                    metadata["license_type"] = meta_data.get("licenseType")

                    dependencies = meta_data.get("dependencies", [])
                    metadata["plugin_dependencies"] = dependencies

                vam_files = [n for n in names if n.endswith(".vam")]
                for vam_file in vam_files:
                    try:
                        import orjson
                        vam_data = orjson.loads(zf.read(vam_file))
                        sub_result = self._extract_vam_data(vam_data)
                        if sub_result.get("morph_count"):
                            metadata["morph_count"] = metadata.get("morph_count", 0) + sub_result["morph_count"]
                        if sub_result.get("clothing_items"):
                            metadata["clothing_items"] = metadata.get("clothing_items", 0) + sub_result["clothing_items"]
                        animations.extend(sub_result.get("animations", []))
                        parameters.extend(sub_result.get("parameters", []))
                    except Exception as e:
                        logger.warning(f"VAM sub-file parse error: {e}")

                texture_files = [
                    n for n in names
                    if n.lower().endswith((".png", ".jpg", ".jpeg", ".tga"))
                ]
                metadata["texture_count"] = len(texture_files)

                max_res = 0
                for tf in texture_files:
                    info = zf.getinfo(tf)
                    if info.file_size > max_res:
                        max_res = info.file_size
                if max_res > 0:
                    if max_res > 16 * 1024 * 1024:
                        metadata["texture_resolution"] = "4K+"
                    elif max_res > 4 * 1024 * 1024:
                        metadata["texture_resolution"] = "4K"
                    elif max_res > 1 * 1024 * 1024:
                        metadata["texture_resolution"] = "2K"
                    else:
                        metadata["texture_resolution"] = "1K"

        except Exception as e:
            logger.error(f"VAM var parse error: {e}")
            warnings.append(f"Parse error: {str(e)}")

        return ModelParseResult(
            model_type=self.model_type,
            name=model_name or file_path.stem,
            metadata=metadata,
            animations=animations,
            parameters=parameters,
            warnings=warnings,
        )

    async def _parse_vam(self, file_path: Path) -> ModelParseResult:
        data = self._safe_read_json(file_path)
        if data is None:
            return ModelParseResult(
                model_type=self.model_type,
                metadata={},
                warnings=["Invalid JSON"],
            )

        metadata: dict = {}
        model_name = data.get("name", data.get("displayName", file_path.stem))

        if "vamVersion" in data:
            metadata["vam_version"] = data["vamVersion"]
        if "creatorName" in data:
            metadata["author"] = data["creatorName"]

        extracted = self._extract_vam_data(data)
        metadata.update(extracted)

        return ModelParseResult(
            model_type=self.model_type,
            name=model_name,
            metadata=metadata,
            animations=extracted.get("animations", []),
            parameters=extracted.get("parameters", []),
        )

    def _extract_vam_data(self, data: dict) -> dict:
        result: dict = {}

        morphs = data.get("morphs", [])
        result["morph_count"] = len(morphs)

        clothing = data.get("clothing", [])
        if isinstance(clothing, list):
            result["clothing_items"] = len(clothing)
        elif isinstance(clothing, dict):
            result["clothing_items"] = len(clothing)

        animations: list[dict] = []
        anim_list = data.get("animations", [])
        for idx, anim in enumerate(anim_list):
            if isinstance(anim, dict):
                animations.append({
                    "name": anim.get("name", f"anim_{idx}"),
                    "type": anim.get("type", "unknown"),
                    "loop": anim.get("loop", False),
                    "blend_time": anim.get("blendTime"),
                })
            elif isinstance(anim, str):
                animations.append({"name": anim, "type": "unknown"})
        result["animations"] = animations

        parameters: list[dict] = []
        param_list = data.get("parameters", data.get("morphs", []))
        for param in param_list:
            if isinstance(param, dict):
                parameters.append({
                    "name": param.get("name", param.get("uid", "")),
                    "value": param.get("value", param.get("defaultValue", 0)),
                    "min": param.get("min", 0),
                    "max": param.get("max", 1),
                })
            elif isinstance(param, str):
                parameters.append({"name": param, "value": 0, "min": 0, "max": 1})
        result["parameters"] = parameters

        return result

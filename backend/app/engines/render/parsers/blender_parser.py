import struct
import zipfile
from pathlib import Path

from loguru import logger

from app.schemas.model_asset import ModelParseResult, ModelType
from .base import BaseParser


class BlenderParser(BaseParser):
    @property
    def model_type(self) -> ModelType:
        return ModelType.BLENDER

    @property
    def supported_extensions(self) -> list[str]:
        return [".glb", ".gltf", ".blend"]

    async def validate(self, file_path: Path) -> bool:
        ext = file_path.suffix.lower()
        if ext == ".glb":
            return await self._validate_glb(file_path)
        if ext == ".gltf":
            return await self._validate_gltf(file_path)
        if ext == ".blend":
            return await self._validate_blend(file_path)
        return False

    async def _validate_glb(self, file_path: Path) -> bool:
        data = self._safe_read_binary(file_path)
        if data is None or len(data) < 12:
            return False
        magic = data[:4]
        return magic == b"glTF"

    async def _validate_gltf(self, file_path: Path) -> bool:
        data = self._safe_read_json(file_path)
        if data is None:
            return False
        return "asset" in data

    async def _validate_blend(self, file_path: Path) -> bool:
        data = self._safe_read_binary(file_path)
        if data is None or len(data) < 7:
            return False
        return data[:7] == b"BLENDER"

    async def parse(self, file_path: Path) -> ModelParseResult:
        ext = file_path.suffix.lower()
        if ext == ".glb":
            return await self._parse_glb(file_path)
        if ext == ".gltf":
            return await self._parse_gltf(file_path)
        if ext == ".blend":
            return await self._parse_blend(file_path)
        return ModelParseResult(
            model_type=self.model_type,
            metadata={},
            warnings=["Unsupported extension"],
        )

    async def _parse_glb(self, file_path: Path) -> ModelParseResult:
        data = self._safe_read_binary(file_path)
        if data is None:
            return ModelParseResult(
                model_type=self.model_type,
                metadata={},
                warnings=["Cannot read file"],
            )

        metadata: dict = {"format": "glb", "file_size": len(data)}
        animations: list[dict] = []
        warnings: list[str] = []

        try:
            magic = data[:4]
            version = struct.unpack("<I", data[4:8])[0]
            total_length = struct.unpack("<I", data[8:12])[0]

            metadata["glb_version"] = version
            metadata["total_length"] = total_length

            offset = 12
            chunk_idx = 0
            json_chunk_data: bytes | None = None

            while offset < len(data) and chunk_idx < 2:
                if offset + 8 > len(data):
                    break
                chunk_length = struct.unpack("<I", data[offset:offset + 4])[0]
                chunk_type = data[offset + 4:offset + 8]

                if chunk_type == b"JSON" and json_chunk_data is None:
                    json_chunk_data = data[offset + 8:offset + 8 + chunk_length]
                elif chunk_type == b"BIN\0":
                    metadata["bin_chunk_size"] = chunk_length

                offset += 8 + chunk_length
                chunk_idx += 1

            if json_chunk_data:
                import orjson
                gltf_data = orjson.loads(json_chunk_data)
                metadata.update(self._extract_gltf_metadata(gltf_data))
                animations = self._extract_gltf_animations(gltf_data)

        except Exception as e:
            logger.error(f"GLB parse error: {e}")
            warnings.append(f"Parse error: {str(e)}")

        return ModelParseResult(
            model_type=self.model_type,
            name=file_path.stem,
            metadata=metadata,
            animations=animations,
            warnings=warnings,
        )

    async def _parse_gltf(self, file_path: Path) -> ModelParseResult:
        data = self._safe_read_json(file_path)
        if data is None:
            return ModelParseResult(
                model_type=self.model_type,
                metadata={},
                warnings=["Invalid JSON"],
            )

        metadata: dict = {"format": "gltf"}
        metadata.update(self._extract_gltf_metadata(data))
        animations = self._extract_gltf_animations(data)

        return ModelParseResult(
            model_type=self.model_type,
            name=file_path.stem,
            metadata=metadata,
            animations=animations,
        )

    async def _parse_blend(self, file_path: Path) -> ModelParseResult:
        data = self._safe_read_binary(file_path)
        if data is None:
            return ModelParseResult(
                model_type=self.model_type,
                metadata={},
                warnings=["Cannot read file"],
            )

        metadata: dict = {"format": "blend", "file_size": len(data)}
        warnings: list[str] = []

        try:
            header = data[:7]
            if header != b"BLENDER":
                warnings.append("Invalid BLENDER header")
            else:
                pointer_size = 8 if data[7:8] == b"-" else 4
                version_bytes = data[8:11].decode("ascii", errors="replace")
                metadata["blender_version"] = version_bytes
                metadata["pointer_size"] = pointer_size
                metadata["is_little_endian"] = data[7:8] == b"v" or True

        except Exception as e:
            logger.error(f"Blend parse error: {e}")
            warnings.append(f"Parse error: {str(e)}")

        return ModelParseResult(
            model_type=self.model_type,
            name=file_path.stem,
            metadata=metadata,
            warnings=warnings,
        )

    def _extract_gltf_metadata(self, gltf_data: dict) -> dict:
        result: dict = {}
        asset_info = gltf_data.get("asset", {})
        result["generator"] = asset_info.get("generator")
        result["gltf_version"] = asset_info.get("version", "2.0")

        scenes = gltf_data.get("scenes", [])
        result["scene_count"] = len(scenes)

        nodes = gltf_data.get("nodes", [])
        result["node_count"] = len(nodes)

        meshes = gltf_data.get("meshes", [])
        result["mesh_count"] = len(meshes)

        materials = gltf_data.get("materials", [])
        result["material_count"] = len(materials)

        skins = gltf_data.get("skins", [])
        result["armature_count"] = len(skins)

        total_vertices = 0
        total_faces = 0
        has_uv = False
        has_morph = False

        accessors = gltf_data.get("accessors", [])
        buffer_views = gltf_data.get("bufferViews", [])

        for mesh in meshes:
            for prim in mesh.get("primitives", []):
                pos_acc_idx = prim.get("attributes", {}).get("POSITION")
                if pos_acc_idx is not None and pos_acc_idx < len(accessors):
                    total_vertices += accessors[pos_acc_idx].get("count", 0)

                indices_idx = prim.get("indices")
                if indices_idx is not None and indices_idx < len(accessors):
                    total_faces += accessors[indices_idx].get("count", 0) // 3

                if "TEXCOORD_0" in prim.get("attributes", {}):
                    has_uv = True
                if prim.get("targets"):
                    has_morph = True

        result["vertex_count"] = total_vertices
        result["face_count"] = total_faces
        result["has_uv_maps"] = has_uv
        result["has_shape_keys"] = has_morph

        textures = gltf_data.get("textures", [])
        result["texture_count"] = len(textures)

        images = gltf_data.get("images", [])
        result["image_count"] = len(images)

        return result

    def _extract_gltf_animations(self, gltf_data: dict) -> list[dict]:
        animations: list[dict] = []
        gltf_anims = gltf_data.get("animations", [])

        for idx, anim in enumerate(gltf_anims):
            channels = anim.get("channels", [])
            samplers = anim.get("samplers", [])

            anim_info: dict = {
                "name": anim.get("name", f"animation_{idx}"),
                "channel_count": len(channels),
                "sampler_count": len(samplers),
                "duration": None,
            }

            accessors = gltf_data.get("accessors", [])
            max_time = 0.0
            for sampler in samplers:
                input_idx = sampler.get("input")
                if input_idx is not None and input_idx < len(accessors):
                    acc = accessors[input_idx]
                    acc_max = acc.get("max", [0])
                    if acc_max:
                        max_time = max(max_time, acc_max[-1])

            if max_time > 0:
                anim_info["duration"] = max_time

            animations.append(anim_info)

        return animations

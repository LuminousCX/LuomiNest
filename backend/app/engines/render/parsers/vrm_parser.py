import struct
import zipfile
from pathlib import Path

from loguru import logger

from app.schemas.model_asset import ModelParseResult, ModelType
from .base import BaseParser


class VRMParser(BaseParser):
    @property
    def model_type(self) -> ModelType:
        return ModelType.VRM

    @property
    def supported_extensions(self) -> list[str]:
        return [".vrm"]

    async def validate(self, file_path: Path) -> bool:
        data = self._safe_read_binary(file_path)
        if data is None or len(data) < 12:
            return False
        magic = data[:4]
        if magic != b"glTF":
            return False
        try:
            import orjson
            json_chunk = self._extract_glb_json(data)
            if json_chunk is None:
                return False
            extensions = json_chunk.get("extensions", {})
            return "VRM" in extensions
        except Exception:
            return False

    async def parse(self, file_path: Path) -> ModelParseResult:
        data = self._safe_read_binary(file_path)
        if data is None:
            return ModelParseResult(
                model_type=self.model_type,
                metadata={},
                warnings=["Cannot read file"],
            )

        metadata: dict = {"format": "vrm"}
        animations: list[dict] = []
        expressions: list[dict] = []
        parameters: list[dict] = []
        warnings: list[str] = []
        model_name: str | None = None

        try:
            json_chunk = self._extract_glb_json(data)
            if json_chunk is None:
                return ModelParseResult(
                    model_type=self.model_type,
                    metadata={},
                    warnings=["Invalid VRM/GLB format"],
                )

            vrm_ext = json_chunk.get("extensions", {}).get("VRM", {})
            meta = vrm_ext.get("meta", {})

            model_name = meta.get("name", meta.get("title", file_path.stem))
            metadata["vrm_version"] = meta.get("version", "0.0")
            metadata["author"] = meta.get("author")
            metadata["contact_information"] = meta.get("contactInformation")
            metadata["reference"] = meta.get("reference")
            metadata["thumbnail"] = meta.get("thumbnail")
            metadata["license_name"] = meta.get("licenseName")
            metadata["license_url"] = meta.get("licenseUrl")
            metadata["commercial_use"] = meta.get("commercialUseNameList", {})
            metadata["allow_modification"] = meta.get("allowModificationNameList", {})
            metadata["allow_redistribution"] = meta.get("allowRedistributionNameList", {})

            humanoid = vrm_ext.get("humanoid", {})
            bone_mapping = humanoid.get("humanBones", [])
            metadata["bone_count"] = len(bone_mapping)
            metadata["bone_mapping"] = [
                {"bone": b.get("bone"), "node": b.get("node")}
                for b in bone_mapping
            ]

            blend_shape_groups = vrm_ext.get("blendShapeMaster", {}).get("blendShapeGroups", [])
            metadata["expression_count"] = len(blend_shape_groups)
            for group in blend_shape_groups:
                expressions.append({
                    "name": group.get("name", ""),
                    "preset": group.get("presetName", ""),
                    "binds_count": len(group.get("binds", [])),
                    "is_binary": group.get("isBinary", False),
                })

            first_person = vrm_ext.get("firstPerson", {})
            metadata["first_person_bone"] = first_person.get("firstPersonBone")
            metadata["eye_look_at_type"] = first_person.get("lookAtTypeName", "")

            look_at = vrm_ext.get("lookAt", {})
            metadata["look_at_type"] = look_at.get("type")
            if look_at.get("offsetFromHeadBone"):
                metadata["look_at_offset"] = look_at["offsetFromHeadBone"]

            spring_bones = vrm_ext.get("secondaryAnimation", {}).get("boneGroups", [])
            metadata["spring_bone_count"] = len(spring_bones)

            gltf_anims = json_chunk.get("animations", [])
            for idx, anim in enumerate(gltf_anims):
                animations.append({
                    "name": anim.get("name", f"animation_{idx}"),
                    "channel_count": len(anim.get("channels", [])),
                })

            meshes = json_chunk.get("meshes", [])
            materials = json_chunk.get("materials", [])
            nodes = json_chunk.get("nodes", [])
            metadata["mesh_count"] = len(meshes)
            metadata["material_count"] = len(materials)
            metadata["node_count"] = len(nodes)

            accessors = json_chunk.get("accessors", [])
            total_vertices = 0
            for mesh in meshes:
                for prim in mesh.get("primitives", []):
                    pos_idx = prim.get("attributes", {}).get("POSITION")
                    if pos_idx is not None and pos_idx < len(accessors):
                        total_vertices += accessors[pos_idx].get("count", 0)
            metadata["vertex_count"] = total_vertices

        except Exception as e:
            logger.error(f"VRM parse error: {e}")
            warnings.append(f"Parse error: {str(e)}")

        return ModelParseResult(
            model_type=self.model_type,
            name=model_name,
            metadata=metadata,
            animations=animations,
            expressions=expressions,
            parameters=parameters,
            warnings=warnings,
        )

    def _extract_glb_json(self, data: bytes) -> dict | None:
        if len(data) < 12:
            return None
        magic = data[:4]
        if magic != b"glTF":
            return None

        try:
            import orjson
            offset = 12
            while offset + 8 <= len(data):
                chunk_length = struct.unpack("<I", data[offset:offset + 4])[0]
                chunk_type = data[offset + 4:offset + 8]
                if chunk_type == b"JSON":
                    json_data = data[offset + 8:offset + 8 + chunk_length]
                    return orjson.loads(json_data)
                offset += 8 + chunk_length
        except Exception:
            pass
        return None

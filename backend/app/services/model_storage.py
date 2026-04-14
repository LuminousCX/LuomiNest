import hashlib
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from loguru import logger

from app.core.config import settings


class ModelStorageManager:
    def __init__(self):
        self._base_dir = Path(settings.AVATAR_DIR)
        self._models_dir = self._base_dir / "models"
        self._thumbnails_dir = self._base_dir / "thumbnails"
        self._temp_dir = self._base_dir / "temp"
        self._versions_dir = self._base_dir / "versions"

    async def initialize(self) -> None:
        for d in [self._models_dir, self._thumbnails_dir, self._temp_dir, self._versions_dir]:
            d.mkdir(parents=True, exist_ok=True)
        logger.info(f"ModelStorageManager initialized at {self._base_dir}")

    def _compute_hash(self, file_path: Path) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    async def save_upload(self, temp_path: Path, model_id: str, original_filename: str) -> str:
        model_dir = self._models_dir / model_id
        model_dir.mkdir(parents=True, exist_ok=True)

        dest = model_dir / original_filename
        shutil.move(str(temp_path), str(dest))

        logger.info(f"Saved model file: {dest}")
        return str(dest)

    async def save_thumbnail(self, image_data: bytes, model_id: str, filename: str = "thumbnail.png") -> str:
        thumb_dir = self._thumbnails_dir / model_id
        thumb_dir.mkdir(parents=True, exist_ok=True)

        dest = thumb_dir / filename
        dest.write_bytes(image_data)

        return str(dest)

    async def create_version(
        self,
        model_id: str,
        file_path: str,
        version: int,
        change_log: str | None = None,
    ) -> dict:
        version_dir = self._versions_dir / model_id
        version_dir.mkdir(parents=True, exist_ok=True)

        src = Path(file_path)
        version_filename = f"v{version}_{src.name}"
        dest = version_dir / version_filename

        shutil.copy2(str(src), str(dest))

        file_hash = self._compute_hash(dest)
        file_size = dest.stat().st_size

        logger.info(f"Created version {version} for model {model_id}: {dest}")

        return {
            "version": version,
            "file_path": str(dest),
            "file_size": file_size,
            "file_hash": file_hash,
            "change_log": change_log,
        }

    async def get_version_path(self, model_id: str, version: int, filename_hint: str = "") -> Path | None:
        version_dir = self._versions_dir / model_id
        if not version_dir.exists():
            return None

        version_prefix = f"v{version}_"
        for f in version_dir.iterdir():
            if f.name.startswith(version_prefix):
                return f

        return None

    async def delete_model_files(self, model_id: str) -> None:
        for d in [self._models_dir / model_id, self._thumbnails_dir / model_id, self._versions_dir / model_id]:
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)
                logger.info(f"Deleted model directory: {d}")

    async def get_file_info(self, file_path: str) -> dict:
        p = Path(file_path)
        if not p.exists():
            return {"exists": False}

        stat = p.stat()
        return {
            "exists": True,
            "size": stat.st_size,
            "hash": self._compute_hash(p),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        }

    async def create_temp_upload_path(self, suffix: str = "") -> Path:
        self._temp_dir.mkdir(parents=True, exist_ok=True)
        temp_name = f"{uuid.uuid4().hex}{suffix}"
        return self._temp_dir / temp_name

    async def cleanup_temp(self, max_age_hours: int = 24) -> int:
        if not self._temp_dir.exists():
            return 0

        count = 0
        now = datetime.now().timestamp()
        max_age_seconds = max_age_hours * 3600

        for f in self._temp_dir.iterdir():
            if f.is_file():
                age = now - f.stat().st_mtime
                if age > max_age_seconds:
                    f.unlink()
                    count += 1

        return count

    def get_model_path(self, model_id: str, filename: str) -> Path:
        return self._models_dir / model_id / filename

    def get_thumbnail_path(self, model_id: str, filename: str = "thumbnail.png") -> Path:
        return self._thumbnails_dir / model_id / filename


class ModelCacheManager:
    def __init__(self):
        self._cache: dict[str, dict] = {}

    def get(self, key: str) -> dict | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        return entry.get("data")

    def set(self, key: str, data: dict, ttl_seconds: int = 3600) -> None:
        self._cache[key] = {
            "data": data,
            "expires_at": datetime.now().timestamp() + ttl_seconds,
        }

    def delete(self, key: str) -> None:
        self._cache.pop(key, None)

    def invalidate_pattern(self, pattern: str) -> int:
        count = 0
        keys_to_delete = [k for k in self._cache if pattern in k]
        for k in keys_to_delete:
            del self._cache[k]
            count += 1
        return count

    def cleanup_expired(self) -> int:
        now = datetime.now().timestamp()
        expired_keys = [
            k for k, v in self._cache.items()
            if v.get("expires_at", 0) < now
        ]
        for k in expired_keys:
            del self._cache[k]
        return len(expired_keys)

    def clear(self) -> None:
        self._cache.clear()

    def stats(self) -> dict:
        return {
            "total_entries": len(self._cache),
            "keys": list(self._cache.keys()),
        }


storage_manager = ModelStorageManager()
cache_manager = ModelCacheManager()

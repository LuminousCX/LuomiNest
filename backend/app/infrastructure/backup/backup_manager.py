import asyncio
import os
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from app.core.config import settings


class LumiBackupManager:
    """数据备份管理器。

    将整个 DATA_DIR 打包为 zip 备份文件，
    支持创建、恢复、列出、自动清理备份。
    """

    MAX_BACKUPS = 10

    def __init__(self):
        self._backup_dir = os.path.join(settings.DATA_DIR, "backups")
        os.makedirs(self._backup_dir, exist_ok=True)

    def create_backup(self, label: str = "") -> str | None:
        """创建数据备份，返回备份文件路径。"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        suffix = f"_{label}" if label else ""
        backup_name = f"luominest_backup_{timestamp}{suffix}.zip"
        backup_path = os.path.join(self._backup_dir, backup_name)

        data_dir = Path(settings.DATA_DIR)
        if not data_dir.exists():
            logger.warning(f"[Backup] DATA_DIR does not exist: {data_dir}")
            return None

        try:
            with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(data_dir):
                    if self._backup_dir in root:
                        continue
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, data_dir)
                        zf.write(file_path, arcname)

            size_mb = os.path.getsize(backup_path) / (1024 * 1024)
            logger.success(f"[Backup] Created: {backup_name} ({size_mb:.1f} MB)")

            self._auto_cleanup()
            return backup_path
        except Exception as e:
            logger.error(f"[Backup] Failed to create backup: {e}")
            if os.path.exists(backup_path):
                try:
                    os.remove(backup_path)
                except OSError as cleanup_error:
                    logger.warning(
                        f"[Backup] Failed to remove partial backup file {backup_path}: {cleanup_error}"
                    )
            return None

    def restore_backup(self, backup_path: str) -> bool:
        """从备份文件恢复数据。"""
        if not os.path.exists(backup_path):
            logger.error(f"[Backup] Backup file not found: {backup_path}")
            return False

        data_dir = Path(settings.DATA_DIR)
        temp_restore = data_dir / "_restore_temp"
        temp_restore.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(backup_path, "r") as zf:
                zf.extractall(temp_restore)

            for item in temp_restore.iterdir():
                target = data_dir / item.name
                if target.exists():
                    if target.is_dir():
                        shutil.rmtree(target)
                    else:
                        target.unlink()
                shutil.move(str(item), str(target))

            logger.success(f"[Backup] Restored from: {os.path.basename(backup_path)}")
            return True
        except Exception as e:
            logger.error(f"[Backup] Failed to restore: {e}")
            return False
        finally:
            if temp_restore.exists():
                shutil.rmtree(temp_restore, ignore_errors=True)

    def list_backups(self) -> list[dict]:
        """列出所有备份文件。"""
        backups = []
        if not os.path.exists(self._backup_dir):
            return backups

        for name in sorted(os.listdir(self._backup_dir), reverse=True):
            if not name.endswith(".zip"):
                continue
            path = os.path.join(self._backup_dir, name)
            stat = os.stat(path)
            backups.append({
                "name": name,
                "path": path,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            })
        return backups

    def delete_backup(self, backup_path: str) -> bool:
        """删除指定备份文件。"""
        if not os.path.exists(backup_path):
            return False
        try:
            os.remove(backup_path)
            logger.info(f"[Backup] Deleted: {os.path.basename(backup_path)}")
            return True
        except Exception as e:
            logger.error(f"[Backup] Failed to delete: {e}")
            return False

    def _auto_cleanup(self):
        """自动清理旧备份，保留最新的 MAX_BACKUPS 个。"""
        backups = self.list_backups()
        if len(backups) <= self.MAX_BACKUPS:
            return

        to_delete = backups[self.MAX_BACKUPS:]
        for backup in to_delete:
            self.delete_backup(backup["path"])
        logger.info(f"[Backup] Auto-cleaned {len(to_delete)} old backups")

    # ── Async wrappers ──

    async def create_backup_async(self, label: str = "") -> str | None:
        return await asyncio.to_thread(self.create_backup, label)

    async def restore_backup_async(self, backup_path: str) -> bool:
        return await asyncio.to_thread(self.restore_backup, backup_path)

    async def list_backups_async(self) -> list[dict]:
        return await asyncio.to_thread(self.list_backups)

    async def delete_backup_async(self, backup_path: str) -> bool:
        return await asyncio.to_thread(self.delete_backup, backup_path)


lumi_backup_manager = LumiBackupManager()

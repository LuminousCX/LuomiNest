import asyncio
import contextlib
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from app.core.config import settings
from app.core.utils import utc_now_dt


class LumiBackupManager:
    """数据备份管理器。

    将 DATA_DIR 打包为 zip 备份文件（活库 luominest.db 先经 sqlite3 backup API
    取在线一致快照，-wal/-shm 中间态不入包），支持创建、恢复、列出、自动清理备份。
    """

    MAX_BACKUPS = 10

    def __init__(self):
        self._backup_dir = os.path.join(settings.DATA_DIR, "backups")
        os.makedirs(self._backup_dir, exist_ok=True)

    def create_backup(self, label: str = "") -> str | None:
        """创建数据备份，返回备份文件路径。"""
        timestamp = utc_now_dt().strftime("%Y%m%d_%H%M%S")
        suffix = f"_{label}" if label else ""
        backup_name = f"luominest_backup_{timestamp}{suffix}.zip"
        backup_path = os.path.join(self._backup_dir, backup_name)

        data_dir = Path(settings.DATA_DIR)
        if not data_dir.exists():
            logger.warning(f"[Backup] DATA_DIR does not exist: {data_dir}")
            return None

        try:
            # 活库不能直接拷贝打包（写入中途会得到不一致快照），
            # 先用 sqlite3 backup API 做在线一致快照，再以快照替代库文件入包
            db_path = data_dir / "luominest.db"
            snapshot_path = ""
            if db_path.exists():
                snapshot_path = self._snapshot_db(str(db_path))

            try:
                with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    for root, _dirs, files in os.walk(data_dir):
                        if self._backup_dir in root:
                            continue
                        for file in files:
                            # -wal/-shm 是写时中间态，数据已含在快照中，不再打包
                            if file in ("luominest.db-wal", "luominest.db-shm"):
                                continue
                            file_path = os.path.join(root, file)
                            if file == "luominest.db" and os.path.abspath(file_path) == str(db_path):
                                zf.write(snapshot_path, "luominest.db")
                                continue
                            arcname = os.path.relpath(file_path, data_dir)
                            zf.write(file_path, arcname)
            finally:
                # 快照只是打包用的中间产物，用完即清理
                if snapshot_path and os.path.exists(snapshot_path):
                    with contextlib.suppress(OSError):
                        os.remove(snapshot_path)

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
                # 预检 zip 完整性，损坏的备份直接拒绝，避免污染现有数据
                bad_file = zf.testzip()
                if bad_file is not None:
                    logger.error(f"[Backup] Backup file corrupted at entry: {bad_file}")
                    return False
                zf.extractall(temp_restore)

            # 覆盖现有数据前先校验解出的数据库完整性，坏库同样不能落盘
            restored_db = temp_restore / "luominest.db"
            if restored_db.exists():
                integrity = self._check_db_integrity(str(restored_db))
                if integrity != "ok":
                    logger.error(f"[Backup] Restored database failed integrity check: {integrity}")
                    return False

            # Windows 下运行中的后端持有 luominest.db 句柄，直接覆盖会失败或产生不一致，
            # 恢复前应先停止后端进程
            logger.warning(
                "[Backup] Restoring over live data; stop the backend first to avoid file-lock issues on Windows"
            )

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

    @staticmethod
    def _snapshot_db(db_path: str) -> str:
        """对活库执行 sqlite3 在线备份，生成一致性快照，返回快照临时文件路径。"""
        fd, snapshot_path = tempfile.mkstemp(prefix="luominest_db_snapshot_", suffix=".db")
        os.close(fd)
        try:
            src = sqlite3.connect(db_path)
            try:
                dst = sqlite3.connect(snapshot_path)
                try:
                    src.backup(dst)
                finally:
                    dst.close()
            finally:
                src.close()
        except Exception:
            # 快照失败时清理半成品临时文件
            with contextlib.suppress(OSError):
                os.remove(snapshot_path)
            raise
        return snapshot_path

    @staticmethod
    def _check_db_integrity(db_path: str) -> str:
        """对 SQLite 数据库执行 PRAGMA integrity_check，返回首行检查结果。"""
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute("PRAGMA integrity_check").fetchone()
            return row[0] if row else "no result"
        finally:
            conn.close()

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


luominest_backup_manager = LumiBackupManager()

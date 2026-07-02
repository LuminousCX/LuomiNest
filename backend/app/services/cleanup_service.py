import asyncio
import os
from datetime import datetime, timedelta, timezone

from loguru import logger

from app.core.config import settings
from app.infrastructure.database.conversation_store import conversation_store
from app.infrastructure.database.usage_store import usage_store


class LumiCleanupService:
    """数据清理服务。

    定期清理过期数据，防止数据无限增长。
    - 软删除超过指定天数的对话
    - 永久删除回收站中超过指定天数的对话
    - 限制使用记录最大条数
    - 清理临时下载文件
    """

    TRASH_RETENTION_DAYS = 30
    MAX_USAGE_RECORDS = 50000
    DOWNLOADS_MAX_AGE_HOURS = 24

    def cleanup_trash(self, days: int | None = None) -> int:
        """永久删除回收站中超过指定天数的对话。"""
        retention = days or self.TRASH_RETENTION_DAYS
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention)
        cutoff_str = cutoff.isoformat()

        trash_items = conversation_store.list_trash()
        deleted = 0
        for item in trash_items:
            deleted_at = item.get("deleted_at", "")
            if deleted_at and deleted_at < cutoff_str:
                if conversation_store.permanent_delete(item["id"]):
                    deleted += 1

        if deleted > 0:
            logger.info(f"[Cleanup] Permanently deleted {deleted} conversations from trash (older than {retention} days)")
        return deleted

    def cleanup_usage_records(self, max_records: int | None = None) -> int:
        """限制使用记录条数，删除超出的旧记录。"""
        limit = max_records or self.MAX_USAGE_RECORDS
        records = usage_store.get_records()
        if len(records) <= limit:
            return 0

        excess = usage_store.trim(limit)
        logger.info(f"[Cleanup] Trimmed {excess} old usage records (keeping latest {limit})")
        return excess

    def cleanup_downloads(self, max_age_hours: int | None = None) -> int:
        """清理过期的临时下载文件。"""
        max_age = max_age_hours or self.DOWNLOADS_MAX_AGE_HOURS
        downloads_dir = os.path.join(settings.DATA_DIR, "downloads")
        if not os.path.exists(downloads_dir):
            return 0

        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age)
        cutoff_ts = cutoff.timestamp()
        deleted = 0

        for name in os.listdir(downloads_dir):
            file_path = os.path.join(downloads_dir, name)
            if not os.path.isfile(file_path):
                continue
            try:
                if os.path.getmtime(file_path) < cutoff_ts:
                    os.remove(file_path)
                    deleted += 1
            except OSError as e:
                logger.warning(f"[Cleanup] Failed to delete {file_path}: {e}")

        if deleted > 0:
            logger.info(f"[Cleanup] Deleted {deleted} expired download files (older than {max_age}h)")
        return deleted

    def cleanup_temp_files(self) -> int:
        """清理所有 .tmp 临时文件。"""
        data_dir = settings.DATA_DIR
        deleted = 0
        for root, dirs, files in os.walk(data_dir):
            for name in files:
                if name.endswith(".tmp"):
                    file_path = os.path.join(root, name)
                    try:
                        os.remove(file_path)
                        deleted += 1
                    except OSError as e:
                        logger.warning(f"[Cleanup] Failed to delete temp file {file_path}: {e}")

        if deleted > 0:
            logger.info(f"[Cleanup] Deleted {deleted} temp files")
        return deleted

    def run_all(self) -> dict:
        """执行所有清理任务，返回清理统计。"""
        logger.info("[Cleanup] Starting full cleanup...")
        stats = {
            "trash_deleted": self.cleanup_trash(),
            "usage_trimmed": self.cleanup_usage_records(),
            "downloads_deleted": self.cleanup_downloads(),
            "temp_files_deleted": self.cleanup_temp_files(),
        }
        total = sum(stats.values())
        logger.info(f"[Cleanup] Completed: {total} items cleaned ({stats})")
        return stats

    # ── Async wrappers ──

    async def cleanup_trash_async(self, days: int | None = None) -> int:
        return await asyncio.to_thread(self.cleanup_trash, days)

    async def cleanup_usage_records_async(self, max_records: int | None = None) -> int:
        return await asyncio.to_thread(self.cleanup_usage_records, max_records)

    async def cleanup_downloads_async(self, max_age_hours: int | None = None) -> int:
        return await asyncio.to_thread(self.cleanup_downloads, max_age_hours)

    async def cleanup_temp_files_async(self) -> int:
        return await asyncio.to_thread(self.cleanup_temp_files)

    async def run_all_async(self) -> dict:
        return await asyncio.to_thread(self.run_all)


lumi_cleanup_service = LumiCleanupService()

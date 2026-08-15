"""config_items 命名空间存储 — 替代分散的裸 JsonStore 单例。

架构治理第二步：用户状态类数据（技能使用统计、改进建议、脚手架历史、
安装记录、插件 KV/settings 等）统一收敛到 SQLite config_items 表
（具备 AES 加密与统一备份链路），以命名空间前缀区分不同集合，
键形如 `<namespace>.<原始key>`。

设计要点：
- 公开方法保持 JsonStore 语义：get/set/delete/list_all/all/clear/mutate
  及对应 async 包装，消费者替换声明即可，调用代码零改动
- 遗留 JSON 幂等合并：由 _migration_meta 标记保护，首次访问时读取一次
  DATA_DIR/store/ 下旧 JsonStore 文件，与 config_items 现有值取并集合并
  （不覆盖运行时已写入的键），重跑不会重复合并；旧 JSON 文件是用户数据，
  仅迁移时读取，不删除文件本身
- mutate 在进程级锁内完成读-改-写，等价 JsonStore.mutate 的原子语义
- DB 尚未初始化时（如模块加载阶段）合并失败不抛错，保持未合并状态，
  下次访问自动重试（参照 CxPluginLifecycle._ensure_legacy_merged 模式）
"""
import asyncio
import hashlib
import os
import threading
from typing import Any, Callable, Optional

from loguru import logger

from app.core.config import settings
from app.infrastructure.database.config_store import luominest_config_store

# config_items.key 列长度上限（String(256)）
_MAX_KEY_LEN = 256

# 进程级已完成遗留合并的 source 缓存（避免重复实例反复查询 _migration_meta）
_MERGED_SOURCES: set[str] = set()


class ConfigNamespaceStore:
    """config_items 后端的命名空间 KV 存储。

    每个遗留 JsonStore 单例对应一个命名空间（如 "skills.usage"），
    记录以 config_items 键 `<namespace>.<原始key>` 存储。

    Args:
        namespace: 命名空间前缀（如 "skills.usage"），无需结尾点号
        legacy_source: _migration_meta 标记源名；空串表示无遗留文件需合并
        legacy_filename: DATA_DIR/store/ 下的遗留 JsonStore 文件名
    """

    def __init__(
        self,
        namespace: str,
        legacy_source: str = "",
        legacy_filename: str = "",
    ) -> None:
        self._prefix = namespace.rstrip(".") + "."
        self._legacy_source = legacy_source
        self._legacy_filename = legacy_filename
        self._lock = threading.Lock()
        # 无遗留文件时无需合并
        self._merged = not legacy_source

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _compose(self, key: str) -> str:
        """拼接 config_items 完整键。

        超长键（超过列宽限制）回退为确定性哈希键，保证 get/set 一致。
        """
        full = f"{self._prefix}{key}"
        if len(full) <= _MAX_KEY_LEN:
            return full
        digest = hashlib.sha256(str(key).encode("utf-8")).hexdigest()[:48]
        return f"{self._prefix}__h__{digest}"

    def _strip(self, full_key: str) -> str:
        """从完整 config_items 键还原原始键（去掉命名空间前缀）。"""
        return full_key[len(self._prefix):]

    def _ensure_merged(self) -> None:
        """确保遗留 JSON 合并至少成功执行过一次（幂等，失败时下次重试）。"""
        if self._merged:
            return
        if self._legacy_source in _MERGED_SOURCES:
            self._merged = True
            return
        try:
            from app.infrastructure.database.migration.json_to_sqlite_migrator import (
                _is_migrated,
                _mark_migrated,
                _read_json_file,
            )

            if _is_migrated(self._legacy_source):
                _MERGED_SOURCES.add(self._legacy_source)
                self._merged = True
                return

            path = os.path.join(settings.DATA_DIR, "store", self._legacy_filename)
            data = _read_json_file(path)
            count = 0
            if isinstance(data, dict) and data:
                existing = luominest_config_store.get_namespace(self._prefix)
                for key, value in data.items():
                    full_key = self._compose(str(key))
                    if full_key in existing:
                        continue  # 并集合并：不覆盖运行时已写入的值
                    luominest_config_store.set(full_key, value)
                    count += 1

            _mark_migrated(self._legacy_source, count)
            _MERGED_SOURCES.add(self._legacy_source)
            self._merged = True
            if count:
                logger.info(
                    f"[ConfigNamespaceStore] Merged legacy JSON {self._legacy_filename} "
                    f"into config_items namespace '{self._prefix.rstrip('.')}': "
                    f"{count} record(s)"
                )
        except Exception as e:
            # DB 可能尚未初始化（模块加载阶段），保持未合并，下次访问重试
            logger.warning(
                f"[ConfigNamespaceStore] Legacy merge deferred ({self._legacy_source}): {e}"
            )

    # ------------------------------------------------------------------
    # JsonStore 兼容读写接口
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            self._ensure_merged()
            return luominest_config_store.get(self._compose(key), default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._ensure_merged()
            luominest_config_store.set(self._compose(key), value)

    def delete(self, key: str) -> None:
        with self._lock:
            self._ensure_merged()
            luominest_config_store.delete(self._compose(key))

    def list_all(self) -> dict:
        """返回 {原始key: value} 映射（已剥离命名空间前缀，与 JsonStore.list_all 一致）。"""
        with self._lock:
            self._ensure_merged()
            data = luominest_config_store.get_namespace(self._prefix)
        return {self._strip(k): v for k, v in data.items()}

    def all(self) -> list:
        with self._lock:
            self._ensure_merged()
            data = luominest_config_store.get_namespace(self._prefix)
        return list(data.values())

    def clear(self) -> None:
        """清空命名空间下所有键值。"""
        with self._lock:
            self._ensure_merged()
            luominest_config_store.delete_namespace(self._prefix)

    def mutate(self, key: str, updater_fn: Callable[[Any], Any]) -> Optional[Any]:
        """原子读-改-写：updater_fn 接收旧值（键不存在时为 None）返回新值。

        整个操作在锁内完成，与 JsonStore.mutate 语义一致。
        """
        with self._lock:
            self._ensure_merged()
            full_key = self._compose(key)
            value = luominest_config_store.get(full_key)
            new_value = updater_fn(value)
            luominest_config_store.set(full_key, new_value)
            return new_value

    # ------------------------------------------------------------------
    # Async wrappers（非阻塞，供 FastAPI async 端点使用）
    # ------------------------------------------------------------------

    async def get_async(self, key: str, default: Any = None) -> Any:
        return await asyncio.to_thread(self.get, key, default)

    async def set_async(self, key: str, value: Any) -> None:
        await asyncio.to_thread(self.set, key, value)

    async def delete_async(self, key: str) -> None:
        await asyncio.to_thread(self.delete, key)

    async def list_all_async(self) -> dict:
        return await asyncio.to_thread(self.list_all)

    async def all_async(self) -> list:
        return await asyncio.to_thread(self.all)

    async def clear_async(self) -> None:
        await asyncio.to_thread(self.clear)

    async def mutate_async(self, key: str, updater_fn: Callable[[Any], Any]) -> Optional[Any]:
        return await asyncio.to_thread(self.mutate, key, updater_fn)

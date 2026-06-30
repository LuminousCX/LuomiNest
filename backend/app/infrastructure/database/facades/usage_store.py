"""UsageStore Facade — 替代原 usage_store 单例。

委托 UsageRepository，保留 UsageStore 方法签名（消费者零改动）。
- record() / get_records() / get_summary() 签名完全一致
- 新增 trim(max_records) 替代 cleanup_service 中直接访问 _records 的 hack
- get_summary() 用 SQL GROUP BY（替代 Python 全表扫描）
"""
import asyncio
from typing import Optional

from app.infrastructure.database.repositories import UsageRepository


class UsageFacade:
    """委托 UsageRepository，接口与 UsageStore 一致。"""

    def __init__(self, repo: UsageRepository):
        self._repo = repo

    def record(
        self,
        provider: str,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        agent_id: Optional[str] = None,
        conv_id: Optional[str] = None,
        is_stream: bool = False,
    ) -> dict:
        return self._repo.record(
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            agent_id=agent_id,
            conv_id=conv_id,
            is_stream=is_stream,
        )

    def get_records(self, days: Optional[int] = None) -> list[dict]:
        return self._repo.get_records(days)

    def get_summary(self, days: Optional[int] = None) -> dict:
        return self._repo.get_summary(days)

    def trim(self, max_records: int) -> int:
        """保留最新 max_records 条记录，删除超出的旧记录。"""
        return self._repo.trim(max_records)

    def clear(self) -> int:
        """清空所有用量记录（管理重置用），返回删除条数。"""
        return self._repo.clear_all()

    # ── Async wrappers ──

    async def record_async(self, **kwargs) -> dict:
        return await asyncio.to_thread(self.record, **kwargs)

    async def get_records_async(self, days: Optional[int] = None) -> list[dict]:
        return await asyncio.to_thread(self.get_records, days)

    async def get_summary_async(self, days: Optional[int] = None) -> dict:
        return await asyncio.to_thread(self.get_summary, days)

    async def trim_async(self, max_records: int) -> int:
        return await asyncio.to_thread(self.trim, max_records)

    async def clear_async(self) -> int:
        return await asyncio.to_thread(self.clear)


# ── 单例 ──

usage_store = UsageFacade(UsageRepository())

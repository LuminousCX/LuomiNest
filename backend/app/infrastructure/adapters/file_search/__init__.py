"""文件搜索适配器包。

提供 FileSearchPort 的具体实现：
- EverythingAdapter（Windows，调用 es.exe）
- OsWalkAdapter（跨平台兜底，纯 Python）

通过 get_file_search_adapter() 工厂函数自动选择最优适配器。
"""
from app.infrastructure.adapters.file_search.everything_adapter import EverythingAdapter
from app.infrastructure.adapters.file_search.os_walk_adapter import OsWalkAdapter


def get_file_search_adapter() -> "EverythingAdapter | OsWalkAdapter":
    """获取最优文件搜索适配器（优先 Everything，不可用回退 OsWalk）。"""
    adapter = EverythingAdapter()
    if adapter.available():
        return adapter
    return OsWalkAdapter()


__all__ = ["EverythingAdapter", "OsWalkAdapter", "get_file_search_adapter"]

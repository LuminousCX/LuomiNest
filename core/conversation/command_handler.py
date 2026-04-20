"""
命令处理模块
Author: LumiNest Team
Date: 2026-04-14
"""
from typing import Optional, Any


from core.predictive_cache import predictive_cache


class CommandHandler:
    """命令处理器类
    
    处理用户输入的系统命令
    """
    
    HELP_TEXT: str = """可用命令：
/clear - 清空记忆
/memory - 查看记忆状态
/stats - 查看系统统计
/help - 查看帮助"""

    def __init__(self, memory_manager: Any, fast_searcher: Optional[Any] = None):
        self.memory_manager = memory_manager
        self.fast_searcher = fast_searcher

    def set_fast_searcher(self, fast_searcher: Any) -> None:
        self.fast_searcher = fast_searcher

    def handle_command(self, command: str, args: Optional[str]) -> str:
        handlers = {
            "/clear": lambda: self._handle_clear(),
            "/help": lambda: self.HELP_TEXT,
            "/memory": lambda: self._handle_memory(),
            "/stats": lambda: self._handle_stats(),
        }
        
        if handler := handlers.get(command):
            return handler()
        return "未知命令，请使用 /help 查看可用命令"

    def _handle_clear(self) -> str:
        self.memory_manager.clear_all_memory()
        predictive_cache.clear()
        if self.fast_searcher:
            self.fast_searcher.clear_cache()
        return "记忆和所有缓存已成功清空"

    def _handle_memory(self) -> str:
        memory_count = self.memory_manager.get_memory_count()
        working_memory = self.memory_manager.get_working_memory()
        
        text = f"记忆状态：\n总记忆数：{memory_count} 条\n工作记忆：{len(working_memory)} 条\n\n"
        
        if working_memory:
            text += "最近对话：\n"
            for i, item in enumerate(working_memory[-3:], 1):
                text += f"{i}. {item[:50]}...\n"
        
        return text

    def _handle_stats(self) -> str:
        memory_count = self.memory_manager.get_memory_count()
        cache_stats = predictive_cache.get_stats()
        
        return f"""系统统计：
记忆总数：{memory_count} 条
缓存命中率：{cache_stats['hit_rate']}
缓存大小：{cache_stats['cache_size']} 条
热门查询：{cache_stats['hot_queries']} 条
总查询数：{cache_stats['total_queries']} 次
缓存命中：{cache_stats['hits']} 次
缓存未命中：{cache_stats['misses']} 次"""

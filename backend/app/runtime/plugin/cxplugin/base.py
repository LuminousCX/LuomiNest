"""CxPlugin 基类 — 所有 LuomiNest 插件的父类。

设计参考了业界插件系统的自动注册模式（__init_subclass__）和生命周期钩子模式，
但所有实现均为原创，使用 Cx 品牌前缀，与 LuomiNest 项目对齐。
"""

from __future__ import annotations

import os
from abc import ABC
from typing import Any

from loguru import logger

from app.models.plugin import CxEventType, CxHandlerEntry


class CxPluginContext:
    """插件运行时上下文 — 暴露给插件使用的 API 接口。

    由 loader 在实例化插件时注入，插件通过 self.context 访问系统能力。
    """

    def __init__(self, plugin_id: str, plugin_dir: str, config: dict[str, Any] | None = None):
        self.plugin_id = plugin_id
        self.plugin_dir = plugin_dir
        self.config = config or {}
        self._handlers: list[CxHandlerEntry] = []

    def register_handler(
        self,
        event_type: CxEventType,
        handler: Any,
        priority: int = 0,
    ) -> None:
        """注册事件处理器。"""
        entry = CxHandlerEntry(
            plugin_id=self.plugin_id,
            event_type=event_type,
            handler=handler,
            priority=priority,
        )
        self._handlers.append(entry)

    def get_handlers(self) -> list[CxHandlerEntry]:
        """获取已注册的处理器列表（供 loader 收集）。"""
        return list(self._handlers)

    def get_data_dir(self) -> str:
        """获取插件专属数据目录。"""
        data_dir = os.path.join(self.plugin_dir, "data")
        os.makedirs(data_dir, exist_ok=True)
        return data_dir

    def get_config(self, key: str, default: Any = None) -> Any:
        """读取插件配置项。"""
        return self.config.get(key, default)


class CxPluginBase(ABC):
    """所有 CxPlugin 的父类。

    子类通过继承此类并实现 initialize/terminate 方法来定义插件生命周期。
    使用 __init_subclass__ 自动收集插件类，供 loader 发现。
    """

    # 子类可覆盖的元数据（也可来自 manifest）
    plugin_name: str = ""
    plugin_version: str = ""
    plugin_description: str = ""
    plugin_author: str = ""

    # 全局已注册的插件类（module_path -> class）
    _cx_registered_classes: dict[str, type[CxPluginBase]] = {}

    def __init__(self, context: CxPluginContext):
        self.context = context
        self.logger = logger.bind(component="CxPlugin", plugin_id=context.plugin_id)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # 记录子类，key 为 module.qualname
        module = getattr(cls, "__module__", "")
        qualname = getattr(cls, "__qualname__", "")
        key = f"{module}.{qualname}"
        CxPluginBase._cx_registered_classes[key] = cls

    async def initialize(self) -> None:
        """插件激活时调用 — 子类覆盖此方法初始化资源、注册 Handler。"""

    async def terminate(self) -> None:
        """插件停用时调用 — 子类覆盖此方法释放资源。"""

    @classmethod
    def clear_registered_classes(cls) -> None:
        """清空已注册的插件类记录（热重载时使用）。"""
        cls._cx_registered_classes.clear()


def cx_handler(event_type: CxEventType, priority: int = 0) -> Any:
    """装饰器 — 标记方法为事件处理器。

    使用方式:
        class MyPlugin(CxPluginBase):
            @cx_handler(CxEventType.ON_CHAT_MESSAGE)
            async def on_message(self, event):
                ...
    """

    def decorator(func: Any) -> Any:
        func._cx_event_type = event_type
        func._cx_priority = priority
        return func

    return decorator

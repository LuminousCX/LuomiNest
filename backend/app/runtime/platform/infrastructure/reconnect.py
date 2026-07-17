"""统一重连框架。

提供可配置的重连策略和可混入的重连逻辑，
供平台适配器基类继承使用。
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from loguru import logger


@dataclass
class ReconnectStrategy:
    """重连策略配置。

    Attributes:
        initial_delay: 首次重连等待时间（秒）。
        max_delay: 单次重连最大等待时间（秒）。
        multiplier: 每次重连后延迟时间的乘数（指数退避）。
        max_attempts: 最大重连尝试次数，0 表示无限重试。
        jitter: 随机抖动上限（秒），避免雷群效应。
    """

    initial_delay: float = 1.0
    max_delay: float = 300.0
    multiplier: float = 2.0
    max_attempts: int = 0
    jitter: float = 1.0


class ReconnectState(Enum):
    """重连状态枚举。"""

    IDLE = auto()       # 空闲，无重连任务
    CONNECTING = auto() # 正在尝试连接
    WAITING = auto()    # 等待下一次重连
    STOPPED = auto()    # 已停止（主动取消）


class ReconnectMixin:
    """可混入的重连逻辑基类。

    提供异步重连循环、调度、取消以及状态追踪。
    子类需实现 `_do_reconnect()` 方法来执行实际的连接逻辑。

    使用示例：

    .. code-block:: python

        class MyAdapter(ReconnectMixin, BasePlatformAdapter):
            async def _do_reconnect(self) -> bool:
                # 返回 True 表示连接成功
                return await self._connect()
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._reconnect_strategy: ReconnectStrategy = ReconnectStrategy()
        self._reconnect_state: ReconnectState = ReconnectState.IDLE
        self._reconnect_task: asyncio.Task[None] | None = None
        self._reconnect_attempt: int = 0
        self._reconnect_count: int = 0  # 累计成功重连次数

    @property
    def reconnect_state(self) -> ReconnectState:
        """当前重连状态。"""
        return self._reconnect_state

    @property
    def reconnect_attempt(self) -> int:
        """当前连续重连尝试次数。"""
        return self._reconnect_attempt

    def set_reconnect_strategy(self, strategy: ReconnectStrategy) -> None:
        """设置重连策略。

        Args:
            strategy: 重连策略配置。
        """
        self._reconnect_strategy = strategy

    async def _do_reconnect(self) -> bool:
        """执行实际的连接逻辑（子类必须实现）。

        Returns:
            True 表示连接成功，False 表示连接失败。
        """
        raise NotImplementedError("子类必须实现 _do_reconnect()")

    def _on_reconnect_success(self) -> None:
        """重连成功回调。

        子类可重写以执行额外操作（如重置状态、通知上层）。
        """
        adapter_name = getattr(self, "platform_name", self.__class__.__name__)
        logger.info(
            f"[Reconnect] {adapter_name} 重连成功 "
            f"(第 {self._reconnect_attempt} 次尝试，累计成功 {self._reconnect_count} 次)"
        )

    def _on_reconnect_failed(self, error: Exception | None = None) -> None:
        """重连失败回调（所有尝试耗尽或主动取消时调用）。

        子类可重写以执行额外操作（如清理资源、通知上层）。

        Args:
            error: 导致失败的异常，为 None 表示主动取消。
        """
        adapter_name = getattr(self, "platform_name", self.__class__.__name__)
        if error:
            logger.error(
                f"[Reconnect] {adapter_name} 重连失败: "
                f"{type(error).__name__}: {error}"
            )
        else:
            logger.info(f"[Reconnect] {adapter_name} 重连已取消")

    def _schedule_reconnect(self) -> None:
        """调度重连任务。

        如果已有重连任务在运行，则忽略本次调度。
        """
        if self._reconnect_task is not None and not self._reconnect_task.done():
            logger.debug("[Reconnect] 重连任务已在运行，跳过调度")
            return

        self._reconnect_state = ReconnectState.WAITING
        self._reconnect_attempt = 0
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())
        adapter_name = getattr(self, "platform_name", self.__class__.__name__)
        logger.info(f"[Reconnect] {adapter_name} 已调度重连任务")

    async def _cancel_reconnect(self) -> None:
        """取消正在进行的或等待中的重连任务。"""
        self._reconnect_state = ReconnectState.STOPPED
        if self._reconnect_task is not None and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
            self._reconnect_task = None
        self._on_reconnect_failed(error=None)

    async def _reconnect_loop(self) -> None:
        """异步重连循环。

        按照 ReconnectStrategy 配置进行指数退避重试，
        直到连接成功、达到最大尝试次数或被取消。
        """
        strategy = self._reconnect_strategy
        adapter_name = getattr(self, "platform_name", self.__class__.__name__)
        delay = strategy.initial_delay

        try:
            while True:
                # 检查是否达到最大尝试次数
                if strategy.max_attempts > 0 and self._reconnect_attempt >= strategy.max_attempts:
                    logger.error(
                        f"[Reconnect] {adapter_name} 已达最大重连次数 "
                        f"({strategy.max_attempts})，停止重连"
                    )
                    self._reconnect_state = ReconnectState.IDLE
                    self._on_reconnect_failed(
                        error=RuntimeError(
                            f"Max reconnect attempts ({strategy.max_attempts}) reached"
                        )
                    )
                    return

                self._reconnect_attempt += 1
                self._reconnect_state = ReconnectState.CONNECTING

                # 添加抖动
                jitter_value = (
                    random.uniform(0, strategy.jitter) if strategy.jitter > 0 else 0.0
                )
                actual_delay = min(delay, strategy.max_delay) + jitter_value

                logger.info(
                    f"[Reconnect] {adapter_name} 第 {self._reconnect_attempt} 次重连，"
                    f"等待 {actual_delay:.2f}s..."
                )
                await asyncio.sleep(actual_delay)

                try:
                    success = await self._do_reconnect()
                    if success:
                        self._reconnect_count += 1
                        self._reconnect_state = ReconnectState.IDLE
                        self._reconnect_attempt = 0
                        self._on_reconnect_success()
                        return
                    else:
                        logger.warning(
                            f"[Reconnect] {adapter_name} 第 {self._reconnect_attempt} "
                            f"次重连返回失败"
                        )
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.warning(
                        f"[Reconnect] {adapter_name} 第 {self._reconnect_attempt} "
                        f"次重连异常: {type(e).__name__}: {e}"
                    )

                # 指数退避
                delay = min(delay * strategy.multiplier, strategy.max_delay)

        except asyncio.CancelledError:
            self._reconnect_state = ReconnectState.STOPPED
            logger.debug(f"[Reconnect] {adapter_name} 重连任务已取消")

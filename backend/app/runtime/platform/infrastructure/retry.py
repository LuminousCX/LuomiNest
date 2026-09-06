"""指数退避重试器（tenacity 执行层）。

为异步操作提供可配置的重试机制，支持指数退避、抖动、
可重试异常区分以及自定义重试回调。对外接口（RetryConfig /
async_retry / RetryCallback）与延迟公式不变，重试调度由 tenacity 承担。
"""

from __future__ import annotations

import asyncio
import functools
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from loguru import logger
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])

# 重试回调签名: (attempt: int, exception: Exception, delay: float) -> Any
RetryCallback = Callable[[int, Exception, float], Any]


@dataclass
class RetryConfig:
    """重试配置。

    Attributes:
        max_retries: 最大重试次数，0 表示不重试。
        base_delay: 基础延迟（秒），实际延迟 = base_delay * 2^(attempt-1)。
        max_delay: 单次重试的最大延迟（秒）。
        jitter: 随机抖动上限（秒），避免雷群效应。
        retryable_exceptions: 可重试的异常类型列表，其他异常会直接抛出。
    """

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    jitter: float = 1.0
    retryable_exceptions: tuple[type[BaseException], ...] = (Exception,)


def _calculate_delay(config: RetryConfig, attempt: int) -> float:
    """计算第 attempt 次重试的等待时间。

    公式: min(base_delay * 2^(attempt-1), max_delay) + random(0, jitter)
    """
    exponential = config.base_delay * (2 ** (attempt - 1))
    capped = min(exponential, config.max_delay)
    jitter_value = random.uniform(0, config.jitter) if config.jitter > 0 else 0.0
    return capped + jitter_value


def async_retry(
    func: Callable[..., Awaitable[Any]] | None = None,
    *,
    config: RetryConfig | None = None,
    on_retry: RetryCallback | None = None,
) -> Any:
    """带指数退避的异步重试执行器。

    可作为装饰器或直接调用：
    ``@async_retry(config=RetryConfig(max_retries=5))`` 装饰异步函数，
    或 ``await async_retry(fn, config=RetryConfig())`` 直接执行。

    Args:
        func: 要执行的异步函数。
        config: 重试配置，为 None 时使用默认配置。
        on_retry: 每次重试前的回调，签名 (attempt, exception, delay)，支持同步或异步。

    Returns:
        被装饰函数的返回值。

    Raises:
        最后一次重试的异常（如果所有重试都失败）。
    """
    if config is None:
        config = RetryConfig()

    if func is None:
        # 装饰器模式，返回包装函数
        def decorator(f: F) -> F:
            @functools.wraps(f)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                return await _execute_with_retry(f, args, kwargs, config, on_retry)
            return wrapper  # type: ignore[return-value]
        return decorator

    # 直接调用模式，返回可等待对象
    return _execute_with_retry(func, (), {}, config, on_retry)


async def _execute_with_retry(
    func: Callable[..., Awaitable[Any]],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    config: RetryConfig,
    on_retry: RetryCallback | None,
) -> Any:
    """核心重试执行逻辑（tenacity AsyncRetrying）。"""
    # tenacity 的 before_sleep 钩子是同步的；异步 on_retry 回调先挂起到
    # pending，由自定义 sleep 在真正睡眠前 await，保持"回调→睡眠"的原顺序。
    pending: Awaitable[Any] | None = None

    def _before_sleep(retry_state: Any) -> None:
        nonlocal pending
        exc = retry_state.outcome.exception()
        delay = retry_state.next_action.sleep
        attempt = retry_state.attempt_number
        logger.warning(
            f"[Retry] {func.__qualname__} 第 {attempt}/{config.max_retries} "
            f"次重试，{delay:.2f}s 后重试 | 异常: {type(exc).__name__}: {exc}"
        )
        if on_retry is not None:
            try:
                result = on_retry(attempt, exc, delay)
                if asyncio.iscoroutine(result):
                    pending = result
            except Exception as cb_err:
                logger.error(f"[Retry] on_retry 回调执行失败: {cb_err}")

    async def _sleep_with_callback(seconds: float) -> None:
        nonlocal pending
        if pending is not None:
            callback, pending = pending, None
            try:
                await callback
            except Exception as cb_err:
                logger.error(f"[Retry] on_retry 回调执行失败: {cb_err}")
        await asyncio.sleep(seconds)

    retrying = AsyncRetrying(
        stop=stop_after_attempt(config.max_retries + 1),
        wait=lambda rs: _calculate_delay(config, rs.attempt_number),
        retry=retry_if_exception_type(config.retryable_exceptions),
        reraise=True,
        before_sleep=_before_sleep,
        sleep=_sleep_with_callback,
    )

    try:
        async for attempt_state in retrying:
            with attempt_state:
                return await func(*args, **kwargs)
    except config.retryable_exceptions:
        logger.error(
            f"[Retry] {func.__qualname__} 已达最大重试次数 "
            f"({config.max_retries})，放弃重试"
        )
        raise

    # 显式兜底，避免隐式返回 None（满足静态分析规则）
    raise RuntimeError("Unexpected retry flow: no result returned and no exception captured")

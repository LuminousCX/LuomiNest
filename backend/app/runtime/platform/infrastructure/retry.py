"""指数退避重试器。

为异步操作提供可配置的重试机制，支持指数退避、抖动、
可重试异常区分以及自定义重试回调。
"""

from __future__ import annotations

import asyncio
import functools
import random
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, TypeVar

from loguru import logger

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

    .. code-block:: python

        # 装饰器用法
        @async_retry(config=RetryConfig(max_retries=5))
        async def fetch_data():
            ...

        # 直接调用
        result = await async_retry(some_func, config=RetryConfig())

    Args:
        func: 要执行的异步函数。
        config: 重试配置，为 None 时使用默认配置。
        on_retry: 每次重试前的回调，签名 (attempt, exception, delay)。

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
    """核心重试执行逻辑。"""
    last_exception: Exception | None = None

    for attempt in range(config.max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except config.retryable_exceptions as e:
            last_exception = e
            if attempt >= config.max_retries:
                logger.error(
                    f"[Retry] {func.__qualname__} 已达最大重试次数 "
                    f"({config.max_retries})，放弃重试"
                )
                raise

            delay = _calculate_delay(config, attempt + 1)
            logger.warning(
                f"[Retry] {func.__qualname__} 第 {attempt + 1}/{config.max_retries} "
                f"次重试，{delay:.2f}s 后重试 | 异常: {type(e).__name__}: {e}"
            )

            if on_retry is not None:
                try:
                    result = on_retry(attempt + 1, e, delay)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as cb_err:
                    logger.error(f"[Retry] on_retry 回调执行失败: {cb_err}")

            await asyncio.sleep(delay)
        except BaseException:
            # 不可重试的异常直接抛出
            raise

    # 理论上不会到这里，但保险起见
    if last_exception is not None:
        raise last_exception

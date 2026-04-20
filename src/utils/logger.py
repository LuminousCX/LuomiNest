"""LuomiNest 统一日志系统。

基于 loguru 实现结构化日志，支持：
- 按级别输出到不同文件
- 上下文携带（trace_id、user_id 等）
- 控制台彩色输出
- 日志文件自动轮转与保留
"""

from __future__ import annotations

import sys
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from loguru import logger

_TRACE_ID: ContextVar[str] = ContextVar("trace_id", default="")
_USER_ID: ContextVar[str] = ContextVar("user_id", default="")

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "{extra[trace_id]} | "
    "{extra[user_id]} | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
)

_PLAIN_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
    "{level: <8} | "
    "{extra[trace_id]} | "
    "{extra[user_id]} | "
    "{name}:{function}:{line} | "
    "{message}"
)


def _contextualize(record: dict[str, Any]) -> None:
    """为日志记录注入上下文变量。"""
    record["extra"]["trace_id"] = _TRACE_ID.get("")
    record["extra"]["user_id"] = _USER_ID.get("")


def set_trace_id(trace_id: str) -> None:
    """设置当前请求的 trace_id。"""
    _TRACE_ID.set(trace_id)


def set_user_id(user_id: str) -> None:
    """设置当前请求的 user_id。"""
    _USER_ID.set(user_id)


def get_trace_id() -> str:
    """获取当前 trace_id。"""
    return _TRACE_ID.get("")


def get_user_id() -> str:
    """获取当前 user_id。"""
    return _USER_ID.get("")


def setup_logger(level: str = "INFO") -> None:
    """初始化日志配置。

    Args:
        level: 最低日志级别，默认 INFO。
    """
    logger.remove()

    logger.configure(patcher=_contextualize)

    logger.add(
        sys.stderr,
        format=_FORMAT,
        level=level,
        colorize=True,
    )

    logger.add(
        str(LOG_DIR / "luminest.log"),
        format=_PLAIN_FORMAT,
        level=level,
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
    )

    logger.add(
        str(LOG_DIR / "luminest_error.log"),
        format=_PLAIN_FORMAT,
        level="ERROR",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
    )


def get_logger() -> logger.__class__:
    """获取全局 logger 实例。"""
    return logger


setup_logger()

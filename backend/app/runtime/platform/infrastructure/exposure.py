"""非 loopback 监听暴露告警（P0-3 传输安全）。

集中实现"监听地址非 loopback → 启动 WARNING"的判定与文案，供：
- main.py：主服务监听告警（/api、/mcp、平台 Webhook 等同端口暴露）
- qq_onebot：反向 WS 绑定非 loopback 且未配 access_token
- rest_api / websocket：主服务非 loopback 且实例未配 api_key/access_token

只告警不打断运行；loopback 判定宽容匹配 127.0.0.0/8、localhost、::1。
"""
from __future__ import annotations

import os

from loguru import logger

# main.py 启动 uvicorn 前把 --host 写入该环境变量，
# 供适配器/lifespan 在不感知 argv 的情况下读取当前监听地址。
LISTEN_HOST_ENV = "LUOMINEST_LISTEN_HOST"

_LOOPBACK_EXACT = {"", "localhost", "::1"}


def is_loopback_host(host: str | None) -> bool:
    """判断监听地址是否仅本机可达（127.0.0.0/8、localhost、::1、空串）。"""
    h = (host or "").strip().lower()
    if h in _LOOPBACK_EXACT:
        return True
    return h.startswith("127.")


def get_backend_listen_host() -> str:
    """读取主服务监听地址（main.py 写入 env；未写入时按默认 127.0.0.1 处理）。"""
    return os.environ.get(LISTEN_HOST_ENV, "127.0.0.1")


def warn_lan_exposure(host: str) -> None:
    """主服务监听非 loopback 时的醒目启动告警（多行、不打断运行）。"""
    if is_loopback_host(host):
        return
    logger.warning("=" * 60)
    logger.warning(f"  ⚠ 安全告警：后端监听地址为 {host}，非 loopback")
    logger.warning("  /api、/mcp、平台 Webhook、内嵌 MQTT 等端口已暴露到局域网/外网：")
    logger.warning("  - /mcp：请确认为开启 Bearer 鉴权状态（MCP_SERVER_AUTH），")
    logger.warning("    token 在设置页查看，泄漏可用 POST /api/v1/mcp/token/reset 重置")
    logger.warning("  - QQ 反向 WS：请为实例配置 access_token，否则任何局域网进程可注入消息")
    logger.warning("  - REST API / 通用 WS 接入：请为实例配置 api_key / access_token")
    logger.warning("  建议改用 127.0.0.1 监听 + 反向代理对外暴露（HTTPS）。")
    logger.warning("=" * 60)


def warn_inbound_without_credential(component: str, host: str, credential_hint: str) -> None:
    """组件入站面在非 loopback 环境且未配置凭证时的启动告警（单行）。"""
    if is_loopback_host(host):
        return
    logger.warning(
        f"[P0-3 安全告警] {component} 暴露在非 loopback 地址 {host}，"
        f"且未配置 {credential_hint}，任何局域网进程均可接入；"
        f"请在实例配置中设置后再对外使用。"
    )

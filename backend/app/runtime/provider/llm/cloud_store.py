"""云路由令牌存储（M4 云路由）。

仅内存保存桌面端（Electron main）运行时注入的云端接入信息：
- accessToken：上游访问令牌（会周期性轮换，每次注入覆盖旧值）
- cloudBaseUrl：云端网关根地址（只来自运行时注入，进程内不落盘、不入库、不打日志全文）
- routingMode：路由开关（off=全部走本地 provider；all=chat 类调用统一走云端网关）

生命周期：进程重启即清空，由桌面端在每次启动/令牌续期后重新注入（PUT /api/v1/cloud/token）。

线程安全：LLMAdapter 的调用方横跨多线程/多协程（25+ 调用点），
用 threading.Lock 保证读写原子性与快照一致性。
"""
from __future__ import annotations

import threading


class CloudTokenStore:
    """云路由令牌存储（线程安全，仅内存）。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._access_token: str = ""
        self._cloud_base_url: str = ""
        self._routing_mode: str = "off"

    def set(self, access_token: str, cloud_base_url: str, routing_mode: str = "off") -> None:
        """注入/覆盖云端接入信息（由桌面端在授权与每次令牌续期后调用）。"""
        with self._lock:
            self._access_token = access_token or ""
            self._cloud_base_url = (cloud_base_url or "").rstrip("/")
            self._routing_mode = routing_mode if routing_mode in ("off", "all") else "off"

    def clear(self) -> None:
        """清空（退出登录 / 令牌失效时由桌面端触发）。"""
        with self._lock:
            self._access_token = ""
            self._cloud_base_url = ""
            self._routing_mode = "off"

    def get(self) -> dict[str, str]:
        """返回当前快照（单次加锁，保证三个字段相互一致）。"""
        with self._lock:
            return {
                "accessToken": self._access_token,
                "cloudBaseUrl": self._cloud_base_url,
                "routingMode": self._routing_mode,
            }

    @property
    def configured(self) -> bool:
        """是否已注入有效配置（令牌与网关地址齐备才算）。"""
        with self._lock:
            return bool(self._access_token and self._cloud_base_url)


# 模块级单例：API 注入端点（endpoints/cloud.py）、CloudProxyProvider 与
# LLMAdapter 路由钩子三方共享同一份内存态。
cloud_token_store = CloudTokenStore()

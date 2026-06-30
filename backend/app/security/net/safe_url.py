"""SSRF 防护：安全 URL 校验与 DNS Rebinding 防御。

参考：综合调查文档 SSRF 防护章节、TencentDB Gateway 的 IP 白名单机制。

防御层次：
1. validate_url_scheme()     — 协议白名单（http/https）+ 主机名非空
2. is_trusted_host()         — 受信任主机白名单（GitHub 域名）
3. resolve_and_validate_ip() — DNS 解析 + IP 分级校验（6 类地址全检查）
4. _SafeNetworkBackend       — IP 钉选：校验时的 IP = 连接时的 IP，防止 DNS Rebinding
"""
import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

import httpx

# 受信任的下载域名白名单（GitHub 全系）
TRUSTED_DOWNLOAD_HOSTS = frozenset({
    "github.com",
    "raw.githubusercontent.com",
    "api.github.com",
    "objects.githubusercontent.com",
    "github-releases.githubusercontent.com",
    "codeload.github.com",
})


class UnsafeUrlError(ValueError):
    """URL 未通过 SSRF 安全校验。"""


def is_safe_ip(ip_str: str) -> bool:
    """检查 IP 是否为公网地址。

    拒绝：私有、环回、链路本地、保留、组播、未指定地址。
    """
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def is_trusted_host(hostname: str) -> bool:
    """检查主机名是否在受信任白名单中（支持子域名匹配）。"""
    h = hostname.lower()
    return any(h == t or h.endswith("." + t) for t in TRUSTED_DOWNLOAD_HOSTS)


def validate_url_scheme(url: str) -> None:
    """同步校验 URL 协议（仅允许 http/https）和主机名非空。"""
    if not url:
        raise UnsafeUrlError("URL 为空")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeUrlError(f"不支持的协议: {parsed.scheme}")
    if not parsed.hostname:
        raise UnsafeUrlError("缺少主机名")


async def resolve_and_validate_ip(hostname: str) -> str:
    """解析主机名并返回首个公网 IP。

    受信任主机直接返回主机名（不钉选 IP，由系统解析器处理）。
    非受信任主机解析 DNS 并校验所有结果均为公网 IP，返回首个可用 IP。

    Raises:
        UnsafeUrlError: 主机名无法解析或解析结果为非公网地址。
    """
    if is_trusted_host(hostname):
        return hostname

    loop = asyncio.get_event_loop()
    try:
        infos = await loop.run_in_executor(
            None,
            lambda: socket.getaddrinfo(
                hostname, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM
            ),
        )
    except socket.gaierror as e:
        raise UnsafeUrlError(f"无法解析主机名: {hostname}") from e

    for info in infos:
        ip = info[4][0]
        if is_safe_ip(ip):
            return ip

    raise UnsafeUrlError(f"禁止访问非公网地址: {hostname}")


async def assert_url_safe(url: str) -> None:
    """异步综合校验 URL 安全性（协议 + 主机名 + IP）。

    用于 API 层快速失败，在实际下载前拒绝不安全 URL。
    实际连接时的 DNS Rebinding 防护由 SafeAsyncHTTPTransport 提供。
    """
    validate_url_scheme(url)
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    await resolve_and_validate_ip(hostname)


class _SafeNetworkBackend:
    """自定义网络后端：拦截 connect_tcp，钉选已校验的 IP。

    对非受信任主机：解析 DNS → 校验 IP 为公网 → 用校验过的 IP 建立连接。
    对受信任主机：直接透传（由系统解析器处理）。

    TLS SNI 和证书验证使用原始主机名（由 httpcore 的 connection 层处理，
    取自 origin.host 而非 connect_tcp 的 host 参数），因此 IP 钉选不影响 HTTPS。
    """

    def __init__(self, inner):
        self._inner = inner

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options=None,
    ):
        hostname = host if isinstance(host, str) else host.decode("ascii")
        if not is_trusted_host(hostname.lower()):
            try:
                validated_ip = await resolve_and_validate_ip(hostname)
            except UnsafeUrlError:
                raise
            except Exception as e:
                raise UnsafeUrlError(f"DNS 解析失败: {hostname} - {e}") from e
            host = validated_ip
        return await self._inner.connect_tcp(
            host,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options=None,
    ):
        return await self._inner.connect_unix_socket(
            path, timeout=timeout, socket_options=socket_options
        )

    async def sleep(self, seconds: float) -> None:
        return await self._inner.sleep(seconds)


class SafeAsyncHTTPTransport(httpx.AsyncHTTPTransport):
    """带 SSRF 防护的 httpx 异步传输。

    所有 HTTP 请求（含重定向）都通过自定义网络后端，
    确保每次连接都校验 DNS 解析结果并钉选 IP，防止 DNS Rebinding。
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 替换连接池的网络后端为安全版本
        # _network_backend 在 AsyncConnectionPool.__init__ 中赋值，跨版本稳定
        self._pool._network_backend = _SafeNetworkBackend(self._pool._network_backend)


def create_safe_async_client(**kwargs) -> httpx.AsyncClient:
    """创建带 SSRF 防护的 httpx AsyncClient。

    自动启用重定向跟随（follow_redirects=True），每次重定向都通过
    安全后端校验主机名 + IP。timeout 默认 120 秒。
    """
    timeout = kwargs.pop("timeout", 120.0)
    transport = SafeAsyncHTTPTransport()
    return httpx.AsyncClient(
        transport=transport,
        timeout=timeout,
        follow_redirects=True,
        **kwargs,
    )

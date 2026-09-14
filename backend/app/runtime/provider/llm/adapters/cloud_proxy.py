"""CloudProxyProvider — 云端网关代理 Provider（M4 云路由）。

继承 OpenAICompatibleProvider，复用其 chat / chat_stream（SSE）/ payload 构建 /
消息清洗管道，仅做最小侵入覆写：

1. base_url：动态属性，实时取 CloudTokenStore 注入的 cloudBaseUrl 拼接
   ``{cloudBaseUrl}/api/v1/llm``（网关地址可被重新注入，绝不固化）
2. _build_headers：每请求实时取最新 accessToken 构造 ``Authorization: Bearer`` 头
   （令牌会周期性轮换，绝不能在创建时固化）+ ``X-LMC-Request-Id: <uuid4>``
   （云端幂等扣减键）
3. embed：云端模式暂不支持向量接口，抛业务异常（embed 路由不接入云网关）

错误透传：通过 httpx response event hook 在收到响应头即检查状态码（流式/非流式
统一生效），>=400 时趁响应流未关闭读取错误响应体，解析 errCode/message 后抛
ProviderError；errCode 以 ``err_code`` 结构化字段随异常冒泡（chat_service /
AgentRunner 各错误出口透传给前端，前端按 errCode 映射本地化文案）。异常 message
有意不含 429 / rate_limit 等可重试关键词：
额度耗尽（QUOTA_EXCEEDED）是确定性错误，重试只会重复触发计费预检。

隐私纪律：本模块不含任何生产端点/域名/密钥；cloudBaseUrl 只来自运行时注入。
"""
from __future__ import annotations

import json
import threading
import uuid

import httpx
from loguru import logger

from app.core.exceptions import ProviderError
from app.runtime.provider.llm.adapters.chat_completions import OpenAICompatibleProvider
from app.runtime.provider.llm.cloud_store import CloudTokenStore, cloud_token_store

# 云网关在 cloudBaseUrl 下的 LLM 代理路径前缀（协议路径，非具体端点信息）
_CLOUD_LLM_PATH_PREFIX = "/api/v1/llm"


def _extract_error_fields(body_text: str) -> tuple[str, str]:
    """从云端网关错误响应体中尽力解析 (errCode, message)。

    兼容三种信封：从站失败信封 ``{"code": <数字>, "errCode": "XXX", "message": ...}``、
    ``{"errCode": ..., "message": ...}`` 与 ``{"error": {"code": ..., "message": ...}}``；
    解析失败返回空串（由调用方回退 HTTP 状态描述）。
    """
    err_code = ""
    message = ""
    try:
        data = json.loads(body_text) if body_text else {}
    except (json.JSONDecodeError, ValueError):
        return "", ""
    if not isinstance(data, dict):
        return "", ""
    err_code = str(data.get("errCode") or data.get("code") or "")
    err_obj = data.get("error")
    if isinstance(err_obj, dict):
        err_code = err_code or str(err_obj.get("code") or "")
        message = message or str(err_obj.get("message") or "")
    message = message or str(data.get("message") or "")
    return err_code, message


class CloudProxyProvider(OpenAICompatibleProvider):
    """云端网关代理 Provider：chat 类调用经本机转发到注入的云端网关。

    共享单例（get_cloud_proxy_provider）：adapter 路由钩子把所有 chat /
    chat_stream 调用换到同一实例，token 与 base_url 均每请求实时解析。
    """

    provider_name = "cloud_proxy"

    def __init__(self, store: CloudTokenStore | None = None):
        # api_key 留空：鉴权头在 _build_headers 中每请求实时构造
        super().__init__(
            api_key="",
            base_url="",  # 实际值由 base_url 动态属性提供
            default_model="",  # 模型由请求体决定（路由钩子在原 provider 解析 model 之后换入）
            provider_name="cloud_proxy",
        )
        self._store = store or cloud_token_store
        # 预建连接池客户端并挂错误透传 hook（ProviderClientMixin.client 会直接复用本实例）
        self._client = httpx.AsyncClient(
            timeout=120.0,
            event_hooks={"response": [self._raise_for_cloud_error]},
        )

    # ── 动态 base_url：实时跟随 CloudTokenStore ──────────────────────────────

    @property
    def base_url(self) -> str:  # type: ignore[override]
        base = self._store.get()["cloudBaseUrl"].rstrip("/")
        if not base:
            raise ProviderError(
                "云端网关地址未注入，无法走云端路由",
                provider=self.provider_name,
                code="CLOUD_TOKEN_MISSING",
                status_code=401,
            )
        return f"{base}{_CLOUD_LLM_PATH_PREFIX}"

    @base_url.setter
    def base_url(self, value: str) -> None:
        # 仅兼容父类 __init__ 的赋值语句；真实地址始终实时取自 CloudTokenStore
        _ = value

    # ── 每请求实时鉴权头 ──────────────────────────────────────────────────────

    def _build_headers(self) -> dict[str, str]:
        token = self._store.get()["accessToken"]
        if not token:
            raise ProviderError(
                "云端访问令牌未注入或已失效，无法走云端路由",
                provider=self.provider_name,
                code="CLOUD_TOKEN_MISSING",
                status_code=401,
            )
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "X-LMC-Request-Id": str(uuid.uuid4()),
        }

    # ── 向量接口不接入云网关 ──────────────────────────────────────────────────

    async def embed(self, text: str) -> list[float]:
        raise ProviderError(
            "云端模式暂不支持向量接口（embed）",
            provider=self.provider_name,
            code="CLOUD_EMBED_UNSUPPORTED",
            status_code=400,
        )

    # ── 错误透传：响应头到达即检查，趁流未关闭读取错误体 ────────────────────

    async def _raise_for_cloud_error(self, response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        try:
            await response.aread()  # 此刻响应流仍打开，读入错误体供解析
            body_text = response.text
        except Exception:  # noqa: BLE001 —— 读取失败时回退状态码描述
            body_text = ""
        err_code, message = _extract_error_fields(body_text)
        status_desc = response.reason_phrase or "gateway error"
        detail = message or status_desc
        prefix = f"[errCode={err_code}] " if err_code else ""
        # 注意：message 有意不含 429/rate_limit 等可重试关键词（避免确定性错误被重试）
        raise ProviderError(
            f"云端调用失败 {prefix}{detail}",
            provider=self.provider_name,
            code="CLOUD_UPSTREAM_ERROR",
            status_code=response.status_code,
            err_code=err_code or None,
        )


# ── 懒建共享单例（adapter 路由钩子调用；进程内所有云路由请求共用一个连接池）──

_cloud_proxy_singleton: CloudProxyProvider | None = None
_cloud_proxy_singleton_lock = threading.Lock()


def get_cloud_proxy_provider(store: CloudTokenStore | None = None) -> CloudProxyProvider:
    """返回共享 CloudProxyProvider 实例（懒建单例，线程安全）。"""
    global _cloud_proxy_singleton
    if _cloud_proxy_singleton is None:
        with _cloud_proxy_singleton_lock:
            if _cloud_proxy_singleton is None:
                _cloud_proxy_singleton = CloudProxyProvider(store)
                logger.info("[Provider] CloudProxyProvider singleton created (cloud routing active)")
    return _cloud_proxy_singleton

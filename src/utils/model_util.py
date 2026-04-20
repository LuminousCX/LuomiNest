"""大模型调用工具类。

封装 OpenAI 兼容接口的调用逻辑，提供：
- 统一的客户端管理
- 专家模式/快速模式配置
- 流式/非流式调用
- Token 统计
- 异常处理与重试
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncGenerator, Optional

from openai import APIConnectionError, APIError, APITimeoutError, AsyncOpenAI, RateLimitError
from pydantic import BaseModel

from src.config.settings import get_settings
from src.exceptions import ModelCallError, ModelRateLimitError, ModelTimeoutError
from src.utils.logger import get_logger

logger = get_logger()


class ResponseMode(str, Enum):
    """响应模式。"""

    EXPERT = "expert"
    FAST = "fast"


@dataclass
class ModeConfig:
    """模式配置。"""

    temperature: float
    max_tokens: int
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0


MODE_CONFIGS: dict[ResponseMode, ModeConfig] = {
    ResponseMode.EXPERT: ModeConfig(
        temperature=0.3,
        max_tokens=4096,
        top_p=0.95,
    ),
    ResponseMode.FAST: ModeConfig(
        temperature=0.7,
        max_tokens=1024,
        top_p=0.9,
    ),
}


class ModelResponse(BaseModel):
    """模型响应结果。"""

    content: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = ""
    finish_reason: str = ""


class StreamChunk(BaseModel):
    """流式响应片段。"""

    content: str = ""
    finish_reason: Optional[str] = None


class ModelUtil:
    """大模型调用工具类。

    封装 OpenAI 兼容接口的调用逻辑。

    Attributes:
        client: OpenAI 异步客户端。
        model_id: 模型 ID。
    """

    def __init__(self) -> None:
        """初始化模型工具类。"""
        self._client: Optional[AsyncOpenAI] = None
        self._model_id: Optional[str] = None

    @property
    def client(self) -> AsyncOpenAI:
        """获取 OpenAI 异步客户端（懒加载）。"""
        if self._client is None:
            settings = get_settings()
            self._client = AsyncOpenAI(
                api_key=settings.llm_api_key.get_secret_value(),
                base_url=settings.llm_base_url,
                max_retries=settings.llm_max_retries,
                timeout=settings.llm_timeout,
            )
            self._model_id = settings.llm_model_id
            logger.info(f"ModelUtil 客户端初始化完成: base_url={settings.llm_base_url}")
        return self._client

    @property
    def model_id(self) -> str:
        """获取模型 ID。"""
        if self._model_id is None:
            settings = get_settings()
            self._model_id = settings.llm_model_id
        return self._model_id

    def get_mode_config(self, mode: ResponseMode) -> ModeConfig:
        """获取模式配置。

        优先使用配置文件中的设置，否则使用默认值。

        Args:
            mode: 响应模式。

        Returns:
            模式配置。
        """
        settings = get_settings()

        if mode == ResponseMode.EXPERT:
            return ModeConfig(
                temperature=settings.llm_expert_temperature,
                max_tokens=settings.llm_expert_max_tokens,
                top_p=settings.llm_expert_top_p,
                frequency_penalty=settings.llm_frequency_penalty,
                presence_penalty=settings.llm_presence_penalty,
            )
        else:
            return ModeConfig(
                temperature=settings.llm_fast_temperature,
                max_tokens=settings.llm_fast_max_tokens,
                top_p=settings.llm_fast_top_p,
                frequency_penalty=settings.llm_frequency_penalty,
                presence_penalty=settings.llm_presence_penalty,
            )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        mode: ResponseMode = ResponseMode.FAST,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        extra_params: Optional[dict[str, Any]] = None,
    ) -> ModelResponse:
        """非流式对话调用。

        Args:
            messages: OpenAI 格式消息列表。
            mode: 响应模式。
            temperature: 自定义温度（覆盖模式配置）。
            max_tokens: 自定义最大 token（覆盖模式配置）。
            extra_params: 额外的 API 参数。

        Returns:
            模型响应结果。

        Raises:
            ModelTimeoutError: 请求超时。
            ModelRateLimitError: 请求频率限制。
            ModelCallError: 其他调用错误。
        """
        mode_config = self.get_mode_config(mode)

        params = {
            "model": self.model_id,
            "messages": messages,
            "temperature": temperature if temperature is not None else mode_config.temperature,
            "max_tokens": max_tokens if max_tokens is not None else mode_config.max_tokens,
            "top_p": mode_config.top_p,
            "frequency_penalty": mode_config.frequency_penalty,
            "presence_penalty": mode_config.presence_penalty,
            "stream": False,
        }

        if extra_params:
            params.update(extra_params)

        logger.debug(f"模型调用参数: model={params['model']}, temperature={params['temperature']:.2f}")

        try:
            response = await self.client.chat.completions.create(**params)

            content = response.choices[0].message.content or ""
            prompt_tokens = response.usage.prompt_tokens if response.usage else 0
            completion_tokens = response.usage.completion_tokens if response.usage else 0
            total_tokens = response.usage.total_tokens if response.usage else 0
            finish_reason = response.choices[0].finish_reason or ""

            logger.info(
                f"模型调用成功: prompt_tokens={prompt_tokens}, "
                f"completion_tokens={completion_tokens}, total_tokens={total_tokens}"
            )

            return ModelResponse(
                content=content,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                model=response.model,
                finish_reason=finish_reason,
            )

        except APITimeoutError as e:
            logger.error(f"模型调用超时: {e}")
            raise ModelTimeoutError(detail={"message": "请求超时，请稍后重试"}) from e

        except RateLimitError as e:
            logger.error(f"请求频率限制: {e}")
            raise ModelRateLimitError(detail={"message": "请求过于频繁，请稍后重试"}) from e

        except APIConnectionError as e:
            logger.error(f"网络连接错误: {e}")
            raise ModelCallError(message=f"网络连接错误: {e}") from e

        except APIError as e:
            logger.error(f"API 错误: {e}")
            raise ModelCallError(message=f"API 错误: {e}") from e

        except Exception as e:
            logger.error(f"模型调用失败: {e}")
            raise ModelCallError(message=f"模型调用失败: {e}") from e

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        mode: ResponseMode = ResponseMode.FAST,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        extra_params: Optional[dict[str, Any]] = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """流式对话调用。

        Args:
            messages: OpenAI 格式消息列表。
            mode: 响应模式。
            temperature: 自定义温度。
            max_tokens: 自定义最大 token。
            extra_params: 额外的 API 参数。

        Yields:
            流式响应片段。

        Raises:
            ModelTimeoutError: 请求超时。
            ModelCallError: 其他调用错误。
        """
        mode_config = self.get_mode_config(mode)

        params = {
            "model": self.model_id,
            "messages": messages,
            "temperature": temperature if temperature is not None else mode_config.temperature,
            "max_tokens": max_tokens if max_tokens is not None else mode_config.max_tokens,
            "top_p": mode_config.top_p,
            "frequency_penalty": mode_config.frequency_penalty,
            "presence_penalty": mode_config.presence_penalty,
            "stream": True,
        }

        if extra_params:
            params.update(extra_params)

        logger.debug(f"流式模型调用参数: model={params['model']}, temperature={params['temperature']:.2f}")

        try:
            stream = await self.client.chat.completions.create(**params)

            async for chunk in stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    finish_reason = chunk.choices[0].finish_reason

                    if delta.content:
                        yield StreamChunk(content=delta.content)

                    if finish_reason:
                        yield StreamChunk(content="", finish_reason=finish_reason)

        except APITimeoutError as e:
            logger.error(f"流式调用超时: {e}")
            raise ModelTimeoutError(detail={"message": "请求超时，请稍后重试"}) from e

        except RateLimitError as e:
            logger.error(f"请求频率限制: {e}")
            raise ModelRateLimitError(detail={"message": "请求过于频繁，请稍后重试"}) from e

        except APIConnectionError as e:
            logger.error(f"网络连接错误: {e}")
            raise ModelCallError(message=f"网络连接错误: {e}") from e

        except APIError as e:
            logger.error(f"API 错误: {e}")
            raise ModelCallError(message=f"API 错误: {e}") from e

        except Exception as e:
            logger.error(f"流式调用失败: {e}")
            raise ModelCallError(message=f"流式调用失败: {e}") from e

    async def collect_stream(
        self,
        messages: list[dict[str, Any]],
        mode: ResponseMode = ResponseMode.FAST,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        extra_params: Optional[dict[str, Any]] = None,
    ) -> str:
        """流式调用并收集完整响应。

        Args:
            messages: OpenAI 格式消息列表。
            mode: 响应模式。
            temperature: 自定义温度。
            max_tokens: 自定义最大 token。
            extra_params: 额外的 API 参数。

        Returns:
            完整的响应内容。
        """
        chunks: list[str] = []
        async for chunk in self.chat_stream(
            messages=messages,
            mode=mode,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_params=extra_params,
        ):
            chunks.append(chunk.content)
        return "".join(chunks)

    async def test_connection(self) -> bool:
        """测试模型连接是否正常。

        Returns:
            连接是否成功。
        """
        try:
            response = await self.chat(
                messages=[{"role": "user", "content": "Hello"}],
                mode=ResponseMode.FAST,
                max_tokens=10,
            )
            return bool(response.content)
        except Exception as e:
            logger.error(f"模型连接测试失败: {e}")
            return False


_model_util: Optional[ModelUtil] = None
_model_util_lock = threading.Lock()


def get_model_util() -> ModelUtil:
    """获取全局 ModelUtil 实例。"""
    global _model_util
    if _model_util is None:
        with _model_util_lock:
            if _model_util is None:
                _model_util = ModelUtil()
    return _model_util

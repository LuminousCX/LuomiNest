"""Token 估算与模型上下文窗口查询（从原 __init__.py 拆出）。"""

from loguru import logger

from app.core.context.constants import (
    DEFAULT_CONTEXT_WINDOW,
    IMAGE_TOKEN_ESTIMATE,
    TOKEN_WEIGHT_CHINESE,
    TOKEN_WEIGHT_OTHER,
)


class TokenCounter:
    def count_tokens(self, messages: list[dict], trusted_token_usage: int = 0) -> int:
        if trusted_token_usage > 0:
            return trusted_token_usage

        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += self._estimate_tokens(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict):
                        if part.get("type") == "text":
                            total += self._estimate_tokens(part.get("text", ""))
                        elif part.get("type") == "image_url":
                            total += IMAGE_TOKEN_ESTIMATE

            tool_calls = msg.get("tool_calls")
            if tool_calls:
                import json
                total += self._estimate_tokens(json.dumps(tool_calls, ensure_ascii=False))

        return total

    def count_messages(self, messages: list[dict]) -> int:
        """Alias for count_tokens without trusted usage — for clarity in budget checks."""
        return self.count_tokens(messages)

    def _estimate_tokens(self, text: str) -> int:
        chinese_count = len([c for c in text if "\u4e00" <= c <= "\u9fff"])
        other_count = len(text) - chinese_count
        return int(chinese_count * TOKEN_WEIGHT_CHINESE + other_count * TOKEN_WEIGHT_OTHER)

    def get_context_window_for_model(self, provider: str, model: str) -> int:
        """获取模型的上下文窗口大小。

        优先级：Provider能力表 > 配置值 > 默认16384
        """
        try:
            from app.runtime.provider.llm.capabilities import get_capabilities
            caps = get_capabilities(provider, model)
            if caps.default_context_window > 0:
                return caps.default_context_window
        except ImportError:
            # capabilities 模块不可用属可选依赖降级，静默回退到配置值
            pass
        except Exception:
            # 能力表查询自身的异常（KeyError/ValueError 等）不可吞掉，否则
            # 配置错误会被静默回退的默认窗口 16384 掩盖
            logger.warning(
                f"[Context] get_capabilities 查询异常，回退配置默认窗口: "
                f"provider={provider}, model={model}",
                exc_info=True,
            )

        from app.core.config import get_settings
        settings = get_settings()
        if settings.LLM_CONTEXT_WINDOW_SIZE > 0:
            return settings.LLM_CONTEXT_WINDOW_SIZE

        return DEFAULT_CONTEXT_WINDOW

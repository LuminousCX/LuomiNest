from app.runtime.pipeline.base import PipelineStage, StopPropagation
from app.runtime.context import PipelineContext, MessageRole
from loguru import logger


class WakeWordStage(PipelineStage):
    @property
    def name(self) -> str:
        return "wake_word"

    @property
    def order(self) -> int:
        return 1

    async def process(self, ctx: PipelineContext) -> PipelineContext:
        wake_words = ["小洛", "luomi", "罗米"]
        is_wake = any(ctx.raw_input.lower().startswith(ww.lower()) for ww in wake_words)
        if is_wake:
            ctx.raw_input = ctx.raw_input.strip()
            for ww in wake_words:
                if ctx.raw_input.lower().startswith(ww.lower()):
                    ctx.raw_input = ctx.raw_input[len(ww):].strip()
                    break
        logger.debug(f"Wake word detected: {is_wake}")
        return ctx


class AuthStage(PipelineStage):
    @property
    def name(self) -> str:
        return "authentication"

    @property
    def order(self) -> int:
        return 2

    async def process(self, ctx: PipelineContext) -> PipelineContext:
        token = ctx.extra.get("token", "")
        if token:
            try:
                from app.security.auth import verify_token
                user = await verify_token(token)
                if user and ctx.user_context:
                    ctx.user_context.user_id = user.id
                    ctx.user_context.permissions = user.permissions
            except (ImportError, Exception) as e:
                logger.debug(f"Auth verification skipped: {e}")
        return ctx


class RateLimitStage(PipelineStage):
    @property
    def name(self) -> str:
        return "rate_limit"

    @property
    def order(self) -> int:
        return 3

    async def process(self, ctx: PipelineContext) -> PipelineContext:
        return ctx


class SessionStage(PipelineStage):
    @property
    def name(self) -> str:
        return "session"

    @property
    def order(self) -> int:
        return 4

    async def process(self, ctx: PipelineContext) -> PipelineContext:
        ctx.add_message(MessageRole.USER, ctx.raw_input)
        return ctx


class ContextBuildStage(PipelineStage):
    @property
    def name(self) -> str:
        return "context_build"

    @property
    def order(self) -> int:
        return 5

    async def process(self, ctx: PipelineContext) -> PipelineContext:
        return ctx


class PreprocessStage(PipelineStage):
    @property
    def name(self) -> str:
        return "preprocess"

    @property
    def order(self) -> int:
        return 6

    async def process(self, ctx: PipelineContext) -> PipelineContext:
        return ctx


class AgentRouteStage(PipelineStage):
    @property
    def name(self) -> str:
        return "agent_route"

    @property
    def order(self) -> int:
        return 7

    async def process(self, ctx: PipelineContext) -> PipelineContext:
        try:
            from app.domains.intent_classifier import IntentClassifier
            classifier = IntentClassifier()
            ctx.intent = await classifier.classify(ctx.raw_input)
            ctx.matched_agent = classifier.select_agent(ctx.intent)
        except (ImportError, Exception) as e:
            logger.debug(f"Agent routing skipped: {e}")
            ctx.intent = "general"
        return ctx


class LLMInferenceStage(PipelineStage):
    @property
    def name(self) -> str:
        return "llm_inference"

    @property
    def order(self) -> int:
        return 8

    async def process(self, ctx: PipelineContext) -> PipelineContext:
        from app.runtime.provider.llm.adapter import LLMAdapter
        from app.runtime.context import AgentResult
        adapter = LLMAdapter()
        messages = [{"role": m.role.value, "content": m.content} for m in ctx.messages]
        response_text = await adapter.chat(messages)
        if ctx.agent_result is None:
            ctx.agent_result = AgentResult(text=response_text)
        else:
            ctx.agent_result.text = response_text
        return ctx


class ToolExecuteStage(PipelineStage):
    @property
    def name(self) -> str:
        return "tool_execute"

    @property
    def order(self) -> int:
        return 9

    async def process(self, ctx: PipelineContext) -> PipelineContext:
        return ctx


class MemoryExtractStage(PipelineStage):
    @property
    def name(self) -> str:
        return "memory_extract"

    @property
    def order(self) -> int:
        return 10

    async def process(self, ctx: PipelineContext) -> PipelineContext:
        return ctx


class EmotionAnalysisStage(PipelineStage):
    @property
    def name(self) -> str:
        return "emotion_analysis"

    @property
    def order(self) -> int:
        return 11

    async def process(self, ctx: PipelineContext) -> PipelineContext:
        return ctx


class ResponseDecorateStage(PipelineStage):
    @property
    def name(self) -> str:
        return "response_decorate"

    @property
    def order(self) -> int:
        return 12

    async def process(self, ctx: PipelineContext) -> PipelineContext:
        return ctx


class MultiDispatchStage(PipelineStage):
    @property
    def name(self) -> str:
        return "multi_dispatch"

    @property
    def order(self) -> int:
        return 13

    async def process(self, ctx: PipelineContext) -> PipelineContext:
        return ctx


class AuditLogStage(PipelineStage):
    @property
    def name(self) -> str:
        return "audit_log"

    @property
    def order(self) -> int:
        return 14

    async def process(self, ctx: PipelineContext) -> PipelineContext:
        return ctx

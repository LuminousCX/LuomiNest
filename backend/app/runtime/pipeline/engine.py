from typing import Optional
from app.runtime.pipeline.base import PipelineStage
from app.runtime.pipeline.stages import (
    WakeWordStage,
    AuthStage,
    RateLimitStage,
    SessionStage,
    ContextBuildStage,
    PreprocessStage,
    AgentRouteStage,
    LLMInferenceStage,
    ToolExecuteStage,
    MemoryExtractStage,
    EmotionAnalysisStage,
    ResponseDecorateStage,
    MultiDispatchStage,
    AuditLogStage,
)
from app.runtime.event_bus import EventBus, EventType
from app.runtime.context import PipelineContext
from loguru import logger


STAGE_REGISTRY = [
    WakeWordStage,
    AuthStage,
    RateLimitStage,
    SessionStage,
    ContextBuildStage,
    PreprocessStage,
    AgentRouteStage,
    LLMInferenceStage,
    ToolExecuteStage,
    MemoryExtractStage,
    EmotionAnalysisStage,
    ResponseDecorateStage,
    MultiDispatchStage,
    AuditLogStage,
]


class Pipeline:
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self.stages: list[PipelineStage] = sorted(
            [s() for s in STAGE_REGISTRY], key=lambda x: x.order
        )

    async def execute(self, ctx: PipelineContext) -> PipelineContext:
        for stage in self.stages:
            try:
                logger.debug(f"Pipeline stage: {stage.name}")
                result = await stage.process(ctx)
                if result is None or ctx.should_stop:
                    break
            except Exception as e:
                logger.error(f"Pipeline stage [{stage.name}] failed: {e}")
                raise

        await self.event_bus.emit(
            EventType.AGENT_RESPONSE,
            {"result": ctx.agent_result, "session_id": ctx.user_context.session_id if ctx.user_context else ""},
        )
        return ctx

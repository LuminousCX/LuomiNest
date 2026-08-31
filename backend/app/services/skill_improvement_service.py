"""CxSkillImprovementService — LuomiNest 技能使用统计与 AI 自改进服务。

参照研究报告 Phase 3 设计，实现技能系统的"自我进化"闭环：
1. **使用统计**：记录每个技能的调用次数、最近使用时间、用户反馈（赞/踩）
2. **改进建议**：基于使用数据与 body 内容，调用 LLM 生成结构化改进建议
3. **自动改进**（可选）：用户开启 auto_improve 后，自动应用改进建议到 SKILL.md

设计原则：
- **数据安全优先**：auto_improve 默认关闭，所有自动修改都先备份原文件
- **可解释性**：每次改进都记录 diff 与原因，供用户审阅
- **LLM 异步**：LLM 调用不阻塞 API 响应，改进建议生成通过后台任务
- **持久化**：统一存入 config_items 表（SQLite，AES 加密与统一备份链路），避免数据丢失
- **品牌一致性**：所有类名使用 Cx 前缀
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Callable

from loguru import logger

from app.core.utils import utc_now
from app.infrastructure.database.config_namespace_store import ConfigNamespaceStore
from app.runtime.plugin.skill.registry import luominest_skill_registry
from app.runtime.provider.llm.adapter import llm_adapter
from app.runtime.provider.llm.types import RouteHint
from app.services.skill_service import luominest_skill_service


# 持久化存储（config_items 为唯一权威源；遗留 JSON 首次访问时幂等并集合并，旧文件保留不删除）
_skill_usage_store = ConfigNamespaceStore(
    "skills.usage",
    legacy_source="skill_usage",
    legacy_filename="cx_skill_usage.json",
)
_skill_suggestions_store = ConfigNamespaceStore(
    "skills.suggestions",
    legacy_source="skill_suggestions",
    legacy_filename="cx_skill_suggestions.json",
)
_skill_backup_dir_name = ".backups"


@dataclass
class SkillUsageStats:
    """技能使用统计。"""

    skill_id: str
    invoke_count: int = 0
    last_invoked_at: str = ""
    last_invoked_query: str = ""
    positive_count: int = 0          # 用户点赞次数
    negative_count: int = 0          # 用户点踩次数
    last_feedback_at: str = ""
    last_feedback_kind: str = ""     # "positive" / "negative" / ""
    last_feedback_comment: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SkillUsageStats":
        return cls(
            skill_id=str(data.get("skill_id", "")),
            invoke_count=int(data.get("invoke_count", 0)),
            last_invoked_at=str(data.get("last_invoked_at", "")),
            last_invoked_query=str(data.get("last_invoked_query", "")),
            positive_count=int(data.get("positive_count", 0)),
            negative_count=int(data.get("negative_count", 0)),
            last_feedback_at=str(data.get("last_feedback_at", "")),
            last_feedback_kind=str(data.get("last_feedback_kind", "")),
            last_feedback_comment=str(data.get("last_feedback_comment", "")),
        )


@dataclass
class SkillImprovementSuggestion:
    """LLM 生成的技能改进建议。"""

    suggestion_id: str
    skill_id: str
    created_at: str
    summary: str                       # 一句话总结
    reasons: list[str] = field(default_factory=list)    # 改进原因列表
    changes: list[dict[str, str]] = field(default_factory=list)  # [{section, old, new, why}]
    suggested_content: str = ""        # 改进后的完整 SKILL.md 内容（可选）
    applied: bool = False              # 是否已应用
    applied_at: str = ""
    applied_diff: str = ""             # 应用时的差异摘要

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CxSkillImprovementService:
    """技能自改进服务 — 全局单例 luominest_skill_improvement_service。

    提供：
    - track_invocation / track_feedback：记录使用数据
    - get_usage_stats / list_usage_stats：查询统计
    - generate_suggestion：异步调用 LLM 生成改进建议
    - apply_suggestion：应用建议到 SKILL.md（含备份）
    - auto_improve开关：开启后自动应用高分建议
    """

    def __init__(self) -> None:
        self._llm_adapter = None
        self._auto_improve_enabled = False
        self._auto_improve_threshold = 0.7  # 建议置信度阈值（0-1）
        self._suggestion_tasks: dict[str, asyncio.Task] = {}

    # ------------------------------------------------------------------
    # LLM 适配器（懒加载，避免循环导入）
    # ------------------------------------------------------------------

    def _get_llm_adapter(self):
        """获取 LLM 适配器。"""
        if self._llm_adapter is None:
            self._llm_adapter = llm_adapter
        return self._llm_adapter

    # ------------------------------------------------------------------
    # 使用统计 — 调用与反馈
    # ------------------------------------------------------------------

    def track_invocation(self, skill_id: str, user_query: str = "") -> SkillUsageStats:
        """记录技能被调用一次。

        供 ContextService 在技能被注入 prompt 时调用。
        """
        stats = self._mutate_stats(skill_id, lambda s: (
            s.__dict__.update(
                invoke_count=s.invoke_count + 1,
                last_invoked_at=utc_now(),
                last_invoked_query=user_query[:200],
            )
        ))
        logger.debug(
            f"[CxSkillImprove] Tracked invocation: {skill_id} "
            f"count={stats.invoke_count}"
        )
        return stats

    def track_feedback(
        self,
        skill_id: str,
        kind: str,
        comment: str = "",
    ) -> SkillUsageStats:
        """记录用户对技能的反馈。

        Args:
            skill_id: 技能 id
            kind: "positive" 或 "negative"
            comment: 用户可选的反馈说明
        """
        if kind not in ("positive", "negative"):
            raise ValueError(f"无效的反馈类型: {kind!r}（应为 positive/negative）")

        def _updater(s: SkillUsageStats) -> None:
            if kind == "positive":
                s.positive_count += 1
            else:
                s.negative_count += 1
            s.last_feedback_at = utc_now()
            s.last_feedback_kind = kind
            s.last_feedback_comment = comment[:500]

        stats = self._mutate_stats(skill_id, _updater)
        logger.info(
            f"[CxSkillImprove] Tracked feedback: {skill_id} kind={kind} "
            f"pos={stats.positive_count} neg={stats.negative_count}"
        )
        return stats

    def get_usage_stats(self, skill_id: str) -> SkillUsageStats | None:
        """获取单个技能的使用统计。"""
        data = _skill_usage_store.get(skill_id)
        if data is None:
            return None
        return SkillUsageStats.from_dict(data)

    def list_usage_stats(self) -> list[SkillUsageStats]:
        """列出所有技能的使用统计。"""
        all_data = _skill_usage_store.list_all()
        return [SkillUsageStats.from_dict(v) for v in all_data.values()]

    def _mutate_stats(
        self,
        skill_id: str,
        updater: Callable[[SkillUsageStats], None],
    ) -> SkillUsageStats:
        """原子更新技能统计。"""
        def _store_updater(old: dict | None) -> dict:
            old_stats = (
                SkillUsageStats.from_dict(old) if old else SkillUsageStats(skill_id=skill_id)
            )
            updater(old_stats)
            return old_stats.to_dict()

        new_data = _skill_usage_store.mutate(skill_id, _store_updater)
        return SkillUsageStats.from_dict(new_data)

    # ------------------------------------------------------------------
    # 改进建议 — LLM 生成
    # ------------------------------------------------------------------

    async def generate_suggestion(
        self,
        skill_id: str,
        force: bool = False,
    ) -> dict[str, Any] | None:
        """异步调用 LLM 生成技能改进建议。

        Args:
            skill_id: 技能 id
            force: 是否强制生成（忽略最近已生成的建议）

        Returns:
            建议字典，或在生成失败时返回 None
        """
        # 防止并发生成同一技能的建议
        existing_task = self._suggestion_tasks.get(skill_id)
        if existing_task and not existing_task.done():
            logger.warning(f"[CxSkillImprove] Suggestion generation already running: {skill_id}")
            return None

        task = asyncio.create_task(self._do_generate_suggestion(skill_id, force))
        self._suggestion_tasks[skill_id] = task
        try:
            return await task
        finally:
            self._suggestion_tasks.pop(skill_id, None)

    async def _do_generate_suggestion(
        self,
        skill_id: str,
        force: bool,
    ) -> dict[str, Any] | None:
        """实际执行建议生成。"""
        skill_detail = luominest_skill_service.get_skill(skill_id)
        if skill_detail is None:
            logger.warning(f"[CxSkillImprove] Skill not found: {skill_id}")
            return None

        # 检查最近是否已有未应用的建议
        if not force:
            recent = self._get_latest_unapplied_suggestion(skill_id)
            if recent is not None:
                logger.info(f"[CxSkillImprove] Has unapplied suggestion: {skill_id}, skip")
                return recent

        usage_stats = self.get_usage_stats(skill_id)
        usage_dict = usage_stats.to_dict() if usage_stats else SkillUsageStats(skill_id=skill_id).to_dict()

        # 构建 LLM prompt
        prompt = self._build_improvement_prompt(skill_detail, usage_dict)
        try:
            llm = self._get_llm_adapter()
            response = await llm.chat(
                messages=[
                    {"role": "system", "content": "你是一位 SKILL.md 技能优化专家。严格按 JSON 格式输出建议。"},
                    {"role": "user", "content": prompt},
                ],
                route_hint=RouteHint.REASONER,
                temperature=0.3,
                max_tokens=4096,
            )
            suggestion_text = str(response).strip()
        except Exception as e:
            logger.error(f"[CxSkillImprove] LLM call failed for {skill_id}: {e}")
            return None

        # 解析 LLM 输出（容错：尝试从 markdown 代码块提取 JSON）
        suggestion_data = self._parse_suggestion_response(suggestion_text, skill_id)
        if suggestion_data is None:
            logger.warning(f"[CxSkillImprove] Failed to parse suggestion for {skill_id}")
            return None

        # 持久化
        suggestion = SkillImprovementSuggestion(
            suggestion_id=suggestion_data["suggestion_id"],
            skill_id=skill_id,
            created_at=utc_now(),
            summary=suggestion_data.get("summary", ""),
            reasons=suggestion_data.get("reasons", []),
            changes=suggestion_data.get("changes", []),
            suggested_content=suggestion_data.get("suggested_content", ""),
        )
        _skill_suggestions_store.set(suggestion.suggestion_id, suggestion.to_dict())

        logger.success(
            f"[CxSkillImprove] Generated suggestion: {suggestion.suggestion_id} "
            f"for {skill_id} (changes={len(suggestion.changes)})"
        )

        # auto_improve 时自动应用
        if (
            self._auto_improve_enabled
            and suggestion.suggested_content
            and suggestion_data.get("confidence", 0) >= self._auto_improve_threshold
        ):
            logger.info(f"[CxSkillImprove] Auto-applying suggestion: {suggestion.suggestion_id}")
            await self.apply_suggestion(suggestion.suggestion_id, auto=True)

        return suggestion.to_dict()

    def _build_improvement_prompt(self, skill_detail: dict, usage: dict) -> str:
        """构建让 LLM 生成改进建议的 prompt。"""
        body = skill_detail.get("body", "")
        usage_summary = (
            f"- 调用次数: {usage.get('invoke_count', 0)}\n"
            f"- 最近调用: {usage.get('last_invoked_at', '无')}\n"
            f"- 最近查询: {usage.get('last_invoked_query', '无')}\n"
            f"- 正面反馈: {usage.get('positive_count', 0)}\n"
            f"- 负面反馈: {usage.get('negative_count', 0)}\n"
            f"- 最近反馈: {usage.get('last_feedback_kind', '无')} - {usage.get('last_feedback_comment', '')}"
        )

        return f"""请分析以下 LuomiNest 技能（SKILL.md），生成具体的改进建议。

## 技能信息
- ID: {skill_detail.get('id', '')}
- 名称: {skill_detail.get('name', '')}
- 描述: {skill_detail.get('description', '')}
- 版本: {skill_detail.get('version', '')}
- 触发关键词: {skill_detail.get('trigger_keywords', [])}

## 使用数据
{usage_summary}

## 当前 SKILL.md body
```
{body}
```

## 改进目标
1. 让 body 更清晰、可执行（避免歧义）
2. 根据使用数据补全缺失场景或精简冗余内容
3. 优化 trigger_keywords 覆盖度（不要无差别扩展）
4. 保持原有结构与作者署名

## 输出格式（严格 JSON）
```json
{{
  "suggestion_id": "sg-{skill_detail.get('id', '')}-{{timestamp}}",
  "summary": "一句话总结改进点",
  "confidence": 0.0,
  "reasons": ["改进原因 1", "改进原因 2"],
  "changes": [
    {{"section": "章节名", "old": "原内容摘要", "new": "新内容摘要", "why": "改进原因"}}
  ],
  "suggested_content": "改进后的完整 SKILL.md 内容（含 frontmatter 与 body），留空则不自动应用"
}}
```

注意：
- confidence 在 0-1 之间，表示改进的把握程度
- suggested_content 必须包含完整的 frontmatter 与 body，且 id 与目录名一致
- 若不建议修改，返回 confidence=0 与空 changes
"""

    def _parse_suggestion_response(
        self,
        text: str,
        skill_id: str,
    ) -> dict[str, Any] | None:
        """解析 LLM 的 JSON 响应，容错处理。"""
        # 尝试从 markdown 代码块提取
        candidates: list[str] = [text]
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                candidates.insert(0, text[start:end].strip())
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                candidates.insert(0, text[start:end].strip())

        for cand in candidates:
            try:
                data = json.loads(cand)
                if isinstance(data, dict):
                    # 补全 suggestion_id
                    if not data.get("suggestion_id"):
                        ts = datetime.now().strftime("%Y%m%d%H%M%S")
                        data["suggestion_id"] = f"sg-{skill_id}-{ts}"
                    return data
            except json.JSONDecodeError:
                continue
        return None

    # ------------------------------------------------------------------
    # 建议查询与应用
    # ------------------------------------------------------------------

    def list_suggestions(
        self,
        skill_id: str | None = None,
        applied_only: bool = False,
        unapplied_only: bool = False,
    ) -> list[dict[str, Any]]:
        """列出改进建议。"""
        all_data = _skill_suggestions_store.list_all()
        result = []
        for sugg in all_data.values():
            if skill_id and sugg.get("skill_id") != skill_id:
                continue
            is_applied = bool(sugg.get("applied"))
            if applied_only and not is_applied:
                continue
            if unapplied_only and is_applied:
                continue
            result.append(sugg)
        # 按创建时间倒序
        result.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return result

    def get_suggestion(self, suggestion_id: str) -> dict[str, Any] | None:
        """获取单个建议。"""
        return _skill_suggestions_store.get(suggestion_id)

    def _get_latest_unapplied_suggestion(self, skill_id: str) -> dict[str, Any] | None:
        """获取某技能最近一条未应用的建议。"""
        suggs = self.list_suggestions(skill_id=skill_id, unapplied_only=True)
        return suggs[0] if suggs else None

    async def apply_suggestion(
        self,
        suggestion_id: str,
        auto: bool = False,
    ) -> dict[str, Any]:
        """应用改进建议到 SKILL.md。

        Args:
            suggestion_id: 建议 id
            auto: 是否为自动应用（影响日志与返回字段）

        Returns:
            操作结果字典

        Raises:
            ValueError: 建议不存在 / 已应用 / 缺少 suggested_content / skill_id 校验失败
        """
        sugg = _skill_suggestions_store.get(suggestion_id)
        if sugg is None:
            raise ValueError(f"建议不存在: {suggestion_id}")
        if sugg.get("applied"):
            raise ValueError(f"建议已应用: {suggestion_id}")
        if not sugg.get("suggested_content"):
            raise ValueError(f"建议无 suggested_content，无法应用: {suggestion_id}")

        skill_id = sugg["skill_id"]
        suggested_content = sugg["suggested_content"]

        # 备份原文件
        backup_path = self._backup_skill_md(skill_id)

        # 写入新内容（覆盖）
        try:
            write_result = await luominest_skill_service.write_skill(
                skill_id, suggested_content, overwrite=True
            )
        except Exception as e:
            logger.error(f"[CxSkillImprove] Apply suggestion failed: {e}")
            # 自动恢复备份
            self._restore_skill_md(skill_id, backup_path)
            raise

        # 构造 diff 摘要（简化的字段级差异）
        diff_summary = self._summarize_diff(sugg)

        # 更新建议状态
        sugg["applied"] = True
        sugg["applied_at"] = utc_now()
        sugg["applied_diff"] = diff_summary
        sugg["auto_applied"] = auto
        _skill_suggestions_store.set(suggestion_id, sugg)

        logger.success(
            f"[CxSkillImprove] Applied suggestion {suggestion_id} to {skill_id} "
            f"(auto={auto}, backup={backup_path})"
        )

        return {
            "suggestion_id": suggestion_id,
            "skill_id": skill_id,
            "applied": True,
            "applied_at": sugg["applied_at"],
            "backup_path": backup_path,
            "write_result": write_result,
            "diff_summary": diff_summary,
            "auto": auto,
        }

    def dismiss_suggestion(self, suggestion_id: str) -> bool:
        """忽略（删除）一条改进建议。"""
        sugg = _skill_suggestions_store.get(suggestion_id)
        if sugg is None:
            return False
        _skill_suggestions_store.delete(suggestion_id)
        logger.info(f"[CxSkillImprove] Dismissed suggestion: {suggestion_id}")
        return True

    # ------------------------------------------------------------------
    # 备份与恢复
    # ------------------------------------------------------------------

    def _backup_skill_md(self, skill_id: str) -> str:
        """备份当前 SKILL.md 到 .backups 目录，返回备份路径。"""
        skill = luominest_skill_registry.get(skill_id)
        if skill is None or not skill.source_path:
            raise ValueError(f"技能未加载或无 source_path: {skill_id}")

        source_path = skill.source_path
        if not os.path.isfile(source_path):
            raise ValueError(f"SKILL.md 文件不存在: {source_path}")

        skill_dir = os.path.dirname(source_path)
        backup_dir = os.path.join(skill_dir, _skill_backup_dir_name)
        os.makedirs(backup_dir, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        backup_filename = f"SKILL.{ts}.md"
        backup_path = os.path.join(backup_dir, backup_filename)

        shutil.copy2(source_path, backup_path)

        # 清理超过 10 个的旧备份
        self._cleanup_old_backups(backup_dir, keep=10)

        return backup_path

    def _restore_skill_md(self, skill_id: str, backup_path: str) -> bool:
        """从备份恢复 SKILL.md。"""
        if not os.path.isfile(backup_path):
            logger.error(f"[CxSkillImprove] Backup not found: {backup_path}")
            return False

        try:
            with open(backup_path, encoding="utf-8") as f:
                content = f.read()
            asyncio.get_event_loop().create_task(
                luominest_skill_service.write_skill(skill_id, content, overwrite=True)
            )
            logger.info(f"[CxSkillImprove] Restored from backup: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"[CxSkillImprove] Restore failed: {e}")
            return False

    def _cleanup_old_backups(self, backup_dir: str, keep: int = 10) -> None:
        """清理旧备份，保留最近 keep 个。"""
        import glob

        try:
            pattern = os.path.join(backup_dir, "SKILL.*.md")
            backups = glob.glob(pattern)
            if len(backups) <= keep:
                return
            # 按修改时间倒序
            backups.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            for old in backups[keep:]:
                try:
                    os.remove(old)
                except OSError as e:
                    logger.debug(
                        f"[CxSkillImprove] Skip removing old backup {old}: {e}"
                    )
        except Exception as e:
            logger.debug(f"[CxSkillImprove] Backup cleanup failed: {e}")

    def _summarize_diff(self, sugg: dict) -> str:
        """生成简化的差异摘要。"""
        changes = sugg.get("changes", [])
        if not changes:
            return "无变更说明"
        lines = []
        for ch in changes[:5]:  # 最多 5 条
            section = ch.get("section", "?")
            why = ch.get("why", "")
            lines.append(f"- [{section}] {why}")
        if len(changes) > 5:
            lines.append(f"- ... 共 {len(changes)} 条变更")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # auto_improve 配置
    # ------------------------------------------------------------------

    def is_auto_improve_enabled(self) -> bool:
        return self._auto_improve_enabled

    def set_auto_improve(self, enabled: bool) -> None:
        """开启/关闭自动改进。"""
        self._auto_improve_enabled = bool(enabled)
        logger.info(f"[CxSkillImprove] auto_improve = {self._auto_improve_enabled}")

    def get_auto_improve_threshold(self) -> float:
        return self._auto_improve_threshold

    def set_auto_improve_threshold(self, threshold: float) -> None:
        """设置自动应用的置信度阈值（0-1）。"""
        if not 0 <= threshold <= 1:
            raise ValueError(f"阈值应在 0-1 之间，当前: {threshold}")
        self._auto_improve_threshold = float(threshold)

    # ------------------------------------------------------------------
    # 统计与建议聚合
    # ------------------------------------------------------------------

    def get_dashboard(self) -> dict[str, Any]:
        """获取技能自改进仪表盘数据（供 API 调用）。"""
        all_stats = self.list_usage_stats()
        all_suggs = self.list_suggestions()

        return {
            "usage": {
                "total_tracked": len(all_stats),
                "total_invocations": sum(s.invoke_count for s in all_stats),
                "total_positive": sum(s.positive_count for s in all_stats),
                "total_negative": sum(s.negative_count for s in all_stats),
                "top_invoked": sorted(
                    [s.to_dict() for s in all_stats],
                    key=lambda x: x.get("invoke_count", 0),
                    reverse=True,
                )[:5],
            },
            "suggestions": {
                "total": len(all_suggs),
                "applied": sum(1 for s in all_suggs if s.get("applied")),
                "pending": sum(1 for s in all_suggs if not s.get("applied")),
                "recent": all_suggs[:5],
            },
            "auto_improve": {
                "enabled": self._auto_improve_enabled,
                "threshold": self._auto_improve_threshold,
            },
        }


# 全局单例
luominest_skill_improvement_service = CxSkillImprovementService()

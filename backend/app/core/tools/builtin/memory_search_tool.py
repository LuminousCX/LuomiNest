"""LuomiNest 记忆主动搜索工具（W5-1 跨轨检索版）。

供群聊 Agent 主动深挖记忆、主 Agent 主动检索长期记忆。基于 contextvars 权限控制：
- "none"：拒绝访问（联系人 Agent 默认）
- "read_main"：可读主 Agent 记忆（群聊 Agent）
- "read_write"：可读写自身记忆（工作台主 Agent，记忆即主 Agent 记忆）

跨轨检索（W5-1，G12）：``track`` 参数支持 ``owner|users|groups|auto``：
- auto：按 DomainPolicy 当前上下文收窄——探针读「父会话 conv_id」contextvar
  （chat_service 主对话路径设置）→ 会话元数据（domain/scene/user_key）→
  DomainPolicy 推导：workbench/agent 域 → owner；platform 域私聊（conv.user_key
  非空）→ 该用户 users 轨；platform 域群聊（说话人身份是消息级信息不落库、
  且平台路径不经 chat_service）→ 无法解析说话人轨，降级 owner；
  探针不可用（无上下文）→ 降级 owner（metadata 记 degraded 原因）。
- users/groups：显式传 user_key/group_key 直查对应轨（经 get_track_engine）。
  群聊合并检索：track=groups 时可再传 user_key（说话人轨）合并两轨结果，
  结果逐条标注来源轨。
- 防泄露（§8.5.10）：users/groups 轨检索默认排除 scope=private 事实
  （与 memory_engine.build_group_members_block 同一底线）；owner 轨不限制。

检索内核（W5-4）：向量 + SQLite FTS5 BM25 两路召回 RRF 融合（k=60），
embedding 异常自动纯 BM25（详见 engines/memory/hybrid_search.py）。

品牌化命名：LuomiNestMemorySearchTool。
"""
from typing import Any

from loguru import logger

from app.core.agents.memory_access import get_luominest_memory_access
from app.core.tools.registry import ToolBase, ToolResult
from app.engines.memory.hybrid_search import (
    HybridSearchMeta,
    filter_valid_facts,
    hybrid_search,
)
from app.engines.memory.models import FACT_SCOPES, SCOPE_PRIVATE

# 各轨道默认可见作用域：owner 不限（None）；用户/群轨屏蔽 private 防泄露
_TRACK_ALLOWED_SCOPES: dict[str, set[str] | None] = {
    "owner": None,
    "users": {"global", "group"},
    "groups": {"global", "group"},
}

_VALID_TRACKS = ("owner", "users", "groups", "auto")


class LuomiNestMemorySearchTool(ToolBase):
    """主动搜索记忆的工具（跨轨版）

    群聊 Agent 与主 Agent 均可通过本工具查询长期记忆，获取用户偏好、历史事实等。
    """

    tier: str = "core"
    scope: str = "shared"

    @property
    def name(self) -> str:
        return "memory_search"

    @property
    def description(self) -> str:
        return (
            "搜索长期记忆库，获取用户偏好、历史事实、过往对话要点等（Mem0 范式）。"
            "适用于：1. 需要了解用户习惯和偏好的场景；"
            "2. 需要引用过往对话事实的场景；"
            "3. 需要个性化回应时深挖用户信息。"
            "支持跨记忆轨道检索：owner=主人记忆（默认），users=平台用户记忆（需 user_key），"
            "groups=群聊公共记忆（需 group_key，可再传 user_key 合并说话人记忆），"
            "auto=按当前对话上下文自动收窄。"
            "返回与查询最相关的记忆条目（含内容、分类、置信度、事实ID、来源轨道）。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询（应清晰描述想查找的记忆内容，如「用户喜欢的编程语言」「用户的饮食习惯」）",
                },
                "track": {
                    "type": "string",
                    "enum": list(_VALID_TRACKS),
                    "description": (
                        "记忆轨道（默认 auto）：owner=主人轨；users=平台用户轨（需 user_key）；"
                        "groups=群聊轨（需 group_key）；auto=按当前对话上下文自动选择"
                        "（私聊=说话人 users 轨，桌面/工作台=owner，群聊无法解析说话人时降级 owner）"
                    ),
                    "default": "auto",
                },
                "user_key": {
                    "type": "string",
                    "description": (
                        "平台用户轨键（track=users 必填；track=groups 时可选，"
                        "用于合并检索说话人的用户轨记忆），形如 qq_onebot_10001"
                    ),
                },
                "group_key": {
                    "type": "string",
                    "description": "平台群组轨键（track=groups 必填），形如 qq_onebot_888888",
                },
                "category": {
                    "type": "string",
                    "description": "按记忆分类过滤（可选，如 preference/knowledge/context/goal/behavior）",
                },
                "scope": {
                    "type": "string",
                    "enum": list(FACT_SCOPES),
                    "description": (
                        "按隐私作用域过滤（可选）。注意 users/groups 轨默认已排除 "
                        "private 私密事实（群聊防泄露底线），此参数只能进一步收窄"
                    ),
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回结果数量（默认 5，最大 10）",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    # ── 轨道解析（W5-1） ──

    @staticmethod
    def _resolve_explicit_track(track: str, user_key: str, group_key: str) -> dict[str, Any]:
        """显式轨道 → 引擎解析参数；缺键时降级 owner 并给出原因。"""
        if track == "users":
            if not user_key:
                return {"track": "owner", "degraded": True,
                        "degrade_reason": "users 轨需要 user_key 参数，已降级 owner"}
            return {"track": "users", "user_key": user_key}
        if track == "groups":
            if not group_key:
                return {"track": "owner", "degraded": True,
                        "degrade_reason": "groups 轨需要 group_key 参数，已降级 owner"}
            return {"track": "groups", "group_key": group_key, "user_key": user_key}
        return {"track": "owner"}

    @staticmethod
    def _probe_domain_policy():
        """auto 探针：父会话 conv_id contextvar → 会话元数据 → DomainPolicy。

        探针链路（2026-09-21 探明）：
        - chat_service.stream_response（工作台主对话）与子 Agent 路径会设置
          luominest_parent_conv_id contextvar，本工具执行时同异步上下文可读；
        - platform_router 的平台工具循环不经过 chat_service，也无会话上下文
          contextvar → 探针返回 None → auto 降级 owner（与改造前行为一致）；
        - 平台群聊的说话人身份（member_user_key）是消息级信息不落库，会话
          user_key 为空 → 群聊场景无法解析说话人轨 → 降级 owner。

        Returns:
            DomainPolicy 或 None（上下文不可用）。
        """
        try:
            from app.core.agents.cluster.agent_tool import get_luominest_parent_conv_id

            conv_id = get_luominest_parent_conv_id()
            if not conv_id:
                return None
            from app.infrastructure.database.conversation_store import conversation_store

            meta = conversation_store.get_meta(conv_id)
            if not meta:
                return None
            from app.core.domain_policy import resolve_domain_policy

            return resolve_domain_policy(
                meta.get("domain") or "",
                scene=meta.get("scene") or "",
                agent_id=meta.get("agent_id"),
                user_key=meta.get("user_key") or "",
            )
        except Exception as e:
            logger.debug(f"[MemorySearch] auto track probe failed: {e}")
            return None

    async def _resolve_auto_track(self) -> dict[str, Any]:
        """auto：按 DomainPolicy 当前上下文收窄轨道；拿不到上下文降级 owner。"""
        from app.core.domain_policy import (
            TRACK_OWNER,
            TRACK_USERS,
            KIND_PLATFORM,
        )

        policy = self._probe_domain_policy()
        if policy is None:
            return {"track": "owner", "degraded": True,
                    "degrade_reason": "无会话上下文（桌面直连或平台工具循环），auto 降级 owner"}
        if policy.memory_track == TRACK_OWNER:
            return {"track": "owner"}
        if policy.kind == KIND_PLATFORM and policy.memory_track == TRACK_USERS and policy.track_user_key:
            # 私聊（conv.user_key 非空）→ 说话人 users 轨；私聊场景其本人
            # private 事实可召回（与注入一致），故放开 private
            return {"track": "users", "user_key": policy.track_user_key,
                    "allow_private": True}
        # 平台群聊（user_key 空，说话人身份不落库）等不可解析场景
        return {"track": "owner", "degraded": True,
                "degrade_reason": "群聊场景说话人轨不可解析（消息级身份不落库），auto 降级 owner"}

    # ── 执行 ──

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        query = arguments.get("query", "").strip()
        category_filter = (arguments.get("category") or "").strip().lower()
        if not query:
            return ToolResult.fail("缺少 query 参数")

        top_k = arguments.get("top_k", 5)
        try:
            top_k = int(top_k)
        except (TypeError, ValueError):
            top_k = 5
        top_k = max(1, min(top_k, 10))

        track = str(arguments.get("track") or "auto").strip().lower()
        if track not in _VALID_TRACKS:
            track = "auto"
        user_key = str(arguments.get("user_key") or "").strip()
        group_key = str(arguments.get("group_key") or "").strip()
        scope_filter = str(arguments.get("scope") or "").strip().lower()
        if scope_filter and scope_filter not in FACT_SCOPES:
            scope_filter = ""

        # 权限策略（2026-09-21 定稿）：本工具面向所有 Agent 开放，读取的是 owner
        # （主人/主 Agent）轨的长期记忆。原 MEMORY_ACCESS_NONE 拦截已按陪伴定位
        # 移除；注意该轨可能包含主人私聊级事实，若未来引入不可信子 Agent，
        # 应在 DomainPolicy 层按 track+scope 收窄而非恢复一刀切拦截。
        access_level = get_luominest_memory_access()

        # 轨道解析：auto 探针 / 显式参数
        if track == "auto":
            resolved = await self._resolve_auto_track()
        else:
            resolved = self._resolve_explicit_track(track, user_key, group_key)

        eff_track = resolved["track"]
        eff_user_key = str(resolved.get("user_key") or "")
        eff_group_key = str(resolved.get("group_key") or "")
        degraded = bool(resolved.get("degraded"))
        degrade_reason = str(resolved.get("degrade_reason") or "")

        # 作用域白名单：owner 不限；users/groups 屏蔽 private（防泄露底线，
        # 与 build_group_members_block 一致）；auto 判定的私聊用户轨放开 private；
        # 显式 scope 参数只能进一步收窄
        allowed_scopes = _TRACK_ALLOWED_SCOPES.get(eff_track)
        if eff_track == "users" and resolved.get("allow_private") and allowed_scopes is not None:
            allowed_scopes = set(allowed_scopes) | {SCOPE_PRIVATE}
        if scope_filter:
            if allowed_scopes is None:
                allowed_scopes = {scope_filter}
            else:
                allowed_scopes = set(allowed_scopes) & {scope_filter}
                if not allowed_scopes:
                    return ToolResult.fail(
                        f"scope={scope_filter} 与 {eff_track} 轨防泄露策略冲突"
                        "（users/groups 轨不含 private 事实）"
                    )

        # 目标引擎（owner 单轨 / groups+users 合并 / users 或 groups 单轨）
        try:
            engines = self._resolve_engines(eff_track, eff_user_key, eff_group_key)
        except Exception as e:
            logger.error(f"[MemorySearch] 获取记忆引擎失败: {e}", exc_info=True)
            return ToolResult.fail(f"记忆引擎不可用: {e}")

        # 检索（向量 + BM25 RRF 融合），多轨时合并后重融合
        results, meta = await self._search_engines(engines, query, top_k, category_filter, allowed_scopes)

        metadata = {
            "query": query,
            "result_count": len(results),
            "track": eff_track,
            "mode": meta.mode,
            "vector_ok": meta.vector_ok,
            "bm25_ok": meta.bm25_ok,
            "degraded": degraded,
        }
        if eff_user_key:
            metadata["user_key"] = eff_user_key
        if eff_group_key:
            metadata["group_key"] = eff_group_key
        if degrade_reason:
            metadata["degrade_reason"] = degrade_reason
        if meta.note:
            metadata["retrieval_note"] = meta.note

        if not results:
            return ToolResult.ok("未找到相关记忆。", metadata=metadata)

        # 格式化结果（逐条标注来源轨）
        result_lines: list[str] = []
        for idx, (fact, scored, track_label) in enumerate(results, start=1):
            pin_mark = " [置顶]" if getattr(fact, "pinned", False) else ""
            scope_mark = " [私密]" if getattr(fact, "scope", "global") == SCOPE_PRIVATE else ""
            result_lines.append(
                f"[{idx}] (轨道: {track_label}, 分类: {fact.category}, 置信度: {fact.confidence:.2f}, "
                f"相关度: {scored.score:.4f}, 事实ID: {fact.id}){pin_mark}{scope_mark}\n{fact.content}"
            )

        result_text = f"查询「{query}」找到 {len(results)} 条相关记忆：\n\n" + "\n\n".join(result_lines)
        logger.info(
            f"[MemorySearch] 查询成功: query_len={len(query)}, matched={len(results)}, "
            f"track={eff_track}, mode={meta.mode}, access={access_level}, degraded={degraded}"
        )
        return ToolResult.ok(result_text, metadata=metadata)

    @staticmethod
    def _resolve_engines(eff_track: str, user_key: str, group_key: str) -> list[tuple[str, Any]]:
        """解析目标引擎列表（含 groups+users 合并检索），[(track_label, engine)]。"""
        from app.core.domain_policy import TRACK_GROUPS, TRACK_OWNER, TRACK_USERS
        from app.engines.memory import get_track_engine

        engines: list[tuple[str, Any]] = []
        if eff_track == TRACK_OWNER:
            engines.append((TRACK_OWNER, get_track_engine(TRACK_OWNER)))
        elif eff_track == TRACK_USERS:
            engines.append((f"users/{user_key}", get_track_engine(TRACK_USERS, user_key)))
        elif eff_track == TRACK_GROUPS:
            engines.append((f"groups/{group_key}", get_track_engine(TRACK_GROUPS, group_key)))
            if user_key:
                # 群聊合并检索：groups 轨 + 说话人 users 轨，结果标注来源轨
                engines.append((f"users/{user_key}", get_track_engine(TRACK_USERS, user_key)))
        return engines

    @staticmethod
    async def _search_engines(
        engines: list[tuple[str, Any]],
        query: str,
        top_k: int,
        category_filter: str,
        allowed_scopes: set[str] | None,
    ) -> tuple[list[tuple[Any, "_HybridScore", str]], HybridSearchMeta]:
        """逐引擎两路召回，多轨时以各轨排名为腿再做一次 RRF 合并。

        Returns:
            [(FactItem, score, track_label)]（已按融合分降序、截断至 top_k）
            与最后一次单轨检索的召回路径元信息。
        """
        import asyncio

        from app.engines.memory.hybrid_search import RRF_K

        facts_by_id: dict[str, tuple[Any, str]] = {}
        legs: list[list[str]] = []
        meta: HybridSearchMeta | None = None
        for track_label, engine in engines:
            scored, meta = await hybrid_search(
                engine, query, k=top_k,
                category=category_filter or None,
                allowed_scopes=allowed_scopes,
            )
            # 同引擎内已闸门过滤，这里仅反查 FactItem 供格式化
            data = await asyncio.to_thread(engine.load_data)
            valid_map = {
                f.id: f
                for f in filter_valid_facts(
                    data.facts, category=category_filter or None, allowed_scopes=allowed_scopes
                )
            }
            leg: list[str] = []
            for s in scored:
                fact = valid_map.get(s.fact_id)
                if fact is not None:
                    leg.append(s.fact_id)
                    facts_by_id[s.fact_id] = (fact, track_label)
            legs.append(leg)

        if meta is None or not legs:
            return [], HybridSearchMeta()

        if len(legs) == 1:
            ranked = [
                (fid, 1.0 / (RRF_K + rank))
                for rank, fid in enumerate(legs[0], start=1)
            ][:top_k]
        else:
            # 多轨合并：每轨作为一个 RRF 腿重新融合，跨轨可比
            scores: dict[str, float] = {}
            for leg in legs:
                for rank, fid in enumerate(leg, start=1):
                    scores[fid] = scores.get(fid, 0.0) + 1.0 / (RRF_K + rank)
            ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        out: list[tuple[Any, _HybridScore, str]] = []
        for fid, score in ranked:
            fact, label = facts_by_id.get(fid, (None, ""))
            if fact is not None:
                out.append((fact, _HybridScore(0, fid, score), label))
        return out, meta


class _HybridScore:
    """轻量打分包装：统一向量/BM25/RRF 分数供结果展示。"""

    def __init__(self, rank: int, fact_id: str, score: float | None = None):
        self.fact_id = fact_id
        if score is not None:
            self.score = float(score)
        else:
            # 单腿时用 1/(RRF_K + rank) 归一，跨轨可比且恒正
            self.score = 1.0 / (60 + rank)

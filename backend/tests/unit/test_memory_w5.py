"""W5 记忆系统增强单元测试。

覆盖（修改书 §6 W5）：
1. W5-4 SQLite FTS5 BM25 腿：触发器同步影子索引、删除/更新同步、存量回填、
   MATCH 表达式构造、RRF 融合与 embedding 失败降级（hybrid_search）。
2. W5-1 跨轨检索：memory_search 工具 track 参数（users/groups 显式直查、
   auto 按 DomainPolicy 收窄与降级）、群聊合并检索标注来源轨、
   users/groups 轨 scope=private 防泄露。
3. W5-2 时间线与置顶工具：memory_get_daily（某日/最近 N 天 + 事实清单）、
   memory_pin（pin/unpin、未知 ID 失败）。
4. W5-3 POST /api/v1/memory/search：响应字段、轨道/作用域过滤、防泄露默认值。
5. W5-6：memory_forget 模糊遗忘同步摘向量；MAX_FACTS 挤出优先「未 pin 低置信」。
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints.memory import router as memory_router
from app.core.domain_policy import (
    TRACK_GROUPS,
    TRACK_OWNER,
    TRACK_USERS,
    platform_group_key,
    platform_user_key,
)
from app.core.exceptions import LuomiNestError
from app.core.tools.builtin.memory_daily_tool import MemoryGetDailyTool
from app.core.tools.builtin.memory_pin_tool import MemoryPinTool
from app.core.tools.builtin.memory_search_tool import LuomiNestMemorySearchTool
from app.core.tools.builtin.memory_tools import MemoryForgetTool
from app.engines.memory import get_track_engine
from app.engines.memory.fact_manager import FactManager
from app.engines.memory.hybrid_search import (
    MODE_BM25,
    MODE_HYBRID,
    MODE_KEYWORD,
    MODE_VECTOR,
    hybrid_search,
)
from app.engines.memory.memory_engine import MemoryEngine, get_memory_engine
from app.engines.memory.models import SCOPE_GLOBAL, SCOPE_PRIVATE, FactItem
from app.engines.memory.store import build_fts_match_query
from app.engines.memory.vector_store import ScoredFact

app = FastAPI()
# memory_router 内部自带 prefix="/memory"，挂载在 "/api/v1" 下（与双轨测试一致）
app.include_router(memory_router, prefix="/api/v1")


@app.exception_handler(LuomiNestError)
async def _luominest_error_handler(request, exc: LuomiNestError):
    """最小化错误信封（对齐 app_factory 全局 handler 的语义，供 TestClient 断言状态码）。"""
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": str(exc), "error": exc.code},
    )


@pytest.fixture
def temp_engine():
    """临时目录独立库引擎（local 模式，自带 FTS5 影子索引）。"""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        engine = MemoryEngine(storage_path=Path(tmpdir))
        yield engine


def _seed_facts(engine: MemoryEngine, *facts: FactItem) -> list[FactItem]:
    for f in facts:
        engine.add_fact(f)
    return list(facts)


def _stub_vector_offline(engine: MemoryEngine, scored: list[ScoredFact] | None = None) -> None:
    """把引擎的向量腿钉为离线返回（单元测试不发真实 embedding 网络请求）。"""

    async def _retrieve(query, k=10):
        return (scored or [])[:k]

    engine.vector_retrieve = _retrieve


# ═══════════════════════════════════════════════════════════════
# W5-4：FTS5 BM25 腿
# ═══════════════════════════════════════════════════════════════


class TestBuildFtsMatchQuery:
    def test_cjk_dict_words_extracted(self):
        expr = build_fts_match_query("喜欢喝咖啡过生日")
        # 双字词典词 + 单字兜底（与索引侧同源分词）
        assert '"喜欢"' in expr and '"咖啡"' in expr and '"生日"' in expr

    def test_stop_words_filtered(self):
        expr = build_fts_match_query("的了吗 用户")
        assert '"的"' not in expr and '"了"' not in expr
        assert '"用户"' in expr or '"用"' in expr

    def test_latin_words(self):
        expr = build_fts_match_query("i love python3")
        assert '"python"' in expr
        assert '"love"' in expr

    def test_pure_punctuation_returns_empty(self):
        assert build_fts_match_query("？？？！！！") == ""

    def test_quote_stripped(self):
        expr = build_fts_match_query('用户说"你好"')
        assert expr != ""
        assert '""' not in expr  # 嵌入双引号被剥离，MATCH 语法安全


class TestFtsShadowIndex:
    def test_bm25_recall_and_delete_sync(self, temp_engine):
        f1, f2 = _seed_facts(
            temp_engine,
            FactItem(content="主人喜欢喝美式咖啡，每天早晨都要来一杯", category="preference", confidence=0.9),
            FactItem(content="用户的生日是3月12日，记得准备蛋糕", category="context", confidence=0.95),
        )
        store = temp_engine._store
        assert store.fts_enabled is True

        # 中文双字词命中（trigram 方案做不到，预分词影子表的核心收益）
        hits = store.search_facts_bm25("喜欢喝美式咖啡", 5)
        assert [fid for fid, _ in hits] == [f1.id]

        hits2 = store.search_facts_bm25("生日蛋糕", 5)
        assert [fid for fid, _ in hits2] == [f2.id]

        # 删除事实 → 检索时 diff 同步摘除影子行
        temp_engine.remove_fact(f1.id)
        assert store.search_facts_bm25("喜欢喝美式咖啡", 5) == []
        # 未删除的事实仍可召回
        assert [fid for fid, _ in store.search_facts_bm25("生日蛋糕", 5)] == [f2.id]

    def test_content_change_synced_on_search(self, temp_engine):
        """事实内容变更后，下次检索按 diff 刷新影子行（旧行换新词）。"""
        f1 = _seed_facts(
            temp_engine,
            FactItem(content="用户正在筹备敦煌旅行", category="goal", confidence=0.8),
        )[0]
        store = temp_engine._store
        assert [fid for fid, _ in store.search_facts_bm25("敦煌旅行", 5)] == [f1.id]

        temp_engine.update_fact(f1.id, content="用户改成了宅家追剧")
        assert store.search_facts_bm25("敦煌旅行", 5) == []
        assert [fid for fid, _ in store.search_facts_bm25("宅家追剧", 5)] == [f1.id]

    def test_stale_scope_backfill(self, temp_engine):
        """存量兜底：影子行被清空后（模拟老库升级），检索时按作用域 diff 回填。"""
        f1 = _seed_facts(
            temp_engine,
            FactItem(content="用户正在筹备一次敦煌旅行", category="goal", confidence=0.8),
        )[0]
        store = temp_engine._store

        # 模拟存量缺口：直连删光本作用域 FTS 行（绕过应用层）
        from sqlalchemy import text

        with store._db.session() as session:
            session.execute(
                text("DELETE FROM memory_facts_fts WHERE owner_key = :o"),
                {"o": store.owner_key},
            )
            session.commit()

        # 检索触发对账回填，仍能召回
        hits = store.search_facts_bm25("敦煌旅行", 5)
        assert [fid for fid, _ in hits] == [f1.id]

    def test_fts_disabled_returns_empty(self, temp_engine):
        """FTS5 不可用（模拟运行时无 FTS5）：BM25 腿静默返回空，不抛异常。"""
        _seed_facts(
            temp_engine,
            FactItem(content="用户养了一只叫豆豆的橘猫", category="context", confidence=0.8),
        )
        store = temp_engine._store
        store.fts_enabled = False  # 模拟 DDL 曾失败（如初始化早于建表）
        with patch("app.engines.memory.store._probe_fts5", return_value=False):
            assert store.search_facts_bm25("橘猫豆豆", 5) == []


class TestHybridSearch:
    def _mock_vector(self, engine, scored: list[ScoredFact], raise_: bool = False):
        async def _retrieve(query, k=10):
            if raise_:
                raise RuntimeError("embedding provider unreachable")
            return scored[:k]

        engine.vector_retrieve = _retrieve

    @pytest.mark.asyncio
    async def test_hybrid_mode_and_rrf_fusion(self, temp_engine):
        f_hit, _f2 = _seed_facts(
            temp_engine,
            FactItem(content="主人对花生重度过敏，外卖备注一定写", category="preference", confidence=0.95),
            FactItem(content="用户喜欢在周末骑行", category="preference", confidence=0.7),
        )
        # 向量腿给 f2 高分、BM25 腿给 f_hit 命中 → 融合应同时返回两条
        self._mock_vector(temp_engine, [ScoredFact(fact_id=_f2.id, score=0.92, category="preference")])
        results, meta = await hybrid_search(temp_engine, "花生过敏", k=5)
        assert meta.mode == MODE_HYBRID
        ids = [s.fact_id for s in results]
        assert set(ids) == {f_hit.id, _f2.id}
        # BM25 命中的 f_hit 与向量命中的 f2 同现时，RRF 分应高于单腿独有条目
        assert results[0].score >= results[-1].score

    @pytest.mark.asyncio
    async def test_embedding_failure_degrades_to_pure_bm25(self, temp_engine):
        f1 = _seed_facts(
            temp_engine,
            FactItem(content="用户计划明年春天搬家到杭州", category="goal", confidence=0.85),
        )[0]
        self._mock_vector(temp_engine, [], raise_=True)
        results, meta = await hybrid_search(temp_engine, "搬家到杭州", k=5)
        assert meta.mode == MODE_BM25
        assert meta.note == "embedding_failed_pure_bm25"
        assert [s.fact_id for s in results] == [f1.id]

    @pytest.mark.asyncio
    async def test_embedding_failure_bm25_no_match_falls_to_keyword(self, temp_engine):
        """embedding 挂 + 查询纯标点（BM25 无词项）→ 关键词 Jaccard 兜底路径。"""
        _seed_facts(
            temp_engine,
            FactItem(content="用户爱喝咖啡，尤其是手冲", category="preference", confidence=0.8),
        )
        self._mock_vector(temp_engine, [], raise_=True)
        results, meta = await hybrid_search(temp_engine, "？？？", k=5)
        assert meta.mode == MODE_KEYWORD
        assert results == []

    @pytest.mark.asyncio
    async def test_embedding_failure_and_fts_down_keyword_finds_facts(self, temp_engine):
        """embedding 挂 + FTS 腿关闭 → 关键词 Jaccard 兜底仍能召回。"""
        f1 = _seed_facts(
            temp_engine,
            FactItem(content="用户爱喝咖啡，尤其是手冲咖啡", category="preference", confidence=0.8),
        )[0]
        temp_engine._store.fts_enabled = False
        self._mock_vector(temp_engine, [], raise_=True)
        with patch("app.engines.memory.store._probe_fts5", return_value=False):
            results, meta = await hybrid_search(temp_engine, "咖啡 手冲", k=5)
        assert meta.mode == MODE_KEYWORD
        assert [s.fact_id for s in results] == [f1.id]

    @pytest.mark.asyncio
    async def test_scope_and_category_gate(self, temp_engine):
        f_pub, _f_priv = _seed_facts(
            temp_engine,
            FactItem(content="用户喜欢看科幻电影", category="preference", confidence=0.9, scope=SCOPE_GLOBAL),
            FactItem(content="用户的心事是筹备转行", category="preference", confidence=0.9, scope=SCOPE_PRIVATE),
        )
        self._mock_vector(temp_engine, [], raise_=True)
        # 防泄露白名单：private 不出现
        results, meta = await hybrid_search(
            temp_engine, "喜欢看科幻电影 转行", k=10, allowed_scopes={"global", "group"}
        )
        ids = [s.fact_id for s in results]
        assert f_pub.id in ids
        assert _f_priv.id not in ids
        # 分类过滤
        results_cat, _ = await hybrid_search(temp_engine, "科幻电影", k=5, category="knowledge")
        assert results_cat == []

    @pytest.mark.asyncio
    async def test_vector_only_when_bm25_unavailable(self, temp_engine):
        f1 = _seed_facts(
            temp_engine,
            FactItem(content="用户在学西班牙语", category="knowledge", confidence=0.8),
        )[0]
        self._mock_vector(temp_engine, [ScoredFact(fact_id=f1.id, score=0.88, category="knowledge")])
        temp_engine._store.fts_enabled = False  # 模拟 DDL 曾失败
        with patch("app.engines.memory.store._probe_fts5", return_value=False):  # 自愈重试也不可用
            results, meta = await hybrid_search(temp_engine, "学西班牙语", k=5)
        assert meta.mode == MODE_VECTOR
        assert meta.note == "bm25_unavailable"
        assert meta.bm25_ok is False
        assert [s.fact_id for s in results] == [f1.id]


# ═══════════════════════════════════════════════════════════════
# W5-1：跨轨检索工具
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def clean_tracks(_init_test_db):
    """清理测试用 users/groups 轨（引擎缓存在 _track_engines，reset_all 清数据）。"""
    keys: list[tuple[str, str]] = []
    yield keys
    for track, key in keys:
        try:
            get_track_engine(track, key).reset_all()
        except Exception:
            pass


class TestCrossTrackSearchTool:
    @pytest.mark.asyncio
    async def test_explicit_users_track_excludes_private(self, clean_tracks):
        ukey = platform_user_key("qq", "w5_fan_01")
        clean_tracks.append((TRACK_USERS, ukey))
        engine = get_track_engine(TRACK_USERS, ukey)
        _stub_vector_offline(engine)
        pub, priv = _seed_facts(
            engine,
            FactItem(content="w5粉丝喜欢下班后打羽毛球", category="preference", confidence=0.9, scope=SCOPE_GLOBAL),
            FactItem(content="w5粉丝私下说正在攒钱 secretly", category="context", confidence=0.9, scope=SCOPE_PRIVATE),
        )

        tool = LuomiNestMemorySearchTool()
        res = await tool.execute({"query": "打羽毛球", "track": "users", "user_key": ukey})
        assert res.success is True
        assert "羽毛球" in res.output
        assert res.metadata["track"] == "users"
        assert res.metadata["user_key"] == ukey
        assert " secretly" not in res.output
        assert pub.id in res.output

        # 缺 user_key → 降级 owner（不抛异常）
        res_missing = await tool.execute({"query": "羽毛球", "track": "users"})
        assert res_missing.success is True
        assert res_missing.metadata["degraded"] is True
        assert res_missing.metadata["track"] == "owner"

    @pytest.mark.asyncio
    async def test_groups_track_merged_with_speaker_users_and_no_private(self, clean_tracks):
        ukey = platform_user_key("qq", "w5_fan_02")
        gkey = platform_group_key("qq", "w5_group_01")
        clean_tracks.extend([(TRACK_USERS, ukey), (TRACK_GROUPS, gkey)])

        g_engine = get_track_engine(TRACK_GROUPS, gkey)
        u_engine = get_track_engine(TRACK_USERS, ukey)
        _stub_vector_offline(g_engine)
        _stub_vector_offline(u_engine)
        g_fact, _g_priv = _seed_facts(
            g_engine,
            FactItem(content="w5群约定每周五晚团建开黑", category="context", confidence=0.9, scope=SCOPE_GLOBAL),
            FactItem(content="w5群不应存在的私密事实", category="context", confidence=0.95, scope=SCOPE_PRIVATE),
        )
        u_fact = _seed_facts(
            u_engine,
            FactItem(content="w5粉丝是群里的活跃分子", category="context", confidence=0.85, scope=SCOPE_GLOBAL),
        )[0]

        tool = LuomiNestMemorySearchTool()
        res = await tool.execute({
            "query": "团建开黑 活跃分子", "track": "groups", "group_key": gkey, "user_key": ukey,
        })
        assert res.success is True
        assert res.metadata["track"] == "groups"
        # 两轨合并：群轨事实与说话人用户轨事实都返回，且标注来源轨
        assert "groups/" in res.output and "users/" in res.output
        assert g_fact.id in res.output and u_fact.id in res.output
        # 防泄露底线：groups 轨 private 事实绝不返回
        assert "不应存在的私密事实" not in res.output

    @pytest.mark.asyncio
    async def test_auto_degrades_to_owner_without_context(self, clean_tracks):
        tool = LuomiNestMemorySearchTool()
        with patch(
            "app.core.agents.cluster.agent_tool.get_luominest_parent_conv_id",
            return_value="",
        ):
            res = await tool.execute({"query": "任意查询词", "track": "auto"})
        assert res.success is True
        assert res.metadata["track"] == "owner"
        assert res.metadata["degraded"] is True
        assert "降级" in res.metadata["degrade_reason"]

    @pytest.mark.asyncio
    async def test_auto_resolves_platform_private_chat_to_users_track(self, clean_tracks):
        ukey = platform_user_key("qq", "w5_fan_03")
        clean_tracks.append((TRACK_USERS, ukey))
        engine = get_track_engine(TRACK_USERS, ukey)
        _stub_vector_offline(engine)
        priv = _seed_facts(
            engine,
            FactItem(content="w5私聊粉丝3月12日过生日", category="context", confidence=0.9, scope=SCOPE_PRIVATE),
        )[0]

        conv_meta = {
            "domain": "platform:inst1", "scene": "platform",
            "agent_id": None, "user_key": ukey,
        }
        tool = LuomiNestMemorySearchTool()
        with (
            patch("app.core.agents.cluster.agent_tool.get_luominest_parent_conv_id", return_value="conv-1"),
            patch(
                "app.infrastructure.database.conversation_store.conversation_store.get_meta",
                return_value=conv_meta,
            ),
        ):
            res = await tool.execute({"query": "生日", "track": "auto"})
        assert res.success is True
        assert res.metadata["track"] == "users"
        assert res.metadata["user_key"] == ukey
        assert res.metadata.get("degraded") is False
        # auto 判定的私聊（conv.user_key）→ 本人 private 事实可召回
        assert priv.id in res.output

    @pytest.mark.asyncio
    async def test_auto_resolves_workbench_to_owner(self, _init_test_db):
        # 工具的 owner 轨引擎经 get_track_engine(TRACK_OWNER) 解析（可能与
        # get_memory_engine() 的 _default 别名不同实例），必须用同一解析器播种
        engine = get_track_engine(TRACK_OWNER)
        _stub_vector_offline(engine)  # 单测不发真实 embedding 请求
        f = _seed_facts(
            engine,
            FactItem(content="主人最爱的 programming 语言是 Rust", category="knowledge", confidence=0.9),
        )[0]
        conv_meta = {"domain": "workbench", "scene": "workbench", "agent_id": None, "user_key": ""}
        tool = LuomiNestMemorySearchTool()
        with (
            patch("app.core.agents.cluster.agent_tool.get_luominest_parent_conv_id", return_value="conv-2"),
            patch(
                "app.infrastructure.database.conversation_store.conversation_store.get_meta",
                return_value=conv_meta,
            ),
        ):
            res = await tool.execute({"query": "Rust", "track": "auto"})
        assert res.success is True
        assert res.metadata["track"] == "owner"
        assert f.id in res.output


# ═══════════════════════════════════════════════════════════════
# W5-2：时间线与置顶工具
# ═══════════════════════════════════════════════════════════════


class TestMemoryDailyAndPinTools:
    @pytest.mark.asyncio
    async def test_get_daily_window_and_facts(self, temp_engine):
        engine = temp_engine
        with patch("app.core.tools.builtin.memory_tools._get_engine", return_value=engine):
            # 种两条每日记录（昨天 + 今天）
            from datetime import datetime, timedelta

            from zoneinfo import ZoneInfo

            tz = ZoneInfo("Asia/Shanghai")
            today = datetime.now(tz)
            today_str = today.strftime("%Y-%m-%d")
            yesterday_str = (today - timedelta(days=1)).strftime("%Y-%m-%d")
            engine.append_daily("早上陪主人晨跑五公里", date=yesterday_str)
            engine.append_daily("下午一起看了纪录片", date=today_str)
            fact = _seed_facts(
                engine,
                FactItem(content="主人喜欢晨跑后喝电解质水", category="preference", confidence=0.9),
            )[0]

            tool = MemoryGetDailyTool()
            # 最近 7 天 → 两天都有
            res = await tool.execute({"days": 7})
            assert res.success is True
            assert "晨跑五公里" in res.output and "纪录片" in res.output
            assert fact.id in res.output or "电解质水" in res.output
            assert set(res.metadata["dates_with_records"]) == {today_str, yesterday_str}

            # 只看昨天
            res_y = await tool.execute({"date": yesterday_str})
            assert res_y.success is True
            assert "晨跑五公里" in res_y.output
            assert "纪录片" not in res_y.output

            # date 格式校验
            res_bad = await tool.execute({"date": "2026/09/21"})
            assert res_bad.success is False

    @pytest.mark.asyncio
    async def test_pin_unpin_roundtrip(self, temp_engine):
        engine = temp_engine
        fact = _seed_facts(
            engine,
            FactItem(content="主人的结婚纪念日是10月1日", category="context", confidence=0.7),
        )[0]
        with patch("app.core.tools.builtin.memory_tools._get_engine", return_value=engine):
            tool = MemoryPinTool()
            res = await tool.execute({"fact_id": fact.id, "pinned": True})
            assert res.success is True
            assert engine.load_data().facts[0].pinned is True

            res_off = await tool.execute({"fact_id": fact.id, "pinned": False})
            assert res_off.success is True
            assert engine.load_data().facts[0].pinned is False

            res_missing = await tool.execute({"fact_id": "fact_not_exist"})
            assert res_missing.success is False

    def test_tools_registered_in_app_factory_section(self):
        """注册形态校验：工具可实例化且 schema 含关键参数（app_factory 注册段改动的前提）。"""
        pin = MemoryPinTool()
        assert pin.name == "memory_pin"
        assert "fact_id" in pin.parameters["properties"]
        daily = MemoryGetDailyTool()
        assert daily.name == "memory_get_daily"
        assert "days" in daily.parameters["properties"]


# ═══════════════════════════════════════════════════════════════
# W5-3：POST /api/v1/memory/search
# ═══════════════════════════════════════════════════════════════


class TestMemorySearchEndpoint:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_search_owner_track_response_fields(self, client, _init_test_db):
        engine = get_memory_engine()
        _stub_vector_offline(engine)  # 单测不发真实 embedding 请求
        f = _seed_facts(
            engine,
            FactItem(content="w5端点测试 主人喜欢收藏机械键盘", category="preference", confidence=0.9, pinned=True),
        )[0]
        resp = client.post("/api/v1/memory/search", json={"query": "机械键盘", "top_k": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        payload = data["data"]
        assert payload["query"] == "机械键盘"
        assert payload["track"] == "owner"
        assert payload["mode"] in (MODE_HYBRID, MODE_BM25)
        assert payload["bm25_ok"] is True
        hit = next(r for r in payload["results"] if r["fact_id"] == f.id)
        for field in ("content", "category", "confidence", "score", "pinned", "track", "user_key"):
            assert field in hit
        assert hit["pinned"] is True
        assert hit["track"] == "owner"
        assert "收藏机械键盘" in hit["content"]

    def test_search_users_track_private_filtered_by_default(self, client, _init_test_db, clean_tracks):
        ukey = platform_user_key("qq", "w5_ep_fan_01")
        clean_tracks.append((TRACK_USERS, ukey))
        engine = get_track_engine(TRACK_USERS, ukey)
        _stub_vector_offline(engine)
        pub, priv = _seed_facts(
            engine,
            FactItem(content="w5端点粉丝喜欢收藏邮票", category="preference", confidence=0.9, scope=SCOPE_GLOBAL),
            FactItem(content="w5端点粉丝的私密心愿", category="context", confidence=0.95, scope=SCOPE_PRIVATE),
        )
        body = {"query": "收藏邮票 私密心愿", "track": "users", "user_key": ukey, "top_k": 10}

        resp = client.post("/api/v1/memory/search", json=body)
        assert resp.status_code == 200
        results = resp.json()["data"]["results"]
        ids = [r["fact_id"] for r in results]
        assert pub.id in ids and priv.id not in ids
        assert all(r["user_key"] == ukey for r in results if r["track"] == "users")

        # include_private=True（主人管理页显式放开）
        resp2 = client.post("/api/v1/memory/search", json={**body, "include_private": True})
        ids2 = [r["fact_id"] for r in resp2.json()["data"]["results"]]
        assert priv.id in ids2

    def test_search_users_track_requires_user_key(self, client, _init_test_db):
        resp = client.post("/api/v1/memory/search", json={"query": "任意", "track": "users"})
        assert resp.status_code in (400, 422)

    def test_search_scope_conflict_rejected(self, client, _init_test_db, clean_tracks):
        ukey = platform_user_key("qq", "w5_ep_fan_02")
        clean_tracks.append((TRACK_USERS, ukey))
        resp = client.post(
            "/api/v1/memory/search",
            json={"query": "任意", "track": "users", "user_key": ukey, "scope": "private"},
        )
        assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════
# W5-6：forget 摘向量 + MAX_FACTS 挤出策略
# ═══════════════════════════════════════════════════════════════


class TestW56Fixes:
    @pytest.mark.asyncio
    async def test_fuzzy_forget_removes_vectors(self, temp_engine):
        engine = temp_engine
        f1, f2 = _seed_facts(
            engine,
            FactItem(content="主人养了一只叫煤球的黑猫", category="context", confidence=0.9),
            FactItem(content="主人喜欢喝乌龙茶", category="preference", confidence=0.9),
        )
        # 注入 mock 向量管理器，验证模糊遗忘分支同步摘除
        mock_vm = MagicMock()
        mock_vm.remove = AsyncMock()
        engine._vector_manager = mock_vm

        tool = MemoryForgetTool()
        with patch.object(
            __import__("app.core.tools.builtin.memory_tools", fromlist=["_get_engine"]),
            "_get_engine",
            return_value=engine,
        ):
            res = await tool.execute({"query": "黑猫"})

        assert res.success is True
        assert "已遗忘" in res.output
        data = engine.load_data()
        by_id = {f.id: f for f in data.facts}
        assert by_id[f1.id].is_latest is False  # 归档失效
        assert by_id[f2.id].is_latest is True
        # W5-6 核心：向量同步摘除
        mock_vm.remove.assert_awaited_once_with(f1.id)

    def test_trim_evicts_unpinned_lowest_confidence_first(self, temp_engine):
        engine = temp_engine
        engine._fact_manager.MAX_FACTS = 3  # 实例属性覆盖，便于构造
        facts = [
            FactItem(content="普通事实A 置信中", category="context", confidence=0.6),
            FactItem(content="普通事实B 置信最低", category="context", confidence=0.2),
            FactItem(content="置顶事实C 置信最低但受保护", category="context", confidence=0.1, pinned=True),
            FactItem(content="普通事实D 置信高", category="context", confidence=0.9),
        ]
        for f in facts:
            engine.add_fact(f)

        kept = {f.content for f in engine.load_data().facts}
        assert len(kept) == 3
        assert "置顶事实C 置信最低但受保护" in kept  # pinned 不被挤出（哪怕置信度最低）
        assert "普通事实D 置信高" in kept
        assert "普通事实B 置信最低" not in kept  # 未 pin 且最低置信被优先挤出

    def test_trim_tie_break_keeps_latest_version(self, temp_engine):
        engine = temp_engine
        engine._fact_manager.MAX_FACTS = 1
        old = FactItem(content="同名事实 旧版本", category="context", confidence=0.5)
        engine.add_fact(old)
        old.is_latest = False  # 模拟归档历史
        engine.save_data(engine.load_data())
        new = FactItem(content="同名事实 新版本", category="context", confidence=0.5)
        engine.add_fact(new)

        kept = engine.load_data().facts
        assert len(kept) == 1
        assert kept[0].is_latest is True

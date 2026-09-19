"""双轨（用户轨 + 群聊轨）与隐私隔离机制单元测试。

验证核心能力：
1. 隐私隔离底线（Anti-Leakage Guarantee）：
   - 群聊场景注入记忆时，用户的 private（私密心事）事实绝对不会泄露到群聊上下文中；
   - 1对1 私聊场景中，用户所有的 global、group 以及 private 记忆均可被博主完整获知。
2. 双轨画像注入（Dual-Track Injection）：
   - 群聊场景同时注入群专属设定 [群聊画像 · 群体设定] 与发言群友画像 [当前用户记忆]；
   - 私聊场景仅注入个人画像，不串扰群设定。
3. 群聊轨独立隔离（Group Track Isolation）：
   - TRACK_GROUPS = "groups" 具备独立的 profile / facts / summary / knowledge；
   - 与博主自身 (owner) 及粉丝个体 (users) 互不污染。
4. 记忆库统计与查询 API：
   - /memory/users 返回所有交互过的粉丝画像及事实统计；
   - /memory/groups 返回所有陪伴过的粉丝群画像及事实统计；
   - /memory/facts 支持携带 scope 参数精确检索与写入。
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints.memory import router as memory_router
from app.core.domain_policy import (
    MAIN_AGENT_ID,
    TRACK_GROUPS,
    TRACK_USERS,
    group_member_user_key,
    platform_group_key,
    platform_user_key,
)
from app.engines.memory import get_track_engine
from app.engines.memory.models import (
    SCOPE_GLOBAL,
    SCOPE_GROUP,
    SCOPE_PRIVATE,
    FactItem,
)
from app.services.context_service import ContextService

app = FastAPI()
# memory_router 内部自带 prefix="/memory"，此处挂载在 "/api/v1" 下
app.include_router(memory_router, prefix="/api/v1")


@pytest.fixture
def clean_dual_tracks(_init_test_db):
    """清理测试中使用的用户轨和群聊轨数据。"""
    user_keys: list[str] = []
    group_keys: list[str] = []
    yield user_keys, group_keys
    for k in user_keys:
        try:
            get_track_engine(TRACK_USERS, k).reset_all()
        except Exception:
            pass
    for k in group_keys:
        try:
            get_track_engine(TRACK_GROUPS, k).reset_all()
        except Exception:
            pass


class TestScopedFactsPrivacy:
    """测试三级隐私范围隔离（global / group / private）。"""

    def test_private_facts_never_leaked_in_group_context(self, clean_dual_tracks):
        """核心安全性检验：群聊场景下 private 事实 100% 隔离不泄露。"""
        user_keys, _ = clean_dual_tracks
        ukey = platform_user_key("qq", "fan_secret_01")
        user_keys.append(ukey)

        engine = get_track_engine(TRACK_USERS, ukey)
        data = engine.load_data()
        data.facts.append(FactItem(
            content="喜欢在直播间给博主送棒棒糖",
            category="preference",
            confidence=0.9,
            scope=SCOPE_GLOBAL,
        ))
        data.facts.append(FactItem(
            content="群内头衔是水群大队长",
            category="preference",
            confidence=0.9,
            scope=SCOPE_GROUP,
            group_id="qq_group_100",
        ))
        data.facts.append(FactItem(
            content="曾在凌晨私信博主倾诉暗恋与失恋的心事",
            category="preference",
            confidence=0.95,
            scope=SCOPE_PRIVATE,
        ))
        engine.save_data(data)

        # 1. 模拟群聊注入：allowed_scopes = {"global", "group"}
        group_ctx = engine.build_context_sync(allowed_scopes={"global", "group"})
        assert "喜欢在直播间给博主送棒棒糖" in group_ctx
        assert "群内头衔是水群大队长" in group_ctx
        assert "曾在凌晨私信博主倾诉暗恋与失恋的心事" not in group_ctx, "严重安全漏洞：私密心事泄露到了群聊上下文中！"

        # 2. 模拟1对1私聊注入：allowed_scopes = {"global", "group", "private"}
        dm_ctx = engine.build_context_sync(allowed_scopes={"global", "group", "private"})
        assert "喜欢在直播间给博主送棒棒糖" in dm_ctx
        assert "群内头衔是水群大队长" in dm_ctx
        assert "曾在凌晨私信博主倾诉暗恋与失恋的心事" in dm_ctx, "私聊场景应可获知用户的私密心事"


class TestDualTrackContextInjection:
    """测试 ContextService 的双轨画像自动编排。"""

    @pytest.mark.asyncio
    async def test_inject_memory_in_group_chat_injects_group_and_user_without_private(self, clean_dual_tracks):
        user_keys, group_keys = clean_dual_tracks
        sender_id = "fan_999"
        group_id = "group_888"
        ukey = group_member_user_key("qq", "inst1", sender_id)
        gkey = platform_group_key("qq", group_id)
        user_keys.append(ukey)
        group_keys.append(gkey)

        # 播种群聊设定
        g_engine = get_track_engine(TRACK_GROUPS, gkey)
        g_data = g_engine.load_data()
        g_data.profile.name = "辰汐粉丝后援会一号群"
        g_data.facts.append(FactItem(
            content="本群规矩：进群发女装照，禁发无端广告",
            category="preference",
            confidence=1.0,
            scope=SCOPE_GROUP,
            group_id=group_id,
        ))
        g_engine.save_data(g_data)

        # 播种群成员画像
        u_engine = get_track_engine(TRACK_USERS, ukey)
        u_data = u_engine.load_data()
        u_data.profile.name = "小明"
        u_data.facts.append(FactItem(
            content="每次博主开播都会抢第一条弹幕",
            category="preference",
            confidence=0.9,
            scope=SCOPE_GLOBAL,
        ))
        u_data.facts.append(FactItem(
            content="现实中真实姓名叫张三，家庭住址在朝阳区",
            category="preference",
            confidence=0.98,
            scope=SCOPE_PRIVATE,
        ))
        u_engine.save_data(u_data)

        svc = ContextService()
        messages = [{"role": "user", "content": "主播好呀！"}]

        injected = await svc.inject_memory(
            messages=messages,
            agent_id=MAIN_AGENT_ID,
            domain="platform:inst1",
            user_key=ukey,
            group_id=group_id,
        )

        sys_content = injected[0]["content"]

        # 必须包含群画像
        assert "辰汐粉丝后援会一号群" in sys_content
        assert "本群规矩：进群发女装照" in sys_content

        # 必须包含发言群友画像（公开部分）
        assert "抢第一条弹幕" in sys_content

        # 绝对不能包含私密隐私（住址、真实姓名）
        assert "家庭住址在朝阳区" not in sys_content
        assert "张三" not in sys_content


class TestGroupTrackIsolation:
    """测试群聊轨独立存储与隔离性。"""

    def test_group_track_data_isolation(self, clean_dual_tracks):
        user_keys, group_keys = clean_dual_tracks
        gkey1 = platform_group_key("tg", "tg_chat_111")
        gkey2 = platform_group_key("tg", "tg_chat_222")
        group_keys.extend([gkey1, gkey2])

        eng1 = get_track_engine(TRACK_GROUPS, gkey1)
        eng2 = get_track_engine(TRACK_GROUPS, gkey2)

        data1 = eng1.load_data()
        data1.profile.name = "TG 二次元交流群"
        data1.facts.append(FactItem(content="群专属梗：大鸟转转转", category="context", scope=SCOPE_GROUP))
        eng1.save_data(data1)

        data2 = eng2.load_data()
        data2.profile.name = "TG 游戏开黑群"
        data2.facts.append(FactItem(content="群专属梗：今晚 Apex 不见不散", category="context", scope=SCOPE_GROUP))
        eng2.save_data(data2)

        ctx1 = eng1.build_context_sync()
        ctx2 = eng2.build_context_sync()

        assert "二次元交流群" in ctx1
        assert "大鸟转转转" in ctx1
        assert "游戏开黑群" not in ctx1
        assert "Apex" not in ctx1

        assert "游戏开黑群" in ctx2
        assert "Apex" in ctx2
        assert "二次元交流群" not in ctx2


class TestMemoryApiEndpoints:
    """测试记忆中枢 API 接口（用户画像列表、群聊画像列表、Scoped 事实 CRUD）。"""

    def test_query_users_and_groups_endpoints(self, clean_dual_tracks):
        user_keys, group_keys = clean_dual_tracks
        ukey = platform_user_key("wechat", "wx_user_abc")
        gkey = platform_group_key("wechat", "wx_room_xyz")
        user_keys.append(ukey)
        group_keys.append(gkey)

        u_eng = get_track_engine(TRACK_USERS, ukey)
        u_data = u_eng.load_data()
        u_data.profile.name = "微信老粉"
        u_data.facts.append(FactItem(content="微信端忠实粉丝", category="preference", scope=SCOPE_GLOBAL))
        u_eng.save_data(u_data)

        g_eng = get_track_engine(TRACK_GROUPS, gkey)
        g_data = g_eng.load_data()
        g_data.profile.name = "微信VIP粉丝群"
        g_data.facts.append(FactItem(content="VIP专属群设定", category="preference", scope=SCOPE_GROUP))
        g_eng.save_data(g_data)

        client = TestClient(app)

        # GET /api/v1/memory/users
        res_users = client.get("/api/v1/memory/users")
        assert res_users.status_code == 200
        users_list = res_users.json().get("data", {}).get("users", [])
        matched_user = next((u for u in users_list if u["user_key"] == ukey), None)
        assert matched_user is not None
        assert matched_user["platform"] == "wechat"
        assert matched_user["fact_count"] >= 1

        # GET /api/v1/memory/groups
        res_groups = client.get("/api/v1/memory/groups")
        assert res_groups.status_code == 200
        groups_list = res_groups.json().get("data", {}).get("groups", [])
        matched_group = next((g for g in groups_list if g["group_key"] == gkey), None)
        assert matched_group is not None
        assert matched_group["platform"] == "wechat"
        assert matched_group["fact_count"] >= 1

    def test_facts_crud_with_scope(self, clean_dual_tracks):
        user_keys, _ = clean_dual_tracks
        ukey = platform_user_key("qq", "test_scope_crud_user")
        user_keys.append(ukey)

        client = TestClient(app)

        # 1. 创建私密事实
        res_add = client.post(
            f"/api/v1/memory/facts?track=users&user_key={ukey}",
            json={
                "content": "这是一条私密的心情随笔",
                "category": "preference",
                "confidence": 0.85,
                "scope": "private",
            },
        )
        assert res_add.status_code == 200
        created = res_add.json().get("data", {}).get("fact", {})
        fact_id = created.get("id")
        assert fact_id is not None
        assert created.get("scope") == "private"

        # 2. 按 scope=private 过滤
        res_filter_priv = client.get(f"/api/v1/memory/facts?track=users&user_key={ukey}&scope=private")
        assert res_filter_priv.status_code == 200
        facts_priv = res_filter_priv.json().get("data", {}).get("facts", [])
        assert any(f["id"] == fact_id for f in facts_priv)

        # 3. 按 scope=global 过滤（不应包含该私密事实）
        res_filter_glob = client.get(f"/api/v1/memory/facts?track=users&user_key={ukey}&scope=global")
        assert res_filter_glob.status_code == 200
        facts_glob = res_filter_glob.json().get("data", {}).get("facts", [])
        assert not any(f["id"] == fact_id for f in facts_glob)

        # 4. 更新 scope 为 global
        res_patch = client.patch(
            f"/api/v1/memory/facts/{fact_id}?track=users&user_key={ukey}",
            json={"scope": "global"},
        )
        assert res_patch.status_code == 200

        # 5. 验证更新后进入 global 过滤
        res_filter_glob2 = client.get(f"/api/v1/memory/facts?track=users&user_key={ukey}&scope=global")
        assert res_filter_glob2.status_code == 200
        facts_glob2 = res_filter_glob2.json().get("data", {}).get("facts", [])
        assert any(f["id"] == fact_id for f in facts_glob2)

        # 6. 删除事实
        res_del = client.delete(f"/api/v1/memory/facts/{fact_id}?track=users&user_key={ukey}")
        assert res_del.status_code == 200

"""P0-1 定时任务闭环回归测试。

覆盖三块根因修复：
1. date/interval/cron 三种任务 持久化 → 恢复 round-trip 不丢失不变形
   （date 走 run_at 列，不再产生 "* * * * *" 幻象 cron；interval 保留 interval_seconds）
2. 迁移探测补列与旧行回填（临时 SQLite 文件，按旧表结构验证 ALTER + 回填）
3. task_result_dispatcher 路由逻辑（mock SubagentExecutor 与平台发送）：
   - web 来源 → 结果作为 [定时任务] 前缀 assistant 消息写回会话（开关可关）
   - platform 来源 → 群/私聊目标推导 + 显式目标优先 + 发送失败降级任务事件
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, inspect, text

from app.core.config import settings
from app.core.scheduler.manager import LuomiSchedulerManager, luominest_scheduler
from app.core.scheduler.models import (
    ORIGIN_API,
    ORIGIN_PLATFORM,
    ORIGIN_WEB_CONVERSATION,
    LuomiTaskStatus,
    LuomiTaskType,
    ScheduledTaskConfig,
    TaskEvent,
)
from app.infrastructure.database.config_store import luominest_config_store
from app.infrastructure.database.conversation_store import conversation_store
from app.services.scheduled_task_persistence import (
    list_scheduled_tasks,
    save_scheduled_task,
)
from app.services.task_result_dispatcher import TaskResultDispatcher, task_result_dispatcher


# ── 公共夹具 ──

@pytest.fixture
def clean_scheduler(_init_test_db):
    """隔离调度器单例的内存状态与事件回调，测试后复原。

    默认注入 FakeSubagentExecutor，防止未显式设 executor 的用例经
    subagent_delegation 端口兜底走真实子 Agent/LLM 调用。
    """
    saved_tasks = dict(luominest_scheduler._tasks)
    saved_callbacks = list(luominest_scheduler._event_callbacks)
    saved_executor = luominest_scheduler._task_executor
    luominest_scheduler._tasks.clear()
    luominest_scheduler._event_callbacks.clear()
    luominest_scheduler._task_executor = FakeSubagentExecutor()
    yield luominest_scheduler
    luominest_scheduler._tasks.clear()
    luominest_scheduler._tasks.update(saved_tasks)
    luominest_scheduler._event_callbacks = saved_callbacks
    luominest_scheduler._task_executor = saved_executor


def _trigger_of(config):
    """经调度器单例构建 APScheduler trigger（验证恢复后的配置可被调度器接受）。"""
    return luominest_scheduler._build_trigger(config)


def _make_info(task_id: str, task_type: str, *, origin_kind: str = ORIGIN_API,
               origin_ref: str = "", origin_target: str = "", **extra) -> dict:
    """构造与 manager.add_task/_reschedule_task 同构的内存任务信息 dict。"""
    info = {
        "id": task_id,
        "name": f"任务-{task_id}",
        "description": "",
        "task_type": task_type,
        "status": LuomiTaskStatus.PENDING.value,
        "run_date": None,
        "cron_year": None,
        "cron_month": None,
        "cron_day": None,
        "cron_week": None,
        "cron_day_of_week": None,
        "cron_hour": None,
        "cron_minute": None,
        "cron_second": None,
        "interval_seconds": None,
        "payload": {"instruction": "执行测试指令", "context": ""},
        "source": "main_agent",
        "origin_kind": origin_kind,
        "origin_ref": origin_ref,
        "origin_target": origin_target,
    }
    info.update(extra)
    return info


# ── 1. round-trip：持久化 → 恢复 ──

@pytest.mark.usefixtures("_init_test_db")
class TestPersistenceRoundTrip:
    @pytest.mark.asyncio
    async def test_date_task_round_trip_keeps_run_at(self):
        """date 任务：run_at 列保存执行时间，恢复后 run_date 一致且无幻象 cron。"""
        run_at = (datetime.now() + timedelta(days=1)).replace(microsecond=0).isoformat()
        info = _make_info("rt-date-1", "date", run_date=run_at,
                          origin_kind=ORIGIN_WEB_CONVERSATION, origin_ref="conv-rt")

        fields = LuomiSchedulerManager._task_info_to_db_fields(info)
        await save_scheduled_task(
            task_id="rt-date-1", name=info["name"], description="",
            created_from=info["source"], **fields,
        )
        row = {t["task_id"]: t for t in await list_scheduled_tasks()}["rt-date-1"]

        # 持久化侧：schedule_cron 不再是 "* * * * *" 幻象 cron
        assert row["trigger_type"] == "date"
        assert row["run_at"] == run_at
        assert row["schedule_cron"] == ""
        assert row["origin_kind"] == ORIGIN_WEB_CONVERSATION
        assert row["origin_ref"] == "conv-rt"

        # 恢复侧：run_date 还原，可被 _build_trigger 解析
        config = LuomiSchedulerManager._db_task_to_config(row)
        assert config.task_type.value == "date"
        assert config.run_date == run_at
        assert _trigger_of(config) is not None

    @pytest.mark.asyncio
    async def test_interval_task_round_trip_keeps_seconds(self):
        """interval 任务：interval_seconds 持久化并原样恢复（不再一律降级 3600s）。"""
        info = _make_info("rt-int-1", "interval", interval_seconds=1800)

        fields = LuomiSchedulerManager._task_info_to_db_fields(info)
        await save_scheduled_task(
            task_id="rt-int-1", name=info["name"], description="",
            created_from=info["source"], **fields,
        )
        row = {t["task_id"]: t for t in await list_scheduled_tasks()}["rt-int-1"]

        assert row["trigger_type"] == "interval"
        assert row["interval_seconds"] == 1800

        config = LuomiSchedulerManager._db_task_to_config(row)
        assert config.task_type.value == "interval"
        assert config.interval_seconds == 1800
        assert _trigger_of(config) is not None

    @pytest.mark.asyncio
    async def test_cron_task_round_trip(self):
        """cron 任务：五段表达式拆字段保存、恢复后字段一致。"""
        info = _make_info("rt-cron-1", "cron", cron_minute="30", cron_hour="8")

        fields = LuomiSchedulerManager._task_info_to_db_fields(info)
        await save_scheduled_task(
            task_id="rt-cron-1", name=info["name"], description="",
            created_from=info["source"], **fields,
        )
        row = {t["task_id"]: t for t in await list_scheduled_tasks()}["rt-cron-1"]

        assert row["trigger_type"] == "cron"
        assert row["schedule_cron"] == "30 8 * * *"

        config = LuomiSchedulerManager._db_task_to_config(row)
        assert config.task_type.value == "cron"
        assert config.cron_minute == "30"
        assert config.cron_hour == "8"
        assert _trigger_of(config) is not None

    def test_legacy_rows_recover(self):
        """旧数据兜底：trigger_type 为空时按遗留 schedule_type 映射；interval 缺秒降级 3600s 并可见。"""
        legacy_interval = LuomiSchedulerManager._db_task_to_config({
            "task_id": "old-1", "schedule_type": "interval",
            "schedule_cron": "", "trigger_type": "", "interval_seconds": None,
        })
        assert legacy_interval.task_type.value == "interval"
        assert legacy_interval.interval_seconds == 3600  # 显式告警后的降级值

        legacy_cron = LuomiSchedulerManager._db_task_to_config({
            "task_id": "old-2", "schedule_type": "cron",
            "schedule_cron": "0 9 * * *", "trigger_type": "",
        })
        assert legacy_cron.task_type.value == "cron"
        assert legacy_cron.cron_minute == "0"

        # 旧 date 行（幻象 cron，run_at 不可恢复）必须显式报错跳过，而非解析崩溃
        with pytest.raises(ValueError):
            LuomiSchedulerManager._db_task_to_config({
                "task_id": "old-3", "schedule_type": "date",
                "schedule_cron": "* * * * *", "trigger_type": "",
            })


# ── 2. 迁移：探测补列 + 旧行回填 ──

class TestScheduledTasksMigration:
    OLD_DDL = """
        CREATE TABLE scheduled_tasks (
            task_id VARCHAR(64) PRIMARY KEY,
            name VARCHAR(128) DEFAULT '',
            schedule_cron VARCHAR(128) DEFAULT '',
            schedule_type VARCHAR(16) DEFAULT 'cron',
            action TEXT DEFAULT '',
            description TEXT,
            context TEXT,
            created_from VARCHAR(16) DEFAULT 'manual',
            is_active BOOLEAN DEFAULT 1,
            created_at VARCHAR(64) DEFAULT '',
            last_run_at VARCHAR(64)
        )
    """

    def _make_legacy_db(self, url: str) -> None:
        engine = create_engine(url)
        with engine.begin() as conn:
            conn.execute(text(self.OLD_DDL))
            conn.execute(text(
                "INSERT INTO scheduled_tasks (task_id, name, schedule_cron, schedule_type, action, is_active, created_at) "
                "VALUES ('m-cron', 'c', '0 8 * * *', 'cron', 'do', 1, '2026-01-01'),"
                "       ('m-int', 'i', '* * * * *', 'interval', 'do', 1, '2026-01-01'),"
                "       ('m-date', 'd', '* * * * *', 'date', 'do', 1, '2026-01-01'),"
                "       ('m-once', 'o', '2026-06-21T08:00:00', 'once', 'do', 1, '2026-01-01')"
            ))
        engine.dispose()

    def test_migrate_adds_columns_and_backfills(self, tmp_path):
        """旧库补 6 列；旧行按 schedule_type 回填 trigger_type，疑似 ISO 串回填 run_at。"""
        db_file = tmp_path / "legacy.db"
        url = f"sqlite:///{db_file.as_posix()}"
        self._make_legacy_db(url)

        from app.infrastructure.database.engine import _migrate_scheduled_tasks_sync

        engine = create_engine(url)
        with engine.begin() as conn:
            inspector = inspect(conn)
            _migrate_scheduled_tasks_sync(conn, inspector)

            cols = {c["name"] for c in inspect(conn).get_columns("scheduled_tasks")}
            assert {"trigger_type", "run_at", "interval_seconds",
                    "origin_kind", "origin_ref", "origin_target"} <= cols

            rows = {
                r[0]: r[1]
                for r in conn.execute(text(
                    "SELECT task_id, trigger_type || '|' || COALESCE(run_at, '') FROM scheduled_tasks"
                )).fetchall()
            }

        engine.dispose()
        assert rows["m-cron"] == "cron|"
        assert rows["m-int"] == "interval|"
        # 幻象 cron 的旧 date 行：run_at 保持空（无法恢复，恢复端告警跳过）
        assert rows["m-date"] == "date|"
        # 历史手工写入的 ISO 串尽力抢救为 run_at
        assert rows["m-once"] == "date|2026-06-21T08:00:00"

    def test_migrate_idempotent(self, tmp_path):
        """重复执行迁移不报错、不重复回填（幂等）。"""
        db_file = tmp_path / "legacy2.db"
        url = f"sqlite:///{db_file.as_posix()}"
        self._make_legacy_db(url)

        from app.infrastructure.database.engine import _migrate_scheduled_tasks_sync

        engine = create_engine(url)
        with engine.begin() as conn:
            _migrate_scheduled_tasks_sync(conn, inspect(conn))
            # 第二遍：列已存在、无空 trigger_type 行，应空操作
            _migrate_scheduled_tasks_sync(conn, inspect(conn))
            count = conn.execute(
                text("SELECT COUNT(*) FROM scheduled_tasks WHERE trigger_type = ''")
            ).scalar()
        engine.dispose()
        assert count == 0

    @pytest.mark.asyncio
    async def test_init_db_creates_new_columns(self, _init_test_db):
        """生产建表路径（create_all + 迁移）出来的新库自带全部新列。"""
        from app.infrastructure.database.engine import sync_engine

        with sync_engine.connect() as conn:
            cols = {c["name"] for c in inspect(conn).get_columns("scheduled_tasks")}
        assert {"trigger_type", "run_at", "interval_seconds",
                "origin_kind", "origin_ref", "origin_target"} <= cols


# ── 3. dispatcher 路由 ──

class FakeSubagentExecutor:
    """SubagentExecutor 测试替身：记录调用并返回固定结果。"""

    def __init__(self, result: str = "子 Agent 执行结果文本"):
        self.calls: list[dict] = []
        self._result = result

    async def execute(self, *, task: str, context: str = "", depth: int = 0, **kwargs):
        self.calls.append({"task": task, "context": context, "depth": depth})
        return self._result


class TestTaskResultDispatcher:
    @pytest.fixture
    def dispatcher_wired(self, clean_scheduler):
        """把 dispatcher 注册为调度器事件回调（组合根同款接线），收集全部事件。"""
        seen_events: list[TaskEvent] = []

        async def _collector(event: TaskEvent) -> None:
            seen_events.append(event)

        clean_scheduler.add_event_callback(task_result_dispatcher.handle_task_event)
        clean_scheduler.add_event_callback(_collector)
        return seen_events

    @staticmethod
    async def _ensure_conversation(conv_id: str) -> None:
        now = "2026-09-26T00:00:00"
        await conversation_store.set_async(conv_id, {
            "id": conv_id, "title": "测试会话", "agent_id": "main",
            "messages": [], "created_at": now, "updated_at": now,
        })

    @pytest.mark.asyncio
    async def test_web_origin_result_written_to_conversation(
        self, clean_scheduler, dispatcher_wired
    ):
        """web 来源：触发完成 → mock 执行器结果带 [定时任务] 前缀写回会话。"""
        await self._ensure_conversation("conv-p0-1")
        executor = FakeSubagentExecutor()
        clean_scheduler._task_executor = executor
        clean_scheduler._tasks["t-web"] = _make_info(
            "t-web", "date", origin_kind=ORIGIN_WEB_CONVERSATION, origin_ref="conv-p0-1",
        )

        await clean_scheduler._execute_task("t-web")

        assert len(executor.calls) == 1
        assert executor.calls[0]["task"] == "执行测试指令"
        assert clean_scheduler._tasks["t-web"]["last_result"] == "子 Agent 执行结果文本"

        conv = await conversation_store.get_async("conv-p0-1")
        tail = conv["messages"][-1]
        assert tail["role"] == "assistant"
        assert tail["content"].startswith("[定时任务]《任务-t-web》")
        assert "子 Agent 执行结果文本" in tail["content"]
        # 任务面板轮询侧：COMPLETED 事件带结果
        statuses = [e.status for e in dispatcher_wired]
        assert LuomiTaskStatus.COMPLETED in statuses

    @pytest.mark.asyncio
    async def test_result_into_chat_disabled_keeps_result_in_task(
        self, clean_scheduler, dispatcher_wired, monkeypatch
    ):
        """SCHEDULER_RESULT_INTO_CHAT=false：不写会话，结果仅保留在任务记录。"""
        monkeypatch.setattr(settings, "SCHEDULER_RESULT_INTO_CHAT", False)
        await self._ensure_conversation("conv-off")
        clean_scheduler._tasks["t-off"] = _make_info(
            "t-off", "date", origin_kind=ORIGIN_WEB_CONVERSATION, origin_ref="conv-off",
        )

        await clean_scheduler._execute_task("t-off")

        conv = await conversation_store.get_async("conv-off")
        assert conv["messages"] == []
        assert clean_scheduler._tasks["t-off"]["last_result"] is not None

    @pytest.mark.asyncio
    async def test_platform_origin_group_target_derived_from_session_mapping(
        self, clean_scheduler, dispatcher_wired, monkeypatch
    ):
        """platform 来源：无显式目标时按会话映射 is_group 推导 group/private 目标。"""
        sent: list[tuple[str, str, str]] = []

        async def _fake_send(instance_id: str, target: str, content: str) -> bool:
            sent.append((instance_id, target, content))
            return True

        monkeypatch.setattr(
            "app.services.task_result_dispatcher.TaskResultDispatcher._send_via_platform",
            staticmethod(_fake_send),
        )
        clean_scheduler._tasks["t-plat"] = _make_info(
            "t-plat", "date", origin_kind=ORIGIN_PLATFORM, origin_ref="inst-qq:888",
        )

        # 会话映射标记为群聊 → 目标推导为 group:888
        from app.infrastructure.database.config_store import luominest_config_store
        luominest_config_store.set("platform.sessions.inst-qq:888", {"is_group": True})

        await clean_scheduler._execute_task("t-plat")

        assert len(sent) == 1
        inst, target, content = sent[0]
        assert (inst, target) == ("inst-qq", "group:888")
        assert content.startswith("[定时任务]《任务-t-plat》")

        luominest_config_store.delete("platform.sessions.inst-qq:888")

    @pytest.mark.asyncio
    async def test_platform_explicit_target_wins(
        self, clean_scheduler, dispatcher_wired, monkeypatch
    ):
        """D5：用户显式指定投递目标时优先于会话映射推导。"""
        sent: list[tuple[str, str]] = []

        async def _fake_send(instance_id: str, target: str, content: str) -> bool:
            sent.append((instance_id, target))
            return True

        monkeypatch.setattr(
            "app.services.task_result_dispatcher.TaskResultDispatcher._send_via_platform",
            staticmethod(_fake_send),
        )
        clean_scheduler._tasks["t-plat2"] = _make_info(
            "t-plat2", "date", origin_kind=ORIGIN_PLATFORM, origin_ref="inst-qq:888",
            origin_target="private:42",
        )

        await clean_scheduler._execute_task("t-plat2")
        assert sent == [("inst-qq", "private:42")]

    @pytest.mark.asyncio
    async def test_platform_send_failure_degrades_to_task_event(
        self, clean_scheduler, dispatcher_wired, monkeypatch
    ):
        """平台发送失败：降级补发任务事件通知，结果不丢（保留在任务记录）。"""
        async def _fail_send(instance_id: str, target: str, content: str) -> bool:
            return False

        monkeypatch.setattr(
            "app.services.task_result_dispatcher.TaskResultDispatcher._send_via_platform",
            staticmethod(_fail_send),
        )
        clean_scheduler._tasks["t-fail"] = _make_info(
            "t-fail", "date", origin_kind=ORIGIN_PLATFORM, origin_ref="inst-off:1",
        )

        await clean_scheduler._execute_task("t-fail")

        assert clean_scheduler._tasks["t-fail"]["last_result"] is not None
        degrade_events = [e for e in dispatcher_wired if "结果已保留在任务记录" in e.message]
        assert degrade_events, "发送失败应补发降级任务事件"

    @pytest.mark.asyncio
    async def test_api_origin_skips_delivery(self, clean_scheduler, dispatcher_wired):
        """api 来源：无会话可回投，仅保留任务记录（不抛错）。"""
        clean_scheduler._tasks["t-api"] = _make_info(
            "t-api", "date", origin_kind=ORIGIN_API, origin_ref="",
        )
        await clean_scheduler._execute_task("t-api")
        assert clean_scheduler._tasks["t-api"]["last_result"] is not None
        assert [e for e in dispatcher_wired if e.status == LuomiTaskStatus.COMPLETED]

    @pytest.mark.asyncio
    async def test_failed_event_reports_error(self, clean_scheduler, dispatcher_wired):
        """执行失败：FAILED 事件携带错误信息，投递器不把失败当成功回投。"""
        class _BoomExecutor:
            async def execute(self, *, task: str, **kwargs):
                raise RuntimeError("子 Agent 爆炸")

        await self._ensure_conversation("conv-boom")
        clean_scheduler._task_executor = _BoomExecutor()
        clean_scheduler._tasks["t-boom"] = _make_info(
            "t-boom", "date", origin_kind=ORIGIN_WEB_CONVERSATION, origin_ref="conv-boom",
        )

        await clean_scheduler._execute_task("t-boom")

        failed = [e for e in dispatcher_wired if e.status == LuomiTaskStatus.FAILED]
        assert failed and "子 Agent 爆炸" in failed[-1].error
        # 失败结果同样回投会话（带失败标记），主不再留 silent
        conv = await conversation_store.get_async("conv-boom")
        assert "执行失败" in conv["messages"][-1]["content"]


# ── 4. 创建来源探测 ──

class TestDetectTaskOrigin:
    def test_platform_context_wins(self):
        from app.core.tools.builtin.scheduler_tool import (
            _platform_task_origin_var,
            detect_task_origin,
            set_platform_task_origin,
        )

        set_platform_task_origin("inst-1", "group-9", is_group=True, platform="qq")
        kind, ref, target = detect_task_origin()
        assert (kind, ref, target) == (ORIGIN_PLATFORM, "inst-1:group-9", "")
        _platform_task_origin_var.set(None)

    def test_web_conversation_from_parent_conv_id(self):
        from app.core.agents.cluster.agent_tool import set_luominest_parent_conv_id
        from app.core.tools.builtin.scheduler_tool import (
            _platform_task_origin_var,
            detect_task_origin,
        )

        _platform_task_origin_var.set(None)
        token = set_luominest_parent_conv_id("conv-abc")
        kind, ref, _ = detect_task_origin()
        assert (kind, ref) == (ORIGIN_WEB_CONVERSATION, "conv-abc")
        set_luominest_parent_conv_id("")

    def test_fallback_to_api(self):
        from app.core.agents.cluster.agent_tool import set_luominest_parent_conv_id
        from app.core.tools.builtin.scheduler_tool import (
            _platform_task_origin_var,
            detect_task_origin,
        )

        _platform_task_origin_var.set(None)
        set_luominest_parent_conv_id("")
        assert detect_task_origin() == (ORIGIN_API, "", "")


# ── 5. 配置创建入参 ──

def test_config_defaults_to_api_origin():
    """ScheduledTaskConfig 未显式指定来源时默认 api（REST 直连路径的安全默认）。"""
    config = ScheduledTaskConfig(
        name="n", task_type="interval", interval_seconds=60,
        payload={"instruction": "x"},
    )
    assert config.origin_kind == ORIGIN_API
    assert config.origin_ref == ""
    assert config.origin_target == ""


# ── 6. REST 端点（/scheduled-tasks）持久化分支 ──

@pytest.mark.usefixtures("_init_test_db")
class TestScheduledTasksApi:
    @pytest.mark.asyncio
    async def test_create_once_task_persists_date_trigger(self):
        """once 类型：run_at 落列、不再产生幻象 cron，来源标 api。"""
        from app.api.v1.endpoints.scheduled_tasks import (
            CreateScheduledTaskRequest,
            create_scheduled_task,
        )

        run_at = "2026-10-01T08:00:00"
        resp = await create_scheduled_task(CreateScheduledTaskRequest(
            name="发布会提醒", schedule_cron=run_at, schedule_type="once",
            action="提醒我", run_at=run_at,
        ))
        assert resp["success"] is True

        row = {t["task_id"]: t for t in await list_scheduled_tasks()}[resp["task_id"]]
        assert row["trigger_type"] == "date"
        assert row["run_at"] == run_at
        assert row["schedule_cron"] == ""
        assert row["origin_kind"] == ORIGIN_API

    @pytest.mark.asyncio
    async def test_create_legacy_once_falls_back_to_schedule_cron_field(self):
        """兼容旧客户端：once 未传 run_at 时从 schedule_cron 字段抢救执行时间。"""
        from app.api.v1.endpoints.scheduled_tasks import (
            CreateScheduledTaskRequest,
            create_scheduled_task,
        )

        resp = await create_scheduled_task(CreateScheduledTaskRequest(
            name="旧客户端任务", schedule_cron="2026-10-02T09:30:00", schedule_type="once",
            action="提醒我",
        ))
        row = {t["task_id"]: t for t in await list_scheduled_tasks()}[resp["task_id"]]
        assert row["trigger_type"] == "date"
        assert row["run_at"] == "2026-10-02T09:30:00"

    @pytest.mark.asyncio
    async def test_create_cron_task_keeps_expression(self):
        """cron 类型：表达式原样落 schedule_cron，trigger_type=cron。"""
        from app.api.v1.endpoints.scheduled_tasks import (
            CreateScheduledTaskRequest,
            create_scheduled_task,
        )

        resp = await create_scheduled_task(CreateScheduledTaskRequest(
            name="每日播报", schedule_cron="30 7 * * *", schedule_type="cron",
            action="播报",
        ))
        row = {t["task_id"]: t for t in await list_scheduled_tasks()}[resp["task_id"]]
        assert row["trigger_type"] == "cron"
        assert row["schedule_cron"] == "30 7 * * *"
        assert row["run_at"] is None


# ── 7. dispatcher 补强：分支级单元测试 ──

class TestTaskResultDispatcherBranches:
    """直接驱动 handle_task_event 与私有小方法，覆盖既有 e2e 用例未触及的分支。

    网络与存储全部 mock（append_message_async / _send_via_platform / platform_router），
    来源解析走 clean_scheduler 隔离后的真实调度器内存态。
    """

    @pytest.fixture
    def wired(self, clean_scheduler):
        """组合根同款接线（dispatcher + 事件收集器），收集全部事件供降级断言。"""
        seen_events: list[TaskEvent] = []

        async def _collector(event: TaskEvent) -> None:
            seen_events.append(event)

        clean_scheduler.add_event_callback(task_result_dispatcher.handle_task_event)
        clean_scheduler.add_event_callback(_collector)
        return seen_events

    @pytest.fixture
    def collector_only(self, clean_scheduler):
        """仅注册事件收集器（不注册 dispatcher），供降级事件直测避免回环。"""
        seen_events: list[TaskEvent] = []

        async def _collector(event: TaskEvent) -> None:
            seen_events.append(event)

        clean_scheduler.add_event_callback(_collector)
        return seen_events

    @staticmethod
    def _spy_append(monkeypatch, *, return_value: bool = True, exc: Exception | None = None):
        """替换 conversation_store.append_message_async，记录调用并按参数返回/抛错。"""
        calls: list[tuple[str, dict]] = []

        async def _fake_append(conv_id: str, message: dict) -> bool:
            calls.append((conv_id, message))
            if exc is not None:
                raise exc
            return return_value

        monkeypatch.setattr(conversation_store, "append_message_async", _fake_append)
        return calls

    @staticmethod
    def _spy_send(monkeypatch, *, return_value: bool = True, exc: Exception | None = None):
        """替换 _send_via_platform，记录 (instance_id, target, content) 并按参数返回/抛错。"""
        calls: list[tuple[str, str, str]] = []

        async def _fake_send(instance_id: str, target: str, content: str) -> bool:
            calls.append((instance_id, target, content))
            if exc is not None:
                raise exc
            return return_value

        monkeypatch.setattr(
            "app.services.task_result_dispatcher.TaskResultDispatcher._send_via_platform",
            staticmethod(_fake_send),
        )
        return calls

    @staticmethod
    def _make_event(task_id: str, status: LuomiTaskStatus, **extra) -> TaskEvent:
        return TaskEvent(
            task_id=task_id,
            task_name=f"任务-{task_id}",
            status=status,
            task_type=LuomiTaskType.DATE,
            result=extra.pop("result", "结果文本"),
            error=extra.pop("error", None),
            **extra,
        )

    # ── 事件入口门卫 ──

    @pytest.mark.asyncio
    async def test_non_terminal_status_events_are_ignored(self, monkeypatch):
        """RUNNING/PENDING/REMOVED 等非终态事件：直接忽略，连来源解析都不发生。"""
        dispatcher = TaskResultDispatcher()
        resolved: list[str] = []

        def _spy_resolve(task_id: str):
            resolved.append(task_id)
            return None

        monkeypatch.setattr(dispatcher, "_resolve_origin", _spy_resolve)

        for status in (LuomiTaskStatus.RUNNING, LuomiTaskStatus.PENDING,
                       LuomiTaskStatus.REMOVED):
            await dispatcher.handle_task_event(self._make_event("t-gate", status))

        assert resolved == []

    @pytest.mark.asyncio
    async def test_unknown_task_id_skips_delivery(self, clean_scheduler, monkeypatch):
        """任务不在调度器内存态（_resolve_origin → None）：静默返回，不做任何投递。"""
        appends = self._spy_append(monkeypatch)
        sends = self._spy_send(monkeypatch)

        await task_result_dispatcher.handle_task_event(
            self._make_event("t-ghost", LuomiTaskStatus.COMPLETED)
        )

        assert appends == []
        assert sends == []

    @pytest.mark.asyncio
    async def test_origin_read_failure_skips_delivery(self, clean_scheduler, monkeypatch):
        """读取任务来源抛异常（如内存态损坏）：告警后静默返回，不中断事件链。"""
        clean_scheduler._tasks["t-broken"] = _make_info("t-broken", "date")

        def _boom_get_task(task_id: str):
            raise RuntimeError("内存任务态读取爆炸")

        monkeypatch.setattr(luominest_scheduler, "get_task", _boom_get_task)
        appends = self._spy_append(monkeypatch)
        sends = self._spy_send(monkeypatch)

        await task_result_dispatcher.handle_task_event(
            self._make_event("t-broken", LuomiTaskStatus.COMPLETED)
        )

        assert appends == []
        assert sends == []

    @pytest.mark.asyncio
    async def test_unknown_origin_kind_skips_delivery(self, clean_scheduler, monkeypatch):
        """未知来源类型（防御性 else 分支）：不回投任何会话/平台。"""
        clean_scheduler._tasks["t-weird"] = _make_info(
            "t-weird", "date", origin_kind="smoke_signal", origin_ref="whatever",
        )
        appends = self._spy_append(monkeypatch)
        sends = self._spy_send(monkeypatch)

        await task_result_dispatcher.handle_task_event(
            self._make_event("t-weird", LuomiTaskStatus.COMPLETED)
        )

        assert appends == []
        assert sends == []

    # ── 消息文案格式化 ──

    def test_build_message_content_all_formats(self):
        """_build_message_content：完成/失败/空结果/无错误 四种文案分支。"""
        build = TaskResultDispatcher._build_message_content

        done = self._make_event("t-fmt", LuomiTaskStatus.COMPLETED, result="  已浇水  ")
        assert build(done) == "[定时任务]《任务-t-fmt》执行完成：\n已浇水"

        empty = self._make_event("t-fmt", LuomiTaskStatus.COMPLETED, result="   ")
        assert "（任务无返回内容）" in build(empty)

        failed = self._make_event("t-fmt", LuomiTaskStatus.FAILED, error="数据库打不开")
        assert build(failed) == "[定时任务]《任务-t-fmt》执行失败：数据库打不开"

        failed_no_reason = self._make_event("t-fmt", LuomiTaskStatus.FAILED, error=None)
        assert build(failed_no_reason).endswith("执行失败：未知错误")

    # ── 网页会话投递分支 ──

    @pytest.mark.asyncio
    async def test_web_origin_missing_conv_id_writes_nothing(
        self, clean_scheduler, monkeypatch
    ):
        """web 来源但 origin_ref 为空（缺会话 ID）：告警降级，不触碰会话存储。"""
        clean_scheduler._tasks["t-noconv"] = _make_info(
            "t-noconv", "date", origin_kind=ORIGIN_WEB_CONVERSATION, origin_ref="",
        )
        appends = self._spy_append(monkeypatch)

        await task_result_dispatcher.handle_task_event(
            self._make_event("t-noconv", LuomiTaskStatus.COMPLETED)
        )

        assert appends == []

    @pytest.mark.asyncio
    async def test_web_origin_conversation_gone_keeps_result_in_task(
        self, clean_scheduler, monkeypatch
    ):
        """会话已删除（append 返回 False）：告警降级，结果保留在任务记录，不抛错。"""
        clean_scheduler._tasks["t-gone"] = _make_info(
            "t-gone", "date", origin_kind=ORIGIN_WEB_CONVERSATION, origin_ref="conv-gone",
        )
        appends = self._spy_append(monkeypatch, return_value=False)

        await task_result_dispatcher.handle_task_event(
            self._make_event("t-gone", LuomiTaskStatus.COMPLETED)
        )

        assert [conv_id for conv_id, _ in appends] == ["conv-gone"]
        written = appends[0][1]
        assert written["role"] == "assistant"
        assert written["scheduled_task"] == {
            "task_id": "t-gone", "status": "completed",
        }

    @pytest.mark.asyncio
    async def test_web_delivery_exception_does_not_break_event_chain(
        self, clean_scheduler, wired, monkeypatch
    ):
        """写会话抛异常：被 handle_task_event 吞掉不外抛（调度器事件链不断），
        且失败路径不补发任何任务事件（事件流不被污染）。"""
        clean_scheduler._tasks["t-expl"] = _make_info(
            "t-expl", "date", origin_kind=ORIGIN_WEB_CONVERSATION, origin_ref="conv-expl",
        )
        self._spy_append(monkeypatch, exc=RuntimeError("会话存储爆炸"))

        # 上句若抛错则测试失败：handle_task_event 必须吞掉投递异常
        await task_result_dispatcher.handle_task_event(
            self._make_event("t-expl", LuomiTaskStatus.COMPLETED)
        )

        assert wired == []

    # ── 平台投递分支 ──

    @pytest.mark.asyncio
    async def test_platform_invalid_origin_ref_no_send_no_degrade(
        self, clean_scheduler, wired, monkeypatch
    ):
        """平台来源引用缺冒号（非法格式）：告警返回，不发送也不补发降级事件。"""
        clean_scheduler._tasks["t-badref"] = _make_info(
            "t-badref", "date", origin_kind=ORIGIN_PLATFORM, origin_ref="inst-without-colon",
        )
        sends = self._spy_send(monkeypatch)

        await task_result_dispatcher.handle_task_event(
            self._make_event("t-badref", LuomiTaskStatus.COMPLETED)
        )

        assert sends == []
        assert not [e for e in wired if "结果已保留在任务记录" in e.message]

    @pytest.mark.asyncio
    async def test_platform_send_exception_swallowed_without_degrade(
        self, clean_scheduler, wired, monkeypatch
    ):
        """平台发送链路抛异常：被吞掉且不走降级补发（异常 ≠ 当前未送达）。"""
        clean_scheduler._tasks["t-pexpl"] = _make_info(
            "t-pexpl", "date", origin_kind=ORIGIN_PLATFORM, origin_ref="inst-x:7",
        )
        self._spy_send(monkeypatch, exc=RuntimeError("适配器爆炸"))

        await task_result_dispatcher.handle_task_event(
            self._make_event("t-pexpl", LuomiTaskStatus.COMPLETED)
        )

        assert not [e for e in wired if "结果已保留在任务记录" in e.message]

    @pytest.mark.asyncio
    async def test_degrade_event_carries_instance_target_and_result(
        self, clean_scheduler, collector_only,
    ):
        """降级事件直测：message 含实例/目标，status/result/error 原样透传。"""
        event = self._make_event(
            "t-dg", LuomiTaskStatus.FAILED, error="下游超时", result=None,
        )
        dispatcher = TaskResultDispatcher()
        await dispatcher._emit_delivery_failure_event(event, "inst-qq", "group:888")

        assert len(collector_only) == 1
        dg = collector_only[0]
        assert dg.status == LuomiTaskStatus.FAILED
        assert dg.error == "下游超时"
        assert "inst-qq" in dg.message and "group:888" in dg.message
        assert "结果已保留在任务记录" in dg.message

    @pytest.mark.asyncio
    async def test_send_via_platform_forwards_text_response_to_router(self, monkeypatch):
        """_send_via_platform 真身：按 (instance_id, target, text 类型 PlatformResponse)
        转发 platform_router，并把底层发送结果原样透传（True/False 两分支）。"""
        captured: dict = {}

        async def _fake_router_send(instance_id, target, response):
            captured["args"] = (instance_id, target, response)
            return captured.get("ret", True)

        monkeypatch.setattr(
            "app.services.platform_router.send_platform_response", _fake_router_send
        )

        captured["ret"] = True
        assert await TaskResultDispatcher._send_via_platform(
            "inst-x", "group:9", "播报内容"
        ) is True
        inst, target, resp = captured["args"]
        assert (inst, target) == ("inst-x", "group:9")
        assert resp.content == "播报内容"
        assert resp.message_type == "text"

        captured["ret"] = False
        assert await TaskResultDispatcher._send_via_platform(
            "inst-x", "private:9", "播报内容"
        ) is False


class TestResolvePlatformTarget:
    """_resolve_platform_target 目标解析：显式优先 / 映射推导 / 异常兜底。"""

    KEY = "platform.sessions.inst-qq:888"

    @pytest.mark.usefixtures("_init_test_db")
    def test_explicit_target_short_circuits_mapping(self, monkeypatch):
        """显式目标直接返回，连会话映射都不读取（读取抛错也不影响）。"""
        def _boom_get(key, default=None):
            raise RuntimeError("配置存储爆炸")

        monkeypatch.setattr(luominest_config_store, "get", _boom_get)
        assert TaskResultDispatcher._resolve_platform_target(
            "inst-qq", "888", "private:42"
        ) == "private:42"

    @pytest.mark.usefixtures("_init_test_db")
    def test_group_mapping_derives_group_target(self):
        """映射 is_group=True → group:{session_id}。"""
        luominest_config_store.set(self.KEY, {"is_group": True})
        try:
            assert TaskResultDispatcher._resolve_platform_target(
                "inst-qq", "888", ""
            ) == "group:888"
        finally:
            luominest_config_store.delete(self.KEY)

    @pytest.mark.usefixtures("_init_test_db")
    def test_private_mapping_and_missing_mapping_derive_private(self):
        """映射 is_group=False 与映射缺失 → 均按私聊 private:{session_id}。"""
        luominest_config_store.set(self.KEY, {"is_group": False})
        try:
            assert TaskResultDispatcher._resolve_platform_target(
                "inst-qq", "888", ""
            ) == "private:888"
        finally:
            luominest_config_store.delete(self.KEY)

        assert TaskResultDispatcher._resolve_platform_target(
            "inst-qq", "888", ""
        ) == "private:888"

    @pytest.mark.usefixtures("_init_test_db")
    def test_non_dict_mapping_and_read_failure_derive_private(self, monkeypatch):
        """映射值非 dict / 读取抛异常 → 告警并按私聊兜底，不抛错。"""
        luominest_config_store.set(self.KEY, "not-a-dict")
        try:
            assert TaskResultDispatcher._resolve_platform_target(
                "inst-qq", "888", ""
            ) == "private:888"
        finally:
            luominest_config_store.delete(self.KEY)

        def _boom_get(key, default=None):
            raise RuntimeError("映射读取爆炸")

        monkeypatch.setattr(luominest_config_store, "get", _boom_get)
        assert TaskResultDispatcher._resolve_platform_target(
            "inst-qq", "888", ""
        ) == "private:888"

"""适配器注册模板与实现配置键漂移防护单测（汇总报告 P1 #7 回归护栏）。

背景：UI 按 config_template 生成实例配置，模板键与实现实际读取键漂移时
（如 rest_api webhook_url vs callback_url、xiaomi mi_user/mi_pass vs
app_key/app_secret、discord guild_id vs allowed_guilds），按模板建实例
必失败或白名单静默失效。

护栏（防再次漂移的最小闭环）：
1. 全量注册适配器遍历：用模板默认值构造 config 实例化并 initialize（不 start），
   断言不抛 KeyError / TypeError —— 模板漏键/错型即测试失败；
   ValueError 视为必填项 UX 校验（如 ws_url/bot_token/app_key 为空），
   不属于漂移信号
2. 每个注册项 config_template 与 config_metadata 键集合一致
"""
from __future__ import annotations

import pytest

from app.runtime.platform.registry import list_adapter_types


def _instantiate_with_template(name: str, adapter_cls, template: dict):
    """用模板默认值实例化并初始化适配器（不 start，不触网）。"""
    adapter = adapter_cls()
    try:
        adapter.initialize(dict(template))
    except (KeyError, TypeError) as exc:
        pytest.fail(
            f"adapter '{name}' 注册模板与实现漂移：用模板默认值初始化抛出 {type(exc).__name__}: {exc!r}"
        )
    except ValueError:
        # 必填项为空属正常 UX 校验（websocket.ws_url / discord.bot_token /
        # xiaomi.app_key 等），仅 KeyError/TypeError 才是模板漂移信号
        pass
    return adapter


def test_all_registered_adapters_initialize_with_template_defaults():
    types = list_adapter_types()
    assert types, "适配器注册表为空（adapters 包未导入？）"

    failures: list[str] = []
    for at in types:
        try:
            _instantiate_with_template(at.name, at.adapter_cls, at.config_template)
        except Exception as exc:  # 防单个适配器构造期异常掩盖其余结果
            failures.append(f"{at.name}: {type(exc).__name__}: {exc}")
    assert not failures, "以下适配器按模板默认值无法实例化:\n" + "\n".join(failures)


def test_every_registered_template_matches_metadata_keys():
    for at in list_adapter_types():
        template_keys = set(at.config_template)
        metadata_keys = set(at.config_metadata)
        assert template_keys == metadata_keys, (
            f"adapter '{at.name}' config_template 与 config_metadata 键不一致: "
            f"仅模板有={sorted(template_keys - metadata_keys)}, "
            f"仅元数据有={sorted(metadata_keys - template_keys)}"
        )


def test_fixed_drift_points_kept_aligned():
    """P1 #5/#7 已知漂移点的定向回归：模板键必须等于实现实际读取键。

    实现读取键以各适配器 initialize() 中 config.get(...) 的代码事实为准
    （grep config.get 快照），实现新增读取键时此处应同步更新。
    """
    impl_keys: dict[str, set[str]] = {
        "websocket": {"ws_url", "access_token", "heartbeat_interval", "reconnect_delay"},
        "rest_api": {"callback_url", "api_key", "max_queue_size"},
        "telegram": {"bot_token", "allowed_users", "polling_interval", "use_webhook", "webhook_url"},
        "discord": {"bot_token", "allowed_guilds", "prefix", "intents"},
        "xiaomi_iot": {"app_key", "app_secret", "server_url", "polling_interval", "webhook_url"},
    }
    by_name = {at.name: at for at in list_adapter_types()}
    for name, keys in impl_keys.items():
        at = by_name.get(name)
        assert at is not None, f"adapter '{name}' 未注册"
        assert set(at.config_template) == keys, (
            f"adapter '{name}' 模板键 {sorted(at.config_template)} 与实现读取键 {sorted(keys)} 漂移"
        )

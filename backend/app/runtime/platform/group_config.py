"""per-group 群配置表（分册10 §16.3：每群独立 @ 门槛/插话频率/记忆开关/启用与否）。

存储：config_items 命名空间 ``platform.groups.{instance_id}:{group_id}``
（luominest_config_store 承载，与 platform.sessions.* 同链路：AES 加密+统一备份）。

默认保守（辰汐定调：默认 @ 才答）：
- enabled          群总开关，False = 完全不应答
- respond_mode     唤醒门槛：at（默认，仅@）/ at_or_reply（@或引用bot）/ all（慎用）
- memory_enabled   该群事实是否写记忆轨（与实例级 memory_write 取与）
- interject_rate   主动插话概率 0-1（远期占位，默认 0 = 不插话）

未知字段写入被忽略；读取时与默认值合并，缺省字段自动补齐——
不存在的群配置天然落默认保守值，无需预建。
"""
from collections.abc import Mapping

from loguru import logger

from app.infrastructure.database.config_store import luominest_config_store

_NAMESPACE = "platform.groups."

DEFAULT_GROUP_CONFIG: dict = {
    "enabled": True,
    "respond_mode": "at",
    "memory_enabled": True,
    "interject_rate": 0.0,
}

# respond_mode 合法值（写入时校验，非法值拒绝并保留旧值）
_VALID_RESPOND_MODES = {"at", "at_or_reply", "all"}


def _config_key(instance_id: str, group_id: str) -> str:
    return f"{_NAMESPACE}{instance_id}:{group_id}"


def _merge(stored: Mapping | None) -> dict:
    cfg = dict(DEFAULT_GROUP_CONFIG)
    if isinstance(stored, Mapping):
        for k, v in stored.items():
            if k in cfg:
                cfg[k] = v
    return cfg


def get_group_config(instance_id: str, group_id: str) -> dict:
    """读取群配置（无配置返回默认保守值；不落盘）。"""
    if not (instance_id or "").strip() or not (group_id or "").strip():
        return dict(DEFAULT_GROUP_CONFIG)
    return _merge(luominest_config_store.get(_config_key(instance_id, str(group_id))))


def safe_get_group_config(instance_id: str, group_id: str) -> dict:
    """消息热路径专用：配置库异常时退回默认保守值，绝不让群响应链路瘫掉。"""
    try:
        return get_group_config(instance_id, group_id)
    except Exception as e:
        logger.warning(f"[GroupConfig] 读取失败，回退默认值 {instance_id}:{group_id}: {e}")
        return dict(DEFAULT_GROUP_CONFIG)


def set_group_config(instance_id: str, group_id: str, patch: Mapping) -> dict:
    """增量更新群配置（仅接受已知字段；respond_mode 非法值拒绝）。"""
    key = _config_key(instance_id, str(group_id))
    current = luominest_config_store.get(key)
    merged = _merge(current if isinstance(current, Mapping) else None)
    for k, v in dict(patch or {}).items():
        if k not in merged:
            continue
        if k == "respond_mode" and v not in _VALID_RESPOND_MODES:
            raise ValueError(f"respond_mode 必须是 {_VALID_RESPOND_MODES} 之一，收到 {v!r}")
        if k == "interject_rate":
            v = max(0.0, min(1.0, float(v)))
        merged[k] = v
    luominest_config_store.set(key, merged)
    return merged


def list_group_configs(instance_id: str | None = None) -> dict[str, dict]:
    """列出群配置（可按实例过滤），键为 ``{instance_id}:{group_id}``。"""
    out: dict[str, dict] = {}
    for key, val in luominest_config_store.get_namespace(_NAMESPACE).items():
        rest = key[len(_NAMESPACE):]
        inst, _, group = rest.partition(":")
        if instance_id and inst != instance_id:
            continue
        out[rest] = _merge(val if isinstance(val, Mapping) else None)
    return out


def reset_group_config(instance_id: str, group_id: str) -> bool:
    """删除群自定义配置（回到默认保守值）。"""
    return luominest_config_store.delete(_config_key(instance_id, str(group_id)))

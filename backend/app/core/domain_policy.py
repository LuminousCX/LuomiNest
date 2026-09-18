"""对话域策略（DomainPolicy）— 表驱动的记忆/工具开关（洋葱架构 §9/§10/§13 B6/B7）。

记忆读写判定由单一布尔 ``is_main_agent(agent_id)`` 升级为本模块的
**DomainPolicy.memory_read / memory_write / memory_track** 三开关，
由对话的 domain（+ scene）查策略表得出；``is_main_agent`` 兼容保留
（context_service 委托到 :func:`is_main_agent_id`）。

domain 取值约定（§5.2）：

- ``""`` / ``"workbench"``          → 工作台（scene=avatar 为皮套工坊/桌宠）
- ``"agent:{agent_id}"``            → 对话页 Agent（非主 Agent）
- ``"platform:{instance_id}"``      → 平台接入（每实例一域）

本模块位于 core 层（最内圈），不依赖 services / engines / runtime，
供 chat_service、context_service、platform_router、engines.memory 共用。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# ──────────────────────────────────────────────────────────────
# 主 Agent 标识（canonical 定义，其余模块从此处导入/兼容再导出）
# ──────────────────────────────────────────────────────────────

MAIN_AGENT_ID = "luominest_main_agent"
# 旧版平台数据中使用的 agent_id，保留以兼容历史会话
LEGACY_MAIN_AGENT_ID = "main"

# ──────────────────────────────────────────────────────────────
# 记忆轨道（§8.5.2 记忆树 namespace）
# ──────────────────────────────────────────────────────────────

TRACK_OWNER = "owner"  # 主人轨道：工作台/皮套/桌宠读写，优先级最高
TRACK_USERS = "users"  # 用户轨道：平台对话按 user_key 提炼写入

# ──────────────────────────────────────────────────────────────
# 场景值（conversation.scene）
# ──────────────────────────────────────────────────────────────

SCENE_WORKBENCH = "workbench"
SCENE_AVATAR = "avatar"      # 皮套工坊/桌宠（D3/D4：共享主人记忆，standard 工具集）
SCENE_PLATFORM = "platform"

# ──────────────────────────────────────────────────────────────
# 工具画像（§10 工具策略矩阵）
# ──────────────────────────────────────────────────────────────

TOOL_PROFILE_CHAT_MODE = "chat_mode"  # 完整工具集，按 chat_mode 路由（工作台）
TOOL_PROFILE_STANDARD = "standard"    # standard 工具集（皮套/桌宠/平台）
TOOL_PROFILE_AGENT = "agent"          # 按 Agent 配置（对话页 Agent，现状不改）

# ──────────────────────────────────────────────────────────────
# domain 常量与解析
# ──────────────────────────────────────────────────────────────

DOMAIN_WORKBENCH = "workbench"
DOMAIN_AGENT_PREFIX = "agent:"
DOMAIN_PLATFORM_PREFIX = "platform:"

KIND_WORKBENCH = "workbench"
KIND_AGENT = "agent"
KIND_PLATFORM = "platform"
KIND_NONE = "none"


def is_main_agent_id(agent_id: str | None) -> bool:
    """判断给定 agent_id 是否为主 Agent（兼容新旧标识）。"""
    return agent_id == MAIN_AGENT_ID or agent_id == LEGACY_MAIN_AGENT_ID


def parse_domain(domain: str | None) -> tuple[str, str]:
    """解析 domain 为 (kind, suffix)。

    - workbench / ""      → ("workbench", "")
    - agent:{id}          → ("agent", "{id}")
    - platform:{instId}   → ("platform", "{instId}")
    - 其他未知取值        → ("none", "")（保守按无权限处理）
    """
    dom = (domain or "").strip()
    if not dom or dom == DOMAIN_WORKBENCH:
        return KIND_WORKBENCH, ""
    if dom.startswith(DOMAIN_AGENT_PREFIX):
        return KIND_AGENT, dom[len(DOMAIN_AGENT_PREFIX):]
    if dom.startswith(DOMAIN_PLATFORM_PREFIX):
        return KIND_PLATFORM, dom[len(DOMAIN_PLATFORM_PREFIX):]
    return KIND_NONE, ""


def domain_for_agent(agent_id: str | None) -> str:
    """新建对话时按 agent_id 推导 domain（与存量回填迁移器规则一致）。

    主 Agent / 无 agent_id → workbench；其余 → agent:{agent_id}。
    """
    if not agent_id or is_main_agent_id(agent_id):
        return DOMAIN_WORKBENCH
    return f"{DOMAIN_AGENT_PREFIX}{agent_id}"


# ──────────────────────────────────────────────────────────────
# 群成员轨 user_key（§8.5.10 本期实现：成员级记忆按「人」建轨）
# ──────────────────────────────────────────────────────────────

# user_key 单段清洗：白名单与 store.resolve_track_dir 的 _USER_KEY_ALLOWED
# （[A-Za-z0-9._-]）保持一致，白名单外字符统一替换为 "_"
_SEGMENT_CLEAN_RE = re.compile(r"[^a-z0-9._-]+")
# 单段限长 40：三段 + 2 个分隔符 ≤ sanitize_track_key 的 128 上限
_SEGMENT_MAX_LEN = 40


def sanitize_key_segment(raw: str | None) -> str:
    """user_key 单段标识清洗：小写化 + 白名单外字符替换为 "_"。

    路径分隔符（/ \\）不在白名单内，必然被替换为 "_"，杜绝路径穿越；
    整段为空 / "." / ".." 时返回占位符 "_"，防止落点逃出 users/ 目录。
    输出保证能通过 store.sanitize_track_key 的白名单校验。
    """
    seg = _SEGMENT_CLEAN_RE.sub("_", (raw or "").strip().lower())
    if seg in ("", ".", ".."):
        return "_"
    return seg[:_SEGMENT_MAX_LEN]


def group_member_user_key(platform: str, identity: str, sender_id: str) -> str:
    """群聊成员 → 用户轨 user_key：``{platform}_{identity}_{sender_id}``。

    - platform: 平台类型（如 qq_onebot，取 PlatformMessage.platform）
    - identity: 平台实例标识（platform:{instId} 域中的 instance_id）
    - sender_id: 发送者在平台内的身份（如 QQ 号，PlatformMessage.user_id）

    三段均经 :func:`sanitize_key_segment` 清洗；identity 取平台实例而非群 id，
    同一人跨群在同一实例下得到同一个轨（按「人」不按「群」）。
    sender_id 为空 → 返回 ""（不建轨，维持现状）。
    """
    if not (sender_id or "").strip():
        return ""
    return (
        f"{sanitize_key_segment(platform)}_"
        f"{sanitize_key_segment(identity)}_"
        f"{sanitize_key_segment(sender_id)}"
    )


@dataclass(frozen=True)
class DomainPolicy:
    """单个对话域的记忆/工具策略（§9 记忆策略矩阵 + §10 工具策略矩阵）。

    - memory_read：是否注入记忆（读）
    - memory_write：是否提炼/落库记忆（写）
    - memory_track：写入/归属轨道（TRACK_OWNER / TRACK_USERS / None=无记忆）
    - tool_profile：工具路由画像（§10）
    - track_user_key：memory_track == TRACK_USERS 时实际生效的用户轨键
      （私聊 = conversation.user_key；群聊 = 群成员轨 group_member_user_key；
      其他轨道为空串）
    """

    kind: str
    memory_read: bool
    memory_write: bool
    memory_track: str | None
    tool_profile: str
    track_user_key: str = ""

    @property
    def has_memory(self) -> bool:
        return self.memory_read or self.memory_write


# 无记忆权限策略（联系人 Agent / 未知域）
NONE_POLICY = DomainPolicy(KIND_NONE, False, False, None, TOOL_PROFILE_AGENT)


def resolve_domain_policy(
    domain: str | None,
    *,
    scene: str = "",
    agent_id: str | None = None,
    user_key: str = "",
    platform_memory_write: bool = False,
    sender_id: str = "",
    platform_name: str = "",
) -> DomainPolicy:
    """按 domain（缺省时按 agent_id 兜底推导）查策略表，返回 DomainPolicy。

    Args:
        domain: 对话域（workbench / agent:{id} / platform:{instId}），可为空
        scene: 场景（avatar → 皮套/桌宠，工具固定 standard）
        agent_id: domain 缺省时按主 Agent 标识兜底推导（legacy 调用兼容）
        user_key: 平台私聊用户标识；群聊为空
        platform_memory_write: 平台实例级记忆写入开关（M5=C，默认关）
        sender_id: 群消息发送者身份（PlatformMessage.user_id）；非空且
            user_key 为空时按群成员轨解析 user_key（§8.5.10 本期实现）
        platform_name: 平台类型（如 qq_onebot）；缺省时群成员轨回退用实例标识

    §9 记忆策略矩阵：

    - workbench（含 scene=avatar）：owner 轨，读 ✅ 写 ✅
    - agent:{id}：owner 轨，读 ✅ 写 ✅（各自 owner:{agent_id} 记忆，记忆中枢可选页）
    - platform:{instId}：读 ✅（owner 优先 + 该用户/说话成员记忆）；
      写受 platform_memory_write 开关控制（默认 ❌），写入 users/{track_user_key}/
      （私聊 = conversation.user_key；群聊 = {platform}_{instId}_{sender_id}，
      无 sender_id 的群消息维持现状不建轨）

    domain 为空/None 时按 agent_id 兜底推导（兼容未携带 domain 的 legacy 调用）：
    主 Agent → workbench；其他 Agent → agent:{id}；均无 → 无记忆权限
    （与 legacy is_main_agent 门控行为一致）。
    """
    dom = (domain or "").strip()
    if not dom:
        if is_main_agent_id(agent_id):
            kind = KIND_WORKBENCH
        elif agent_id:
            kind = KIND_AGENT
        else:
            # 无 domain 且无 agent_id：无记忆权限（legacy is_main_agent(None) 行为）
            return NONE_POLICY
    else:
        kind, _suffix = parse_domain(dom)
        if kind == KIND_NONE:
            # 未知非空 domain：保守按无记忆权限处理
            return NONE_POLICY

    if kind == KIND_WORKBENCH:
        # D3/D4：皮套/桌宠共享主人记忆读写，工具固定 standard 子集
        tool_profile = TOOL_PROFILE_STANDARD if scene == SCENE_AVATAR else TOOL_PROFILE_CHAT_MODE
        return DomainPolicy(KIND_WORKBENCH, True, True, TRACK_OWNER, tool_profile)

    if kind == KIND_PLATFORM:
        inst_id = parse_domain(dom)[1]
        effective_user_key = (user_key or "").strip()
        if not effective_user_key and (sender_id or "").strip():
            # 群聊成员轨（按「人」不按「群」，同一人跨群同实例同轨）
            effective_user_key = group_member_user_key(
                platform_name or inst_id, inst_id, sender_id,
            )
        track = TRACK_USERS if effective_user_key else None
        memory_write = bool(platform_memory_write) and bool(effective_user_key)
        return DomainPolicy(
            KIND_PLATFORM, True, memory_write, track, TOOL_PROFILE_STANDARD,
            track_user_key=effective_user_key,
        )

    # agent:{id}：子 Agent 对话读写各自 owner:{agent_id} 记忆（A 方案，记忆中枢可选页）
    return DomainPolicy(KIND_AGENT, True, True, TRACK_OWNER, TOOL_PROFILE_AGENT)

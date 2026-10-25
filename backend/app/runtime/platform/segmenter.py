"""平台分段发送服务（G0-D，2026-10-25 拍板⑫）。

人类聊天不是一次性倾倒整段文本：短回复按句切段、段间有打字延迟、
段尾不收句号。切分/延迟/清理三组参数均出自 AstrBot segmented_reply
的实测口径（config/default.py:4511-4576，洁净室只借参数不借代码）：

- 切分：标点正则（[。？！?!…]+ 与换行）逐句切；总长超 max_chars（默认
  150 字）时放弃切分直接整发——长文本切碎会刷屏成碎条流，AstrBot 同款保护；
- 段间延迟两种模式：
  * log 模式（默认）：y = log_base(段字数) 秒，打字时间随长度对数增长
    （base≈2.6 时 10 字 ≈ 2.4s，50 字 ≈ 4.4s），短段快、长段慢，拟真度高；
  * random 模式：均匀分布 [delay_min, delay_max]（默认 1.5~3.5s）；
- 清理规则：去段尾句号（人类聊天不收尾"。"，问号叹号保留——情绪载体）；
- 思考延迟：回复前 base + 随机抖动（模拟"看完再打字"）。

本模块保持纯逻辑（不依赖适配器/数据库），发送循环由 platform_router 承载；
参数经 group_config 的 platform.groups.* 命名空间 per-group 可调（拍板⑫）。
流式平台"收到标点即发"的实时分段后置 G4；QQ 无 typing API，靠延迟本身拟真。
"""
from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass

# 句末切分正则：中英句读 + 省略号 + 换行（切分符本身不保留在段内）
_SEGMENT_SPLIT_RE = re.compile(r"[。？！?!…；;]+|\n+")
# 段尾句号清理（人类聊天不收尾"。"；仅去中文句号/全角点，保留？！与英文句点）
_TRAILING_PERIOD_RE = re.compile(r"[。．]+$")

# log 模式延迟下限（秒）：单字段 log 值趋 0，瞬时连发破坏拟真
_MIN_SEGMENT_DELAY = 0.5
# log 模式延迟上限（秒）：超长段打字时间封顶，避免群友等半天
_MAX_SEGMENT_DELAY = 8.0


@dataclass
class SegmentParams:
    """分段发送参数（默认值 = AstrBot segmented_reply 实测口径）。"""

    # 总长保护：回复总字符数超过该值时放弃切分直接整发（防刷屏碎条）
    max_chars: int = 150
    # 段间延迟模式："log"（对数打字时间）| "random"（均匀随机区间）
    delay_mode: str = "log"
    # log 模式底数：y = log_base(段字数) 秒
    log_base: float = 2.6
    # random 模式均匀区间（秒）
    delay_min: float = 1.5
    delay_max: float = 3.5
    # 回复前思考延迟：base + uniform(0, jitter) 秒（模拟"看完再打字"）
    think_base: float = 1.2
    think_jitter: float = 2.0


def clean_segment(segment: str) -> str:
    """段内清理：去首尾空白 + 去段尾句号（？！保留）。"""
    return _TRAILING_PERIOD_RE.sub("", segment.strip())


def split_reply(text: str, params: SegmentParams | None = None) -> list[str]:
    """按句末标点/换行切分回复，返回清理后的段列表。

    - 总长超 params.max_chars：放弃切分直接整发（防刷屏碎条保护）；
    - 空段（连续标点/首尾标点产生）丢弃；
    - 单段（无切分点）原样返回。
    """
    params = params or SegmentParams()
    text = (text or "").strip()
    if not text:
        return []
    if len(text) > params.max_chars:
        return [text]

    segments: list[str] = []
    for raw in _SEGMENT_SPLIT_RE.split(text):
        seg = clean_segment(raw)
        if seg:
            segments.append(seg)
    return segments or [text]


def segment_delay(segment: str, params: SegmentParams | None = None) -> float:
    """某段发出前的等待秒数（段间延迟；首段由调用方改用 think_delay）。"""
    params = params or SegmentParams()
    if params.delay_mode == "random":
        low, high = sorted((params.delay_min, params.delay_max))
        return random.uniform(low, high)
    base = params.log_base if params.log_base > 1.0 else 2.6
    chars = max(len(clean_segment(segment)), 1)
    return min(_MAX_SEGMENT_DELAY, max(_MIN_SEGMENT_DELAY, math.log(chars, base)))


def think_delay(params: SegmentParams | None = None) -> float:
    """回复前思考延迟：base + uniform(0, jitter)（模拟"看完再打字"）。"""
    params = params or SegmentParams()
    jitter = max(params.think_jitter, 0.0)
    return params.think_base + random.uniform(0.0, jitter)


def segment_reply_plan(text: str, params: SegmentParams | None = None) -> list[tuple[str, float]]:
    """一次给出完整发送计划：[(段文本, 发送前等待秒数)]。

    首段等待 = 思考延迟（think_delay）；后续段等待 = 段间延迟（segment_delay）。
    调用方按序 sleep + 发送即可；总长超限的整发场景返回单元素计划
    （等待仍为思考延迟——整发不省"打字时间"）。
    """
    params = params or SegmentParams()
    segments = split_reply(text, params)
    if not segments:
        return []
    plan: list[tuple[str, float]] = [(segments[0], think_delay(params))]
    for seg in segments[1:]:
        plan.append((seg, segment_delay(seg, params)))
    return plan

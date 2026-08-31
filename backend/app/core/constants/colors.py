"""LuomiNest 颜色常量 — 后端产出数据的唯一颜色源头。

对齐前端默认主题（frontend/src/renderer/src/styles/variables.css）：
- 品牌主色 --lumi-brand: #147EBC（蓝色，默认 Agent / 主 Agent 显示色）
- 角色色板与 --lumi-success/--lumi-amber/--lumi-danger/--lumi-emerald 一致

规范：
- 业务代码禁止硬编码 hex 颜色字面量，一律引用本模块；
- 前端主题切换不影响此处常量：这些值仅作为"未指定颜色时的后端默认值"
  写入数据（如新建 Agent 的 color 字段），存量数据不回填。
"""

# Agent 默认主色（对齐前端 --lumi-brand，蓝色）
DEFAULT_AGENT_COLOR: str = "#147EBC"

# 多 Agent 协作角色色板（agent_role_registry 内置角色专用）
# 与前端主题变量同源：--lumi-brand / --lumi-success / --lumi-amber / --lumi-danger / --lumi-emerald
ROLE_COLORS: dict[str, str] = {
    "coordinator": "#147EBC",   # 调度员 — 品牌蓝
    "data-agent": "#22C55E",    # 数据专员 — success 绿
    "compute-agent": "#F59E0B", # 计算专员 — amber 黄
    "review-agent": "#EF4444",  # 审核专员 — danger 红
    "creative-agent": "#10B981",# 创意专员 — emerald 翠绿
}

# 市场标签默认色（无语义标签的中性灰）
TAG_COLOR_MUTED: str = "#888888"    # marketplace / registry 同步的默认标签色
TAG_COLOR_NEUTRAL: str = "#6B7280"  # GitHub 同步的默认标签色（= --text-muted）

# 图表渲染默认系列色（matplotlib C0 默认蓝，非品牌色，仅 chart-renderer 插件使用）
CHART_DEFAULT_SERIES_COLOR: str = "#1f77b4"

"""上下文管理常量（从原 __init__.py 拆出，值与语义不变）。"""

# ── Token 估算与上下文预算常量（LuomiNest 语义，勿散落字面量）──────────────
# 注意：下列两组 0.6/0.3 同值不同义，禁止互相混用：
#   - TOKEN_WEIGHT_* 用于字符数→token 数的估算换算；
#   - REBUILD_BUDGET_RATIO / SUMMARY_TEMPERATURE 用于摘要压缩策略。

# 单张图片消息的固定 token 估算值
IMAGE_TOKEN_ESTIMATE: int = 765
# 中文字符的 token 换算权重（1 汉字 ≈ 0.6 token）
TOKEN_WEIGHT_CHINESE: float = 0.6
# 非中文字符的 token 换算权重（1 其他字符 ≈ 0.3 token）
TOKEN_WEIGHT_OTHER: float = 0.3
# Provider 能力表与配置均未提供时的默认上下文窗口
DEFAULT_CONTEXT_WINDOW: int = 16384
# context_window 解析失败（<=0）时的宽口径回退窗口
FALLBACK_CONTEXT_WINDOW: int = 128000
# 防漂移重建预算占历史预算的比例
REBUILD_BUDGET_RATIO: float = 0.6
# 摘要生成的 LLM 采样温度（低温保证摘要稳定）
SUMMARY_TEMPERATURE: float = 0.3

"""LuomiNest 默认音色常量 — 后端默认音色的唯一源头。

规范：
- 业务代码禁止硬编码默认音色字面量，一律引用本模块；
- 这些值仅作为"未指定音色时的后端默认值"写入数据/请求（如 TTS 合成
  回退、新建 Avatar 绑定、voice_config 默认结构），存量数据不回填；
- 可选音色清单（voices 列表）不属于默认值范畴，仍在各 TTS Provider
  的 CAPABILITIES 中声明。
"""

# Edge TTS 默认音色（晓晓，女·温柔，中文）
DEFAULT_EDGE_VOICE: str = "zh-CN-XiaoxiaoNeural"

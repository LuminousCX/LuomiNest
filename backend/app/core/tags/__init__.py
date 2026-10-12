"""统一标签网关（辰汐生态打通 W2，分册 08 §15 / 分册 10 §18）。

五类合同标签的流式安全解析与翻译：
- 情绪   <exp:WORD/>（合同 8 词，自闭合）/ <exp:ID>（LuomiNest 现役 12 语义 ID，非自闭合）
- 动作   <act:NAME/>
- 导航   <ui:navigate target="X"/>
- 皮套工具 <tool:avatar_motion name="X"/> / <tool:avatar_expression name="X"/>
- 派发   <dispatch task="X"/>

模块结构（遵循六边形分层，core 不反向依赖 services）：
- definitions: 词表 / 白名单 / 正则 / 约定常量
- translator:  合同词 → LuomiNest 语义 ID（内置 8→12 映射 + JSON 覆盖 + neutral 兜底 + 计数）
- parser:      流式安全 TagStreamParser（喂 token 吐 clean_text + 结构化事件）
"""

from app.core.tags.parser import TagEvent, TagStreamParser, parse_tags, strip_all_tags
from app.core.tags.translator import TagTranslator, get_default_translator

__all__ = [
    "TagEvent",
    "TagStreamParser",
    "TagTranslator",
    "get_default_translator",
    "parse_tags",
    "strip_all_tags",
]

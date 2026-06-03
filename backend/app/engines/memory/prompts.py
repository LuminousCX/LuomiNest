_FACT_EXTRACT_PROMPT = """你是一个记忆提取助手。从用户消息中提取关键信息，包括用户名字和事实。

规则：
1. profile_name：只提取用户自己的名字，不提取别人的名字
2. 如果用户在问问题（"我叫什么？"）或假设性语句（"如果我叫小明"），profile_name留空
3. 名字长度不超过20个字符
4. 事实提取规则：
   - 只提取明确陈述或强暗示的信息，不提取假设性内容
   - 每条事实必须有明确的类别
   - 置信度：0.9-1.0（明确陈述）、0.7-0.8（强暗示）、0.5-0.6（推断模式）
   - 如果是纠正之前的信息，使用 correction 类别，并在 source_error 中记录之前的错误信息

类别：
- preference: 用户偏好（喜欢/不喜欢什么）
- knowledge: 用户知识/专长
- context: 用户当前背景（工作、项目等）
- behavior: 用户行为模式（习惯、风格等）
- goal: 用户目标/计划
- correction: 纠正之前的错误信息

请严格按以下JSON格式回复，不要添加任何其他内容：
{{"profile_name": "用户名字或空字符串", "facts": [{{"content": "事实内容", "category": "类别", "confidence": 0.9, "source_error": ""}}]}}

如果消息中不包含可提取的内容，返回：
{{"profile_name": "", "facts": []}}

用户消息：{message}"""

_CORRECTION_HINT = "特别注意：用户在最近的对话中表达了纠正/不满，请以 correction 类别、confidence >= 0.95 记录正确做法，并在 source_error 中记录之前的错误信息。"

_REINFORCEMENT_HINT = "特别注意：用户在最近的对话中确认了某个信息，请以 preference 或 behavior 类别、confidence >= 0.9 记录确认的做法。"

_DISTILL_PROMPT = """你是一个记忆蒸馏助手。根据当前记忆和近期对话，完成两项任务：

任务1：提取结构化事实（回填到用户档案）
从对话中提取所有可确认的事实信息，包括用户名字、偏好、背景等。

任务2：更新叙事性总结
保留已有的正确信息，只更新或补充。每个部分用简洁的要点列出，不要写长段落。事件时间线按时间倒序排列，最多保留20条。

规则：
1. 事实提取是最高优先级——如果对话中用户说了名字，必须提取
2. 如果用户纠正了之前的信息，用 correction 类别记录，source_error 填写被纠正的旧信息
3. 名字提取规则：只提取用户自己的名字，不提取别人或假设性的名字
4. 总结中的信息必须与提取的事实一致，不能矛盾
5. 维度划分规则：
   - 用户画像：客观身份事实（姓名、职业、年龄段、地区、技术栈等）
   - 偏好设置：交互行为偏好（回复风格、代码风格、是否希望被称呼名字等）
   - 兴趣目标：学习/生活兴趣（想学的技术、想去的地方、目标计划等）
   - 近期状态：临时状态（当前心情、本周状态等）
   - 事件时间线：重要事件、里程碑

请严格按以下JSON格式回复，不要添加任何其他内容：
{{
  "facts": [{{"content": "事实内容", "category": "类别", "confidence": 0.9, "source_error": ""}}],
  "profile_name": "",
  "summary": {{
    "用户画像": "",
    "偏好设置": "",
    "兴趣目标": "",
    "近期状态": "",
    "事件时间线": ""
  }}
}}

其中 profile_name 仅在对话中明确提到用户名字时填写，否则留空。
summary 的每个字段用 Markdown 要点格式填写（每行以 "- " 开头），如果某个部分没有新信息则保留原文。

当前记忆：
- 用户名字：{current_name}
- 已有事实：{current_facts}
- 当前总结：
{current_summary}

近期对话摘要：
{conversation_summary}

{correction_hint}"""

_CORRECTION_PATTERNS_ZH = [
    "不对", "你理解错了", "你理解有误", "不是这样的", "错了",
    "重试", "重新来", "换一种", "改用", "别这样",
]

_CORRECTION_PATTERNS_EN = [
    "that's wrong", "you misunderstood", "try again", "redo",
    "not what i meant", "incorrect",
]

_REINFORCEMENT_PATTERNS_ZH = [
    "对，就是这样", "完全正确", "正是我想要的", "继续保持", "很好",
    "没错", "对的", "就是这样",
]

_REINFORCEMENT_PATTERNS_EN = [
    "yes exactly", "perfect", "that's right", "keep doing that",
    "this is great", "correct",
]

_MERGE_SUMMARY_PROMPT = """合并为一份统一的用户画像摘要：

<已有摘要>
{old_summary}
</已有摘要>

<新观察>
{new_summary}
</新观察>

要求：
1. 合并所有信息，去重去冗余
2. 新信息覆盖旧信息中的矛盾/过期内容
3. bullet point 格式，每条 ≤30字
4. 总长度 ≤300字"""

_DISTILL_PROMPT_ROUND = """你是对话分析专家。提取以下对话中的所有关键信息：

<对话>
{messages}
</对话>

要求：
- 提取：用户说了什么、AI做了什么决策、任何偏好/约定/事实
- 用中文 bullet point，每条 ≤30字
- 忽略寒暄和纯确认性回复
- 输出不超过 200 字"""

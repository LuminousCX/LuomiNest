"""
搜索意图识别器 —— 多维度评分制判断用户是否需要联网搜索

设计思路：
  旧方案（纯关键词匹配）太片面，只能识别"搜索"、"查一下"等显式搜索词，
  无法覆盖大量隐式搜索需求，如：
    - "2026年世界杯在哪举办"（地点查询）
    - "iPhone 18什么时候出"（时间查询）
    - "特斯拉股价多少"（实时数据）
    - "最近有什么好看的电影"（时效性推荐）
    - "河北软考几号"（具体事件日期）

  新方案（八维度评分制）综合考虑以下信号：
    1. 问题模式层：疑问词+实体 → "X是几号"/"X什么时候"/"X在哪"
    2. 实体时效层：专有名词+时间词 → "2026年软考"/"最近新闻"
    3. 话题类别层：特定话题几乎必搜 → 股价/新闻/考试/赛事
    4. 否定信号层：明确不需要搜索 → 数学/创作/编程/历史常识
    5. 知识边界层：LLM 训练截止后的事实 → "2025年"/"最新政策"
    6. 实体识别层：专有名词+疑问结构 → "GPT-5什么时候出"
    7. 比较评价层：需要实时数据对比 → "X和Y哪个好"
    8. 事实特异性层：要求精确数字/日期/地点 → "X的录取分数线"

  每个信号加权评分，总分超过阈值则触发搜索。

  上下文感知：
    支持传入对话历史，识别追问型搜索需求（"那X呢"/"还有呢"）。
"""

import re
from loguru import logger


# =============================================================================
# 信号定义（正则 + 权重）
# =============================================================================

# ---------------------------------------------------------------------------
# 维度1：问题模式（疑问词 + 实体）
# ---------------------------------------------------------------------------
_POSITIVE_PATTERNS: list[tuple[re.Pattern, int, str]] = [
    (re.compile(r"什么时候"), 4, "时间疑问"),
    (re.compile(r"是哪天|是几号|哪一天|几号"), 4, "日期疑问"),
    (re.compile(r"在哪里|在哪|在哪举办|在哪个"), 3, "地点疑问"),
    (re.compile(r"多少|多少钱|几钱|价格"), 3, "数值疑问"),
    (re.compile(r"有没有|是否|会不会|能不能"), 1, "是非疑问"),
    (re.compile(r"怎么样|如何|好不好"), 2, "评价疑问"),

    (re.compile(r"距离|离.*还有|还剩|还有几|还差几"), 4, "倒计时模式"),

    (re.compile(r"搜索|查找|搜一下|帮我搜|帮我查|查一下|查查|搜一搜"), 5, "显式搜索"),

    (re.compile(r"今年|明年|去年|本周|上周|最近|最新|当前|目前|现在|今日|昨日"), 2, "时效性词"),
    (re.compile(r"\d{4}年"), 1, "年份引用"),

    (re.compile(r"股价|股票|行情|涨幅|跌幅|市值|基金|比特币|加密货币"), 5, "金融实时"),
    (re.compile(r"新闻|热点|头条|爆料|事件|事故"), 4, "新闻热点"),
    (re.compile(r"考试|报名|准考证|成绩|录取|分数线|软考|考研|高考|中考|国考"), 4, "考试信息"),
    (re.compile(r"比赛|赛事|比分|积分|排名|赛程|对阵|世界杯|奥运会|欧冠|NBA"), 4, "体育赛事"),
    (re.compile(r"上映|票房|评分|豆瓣|IMDb|排行|榜单|推荐.*电影|好看.*剧|好看.*电影|好看.*片|有什么好看|有什么.*推荐"), 3, "影视娱乐"),
    (re.compile(r"航班|高铁|火车|机票|车次|时刻表|晚点"), 4, "交通出行"),
    (re.compile(r"政策|法规|规定|新规|出台|实施|生效"), 3, "政策法规"),
    (re.compile(r"发布|推出|上市|开售|预售|发售|新品"), 3, "产品发布"),

    (re.compile(r"[\u4e00-\u9fa5]{2,}(什么时候|是几号|是哪天|在哪|多少|怎么样)"), 3, "实体+疑问"),

    (re.compile(r"旅游|旅行|攻略|景点|酒店|民宿|机票|签证"), 3, "旅游出行"),

    (re.compile(r"iPhone|iPad|MacBook|华为|小米|三星|特斯拉|比亚迪|蔚来"), 2, "品牌产品"),

    (re.compile(r"推荐|好不好|值不值得|值得|怎么样"), 2, "推荐评价"),
]

# ---------------------------------------------------------------------------
# 维度5：知识边界信号（LLM 训练截止后的事实，几乎必搜）
# ---------------------------------------------------------------------------
_KNOWLEDGE_BOUNDARY_PATTERNS: list[tuple[re.Pattern, int, str]] = [
    (re.compile(r"202[5-9]年"), 3, "近年引用"),
    (re.compile(r"今年.*?(政策|规定|新规|考试|报名|分数线|录取|赛事|举办)"), 4, "今年+时效词"),
    (re.compile(r"最新.*?(政策|规定|版本|消息|动态|公告|通知|发布)"), 4, "最新+时效词"),
    (re.compile(r"当前.*?(状态|情况|进度|排名|价格|行情|政策)"), 4, "当前+状态词"),
    (re.compile(r"目前.*?(支持|可用|开放|上线|发布|运行)"), 3, "目前+状态词"),
    (re.compile(r"现在.*?(能不能|可不可以|是否可以|还来得及|还开不开)"), 3, "现在+可行性"),
    (re.compile(r"刚刚|刚|才|刚刚才|刚才"), 1, "即时性词"),
    (re.compile(r"有没有.*?(出|发|开|上|更新|修复|支持)"), 3, "有无更新"),
    (re.compile(r"什么时候.*?(出|发|开|上|更新|修复|支持|上线|开放)"), 4, "何时更新"),
    (re.compile(r"(什么是|什么叫|介绍下|介绍一下).{0,5}?(GPT|Claude|Gemini|DeepSeek|Kimi|Sora|Copilot|ChatGPT|OpenAI|Llama)"), 4, "AI概念查询"),
    (re.compile(r"(什么是|什么叫|介绍下|介绍一下).{0,5}?(202[5-9]|最新|新出|新规)"), 4, "时敏概念查询"),
]

# ---------------------------------------------------------------------------
# 维度6：实体识别信号（专有名词 + 疑问结构）
# ---------------------------------------------------------------------------
_ENTITY_PATTERNS: list[tuple[re.Pattern, int, str]] = [
    (re.compile(r"GPT-?\d|Claude|Gemini|Llama|通义|文心|千问|智谱|DeepSeek|Kimi|豆包"), 3, "AI产品"),
    (re.compile(r"Windows\s*\d+|macOS|iOS\s*\d+|Android\s*\d+|HarmonyOS"), 3, "操作系统"),
    (re.compile(r"Python\s*3\.\d+|Node\.js|React|Vue|Next\.js|Django|FastAPI"), 1, "编程框架"),
    (re.compile(r"ChatGPT|OpenAI|Anthropic|Google|Meta|Microsoft|Apple|Nvidia"), 2, "科技公司"),
    (re.compile(r"世博会|奥运会|世界杯|亚运会|冬奥会|欧洲杯|亚洲杯|全运会"), 4, "大型赛事"),
    (re.compile(r"双十一|618|黑五|双十二|年货节|购物节"), 3, "购物节"),
    (re.compile(r"考研|国考|省考|事业编|公务员|选调|教资|法考|注会|一建|二建"), 3, "考试名称"),
    (re.compile(r"诺贝尔|奥斯卡|格莱美|金球奖|金鸡奖|百花奖|茅盾奖"), 3, "奖项名称"),
    (re.compile(r"两会|人大|政协|党代会|中央全会|国务院"), 3, "政治事件"),
    (re.compile(r"[\u4e00-\u9fa5]{2,4}(省|市|自治区)(的)?(政策|规定|补贴|落户|限购)"), 3, "地方政策"),
    (re.compile(r"[\u4e00-\u9fa5]{2,6}(大学|学院|中学)(的)?(录取线|分数线|招生|排名)"), 3, "学校信息"),
    (re.compile(r"[\u4e00-\u9fa5]{2,}(医院|诊所)(的)?(挂号|排班|专家|门诊)"), 2, "医疗信息"),
    (re.compile(r"[\u4e00-\u9fa5]{2,}(地铁|公交|高铁|火车|航班)(的)?(时刻表|路线|班次|票价)"), 3, "交通信息"),
]

# ---------------------------------------------------------------------------
# 维度7：比较评价信号（需要实时数据对比）
# ---------------------------------------------------------------------------
_COMPARISON_PATTERNS: list[tuple[re.Pattern, int, str]] = [
    (re.compile(r"和.{1,10}(哪个好|哪个值得|哪个好|哪个强|哪个便宜|怎么选|区别|对比|比较|不同|差异)"), 4, "比较选择"),
    (re.compile(r"还是.{1,10}(好|值得|强|便宜|划算)"), 3, "还是选择"),
    (re.compile(r"对比|比较|区别|差异|不同|优缺点|优劣"), 2, "对比词"),
    (re.compile(r"性价比|划算|值得买|推荐买|买哪个|选哪个"), 3, "购买决策"),
    (re.compile(r"排行|排名|Top|top|前十|前五|榜单|口碑"), 3, "排名推荐"),
    (re.compile(r"评测|测评|体验|使用感受|真实评价"), 3, "评测体验"),
]

# ---------------------------------------------------------------------------
# 维度8：事实特异性信号（要求精确数字/日期/地点）
# ---------------------------------------------------------------------------
_FACT_SPECIFICITY_PATTERNS: list[tuple[re.Pattern, int, str]] = [
    (re.compile(r"\d+月\d+[日号]"), 3, "具体日期"),
    (re.compile(r"放假|放假安排|假期|调休|补班|补休|调课"), 4, "假期安排"),
    (re.compile(r"录取线|分数线|合格线|及格线|最低分|最高分"), 4, "分数查询"),
    (re.compile(r"报名费|学费|票价|门票|价格|多少钱|收费"), 3, "价格查询"),
    (re.compile(r"营业时间|开放时间|上班时间|开门|关门|打烊"), 4, "时间查询"),
    (re.compile(r"地址|在哪|位置|怎么走|怎么去|路线|导航"), 2, "地点查询"),
    (re.compile(r"电话|联系方式|客服|咨询电话|预约"), 2, "联系方式"),
    (re.compile(r"要求|条件|资格|门槛|限制|年龄限制|学历要求"), 2, "条件查询"),
    (re.compile(r"流程|步骤|怎么办|如何办理|怎么申请|怎么操作"), 1, "流程查询"),
    (re.compile(r"名额|招生人数|招聘人数|录取人数|限购"), 3, "名额查询"),
    (re.compile(r"官网|官方网站|下载地址|下载链接|安装包"), 3, "官方资源"),
]

# ---------------------------------------------------------------------------
# 维度3补充：实时数据信号（数据频繁变化的领域）
# ---------------------------------------------------------------------------
_REALTIME_DATA_PATTERNS: list[tuple[re.Pattern, int, str]] = [
    (re.compile(r"汇率|换汇|外汇|人民币汇率|美元汇率|欧元汇率"), 5, "汇率查询"),
    (re.compile(r"油价|汽油价|柴油价|92号|95号|98号"), 5, "油价查询"),
    (re.compile(r"金价|黄金价|银价|铂金价|金价走势"), 5, "贵金属价格"),
    (re.compile(r"房价|二手房|新房|楼盘|均价|成交价"), 4, "房价查询"),
    (re.compile(r"限行|限号|尾号限行|单双号"), 4, "限行查询"),
    (re.compile(r"停水|停电|停气|检修|维修|维护通知"), 4, "民生通知"),
    (re.compile(r"快递|物流|发货|到货|运费|邮费"), 2, "物流查询"),
    (re.compile(r"招聘|求职|岗位|薪资|待遇|offer|面试结果"), 3, "招聘求职"),
    (re.compile(r"疫苗|挂号|核酸检测|门诊|就诊|医保"), 3, "医疗健康"),
    (re.compile(r"签证|护照|出入境|海关|入境政策"), 4, "出入境"),
]

# ---------------------------------------------------------------------------
# 维度4：否定信号（明确不需要搜索的场景）
# ---------------------------------------------------------------------------
_NEGATIVE_PATTERNS: list[tuple[re.Pattern, int, str]] = [
    (re.compile(r"计算|算一下|等于多少|\d+\s*[\+\-\*×xX÷/]\s*\d+"), 3, "数学计算"),
    (re.compile(r"写(一|个|段|篇)|帮我写|生成|创作|编一个|编个"), 3, "创作写作"),
    (re.compile(r"代码|编程|python|java|javascript|函数|算法|bug|调试"), 2, "编程问题"),
    (re.compile(r"翻译|translate"), 2, "翻译请求"),
    (re.compile(r"你好|早上好|晚上好|晚安|谢谢|再见"), 3, "寒暄闲聊"),
    (re.compile(r"^(今天|现在|当前)(几号|几点|几时|星期几|周几|什么时间|什么日期)$"), 5, "纯时间查询"),
]

# ---------------------------------------------------------------------------
# 否定信号增强：时敏性常识例外（"什么是X"但X是近期概念，仍需搜索）
# ---------------------------------------------------------------------------
_NEGATIVE_OVERRIDE_PATTERNS: list[tuple[re.Pattern, int, str]] = [
    (re.compile(r"什么是.*?(GPT|Claude|Gemini|Llama|Sora|Copilot|DeepSeek|Kimi|豆包|通义|文心)"), 4, "AI概念解释"),
    (re.compile(r"什么是.*?(202[5-9]|最新|新出|新发|新规|新政)"), 4, "时敏概念解释"),
    (re.compile(r"解释一下.*?(政策|规定|新规|新法|改革|调整)"), 3, "时敏政策解释"),
    (re.compile(r"(什么是|什么叫|介绍下|介绍一下).{0,5}?(GPT|Claude|Gemini|DeepSeek|Kimi|Sora|Copilot|ChatGPT|OpenAI)"), 4, "AI产品解释"),
]

# ---------------------------------------------------------------------------
# 上下文感知：追问型搜索需求
# ---------------------------------------------------------------------------
_FOLLOWUP_SEARCH_PATTERNS: list[tuple[re.Pattern, int, str]] = [
    (re.compile(r"^那.{1,10}(呢|怎么样|什么时候|在哪|多少|有没有)$"), 3, "追问话题"),
    (re.compile(r"^还有呢|还有吗|还有没有|除此之外"), 2, "追问补充"),
    (re.compile(r"^具体(一点|来说|是)|详细(一点|说说|介绍)"), 1, "追问详情"),
]

# 搜索阈值：总分 >= 此值则触发搜索
_SEARCH_THRESHOLD = 4


def _check_negative_override(clean_msg: str) -> int:
    """检查否定信号的覆盖条件

    当消息同时命中否定信号和覆盖信号时，覆盖信号可以抵消否定减分。
    例如 "什么是GPT-5" 虽然命中"什么是"否定信号，
    但 GPT-5 是近期概念，仍需搜索。

    参数:
        clean_msg: 清洗后的消息

    返回:
        覆盖加分（抵消否定减分）
    """
    bonus = 0
    for pattern, weight, label in _NEGATIVE_OVERRIDE_PATTERNS:
        if pattern.search(clean_msg):
            bonus += weight
    return bonus


def compute_search_score(
    user_message: str,
    conversation_history: list[dict] | None = None,
) -> tuple[int, list[str]]:
    """计算用户消息的搜索需求评分

    八维度评分：
      1. 问题模式层：疑问词+实体
      2. 实体时效层：专有名词+时间词
      3. 话题类别层：特定话题几乎必搜
      4. 否定信号层：明确不需要搜索
      5. 知识边界层：LLM 训练截止后的事实
      6. 实体识别层：专有名词+疑问结构
      7. 比较评价层：需要实时数据对比
      8. 事实特异性层：要求精确数字/日期/地点

    参数:
        user_message: 用户原始消息
        conversation_history: 对话历史（可选，用于上下文感知）

    返回:
        (总分, 命中信号列表)
    """
    if not user_message or not user_message.strip():
        return (0, [])

    clean_msg = user_message.replace("？", "").replace("?", "").replace(" ", "")
    score = 0
    signals: list[str] = []

    # 维度1-3：基础正向信号
    for pattern, weight, label in _POSITIVE_PATTERNS:
        if pattern.search(clean_msg):
            score += weight
            signals.append(f"+{weight} {label}")

    # 维度5：知识边界信号
    for pattern, weight, label in _KNOWLEDGE_BOUNDARY_PATTERNS:
        if pattern.search(clean_msg):
            score += weight
            signals.append(f"+{weight} [KB]{label}")

    # 维度6：实体识别信号
    for pattern, weight, label in _ENTITY_PATTERNS:
        if pattern.search(clean_msg):
            score += weight
            signals.append(f"+{weight} [ENT]{label}")

    # 维度7：比较评价信号
    for pattern, weight, label in _COMPARISON_PATTERNS:
        if pattern.search(clean_msg):
            score += weight
            signals.append(f"+{weight} [CMP]{label}")

    # 维度8：事实特异性信号
    for pattern, weight, label in _FACT_SPECIFICITY_PATTERNS:
        if pattern.search(clean_msg):
            score += weight
            signals.append(f"+{weight} [FACT]{label}")

    # 维度3补充：实时数据信号
    for pattern, weight, label in _REALTIME_DATA_PATTERNS:
        if pattern.search(clean_msg):
            score += weight
            signals.append(f"+{weight} [RT]{label}")

    # 维度4：否定信号
    neg_total = 0
    for pattern, weight, label in _NEGATIVE_PATTERNS:
        if pattern.search(clean_msg):
            neg_total += weight
            signals.append(f"-{weight} {label}")

    # 否定信号覆盖检查
    if neg_total > 0:
        override_bonus = _check_negative_override(clean_msg)
        if override_bonus > 0:
            neg_total = max(0, neg_total - override_bonus)
            signals.append(f"+{override_bonus} 否定覆盖")

    score -= neg_total

    # 上下文感知：追问型搜索需求
    if conversation_history:
        followup_bonus = _check_followup_context(clean_msg, conversation_history)
        if followup_bonus > 0:
            score += followup_bonus
            signals.append(f"+{followup_bonus} [CTX]追问搜索")

    # 追问模式（无需对话历史也能检测的简单模式）
    for pattern, weight, label in _FOLLOWUP_SEARCH_PATTERNS:
        if pattern.search(clean_msg):
            score += weight
            signals.append(f"+{weight} [FUP]{label}")

    return (score, signals)


def _check_followup_context(
    clean_msg: str,
    conversation_history: list[dict],
) -> int:
    """检查对话历史中的追问型搜索需求

    当用户在搜索结果后追问相关话题时，追加搜索评分。
    例如：
      AI: "2026年软考时间是5月..." → 用户: "那报名条件是什么"
      AI: "北京明天晴..." → 用户: "后天呢"

    参数:
        clean_msg: 清洗后的消息
        conversation_history: 对话历史

    返回:
        追问搜索加分
    """
    if not conversation_history or len(conversation_history) < 2:
        return 0

    last_assistant_msg = ""
    for msg in reversed(conversation_history):
        if msg.get("role") == "assistant":
            last_assistant_msg = msg.get("content", "")
            break

    if not last_assistant_msg:
        return 0

    assistant_search_indicators = [
        "搜索结果", "查询到", "根据搜索", "网上", "来源:",
        "搜索显示", "查到", "检索到", "最新消息", "据报道",
    ]
    is_search_result = any(ind in last_assistant_msg for ind in assistant_search_indicators)

    if not is_search_result:
        return 0

    followup_patterns = [
        r"^那.{1,10}(呢|怎么样|什么时候|在哪|多少|有没有)",
        r"^还有呢|还有吗|还有没有",
        r"^具体(一点|来说|是)",
    ]
    for pat in followup_patterns:
        if re.search(pat, clean_msg):
            return 3

    return 0


def needs_search(
    user_message: str,
    conversation_history: list[dict] | None = None,
) -> bool:
    """判断用户消息是否需要联网搜索

    参数:
        user_message: 用户原始消息
        conversation_history: 对话历史（可选，用于上下文感知）

    返回:
        True: 需要搜索
        False: 不需要搜索
    """
    score, signals = compute_search_score(user_message, conversation_history)
    result = score >= _SEARCH_THRESHOLD
    if result:
        logger.info(f"[SearchIntent] 搜索意图命中: score={score}, signals={signals}")
    return result


def extract_search_query(user_message: str) -> str:
    """从用户消息中提取适合搜索的查询词

    清洗策略：
      1. 去除寒暄词
      2. 去除倒计时词（"距离"/"还有几天"）
      3. 去除搜索前缀词（"帮我搜"/"查一下"）
      4. 去除比较选择词（"和X哪个好"）
      5. 添加时间上下文（当前年份、上半年/下半年推断）
      6. 如果清洗后为空，返回原始消息

    时间上下文增强：
      - 当查询涉及考试/赛事等周期性事件时，自动推断当前应搜索的时间范围
      - 例如5月问"软考"→ 上半年已过 → 搜索"2026年下半年软考时间"
      - 例如1月问"软考"→ 上半年未到 → 搜索"2026年上半年软考时间"

    参数:
        user_message: 用户原始消息

    返回:
        清洗后并添加时间上下文的搜索查询词
    """
    query = user_message.strip()

    query = re.sub(
        r"^(搜索|查找|搜一下|帮我搜|帮我查|查一下|查查|搜一搜|帮我搜索|帮我查找|帮我找|帮我找找|请问|麻烦问|问一下)\s*",
        "", query
    ).strip()

    query = re.sub(r"(距离|离)\s*", "", query).strip()
    query = re.sub(r"(还有几天|还剩几天|剩下几天|还有多久|还差几天)\s*$", "", query).strip()

    query = re.sub(r"^(请问|麻烦|帮忙|你好|您好)\s*", "", query).strip()

    query = re.sub(r"(和.{1,10}哪个好|和.{1,10}怎么选|还是.{1,5}好)\s*$", "", query).strip()

    if not query:
        query = user_message.strip()

    query = _enrich_query_with_time_context(query)

    return query


def _enrich_query_with_time_context(query: str) -> str:
    """为搜索查询添加时间上下文

    核心逻辑：
      1. 检测查询中是否包含周期性事件关键词（考试/赛事/节日等）
      2. 如果包含且查询中没有明确年份/上下半年 → 自动补充
      3. 推断规则：
         - 1-4月 → 搜索"上半年"（上半年考试通常5-6月举行）
         - 5-8月 → 搜索"下半年"（上半年已过，下半年通常11月举行）
         - 9-12月 → 搜索"下半年"（下半年考试通常11月举行）

    参数:
        query: 清洗后的搜索查询词

    返回:
        添加时间上下文后的搜索查询词
    """
    has_year = bool(re.search(r"20\d{2}年", query))
    has_half = bool(re.search(r"上半年|下半年", query))

    if has_year and has_half:
        return query

    periodic_event_patterns = [
        (re.compile(r"软考"), "考试"),
        (re.compile(r"考研"), "考试"),
        (re.compile(r"高考"), "考试"),
        (re.compile(r"中考"), "考试"),
        (re.compile(r"国考"), "考试"),
        (re.compile(r"省考"), "考试"),
        (re.compile(r"考公"), "考试"),
        (re.compile(r"事业编"), "考试"),
        (re.compile(r"教资|教师资格"), "考试"),
        (re.compile(r"法考"), "考试"),
        (re.compile(r"注会"), "考试"),
        (re.compile(r"一建|二建"), "考试"),
        (re.compile(r"公务员"), "考试"),
        (re.compile(r"选调"), "考试"),
        (re.compile(r"世界杯"), "赛事"),
        (re.compile(r"奥运会"), "赛事"),
        (re.compile(r"亚运会"), "赛事"),
        (re.compile(r"欧冠"), "赛事"),
        (re.compile(r"欧洲杯"), "赛事"),
        (re.compile(r"亚洲杯"), "赛事"),
        (re.compile(r"全运会"), "赛事"),
        (re.compile(r"世博会"), "展会"),
        (re.compile(r"进博会"), "展会"),
        (re.compile(r"广交会"), "展会"),
        (re.compile(r"双十一|618"), "购物节"),
        (re.compile(r"春运"), "民生"),
        (re.compile(r"秋招|春招"), "招聘"),
        (re.compile(r"报名"), "报名"),
        (re.compile(r"录取"), "录取"),
        (re.compile(r"分数线"), "分数"),
    ]

    matched_event = None
    for pattern, event_type in periodic_event_patterns:
        if pattern.search(query):
            matched_event = event_type
            break

    if not matched_event:
        return query

    # 清洗疑问词和冗余词，提取核心搜索词
    core_query = query
    core_query = re.sub(r"^今天|^现在|^当前|^目前|^今年", "", core_query)
    core_query = re.sub(r"什么时候|几号|几时|哪天|哪一天|是哪天|是几号", "", core_query)
    core_query = re.sub(r"还有几天|还剩几天|还有多久|还差几天$", "", core_query)
    core_query = re.sub(r"多少|怎么样|好不好|有没有|是否", "", core_query)
    core_query = core_query.strip()

    if not core_query:
        core_query = query

    from datetime import datetime
    now = datetime.now()
    year = now.year
    month = now.month

    enriched = core_query
    if not has_year:
        enriched = f"{year}年" + enriched

    if not has_half and matched_event in ("考试", "报名", "录取", "分数", "招聘"):
        # 高考/中考固定在6月举行，始终搜索上半年
        first_half_only = bool(re.search(r"高考|中考", core_query))
        if first_half_only:
            enriched = enriched + "上半年"
        elif month >= 5 and month <= 8:
            enriched = enriched + "下半年"
        elif month >= 9:
            enriched = enriched + "下半年"
        else:
            enriched = enriched + "上半年"

    if matched_event in ("考试", "报名", "录取", "分数") and "时间" not in enriched:
        enriched = enriched + "时间"

    # 优化顺序：将"下半年/上半年"移到事件名后面、时间前面
    # 例如 "河北软考下半年时间" → "下半年河北软考时间"（更自然的搜索词）
    enriched = re.sub(
        r"^(20\d{2}年)(.+?)(上半年|下半年)(时间)$",
        r"\1\3\2\4",
        enriched
    )

    return enriched


def get_search_confidence(
    user_message: str,
    conversation_history: list[dict] | None = None,
) -> str:
    """获取搜索意图的置信度等级

    用于前端展示或日志分析，帮助理解分类决策。

    参数:
        user_message: 用户原始消息
        conversation_history: 对话历史（可选）

    返回:
        "high" / "medium" / "low" / "none"
    """
    score, _ = compute_search_score(user_message, conversation_history)
    if score >= 8:
        return "high"
    elif score >= _SEARCH_THRESHOLD:
        return "medium"
    elif score >= 2:
        return "low"
    else:
        return "none"


# =============================================================================
# 直接运行验证
# =============================================================================
if __name__ == "__main__":
    test_cases = [
        # 需要搜索 - 基础场景
        ("距离河北软考还有几天", True),
        ("2026年世界杯在哪举办", True),
        ("iPhone 18什么时候出", True),
        ("特斯拉股价多少", True),
        ("最近有什么好看的电影", True),
        ("帮我搜索一下Python教程", True),
        ("河北软考几号", True),
        ("今年考研什么时候报名", True),
        ("NBA总决赛比分", True),
        ("北京到上海的高铁时刻表", True),
        ("2026年软考时间安排", True),
        ("最近有什么新闻", True),
        ("推荐一个旅游景点", True),
        ("明天北京天气怎么样", True),

        # 需要搜索 - 知识边界场景
        ("2025年有什么新政策", True),
        ("2026年世博会在哪举办", True),
        ("最新版本的ChatGPT是什么", True),
        ("目前GPT-5出了吗", True),
        ("今年国考什么时候报名", True),
        ("当前人民币汇率是多少", True),

        # 需要搜索 - 实体识别场景
        ("GPT-5什么时候发布", True),
        ("DeepSeek最新模型是什么", True),
        ("Windows 12什么时候出", True),
        ("2026年亚运会在哪办", True),
        ("诺贝尔奖2025年得主是谁", True),
        ("广东省最新落户政策", True),

        # 需要搜索 - 比较评价场景
        ("iPhone 16和华为Mate70哪个好", True),
        ("比亚迪和特斯拉怎么选", True),
        ("考研和考公哪个更值得", True),
        ("笔记本电脑性价比排行", True),
        ("React和Vue哪个好", True),

        # 需要搜索 - 事实特异性场景
        ("5月1号放假安排", True),
        ("清华录取分数线多少", True),
        ("北京故宫门票多少钱", True),
        ("国家图书馆营业时间", True),
        ("软考报名条件是什么", True),
        ("GPT-4官网下载地址", True),

        # 需要搜索 - 实时数据场景
        ("今天油价多少", True),
        ("黄金价格多少一克", True),
        ("北京今天限行尾号", True),
        ("上海二手房均价多少", True),
        ("美元汇率多少", True),
        ("最近有没有招聘会", True),

        # 需要搜索 - 否定覆盖场景
        ("什么是GPT-5", True),
        ("什么是2025年新规", True),

        # 不需要搜索
        ("今天几号", False),
        ("现在几点了", False),
        ("3+5等于多少", False),
        ("帮我写一段朋友圈文案", False),
        ("你好，请介绍一下你自己", False),
        ("Python怎么写快速排序", False),
        ("什么是量子力学", False),
        ("翻译一下这段话", False),
        ("解释一下相对论", False),
        ("今天天气不错", False),
        ("几点吃饭", False),
    ]

    print("=" * 80)
    print("  SearchIntent 八维度搜索意图识别 测试结果")
    print("=" * 80)
    print()

    passed = 0
    failed = 0

    for msg, expected in test_cases:
        score, signals = compute_search_score(msg)
        result = score >= _SEARCH_THRESHOLD
        status = "PASS" if result == expected else "FAIL"
        if status == "PASS":
            passed += 1
        else:
            failed += 1
        signal_str = ", ".join(signals[:4]) if signals else "无"
        confidence = get_search_confidence(msg)
        print(f"  [{status}] {msg:40} | score={score:2d} | conf={confidence:6s} | "
              f"预期={'搜' if expected else '不搜':2s} | 实际={'搜' if result else '不搜':2s} | {signal_str}")

    print()
    print(f"  通过: {passed}  失败: {failed}  总计: {len(test_cases)}")

    if failed == 0:
        print("\n  全部测试通过!")
    else:
        print(f"\n  有 {failed} 个测试未通过，需要调整规则")

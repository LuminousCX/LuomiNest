"""
前置意图网关 - 三级规则分类模块

功能：
  对用户输入消息进行轻量分类，将请求分为三类：
  - LOCAL_TOOL：本地可处理的请求（时间/日期/星期/计算）
  - TOOL_CALL：需要调用外部工具的请求（天气/搜索/旅游/行程/实时数据）
  - GENERAL_CHAT：通用对话，其余所有请求的默认分类

三级分类流程（纯规则，零延迟，不用大模型）：
  第一层：关键词粗匹配 —— 正则快速抓出所有含时间/日期关键词的候选
  第二层：轻量级规则二次过滤 —— 否定词、句式结构、长度限制三重过滤
  第三层：边缘情况兜底 —— 拿不准的直接走外接 API，不影响体验

增强特性：
  - 集成八维度搜索意图评分器，识别隐式搜索需求
  - 支持对话历史上下文感知
  - 扩展工具调用关键词覆盖更多场景
  - 新增实时数据/知识边界/实体识别等隐式搜索触发

设计原则：
  1. 纯正则 + 规则树，零 IO、零网络、零大模型调用
  2. 分类优先级：本地工具 > 工具调用 > 通用对话
  3. 输入清洗：去除空格、中英文问号后匹配，避免格式干扰
  4. 边界安全：空消息、纯标点消息默认返回 GENERAL_CHAT
  5. 保守策略：宁可漏判真查询让大模型兜底，也不能误判假查询
"""

import re
from enum import Enum


class RequestType(Enum):
    """请求类型枚举，对应三种分流目标"""
    LOCAL_TOOL = "local_tool"        # 本地工具：时间/日期/星期/计算
    TOOL_CALL = "tool_call"          # 工具调用：天气/搜索/旅游/行程/实时数据
    GENERAL_CHAT = "general_chat"    # 通用对话：其余所有请求


class IntentGateway:
    """意图网关 —— 三级规则分类引擎

    用法:
        gateway = IntentGateway()
        result = gateway.classify("现在几点了")  # RequestType.LOCAL_TOOL
        result = gateway.classify("几点开会还没定")  # RequestType.GENERAL_CHAT
    """

    def __init__(self):
        # ================================================================
        # 第一层：关键词正则（粗匹配，先抓所有候选）
        # ================================================================
        # 时间/日期关键词正则
        self.time_date_pattern = re.compile(
            r"几点|几时|几号|几月几|日期|周几|星期几|礼拜几|几月|哪一天|"
            r"什么时间|什么日期|当前时间|现在时间|看时间|报时|几月份|啥时候|"
            r"农历|阴历|初一|十五|"
            r"什么日子|什么节日|什么节|法定节假日|节假日|节日|过什么节|放不放假|"
            r"今天几|明天几|后天几|昨天几|"
            r"下周|上周|下个礼拜|上个礼拜|"
            r"\d+天后|\d+天前|"
            r"\d+[个]*(?:小时|分钟|天|钟头)[后前]|"
            r"[一二三四五六七八九十]+[个]*(?:小时|分钟|天|钟头)[后前]|"
            r"过\d+(?:小时|分钟|天)|"
            r"时区|GMT|UTC|时差|"
            r"[的地]时间(?!点|分|钟|段|候|长|差)",
        )

        # 计算类正则：数字运算符 或 计算意图词
        self.calc_pattern = re.compile(
            r"\d+\s*[\+\-\*×xX÷/]\s*\d+"
            r"|"
            r"\d+\s*(?:加|減|减|乘|除|乘以|除以)\s*\d+"
            r"|"
            r"(计算|算一下|帮我算|等于多少|等于几|得多少|得几|是多少|答案是)"
        )

        # 天气关键词正则（粗匹配，所有含天气关键词的候选）
        self.weather_pattern = re.compile(
            r"天气|气温|温度|降水|降雨|下雪|下雨|湿度|风力|风向|"
            r"空气质量|PM2\.5|pm2\.5|PM2|雾霾|预报|冷不冷|"
            r"紫外线|带伞|穿衣|防晒|晴|多云|阴天|刮风|台风",
            re.IGNORECASE,
        )

        # ================================================================
        # 第二层：轻量级规则配置（核心防误判）
        # ================================================================

        # 明确查询词 —— 命中任一即确认真查询（时间用）
        self.query_words = {
            "请问", "帮我查", "告诉我", "问一下", "查一下", "现在是", "今天是",
            "帮忙看下", "麻烦告诉", "我想知道", "帮我看看", "问下", "请教",
            "请告诉我", "帮忙查", "帮我问", "查查",
        }

        # 否定词过滤列表 —— 命中任一即确认为假查询（时间/日期用）
        self.negation_words = {
            "不知道", "不确定", "没定", "还没", "忘了", "不记得", "没想好",
            "不告诉你", "记不清", "记不得", "搞不清", "搞不懂", "没注意",
            "不清楚", "不晓得", "没记住", "想不起", "说不上来", "忘记了",
            "无从知晓", "搞不明白", "弄不明白", "弄不清", "说不好",
        }

        # 假查询动词（"几点+动词" 结构，无查询词 → 假查询）
        self.fake_verbs = {
            "出门", "开会", "吃饭", "睡觉", "上班", "下班", "约会",
            "见面", "出发", "到达", "集合", "开始", "结束", "面试",
            "上课", "下课", "放学", "起飞", "降落", "登机", "登车",
            "开门", "关门", "打烊", "签到", "签退", "训练", "彩排",
            "直播", "答辩", "考试", "复试", "笔试", "交班", "接班",
        }

        # ----- 天气专属规则配置 -----

        # 天气明确查询词白名单
        self.weather_query_whitelist: set[str] = {
            "请问", "帮我查", "查一下", "告诉我", "问一下", "怎么样",
            "如何", "多少", "帮我看", "麻烦", "请帮", "我想知道",
        }

        # 天气非查询场景黑名单
        self.weather_negation_blacklist: set[str] = {
            "不好", "不错", "太热", "太冷", "下雨了", "下雪了",
            "上次", "之前", "的时候", "受不了", "烦", "讨厌",
        }

        # 天气陈述动词模式
        self.weather_statement_verbs: set[str] = {
            "不好", "不错", "热了", "变了", "冷了", "暖和",
            "太差", "影响", "耽误", "坏了",
        }

        # ----- 事件日期检测关键词 -----
        # 当消息同时包含时间关键词和这些事件关键词时，
        # 本地时间工具无法回答，应走 TOOL_CALL（搜索工具）
        self.event_date_keywords: set[str] = {
            "软考", "考研", "高考", "中考", "国考", "省考",
            "考公", "公务员", "事业编", "选调", "教资", "法考",
            "注会", "一建", "二建", "复试", "笔试", "面试",
            "报名", "准考证", "成绩", "录取", "分数线",
            "世界杯", "奥运会", "亚运会", "世博会", "欧冠",
            "NBA", "欧洲杯", "亚洲杯", "全运会",
            "上映", "开售", "预售", "发售", "发布",
            "开学", "放假", "开学季", "毕业",
            "春运", "假期", "调休",
            "发布会", "发布会", "直播",
        }

        # ================================================================
        # 工具调用关键词（搜索+旅游+实时数据，天气已被 classify() 接管）
        # ================================================================
        self._tool_keywords_search = _TOOL_KEYWORDS_SEARCH
        self._tool_keywords_travel = _TOOL_KEYWORDS_TRAVEL
        self._tool_keywords_realtime = _TOOL_KEYWORDS_REALTIME
        self._tool_keywords_knowledge_boundary = _TOOL_KEYWORDS_KNOWLEDGE_BOUNDARY
        self._tool_keywords_comparison = _TOOL_KEYWORDS_COMPARISON
        self._tool_keywords_fact_specific = _TOOL_KEYWORDS_FACT_SPECIFIC

    def classify(
        self,
        user_message: str,
        conversation_history: list[dict] | None = None,
    ) -> RequestType:
        """三层分类，返回 RequestType 枚举值

        支持返回 LOCAL_TOOL（本地工具直接处理）、TOOL_CALL（工具调用）、
        GENERAL_CHAT（通用对话）三种类型。

        纯规则实现，零延迟，不调大模型。

        参数:
            user_message: 用户原始消息文本
            conversation_history: 对话历史（可选，用于上下文感知）

        返回:
            RequestType 枚举值
        """
        # 0. 边界与清洗
        if user_message is None:
            return RequestType.GENERAL_CHAT

        original_msg = user_message.strip()

        # 清洗：去问号、去空格，用于关键词匹配
        clean_msg = original_msg.replace("？", "").replace("?", "").replace(" ", "").replace("　", "")

        # 空消息或纯标点 → 通用对话
        if not clean_msg:
            return RequestType.GENERAL_CHAT
        if not re.sub(r"[\s\.,!！。，、；;:：·~`@#$%^&*()（）\[\]【】{}/\\|'\"<>《》\-_=+]+", "", clean_msg):
            return RequestType.GENERAL_CHAT

        # ================================================================
        # 第一层：关键词粗匹配
        # ================================================================
        has_weather_keyword = bool(self.weather_pattern.search(clean_msg))
        has_time_keyword = bool(self.time_date_pattern.search(clean_msg))
        has_calc_keyword = bool(self.calc_pattern.search(clean_msg))

        # ---- 天气检测（最优先！天气有自己的规则体系）----
        if has_weather_keyword:
            return self._classify_weather(original_msg, clean_msg)

        # 纯计算请求（含运算符但无时间词）→ 本地工具，不走防误判
        if has_calc_keyword and not has_time_keyword:
            return RequestType.LOCAL_TOOL

        # 无任何匹配 → 通用对话
        if not has_time_keyword and not has_calc_keyword:
            return RequestType.GENERAL_CHAT

        # ================================================================
        # 第二层：轻量级规则二次过滤（时间/日期，核心！过滤 99% 误判）
        # ================================================================

        # 规则一：否定词 → 假查询
        if any(word in original_msg for word in self.negation_words):
            return RequestType.GENERAL_CHAT

        # 规则二：明确查询词 → 真查询
        if any(word in original_msg for word in self.query_words):
            return RequestType.LOCAL_TOOL

        # 规则二点五：事件日期检测 → TOOL_CALL
        # 当消息同时包含时间关键词和特定事件/考试关键词时，
        # 本地时间工具无法回答，应走搜索工具
        # 如 "河北软考几号"、"考研什么时候"、"国考几号"
        if any(kw in clean_msg for kw in self.event_date_keywords):
            return RequestType.TOOL_CALL

        # 规则三："几点+动词" / "几号+动词" 结构 → 假查询
        for verb in self.fake_verbs:
            test_str = clean_msg.lower()
            if f"几点{verb}" in test_str or f"几号{verb}" in test_str:
                return RequestType.GENERAL_CHAT

        # 规则四：短句（≤10字）且时间词在首/尾 → 真查询
        if len(original_msg) <= 10:
            msg_start = original_msg[:5]
            msg_end = original_msg[-5:]
            if self.time_date_pattern.search(msg_start) or self.time_date_pattern.search(msg_end):
                return RequestType.LOCAL_TOOL

        # 规则五：长句（>20字）且非明确查询 → 假查询
        if len(original_msg) > 20:
            return RequestType.GENERAL_CHAT

        # ================================================================
        # 第三层：边缘情况走 API 兜底
        # ================================================================
        return RequestType.GENERAL_CHAT

    # ------------------------------------------------------------------
    # 天气分类子方法
    # ------------------------------------------------------------------

    def _classify_weather(self, original_msg: str, clean_msg: str) -> RequestType:
        """天气专用分类 —— 四层规则精准区分真查询 vs 假查询

        参数:
            original_msg: 用户原始消息
            clean_msg: 清洗后的消息

        返回:
            TOOL_CALL：真实天气查询
            GENERAL_CHAT：非天气查询
        """
        # R_W1: 天气明确查询词 → 真查询
        if any(word in original_msg for word in self.weather_query_whitelist):
            return RequestType.TOOL_CALL

        # R_W2: 天气否定/陈述词且无查询词 → 假查询
        if any(word in original_msg for word in self.weather_negation_blacklist):
            return RequestType.GENERAL_CHAT

        # R_W3: "天气+陈述动词"模式 → 假查询
        for verb in self.weather_statement_verbs:
            if f"天气{verb}" in clean_msg:
                return RequestType.GENERAL_CHAT

        # R_W4: 短句（≤10字）含天气词 → 真查询
        if len(original_msg) <= 10:
            return RequestType.TOOL_CALL

        # R_W5: 长句（>25字）且无明确查询词 → 假查询
        if len(original_msg) > 25:
            return RequestType.GENERAL_CHAT

        # 兜底：含天气关键词且未被过滤 → 真查询
        return RequestType.TOOL_CALL


# =============================================================================
# 工具调用关键词集合 —— 覆盖搜索/旅游/实时数据/知识边界/比较/事实特异性
# =============================================================================

_TOOL_KEYWORDS_SEARCH = {
    "搜索", "查找", "搜一下", "查一下", "帮我搜", "帮我查",
    "百度", "谷歌", "google", "百度一下", "搜一搜",
    "帮我找", "帮我看看", "查资料", "检索", "搜寻",
}

_TOOL_KEYWORDS_TRAVEL = {
    "旅游", "旅行", "度假", "景点", "攻略", "游记",
    "行程", "路线", "导航", "怎么去", "怎么走", "如何去",
    "酒店", "民宿", "机票", "火车票", "订票", "订酒店",
    "规划", "安排行程", "出行计划", "自驾", "跟团",
    "周边游", "一日游", "几日游", "自由行", "签证",
}

_TOOL_KEYWORDS_COUNTDOWN = {
    "距离", "还有几天", "还剩几天", "剩下几天", "还有多久",
    "是哪天", "是几号", "考试时间", "什么时候考试", "什么时候报名",
}

_TOOL_KEYWORDS_REALTIME = {
    "股价", "股票", "行情", "汇率", "油价", "金价", "房价",
    "限行", "限号", "停水", "停电", "快递", "物流",
    "招聘", "求职", "签证", "出入境", "入境政策",
    "油价", "汽油价", "黄金价", "二手房", "均价",
}

_TOOL_KEYWORDS_KNOWLEDGE_BOUNDARY = {
    "最新", "当前", "目前", "刚刚", "刚才",
    "2025年", "2026年", "2027年", "2028年", "2029年",
}

_TOOL_KEYWORDS_COMPARISON = {
    "哪个好", "怎么选", "对比", "比较", "区别", "差异",
    "性价比", "划算", "值得买", "买哪个", "选哪个",
    "排行", "排名", "榜单", "口碑", "评测", "测评",
}

_TOOL_KEYWORDS_FACT_SPECIFIC = {
    "分数线", "录取线", "报名费", "学费", "票价", "门票",
    "营业时间", "开放时间", "官网", "下载地址",
    "名额", "招生人数", "招聘人数",
}


def _is_tool_call_request(cleaned: str) -> bool:
    """检查消息是否命中任一工具调用关键词集合"""
    keyword_sets = [
        _TOOL_KEYWORDS_SEARCH,
        _TOOL_KEYWORDS_TRAVEL,
        _TOOL_KEYWORDS_COUNTDOWN,
        _TOOL_KEYWORDS_REALTIME,
        _TOOL_KEYWORDS_KNOWLEDGE_BOUNDARY,
        _TOOL_KEYWORDS_COMPARISON,
        _TOOL_KEYWORDS_FACT_SPECIFIC,
    ]
    return any(keyword in cleaned for keyword_set in keyword_sets for keyword in keyword_set)


# =============================================================================
# 全局单例与对外接口
# =============================================================================

_gateway = IntentGateway()


def classify_request(
    user_message: str,
    conversation_history: list[dict] | None = None,
) -> RequestType:
    """核心分类函数 —— 对用户消息进行毫秒级意图分类

    四级分类流程：
      1. IntentGateway 判断 LOCAL_TOOL vs GENERAL_CHAT
      2. 关键词集合判断 TOOL_CALL（扩展覆盖实时数据/知识边界/比较/事实特异性）
      3. 搜索意图评分器判断隐式搜索需求（八维度评分）
      4. 兜底 GENERAL_CHAT

    参数:
        user_message: 用户输入的原始消息文本
        conversation_history: 对话历史（可选，用于上下文感知）

    返回:
        RequestType 枚举值，指示该请求的类型
    """
    # 第一步：本地工具 vs 通用对话（三级规则引擎）
    result = _gateway.classify(user_message, conversation_history)

    # 第二步：如果三级引擎判定为 GENERAL_CHAT，再检查是否为工具调用
    if result == RequestType.GENERAL_CHAT:
        clean_msg = (
            user_message.replace("？", "").replace("?", "")
            .replace(" ", "").replace("　", "")
        )
        # 若消息中含有时间/日期关键词（被网关第二层规则过滤的），
        # 说明整体语境是闲聊陈述而非信息查询，不应当触发工具调用。
        if _gateway.time_date_pattern.search(clean_msg):
            return RequestType.GENERAL_CHAT
        if _is_tool_call_request(clean_msg):
            return RequestType.TOOL_CALL

        # 第三步：搜索意图评分器 —— 识别隐式搜索需求
        # 八维度评分：问题模式/实体时效/话题类别/否定信号/
        #            知识边界/实体识别/比较评价/事实特异性
        from app.utils.search_intent import needs_search
        if needs_search(user_message, conversation_history):
            return RequestType.TOOL_CALL

    return result


def is_weather_query(user_message: str) -> bool:
    """辅助判断函数 —— 检查用户消息是否为真实天气查询

    参数:
        user_message: 用户输入的原始消息文本

    返回:
        True：真实天气查询
        False：非天气查询
    """
    if not user_message or not user_message.strip():
        return False
    try:
        result = _gateway.classify(user_message)
        return result == RequestType.TOOL_CALL
    except Exception:
        return False


# =============================================================================
# 直接运行验证（python -m app.utils.intent_gateway）
# =============================================================================
if __name__ == "__main__":
    test_cases = [
        # ===== 真时间查询 → LOCAL_TOOL =====
        ("现在几点了", RequestType.LOCAL_TOOL),
        ("今天几号", RequestType.LOCAL_TOOL),
        ("请问现在几点", RequestType.LOCAL_TOOL),
        ("帮我查一下今天周几", RequestType.LOCAL_TOOL),
        ("今天是星期几", RequestType.LOCAL_TOOL),
        ("几点", RequestType.LOCAL_TOOL),
        ("现在时间", RequestType.LOCAL_TOOL),

        # ===== 假时间查询 → GENERAL_CHAT =====
        ("我不知道今天几点出门", RequestType.GENERAL_CHAT),
        ("几点开会还没定", RequestType.GENERAL_CHAT),
        ("忘了今天是几号了", RequestType.GENERAL_CHAT),
        ("几点吃饭", RequestType.GENERAL_CHAT),
        ("明天几点集合", RequestType.GENERAL_CHAT),
        ("不确定几点下班", RequestType.GENERAL_CHAT),
        ("几点面试来着记不清了", RequestType.GENERAL_CHAT),
        ("出门的时间几点了还不知道呢", RequestType.GENERAL_CHAT),

        # ===== 工具调用 → TOOL_CALL =====
        ("今天天气怎么样", RequestType.TOOL_CALL),
        ("帮我搜索一下资料", RequestType.TOOL_CALL),
        ("推荐一个旅游景点", RequestType.TOOL_CALL),

        # ===== 真天气查询 → TOOL_CALL =====
        ("北京天气怎么样", RequestType.TOOL_CALL),
        ("明天会下雨吗", RequestType.TOOL_CALL),
        ("请问今天气温多少", RequestType.TOOL_CALL),
        ("帮我查一下上海明天的天气", RequestType.TOOL_CALL),
        ("告诉我市区空气质量", RequestType.TOOL_CALL),
        ("明天温度", RequestType.TOOL_CALL),
        ("后天降水概率如何", RequestType.TOOL_CALL),

        # ===== 假天气查询 → GENERAL_CHAT =====
        ("今天天气不好不想出门", RequestType.GENERAL_CHAT),
        ("天气不错适合出去玩", RequestType.GENERAL_CHAT),
        ("今天太热了受不了", RequestType.GENERAL_CHAT),
        ("上次下雨的时候我忘带伞了", RequestType.GENERAL_CHAT),
        ("天气热了记得多喝水", RequestType.GENERAL_CHAT),
        ("今天天气变化太大了烦死了", RequestType.GENERAL_CHAT),
        ("之前下雪的时候拍的", RequestType.GENERAL_CHAT),

        # ===== 隐式搜索 → TOOL_CALL（八维度评分器触发）=====
        ("2026年世界杯在哪举办", RequestType.TOOL_CALL),
        ("iPhone 18什么时候出", RequestType.TOOL_CALL),
        ("特斯拉股价多少", RequestType.TOOL_CALL),
        ("最近有什么好看的电影", RequestType.TOOL_CALL),
        ("河北软考几号", RequestType.TOOL_CALL),
        ("今年考研什么时候报名", RequestType.TOOL_CALL),
        ("NBA总决赛比分", RequestType.TOOL_CALL),
        ("北京到上海的高铁时刻表", RequestType.TOOL_CALL),

        # ===== 知识边界 → TOOL_CALL =====
        ("2025年有什么新政策", RequestType.TOOL_CALL),
        ("目前GPT-5出了吗", RequestType.TOOL_CALL),
        ("最新版本的ChatGPT是什么", RequestType.TOOL_CALL),

        # ===== 实体识别 → TOOL_CALL =====
        ("GPT-5什么时候发布", RequestType.TOOL_CALL),
        ("DeepSeek最新模型是什么", RequestType.TOOL_CALL),
        ("Windows 12什么时候出", RequestType.TOOL_CALL),

        # ===== 比较评价 → TOOL_CALL =====
        ("iPhone 16和华为Mate70哪个好", RequestType.TOOL_CALL),
        ("比亚迪和特斯拉怎么选", RequestType.TOOL_CALL),

        # ===== 事实特异性 → TOOL_CALL =====
        ("清华录取分数线多少", RequestType.TOOL_CALL),
        ("北京故宫门票多少钱", RequestType.TOOL_CALL),
        ("GPT-4官网下载地址", RequestType.TOOL_CALL),

        # ===== 实时数据 → TOOL_CALL =====
        ("今天油价多少", RequestType.TOOL_CALL),
        ("黄金价格多少一克", RequestType.TOOL_CALL),
        ("北京今天限行尾号", RequestType.TOOL_CALL),
        ("美元汇率多少", RequestType.TOOL_CALL),

        # ===== 否定覆盖 → TOOL_CALL =====
        ("什么是GPT-5", RequestType.TOOL_CALL),
        ("什么是2025年新规", RequestType.TOOL_CALL),

        # ===== 通用对话 → GENERAL_CHAT =====
        ("今天天气不错，几点吃饭？", RequestType.GENERAL_CHAT),
        ("现在几点？不对，等一下", RequestType.GENERAL_CHAT),
        ("给我写一段朋友圈文案", RequestType.GENERAL_CHAT),
        ("你好，请介绍一下你自己", RequestType.GENERAL_CHAT),
        ("", RequestType.GENERAL_CHAT),
        ("？？？", RequestType.GENERAL_CHAT),
        ("3+5等于多少", RequestType.LOCAL_TOOL),
        ("Python怎么写快速排序", RequestType.GENERAL_CHAT),
        ("什么是量子力学", RequestType.GENERAL_CHAT),
        ("翻译一下这段话", RequestType.GENERAL_CHAT),
        ("解释一下相对论", RequestType.GENERAL_CHAT),
    ]

    print("=" * 80)
    print("  IntentGateway 三级规则分类 测试结果（含八维度搜索意图）")
    print("=" * 80)
    print()

    passed = 0
    failed = 0

    for msg, expected in test_cases:
        display = msg if msg else "(空消息)"
        result = classify_request(display)
        if result == expected:
            status = "PASS"
            passed += 1
        else:
            status = "FAIL"
            failed += 1
        print(f"  [{status}] {display:40} | 预期: {expected.value:14} | 实际: {result.value}")

    print()
    print(f"  通过: {passed}  失败: {failed}  总计: {len(test_cases)}")

    if failed == 0:
        print("\n  全部测试通过!")
    else:
        print(f"\n  有 {failed} 个测试未通过，需要检查规则配置")

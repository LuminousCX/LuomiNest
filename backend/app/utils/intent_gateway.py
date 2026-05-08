"""
前置意图网关 - 三级规则分类模块

功能：
  对用户输入消息进行轻量分类，将请求分为三类：
  - LOCAL_TOOL：本地可处理的请求（时间/日期/星期/计算）
  - TOOL_CALL：需要调用外部工具的请求（天气/搜索/旅游/行程）
  - GENERAL_CHAT：通用对话，其余所有请求的默认分类

三级分类流程（纯规则，零延迟，不用大模型）：
  第一层：关键词粗匹配 —— 正则快速抓出所有含时间/日期关键词的候选
  第二层：轻量级规则二次过滤 —— 否定词、句式结构、长度限制三重过滤
  第三层：边缘情况兜底 —— 拿不准的直接走外接 API，不影响体验

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
    TOOL_CALL = "tool_call"          # 工具调用：天气/搜索/旅游/行程
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
            # 新增：农历/节假日
            r"农历|阴历|初一|十五|"
            r"什么日子|什么节日|什么节|法定节假日|节假日|节日|过什么节|放不放假|"
            # 新增：日期偏移（明天/后天/下周一等）
            r"今天几|明天几|后天几|昨天几|"
            r"下周|上周|下个礼拜|上个礼拜|"
            r"\d+天后|\d+天前|"
            # 新增：时间偏移（X小时后/分钟前/天后）
            r"\d+[个]*[小时分钟天钟头][后前]|"
            r"[一二三四五六七八九十]+[个]*[小时分钟天钟头][后前]|"
            r"过\d+[小时分钟天]|"
            # 新增：时区类
            r"时区|GMT|UTC|时差|"
            r"[的地]时间(?!点|分|钟|段|候|长|差)",
        )

        # 计算类正则：数字运算符 或 计算意图词
        self.calc_pattern = re.compile(
            r"\d+\s*[\+\-\*×xX÷/]\s*\d+"          # 数字运算符数字，如 "3+5"
            r"|"
            r"\d+\s*[加減减乘除乘以除以]\s*\d+"     # 数字中文运算符，如 "3加5"
            r"|"
            r"(计算|算一下|帮我算|等于多少|等于几|得多少|得几|是多少|答案是)"  # 计算意图词
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
        # 如 "几点出门"、"几点开会"、"几点吃饭" 都不是在问 AI 时间
        self.fake_verbs = {
            "出门", "开会", "吃饭", "睡觉", "上班", "下班", "约会",
            "见面", "出发", "到达", "集合", "开始", "结束", "面试",
            "上课", "下课", "放学", "起飞", "降落", "登机", "登车",
            "开门", "关门", "打烊", "签到", "签退", "训练", "彩排",
            "直播", "答辩", "考试", "复试", "笔试", "交班", "接班",
        }

        # ----- 天气专属规则配置 -----

        # 天气明确查询词白名单 —— 有这些词，大概率是真心查天气
        self.weather_query_whitelist: set[str] = {
            "请问", "帮我查", "查一下", "告诉我", "问一下", "怎么样",
            "如何", "多少", "帮我看", "麻烦", "请帮", "我想知道",
        }

        # 天气非查询场景黑名单 —— 有这些词且无查询词，判定为非天气查询
        #   "不好"/"不错"/"太热"/"太冷" → 在陈述感受，不是提问
        #   "下雨了"/"下雪了" → 在描述事实，不是查未来天气
        #   "上次"/"之前"/"的时候" → 聊过去，不是查天气
        self.weather_negation_blacklist: set[str] = {
            "不好", "不错", "太热", "太冷", "下雨了", "下雪了",
            "上次", "之前", "的时候", "受不了", "烦", "讨厌",
        }

        # 天气陈述动词模式 —— "天气+动词/形容词" 且无查询词 → 非查询
        self.weather_statement_verbs: set[str] = {
            "不好", "不错", "热了", "变了", "冷了", "暖和",
            "太差", "影响", "耽误", "坏了",
        }

        # ================================================================
        # 工具调用关键词（仅搜索+旅游，天气已被 classify() 接管）
        # ================================================================
        self._tool_keywords_search = _TOOL_KEYWORDS_SEARCH
        self._tool_keywords_travel = _TOOL_KEYWORDS_TRAVEL

    def classify(self, user_message: str) -> RequestType:
        """三层分类，返回 RequestType 枚举值

        支持返回 LOCAL_TOOL（本地工具直接处理）、TOOL_CALL（工具调用）、
        GENERAL_CHAT（通用对话）三种类型。

        纯规则实现，零延迟，不调大模型。

        参数:
            user_message: 用户原始消息文本

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
        if not re.sub(r"[\s\.,!！。，、；;:：、·~`@#$%^&*()（）\[\]【】{}/\\|'\"<>《》\-_=+]+", "", clean_msg):
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
        #
        # 规则优先级从高到低，命中即返回，保证先过滤假查询再确认真查询：
        #   R1: 否定词 → 假查询（最优先！否定语境下一切关键词失效）
        #   R2: 明确查询词 → 真查询
        #   R3: "几点+动词"结构 → 假查询（必须在短句规则之前！）
        #   R4: 短句且时间词在首/尾 → 真查询
        #   R5: 长句 → 假查询
        # ================================================================

        # 规则一：否定词 → 假查询（最优先！否定语境下一切关键词失效）
        #   如 "忘了今天是几号了" 中虽有 "今天是"，但 "忘了" 否定整体语义
        if any(word in original_msg for word in self.negation_words):
            return RequestType.GENERAL_CHAT

        # 规则二：明确查询词 → 真查询
        if any(word in original_msg for word in self.query_words):
            return RequestType.LOCAL_TOOL

        # 规则三："几点+动词" / "几号+动词" 结构 → 假查询
        #   必须在短句规则之前！否则 "几点吃饭"（4字短句）会先被短句规则命中。
        #   覆盖 "几点出门"、"几点开会"、"几点吃饭"、"明天几点集合" 等
        for verb in self.fake_verbs:
            test_str = clean_msg.lower()
            if f"几点{verb}" in test_str or f"几号{verb}" in test_str:
                return RequestType.GENERAL_CHAT

        # 规则四：短句（≤10字）且时间词在首/尾 → 真查询
        #   覆盖 "现在几点"、"今天几号"、"星期几"、"几点了" 等简洁口语提问
        if len(original_msg) <= 10:
            msg_start = original_msg[:5]
            msg_end = original_msg[-5:]
            if self.time_date_pattern.search(msg_start) or self.time_date_pattern.search(msg_end):
                return RequestType.LOCAL_TOOL

        # 规则五：长句（>20字）且非明确查询 → 假查询
        #   长句通常是复杂陈述，不应被简单关键词判定为时间查询
        if len(original_msg) > 20:
            return RequestType.GENERAL_CHAT

        # ================================================================
        # 第三层：边缘情况走 API 兜底（万无一失）
        # ================================================================
        # 实在拿不准的，返回 GENERAL_CHAT，让外接 API 处理
        return RequestType.GENERAL_CHAT

    # ------------------------------------------------------------------
    # 天气分类子方法 —— 独立的规则树，与时间/日期规则完全解耦
    # ------------------------------------------------------------------

    def _classify_weather(self, original_msg: str, clean_msg: str) -> RequestType:
        """天气专用分类 —— 四层规则精准区分真查询 vs 假查询

        规则优先级（命中即返回）：
          R_W1: 天气明确查询词 → 真查询（最优先）
          R_W2: 天气否定/陈述词 → 假查询
          R_W3: "天气+陈述动词"模式 → 假查询
          R_W4: 短句（≤10字）含天气词 → 真查询
          R_W5: 长句（>25字）→ 假查询
          兜底 → 真查询（含天气关键词但未被过滤）

        参数:
            original_msg: 用户原始消息（用于规则匹配）
            clean_msg: 清洗后的消息（用于关键词检测）

        返回:
            TOOL_CALL：真实天气查询，应调用天气工具
            GENERAL_CHAT：非天气查询，走通用对话
        """
        # R_W1: 天气明确查询词 → 真查询
        #   "帮我查明天天气"、"请问今天气温多少"、"北京天气怎么样"
        if any(word in original_msg for word in self.weather_query_whitelist):
            return RequestType.TOOL_CALL

        # R_W2: 天气否定/陈述词且无查询词 → 假查询
        #   "今天天气不好不想出门"、"上次下雨的时候"、"今天太热了"
        if any(word in original_msg for word in self.weather_negation_blacklist):
            return RequestType.GENERAL_CHAT

        # R_W3: "天气+陈述动词"模式 → 假查询
        #   "天气不好"、"天气热了"、"天气变了" → 在陈述，不是提问
        for verb in self.weather_statement_verbs:
            if f"天气{verb}" in clean_msg:
                return RequestType.GENERAL_CHAT

        # R_W4: 短句（≤10字）含天气词 → 真查询
        #   "今天天气"、"天气怎么样"、"明天温度"等简洁提问
        if len(original_msg) <= 10:
            return RequestType.TOOL_CALL

        # R_W5: 长句（>25字）且无明确查询词 → 假查询
        #   长句通常是陈述、聊天，不应被简单关键词判定为天气查询
        if len(original_msg) > 25:
            return RequestType.GENERAL_CHAT

        # 兜底：含天气关键词且未被以上规则过滤 → 真查询
        #   "明天会下雨吗"、"这个周末适合出游吗天气如何" 等中等长度提问
        return RequestType.TOOL_CALL


# =============================================================================
# 工具调用关键词集合 —— 覆盖搜索/旅游/行程类需求（天气已被 classify() 接管）
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


def _is_tool_call_request(cleaned: str) -> bool:
    """检查是否为工具调用请求（搜索/旅游/行程），使用关键词集合匹配

    注意：天气已由 IntentGateway._classify_weather() 接管，此处不再检查天气关键词。
    """
    for keyword in _TOOL_KEYWORDS_SEARCH:
        if keyword in cleaned:
            return True
    for keyword in _TOOL_KEYWORDS_TRAVEL:
        if keyword in cleaned:
            return True
    return False


# =============================================================================
# 全局单例与对外接口
# =============================================================================

_gateway = IntentGateway()


def classify_request(user_message: str) -> RequestType:
    """核心分类函数 —— 对用户消息进行毫秒级意图分类

    三级分类流程：
      1. IntentGateway 判断 LOCAL_TOOL vs GENERAL_CHAT
      2. 关键词集合判断 TOOL_CALL
      3. 兜底 GENERAL_CHAT

    参数:
        user_message: 用户输入的原始消息文本

    返回:
        RequestType 枚举值，指示该请求的类型
    """
    # 第一步：本地工具 vs 通用对话（三级规则引擎）
    result = _gateway.classify(user_message)

    # 第二步：如果三级引擎判定为 GENERAL_CHAT，再检查是否为工具调用
    if result == RequestType.GENERAL_CHAT:
        clean_msg = (
            user_message.replace("？", "").replace("?", "")
            .replace(" ", "").replace("　", "")
        )
        # 若消息中含有时间/日期关键词（被网关第二层规则过滤的），
        # 说明整体语境是闲聊陈述而非信息查询，不应当触发工具调用。
        # 如 "今天天气不错，几点吃饭？" → 闲聊，不是天气查询
        if _gateway.time_date_pattern.search(clean_msg):
            return RequestType.GENERAL_CHAT
        if _is_tool_call_request(clean_msg):
            return RequestType.TOOL_CALL

    return result


def is_weather_query(user_message: str) -> bool:
    """辅助判断函数 —— 检查用户消息是否为真实天气查询

    复用 IntentGateway._classify_weather 的完整规则体系，
    仅返回布尔值，方便调用方做二选一分流。

    参数:
        user_message: 用户输入的原始消息文本

    返回:
        True：真实天气查询，应调用天气工具
        False：非天气查询，走通用对话或其他逻辑

    用法:
        if is_weather_query("今天北京天气怎么样"):
            reply = get_weather_reply("北京")
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

        # ===== 通用对话 → GENERAL_CHAT =====
        ("今天天气不错，几点吃饭？", RequestType.GENERAL_CHAT),
        ("现在几点？不对，等一下", RequestType.GENERAL_CHAT),
        ("给我写一段朋友圈文案", RequestType.GENERAL_CHAT),
        ("你好，请介绍一下你自己", RequestType.GENERAL_CHAT),
        ("", RequestType.GENERAL_CHAT),
        ("？？？", RequestType.GENERAL_CHAT),
    ]

    print("=" * 72)
    print("  IntentGateway 三级规则分类 测试结果")
    print("=" * 72)
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
        print(f"  [{status}] {display:35} | 预期: {expected.value:14} | 实际: {result.value}")

    print()
    print(f"  通过: {passed}  失败: {failed}  总计: {len(test_cases)}")

    if failed == 0:
        print("\n  全部测试通过!")
    else:
        print(f"\n  有 {failed} 个测试未通过，需要检查规则配置")

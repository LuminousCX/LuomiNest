"""
工具参数提取器 —— 从用户自然语言查询中智能提取工具所需参数

功能：
  对用户的自然语言查询进行规则匹配，自动提取工具所需参数（城市、日期、搜索关键词等），
  无需依赖大模型，纯正则+规则树实现，零延迟。

设计原则：
  1. 纯正则 + 规则树，零 IO、零网络、零大模型调用
  2. 每种工具一个专属提取方法，针对性处理
  3. 提取失败返回空字段，不抛异常，不中断流程
  4. 兼容现有的 city_pattern / date_pattern / weekday_pattern

用法:
    extractor = ToolParameterExtractor()
    args = extractor.extract("get_weather", "北京明天天气怎么样")
    # 返回 {"city": "北京", "date": "明天"}
"""

import re
from datetime import datetime, timedelta


class ToolParameterExtractor:
    """工具参数提取器 —— 纯规则引擎，按工具名分发专属提取方法"""

    def __init__(self):
        # ---------- 城市名正则 ----------
        self.city_pattern = re.compile(
            r"(北京|上海|广州|深圳|杭州|成都|武汉|西安|南京|重庆|天津|"
            r"苏州|长沙|郑州|济南|青岛|大连|厦门|福州|昆明|贵阳|南宁|"
            r"海口|三亚|哈尔滨|长春|沈阳|乌鲁木齐|拉萨|兰州|银川|西宁|"
            r"呼和浩特|太原|石家庄|合肥|南昌|东莞|佛山|无锡|宁波|温州|"
            r"徐州|珠海|惠州|中山|烟台|威海)"
        )

        # 城市单字别名（前后不能有中文字符）
        self.city_alias_pattern = re.compile(
            r"(?<![\u4e00-\u9fa5])(京|沪|穗|深|蓉|渝)(?![\u4e00-\u9fa5])"
        )
        self.city_alias: dict[str, str] = {
            "京": "北京", "沪": "上海", "穗": "广州",
            "深": "深圳", "蓉": "成都", "渝": "重庆",
        }

        # ---------- 日期正则 ----------
        self.date_pattern = re.compile(
            r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?)"
        )
        self.weekday_pattern = re.compile(
            r"(周一|周二|周三|周四|周五|周六|周日|星期[一二三四五六日])"
        )
        self.relative_day_pattern = re.compile(
            r"(今天|明天|后天|大后天|昨天|前天)"
        )
        self.day_offset_pattern = re.compile(
            r"(\d+)[天日]后"
        )
        self.day_before_pattern = re.compile(
            r"(\d+)[天日]前"
        )
        self.next_week_pattern = re.compile(
            r"下(周|礼拜)([一二三四五六日天])"
        )

        # ---------- 搜索关键词提取 ----------
        self.search_stop_words = re.compile(
            r"^(搜索|查一下|帮我查|帮我搜|搜一下|帮我搜索|查查|查找|搜一搜|"
            r"帮我查找|帮我找|帮我找找)"
        )
        self.countdown_stop_words = re.compile(
            r"(距离|离|还有几天|还剩几天|剩下几天|还有多久)\s*"
        )

    # =========================================================================
    # 核心接口：按工具名分发
    # =========================================================================

    def extract(self, tool_name: str, user_query: str) -> dict:
        """根据工具名提取参数

        参数:
            tool_name: 工具名称
            user_query: 用户原始提问

        返回:
            参数字典，若无匹配参数则返回空 dict
        """
        if tool_name == "get_weather":
            return self._extract_weather_args(user_query)
        elif tool_name == "get_current_time":
            return self._extract_time_args(user_query)
        elif tool_name in ("search", "web_search"):
            return self._extract_search_args(user_query)
        elif tool_name == "calculate":
            return {}
        else:
            return {}

    # =========================================================================
    # 通用提取方法
    # =========================================================================

    def extract_city(self, user_query: str) -> str | None:
        matched = self.city_pattern.findall(user_query)
        if matched:
            return matched[0]
        alias_matched = self.city_alias_pattern.findall(user_query)
        if alias_matched:
            city = alias_matched[0]
            return self.city_alias.get(city, city)
        return None

    def extract_date_text(self, user_query: str) -> str | None:
        """从查询中提取日期文本（明天/下周一/5.1号等），返回可用于 _weather_tool 的日期字符串"""
        # 绝对日期
        match = self.date_pattern.search(user_query)
        if match:
            return match.group(1)
        # 相对日期
        match = self.relative_day_pattern.search(user_query)
        if match:
            return match.group(1)
        # 星期偏移
        match = self.weekday_pattern.search(user_query)
        if match:
            return match.group(1)
        # 下周x
        match = self.next_week_pattern.search(user_query)
        if match:
            return f"下周{match.group(2)}"
        # 天数偏移
        match = self.day_offset_pattern.search(user_query)
        if match:
            return f"{match.group(1)}天后"
        match = self.day_before_pattern.search(user_query)
        if match:
            return f"{match.group(1)}天前"
        return None

    # =========================================================================
    # 专属提取方法
    # =========================================================================

    def _extract_weather_args(self, user_query: str) -> dict:
        """提取天气工具参数"""
        args: dict = {}
        city = self.extract_city(user_query)
        if city:
            args["city"] = city
        date_text = self.extract_date_text(user_query)
        if date_text:
            args["date_str"] = date_text
        return args

    def _extract_time_args(self, user_query: str) -> dict:
        """提取时间工具参数"""
        args: dict = {}
        date_text = self.extract_date_text(user_query)
        if date_text:
            args["date_str"] = date_text

        # 时间偏移
        match = re.search(r"(\d+)[个]*(?:小时|钟头)[后前]", user_query)
        if match:
            val = int(match.group(1))
            if "前" in match.group(0):
                val = -val
            args["hour_offset"] = val
        return args

    def _extract_search_args(self, user_query: str) -> dict:
        """提取搜索工具参数，自动清除查询前缀和倒计时词，并添加时间上下文"""
        args: dict = {}
        # 去除"搜索"等前缀
        query = self.search_stop_words.sub("", user_query).strip()
        # 去除"距离/还有几天"等倒计时词
        query = self.countdown_stop_words.sub("", query).strip()
        # 尾随的"还有几天"/"还剩几天"
        query = re.sub(r"(还有几天|还剩几天|剩下几天|还有多久)$", "", query).strip()
        if not query:
            query = user_query.strip()
        # 如果查询词太短（<=3字），补充"时间"后缀以获得更好的搜索结果
        if len(query) <= 3:
            query = query + " 时间"
        # 添加时间上下文（年份+上半年/下半年推断）
        query = self._enrich_search_query_with_time_context(query)
        args["query"] = query
        return args

    def _enrich_search_query_with_time_context(self, query: str) -> str:
        """为搜索查询添加时间上下文

        当查询涉及周期性事件（考试/赛事等）且没有明确年份/上下半年时，
        自动补充当前年份和合理的上下半年推断。

        推断规则：
          - 1-4月 → 搜索"上半年"（上半年考试通常5-6月举行）
          - 5-8月 → 搜索"下半年"（上半年已过，下半年通常11月举行）
          - 9-12月 → 搜索"下半年"（下半年考试通常11月举行）
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
        enriched = re.sub(
            r"^(20\d{2}年)(.+?)(上半年|下半年)(时间)$",
            r"\1\3\2\4",
            enriched
        )

        return enriched
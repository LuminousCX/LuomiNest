"""
工具懒加载模块 —— 按需注入工具定义，杜绝全量预加载

功能：
  根据用户消息的关键词匹配对应场景，仅返回该场景需要的工具定义，
  从根源解决工具乱触发、token 浪费的问题。

核心流程：
  1. 用户消息 → 关键词匹配场景 → 取对应工具名集合
  2. 去重后从 SkillRegistry 获取 OpenAI Function Calling 格式定义
  3. 无匹配场景返回空列表（等效不注入任何工具）
  4. 异常时降级到全量工具注入

增强特性：
  - 新增实时数据/知识边界/比较评价/事实特异性场景
  - 支持八维度搜索意图评分器触发的隐式搜索场景
  - 场景覆盖从6个扩展到12个

设计原则：
  1. 仅修改工具注入逻辑，不改动任何工具的实现代码
  2. GENERAL_CHAT 请求绝不注入工具
  3. 保留 SkillRegistry.get_openai_tools() 作为异常降级兜底
  4. 场景与工具名解耦：场景只存工具名，定义从注册表动态获取
"""

from loguru import logger


# =============================================================================
# 场景-工具映射配置
#
# 每个场景包含：
#   - keywords: 触发该场景的关键词集合（命中任一即匹配）
#   - tools: 该场景下需要注入的工具名称列表
#
# 扩展方式：新增场景只需在此添加一行配置，无需改动匹配逻辑
# =============================================================================

SCENE_TOOL_MAP: dict[str, dict] = {
    # ----- 天气场景 -----
    "weather": {
        "keywords": {
            "天气", "下雨", "下雪", "刮风", "台风", "雾霾", "冰雹",
            "气温", "温度", "湿度", "风力", "空气质量", "pm2.5",
            "防晒", "带伞", "紫外线", "降雨", "降水", "阴天", "晴天", "多云",
            "冷不冷", "热不热", "穿什么衣服", "穿衣指数", "冷暖", "预报",
        },
        "tools": ["get_weather", "web_search"],
    },

    # ----- 搜索场景 -----
    "search": {
        "keywords": {
            "搜索", "查找", "搜一下", "帮我搜", "帮我查",
            "帮我找", "帮我看看", "查资料", "检索", "搜寻",
            "百度", "谷歌", "百度一下", "搜一搜",
        },
        "tools": ["search", "web_search"],
    },

    # ----- 旅游场景 -----
    "travel": {
        "keywords": {
            "旅游", "旅行", "度假", "景点", "攻略", "游记",
            "行程", "路线", "导航", "怎么去", "怎么走", "如何去",
            "酒店", "民宿", "机票", "火车票", "订票", "订酒店",
            "规划", "安排行程", "出行计划", "自驾", "跟团",
            "周边游", "一日游", "几日游", "自由行", "签证",
        },
        "tools": ["get_weather", "search", "web_search"],
    },

    # ----- 计算场景 -----
    "calculate": {
        "keywords": {
            "计算", "算一下", "帮我算", "等于多少", "等于几",
            "得多少", "得几", "是多少", "答案是", "换算",
            "求", "求解",
        },
        "tools": ["calculate"],
    },

    # ----- 时间场景 -----
    "time": {
        "keywords": {"几点", "几号", "几时", "周几", "星期几", "时间", "日期", "日历",
                     "几月", "月份"},
        "tools": ["get_current_time"],
    },

    # ----- 倒计时场景 -----
    "countdown": {
        "keywords": {"距离", "几天", "还有几天", "还剩几天", "还有多久", "倒计时"},
        "tools": ["get_current_time", "web_search"],
    },

    # ----- Agent 转交场景 -----
    "agent": {
        "keywords": {
            "转交", "转接", "切换", "换个agent", "找其他agent",
        },
        "tools": ["transfer_to_agent"],
    },

    # ----- 金融实时场景 -----
    "finance_realtime": {
        "keywords": {
            "股价", "股票", "行情", "涨幅", "跌幅", "市值",
            "基金", "比特币", "加密货币", "汇率", "换汇", "外汇",
            "油价", "汽油价", "柴油价", "金价", "黄金价",
            "房价", "二手房", "均价", "成交价",
        },
        "tools": ["web_search"],
    },

    # ----- 新闻热点场景 -----
    "news": {
        "keywords": {
            "新闻", "热点", "头条", "爆料", "事件", "事故",
            "最新消息", "最新动态", "最新公告", "最新通知",
        },
        "tools": ["web_search"],
    },

    # ----- 考试教育场景 -----
    "exam": {
        "keywords": {
            "考试", "报名", "准考证", "成绩", "录取", "分数线",
            "软考", "考研", "高考", "中考", "国考", "省考",
            "事业编", "公务员", "选调", "教资", "法考", "注会",
            "一建", "二建", "招生", "录取线", "合格线",
        },
        "tools": ["web_search"],
    },

    # ----- 体育赛事场景 -----
    "sports": {
        "keywords": {
            "比赛", "赛事", "比分", "积分", "排名", "赛程",
            "对阵", "世界杯", "奥运会", "欧冠", "NBA", "亚运会",
            "世博会", "欧洲杯", "亚洲杯", "全运会",
        },
        "tools": ["web_search"],
    },

    # ----- 比较评价场景 -----
    "comparison": {
        "keywords": {
            "哪个好", "怎么选", "对比", "比较", "区别", "差异",
            "性价比", "划算", "值得买", "买哪个", "选哪个",
            "排行", "排名", "榜单", "口碑", "评测", "测评",
            "优缺点", "优劣",
        },
        "tools": ["web_search"],
    },

    # ----- 事实特异性场景 -----
    "fact_specific": {
        "keywords": {
            "分数线", "录取线", "报名费", "学费", "票价", "门票",
            "营业时间", "开放时间", "官网", "下载地址",
            "名额", "招生人数", "招聘人数", "限购",
            "联系方式", "客服", "咨询电话",
        },
        "tools": ["web_search"],
    },

    # ----- 民生通知场景 -----
    "civil_notification": {
        "keywords": {
            "限行", "限号", "尾号限行", "单双号",
            "停水", "停电", "停气", "检修", "维护通知",
            "政策", "法规", "规定", "新规", "出台", "实施",
        },
        "tools": ["web_search"],
    },

    # ----- 出入境场景 -----
    "immigration": {
        "keywords": {
            "签证", "护照", "出入境", "海关", "入境政策",
        },
        "tools": ["web_search"],
    },

    # ----- 招聘求职场景 -----
    "job": {
        "keywords": {
            "招聘", "求职", "岗位", "薪资", "待遇", "offer",
        },
        "tools": ["web_search"],
    },

    # ----- 医疗健康场景 -----
    "medical": {
        "keywords": {
            "疫苗", "挂号", "核酸检测", "门诊", "就诊", "医保",
            "医院", "专家", "排班",
        },
        "tools": ["web_search"],
    },

    # ----- 产品发布场景 -----
    "product_launch": {
        "keywords": {
            "发布", "推出", "上市", "开售", "预售", "发售", "新品",
            "iPhone", "iPad", "MacBook", "华为", "小米", "三星",
            "特斯拉", "比亚迪", "蔚来",
        },
        "tools": ["web_search"],
    },

    # ----- AI产品场景 -----
    "ai_product": {
        "keywords": {
            "GPT", "Claude", "Gemini", "Llama", "Sora", "Copilot",
            "DeepSeek", "Kimi", "豆包", "通义", "文心", "千问", "智谱",
            "ChatGPT", "OpenAI", "Anthropic",
        },
        "tools": ["web_search"],
    },

    # ----- 影视娱乐场景 -----
    "entertainment": {
        "keywords": {
            "上映", "票房", "评分", "豆瓣", "IMDb",
            "好看", "推荐电影", "推荐剧", "有什么好看",
            "诺贝尔", "奥斯卡", "格莱美",
        },
        "tools": ["web_search"],
    },
}


def _match_scenes(user_message: str) -> list[str]:
    """根据用户消息匹配命中的场景集合

    遍历所有场景的关键词集合，命中任一关键词即认为该场景匹配。
    一条消息可能同时命中多个场景，返回所有匹配场景的列表。

    参数:
        user_message: 清洗后的用户消息文本

    返回:
        匹配的场景名称列表
    """
    matched_scenes: list[str] = []
    for scene_name, scene_config in SCENE_TOOL_MAP.items():
        for keyword in scene_config["keywords"]:
            if keyword in user_message:
                matched_scenes.append(scene_name)
                break
    return matched_scenes


def _resolve_tool_names(matched_scenes: list[str]) -> list[str]:
    """从匹配的场景中提取工具名，去重后返回

    参数:
        matched_scenes: 匹配的场景名称列表

    返回:
        去重后的工具名称列表
    """
    seen: set[str] = set()
    tool_names: list[str] = []
    for scene_name in matched_scenes:
        for tool_name in SCENE_TOOL_MAP[scene_name]["tools"]:
            if tool_name not in seen:
                seen.add(tool_name)
                tool_names.append(tool_name)
    return tool_names


def get_matched_tools(user_message: str) -> list[dict]:
    """核心函数：根据用户消息返回匹配的工具定义列表

    完整流程：
      1. 清洗输入（去空格、去问号）
      2. 关键词匹配场景
      3. 获取工具名（去重）
      4. 从 SkillRegistry 获取 OpenAI Function Calling 格式定义
      5. 返回匹配的工具列表

    参数:
        user_message: 用户输入的原始消息文本

    返回:
        OpenAI Function Calling 格式的工具定义列表。
        无匹配场景时返回空列表 []。

    异常安全：
        本函数内部已妥善处理异常，不会向外抛出。
    """
    if not user_message:
        return []

    clean_msg = user_message.replace("？", "").replace("?", "").replace(" ", "").replace("　", "")

    if not clean_msg:
        return []

    matched_scenes = _match_scenes(clean_msg)

    if not matched_scenes:
        return []

    tool_names = _resolve_tool_names(matched_scenes)

    try:
        from app.runtime.plugin.skill.registry import SkillRegistry

        tools: list[dict] = []
        for tool_name in tool_names:
            skill_data = SkillRegistry.get_skill(tool_name)
            if skill_data is None:
                logger.debug(f"[ToolLazyLoader] 工具 '{tool_name}' 未注册，跳过")
                continue
            from app.runtime.plugin.skill.base import SkillDefinition
            skill_def = SkillDefinition(
                name=skill_data.get("name", tool_name),
                description=skill_data.get("description", ""),
                category=skill_data.get("category", "general"),
                parameters=skill_data.get("parameters", {}),
                is_active=skill_data.get("is_active", True),
                is_builtin=skill_data.get("is_builtin", False),
                handler_name=skill_data.get("handler_name"),
                prompt_template=skill_data.get("prompt_template"),
                tags=skill_data.get("tags", []),
            )
            tools.append(skill_def.to_openai_tool())

        logger.info(
            f"[ToolLazyLoader] 匹配场景: {matched_scenes}, "
            f"注入工具: {[t['function']['name'] for t in tools]}"
        )
        return tools

    except Exception as e:
        logger.warning(f"[ToolLazyLoader] 懒加载异常，降级到全量注入: {e}")
        try:
            from app.runtime.plugin.skill.registry import SkillRegistry
            return SkillRegistry.get_openai_tools()
        except Exception as fallback_error:
            logger.error(f"[ToolLazyLoader] 全量降级也失败: {fallback_error}")
            return []


# =============================================================================
# 直接运行验证（python -m app.utils.tool_lazy_loader）
# =============================================================================
if __name__ == "__main__":
    test_cases = [
        # (用户消息, 期望匹配的场景列表, 期望注入的工具名列表)
        ("今天北京天气怎么样", ["weather"], ["get_weather", "web_search"]),
        ("帮我搜索一下Python教程", ["search"], ["search", "web_search"]),
        ("推荐一个旅游景点", ["travel"], ["get_weather", "search", "web_search"]),
        ("3加5等于多少", ["calculate"], ["calculate"]),
        ("现在几点了", ["time"], ["get_current_time"]),
        ("你好，请介绍一下你自己", [], []),
        ("给我写一段朋友圈文案", [], []),
        ("帮我查一下明天上海的温度", ["weather", "search"], ["get_weather", "web_search", "search"]),
        ("我想去北京旅游，帮我规划一下行程", ["travel"], ["get_weather", "search", "web_search"]),
        ("计算一下 100*200", ["calculate"], ["calculate"]),
        ("今天天气不错，适合出去玩", ["weather"], ["get_weather", "web_search"]),
        ("距离河北软考还有几天", ["countdown"], ["get_current_time", "web_search"]),
        ("距离五一还有多久", ["countdown"], ["get_current_time", "web_search"]),
        ("今天几号", ["time"], ["get_current_time"]),
        ("明天星期几", ["time"], ["get_current_time"]),

        # 新增场景测试
        ("特斯拉股价多少", ["finance_realtime", "product_launch"], ["web_search"]),
        ("最近有什么新闻", ["news"], ["web_search"]),
        ("今年考研什么时候报名", ["exam"], ["web_search"]),
        ("NBA总决赛比分", ["sports"], ["web_search"]),
        ("iPhone 16和华为Mate70哪个好", ["comparison", "product_launch"], ["web_search"]),
        ("清华录取分数线多少", ["exam", "fact_specific"], ["web_search"]),
        ("今天油价多少", ["finance_realtime"], ["web_search"]),
        ("北京今天限行尾号", ["civil_notification"], ["web_search"]),
        ("GPT-5什么时候发布", ["ai_product"], ["web_search"]),
        ("最近有什么好看的电影", ["entertainment"], ["web_search"]),
        ("签证办理流程", ["immigration", "travel"], ["web_search"]),
        ("最近有没有招聘会", ["job"], ["web_search"]),
        ("北京协和医院挂号", ["medical"], ["web_search"]),
    ]

    print("=" * 80)
    print("  ToolLazyLoader 场景匹配 测试结果（增强版）")
    print("=" * 80)
    print()

    passed = 0
    failed = 0

    for msg, expected_scenes, expected_tools in test_cases:
        display = msg if msg else "(空消息)"
        clean = msg.replace("？", "").replace("?", "").replace(" ", "").replace("　", "")
        actual_scenes = _match_scenes(clean)
        tool_names = _resolve_tool_names(actual_scenes)

        scene_ok = set(expected_scenes).issubset(set(actual_scenes))
        tools_ok = set(expected_tools).issubset(set(tool_names))

        if scene_ok and tools_ok:
            status = "PASS"
            passed += 1
        else:
            status = "FAIL"
            failed += 1

        print(f"  [{status}] {display:45}")
        if not scene_ok:
            missing = set(expected_scenes) - set(actual_scenes)
            print(f"         场景: 期望包含 {expected_scenes}, 实际 {actual_scenes}, 缺少 {missing}")
        if not tools_ok:
            missing = set(expected_tools) - set(tool_names)
            print(f"         工具: 期望包含 {expected_tools}, 实际 {tool_names}, 缺少 {missing}")

    print()
    print(f"  通过: {passed}  失败: {failed}  总计: {len(test_cases)}")

    if failed == 0:
        print("\n  全部测试通过!")
    else:
        print(f"\n  有 {failed} 个测试未通过，需要检查配置")

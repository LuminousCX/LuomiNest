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
    # ----- 天气场景：用户询问天气、气温、空气质量等 -----
    "weather": {
        "keywords": {
            "天气", "下雨", "下雪", "刮风", "台风", "雾霾", "冰雹",
            "气温", "温度", "湿度", "风力", "空气质量", "pm2.5",
            "防晒", "带伞", "紫外线", "降雨", "降水", "阴天", "晴天", "多云",
            "冷不冷", "热不热", "穿什么衣服", "穿衣指数", "冷暖", "预报",
            # 预报相关关键词
            "明天", "后天", "大后天", "几号", "哪一天", "哪天",
            "下周", "下周天", "下周一", "下周二", "下周三", "下周四",
            "下周五", "下周六", "下周日", "下星期",
        },
        "tools": ["get_weather", "web_search"],
    },

    # ----- 搜索场景：用户想要搜索资料、查找信息 -----
    "search": {
        "keywords": {
            "搜索", "查找", "搜一下", "帮我搜", "帮我查",
            "帮我找", "帮我看看", "查资料", "检索", "搜寻",
            "百度", "谷歌", "百度一下", "搜一搜",
        },
        "tools": ["search", "web_search"],
    },

    # ----- 旅游场景：用户规划旅行、查攻略、订票等 -----
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

    # ----- 计算场景：用户要做数学计算或单位换算 -----
    "calculate": {
        "keywords": {
            "计算", "算一下", "帮我算", "等于多少", "等于几",
            "得多少", "得几", "是多少", "答案是", "换算",
            "求", "求解",
        },
        "tools": ["calculate"],
    },

    # ----- 时间场景：用户要获取当前日期时间 -----
    "time": {
        "keywords": {
            "时间", "日期", "星期", "周几", "几点", "几号",
            "几时", "几月", "当前时间", "现在时间",
        },
        "tools": ["get_current_time"],
    },

    # ----- Agent 转交场景：需要把任务转给其他 Agent -----
    "agent": {
        "keywords": {
            "转交", "转接", "切换", "换个agent", "找其他agent",
        },
        "tools": ["transfer_to_agent"],
    },
}


def _match_scenes(user_message: str) -> list[str]:
    """根据用户消息匹配命中的场景集合

    遍历所有场景的关键词集合，命中任一关键词即认为该场景匹配。
    一条消息可能同时命中多个场景（如"帮我搜一下北京的天气"同时命中搜索+天气），
    返回所有匹配场景的列表，按 SCENE_TOOL_MAP 中的配置顺序排列。

    参数:
        user_message: 清洗后的用户消息文本（已去除空格和问号）

    返回:
        匹配的场景名称列表，如 ["weather", "search"]
    """
    matched_scenes: list[str] = []
    for scene_name, scene_config in SCENE_TOOL_MAP.items():
        for keyword in scene_config["keywords"]:
            if keyword in user_message:
                matched_scenes.append(scene_name)
                break  # 命中一个关键词即确认场景，跳出内层循环
    return matched_scenes


def _resolve_tool_names(matched_scenes: list[str]) -> list[str]:
    """从匹配的场景中提取工具名，去重后返回

    参数:
        matched_scenes: 匹配的场景名称列表（有序）

    返回:
        去重后的工具名称列表，保持与场景配置一致的稳定顺序
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
        无匹配场景时返回空列表 []，等效不注入任何工具。

    异常安全：
        本函数内部已妥善处理异常，不会向外抛出。异常时降级到全量工具。

    用法:
        tools = get_matched_tools("今天北京天气怎么样")
        # 返回 [get_weather 的 OpenAI 格式定义, web_search 的 OpenAI 格式定义]
    """
    # 0. 边界与清洗
    if not user_message:
        return []

    clean_msg = user_message.replace("？", "").replace("?", "").replace(" ", "").replace("　", "")

    if not clean_msg:
        return []

    # 1. 匹配场景
    matched_scenes = _match_scenes(clean_msg)

    if not matched_scenes:
        return []

    # 2. 获取工具名（去重）
    tool_names = _resolve_tool_names(matched_scenes)

    # 3. 从 SkillRegistry 获取工具定义
    try:
        from app.runtime.plugin.skill.registry import SkillRegistry

        tools: list[dict] = []
        for tool_name in tool_names:
            skill_data = SkillRegistry.get_skill(tool_name)
            if skill_data is None:
                logger.debug(f"[ToolLazyLoader] 工具 '{tool_name}' 未注册，跳过")
                continue
            # 将 skill_data 转换为 SkillDefinition 再转为 OpenAI 格式
            # 必须传入所有字段，与 SkillRegistry.get_openai_tools() 保持一致
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
        # 异常降级：返回全量工具，保证对话不受影响
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
    ]

    print("=" * 72)
    print("  ToolLazyLoader 场景匹配 测试结果")
    print("=" * 72)
    print()

    passed = 0
    failed = 0

    for msg, expected_scenes, expected_tools in test_cases:
        display = msg if msg else "(空消息)"
        # 第一步：验证场景匹配
        clean = msg.replace("？", "").replace("?", "").replace(" ", "").replace("　", "")
        actual_scenes = _match_scenes(clean)
        tool_names = _resolve_tool_names(actual_scenes)

        scene_ok = actual_scenes == expected_scenes
        # 第二步：验证工具名列表
        tools_ok = tool_names == expected_tools

        if scene_ok and tools_ok:
            status = "PASS"
            passed += 1
        else:
            status = "FAIL"
            failed += 1

        scene_status = "匹配" if scene_ok else f"不匹配"
        tools_status = "匹配" if tools_ok else f"不匹配"
        print(f"  [{status}] {display:40}")
        if not scene_ok:
            print(f"         场景: 期望 {expected_scenes} 实际 {actual_scenes}")
        if not tools_ok:
            print(f"         工具: 期望 {expected_tools} 实际 {tool_names}")

    print()
    print(f"  通过: {passed}  失败: {failed}  总计: {len(test_cases)}")

    if failed == 0:
        print("\n  全部测试通过!")
    else:
        print(f"\n  有 {failed} 个测试未通过，需要检查配置")

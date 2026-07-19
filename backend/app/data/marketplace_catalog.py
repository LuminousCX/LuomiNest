"""市场目录数据源 — CxPlugin 插件、Skill 技能、Agent 智能体静态目录。

此模块为市场前端提供统一的目录数据源，与前端 marketplace-data.ts 保持一致。
后端 GET /marketplace/items 端点从此处读取数据返回。
"""
from typing import Any

# ─── 分类定义 ──────────────────────────────────────────────────

PLUGIN_CATEGORIES: list[dict[str, Any]] = [
    {"id": "all", "name": "全部", "icon": "LayoutGrid"},
    {"id": "ai-model", "name": "AI 模型", "icon": "Cpu", "children": [
        {"id": "llm", "name": "大语言模型"},
        {"id": "embedding", "name": "嵌入模型"},
        {"id": "vision", "name": "视觉模型"},
        {"id": "tts", "name": "语音合成"},
        {"id": "stt", "name": "语音识别"},
    ]},
    {"id": "tool", "name": "工具", "icon": "Wrench", "children": [
        {"id": "search", "name": "搜索"},
        {"id": "code", "name": "代码"},
        {"id": "file", "name": "文件"},
        {"id": "web", "name": "网页"},
        {"id": "database", "name": "数据库"},
    ]},
    {"id": "integration", "name": "集成", "icon": "Puzzle", "children": [
        {"id": "messaging", "name": "消息平台"},
        {"id": "iot", "name": "IoT 设备"},
        {"id": "api", "name": "API 接入"},
        {"id": "cloud", "name": "云服务"},
    ]},
    {"id": "avatar", "name": "形象", "icon": "Palette", "children": [
        {"id": "live2d", "name": "Live2D"},
        {"id": "vrm", "name": "VRM"},
        {"id": "voice", "name": "语音包"},
    ]},
    {"id": "productivity", "name": "效率", "icon": "Zap", "children": [
        {"id": "automation", "name": "自动化"},
        {"id": "workflow", "name": "工作流"},
        {"id": "schedule", "name": "日程"},
    ]},
]

SKILL_CATEGORIES: list[dict[str, Any]] = [
    {"id": "all", "name": "全部", "icon": "LayoutGrid"},
    {"id": "coding", "name": "编程", "icon": "Code", "children": [
        {"id": "frontend", "name": "前端开发"},
        {"id": "backend", "name": "后端开发"},
        {"id": "fullstack", "name": "全栈工程"},
        {"id": "refactor", "name": "重构优化"},
    ]},
    {"id": "document", "name": "文档", "icon": "FileText", "children": [
        {"id": "word", "name": "Word 文档"},
        {"id": "pdf", "name": "PDF 文档"},
        {"id": "slides", "name": "演示文稿"},
        {"id": "coauthor", "name": "协作写作"},
    ]},
    {"id": "design", "name": "设计", "icon": "Palette", "children": [
        {"id": "visual", "name": "视觉设计"},
        {"id": "brand", "name": "品牌规范"},
        {"id": "art", "name": "艺术创作"},
    ]},
    {"id": "knowledge", "name": "知识", "icon": "BookOpen", "children": [
        {"id": "comms", "name": "内部通讯"},
        {"id": "content", "name": "内容创作"},
        {"id": "research", "name": "研究分析"},
    ]},
    {"id": "media", "name": "媒体", "icon": "Image", "children": [
        {"id": "image-gen", "name": "图片生成"},
        {"id": "animation", "name": "动画"},
        {"id": "gif", "name": "GIF 制作"},
    ]},
]

AGENT_CATEGORIES: list[dict[str, Any]] = [
    {"id": "all", "name": "全部", "icon": "LayoutGrid"},
    {"id": "assistant", "name": "助手", "icon": "Bot", "children": [
        {"id": "customer-service", "name": "客服助手"},
        {"id": "sales", "name": "销售助手"},
        {"id": "personal", "name": "个人助理"},
    ]},
    {"id": "creative", "name": "创意", "icon": "Lightbulb", "children": [
        {"id": "writing", "name": "写作"},
        {"id": "design", "name": "设计"},
        {"id": "music", "name": "音乐"},
    ]},
    {"id": "analysis", "name": "分析", "icon": "BarChart3", "children": [
        {"id": "data-analysis", "name": "数据分析"},
        {"id": "market-research", "name": "市场研究"},
        {"id": "finance", "name": "财务分析"},
    ]},
    {"id": "development", "name": "开发", "icon": "Terminal", "children": [
        {"id": "code-gen", "name": "代码生成"},
        {"id": "testing", "name": "测试"},
        {"id": "devops", "name": "运维"},
    ]},
    {"id": "education", "name": "教育", "icon": "GraduationCap", "children": [
        {"id": "teaching", "name": "教学"},
        {"id": "tutoring", "name": "辅导"},
        {"id": "training", "name": "培训"},
    ]},
]

COMMON_TAGS: list[dict[str, str]] = [
    {"id": "official", "name": "官方", "color": "#147EBC"},
    {"id": "community", "name": "社区", "color": "#6366f1"},
    {"id": "free", "name": "免费", "color": "#22c55e"},
    {"id": "premium", "name": "付费", "color": "#f59e0b"},
    {"id": "popular", "name": "热门", "color": "#f43f5e"},
    {"id": "new", "name": "新品", "color": "#3b82f6"},
    {"id": "experimental", "name": "实验性", "color": "#8b5cf6"},
    {"id": "stable", "name": "稳定", "color": "#147EBC"},
]

# ─── 作者定义 ──────────────────────────────────────────────────

_AUTHORS: list[dict[str, Any]] = [
    {"id": "a1", "name": "LuminousCX", "avatar": "", "verified": True},
    {"id": "a2", "name": "LuomiNest", "avatar": "", "verified": True},
    {"id": "a3", "name": "ChenXiLab", "avatar": "", "verified": True},
    {"id": "a4", "name": "OpenSkill", "avatar": "", "verified": False},
    {"id": "a5", "name": "DevCommunity", "avatar": "", "verified": False},
]

# 标签索引快捷引用
_T = {t["id"]: t for t in COMMON_TAGS}
_A = {a["id"]: a for a in _AUTHORS}


# ─── CxPlugin 插件目录 ─────────────────────────────────────────

CATALOG_PLUGINS: list[dict[str, Any]] = [
    {
        "id": "cxp-deepseek", "type": "plugin", "name": "CxPlugin DeepSeek 接入",
        "description": "基于 CxPlugin 框架接入 DeepSeek 系列大语言模型，支持 DeepSeek-V3、DeepSeek-R1 等模型，提供高质量推理与流式对话能力，可注册为 LLM Provider。",
        "summary": "DeepSeek 系列模型 CxPlugin 接入", "icon": "Brain", "author": _A["a1"], "category": "ai-model",
        "tags": [_T["official"], _T["free"], _T["stable"]], "version": "1.2.0", "versions": [
            {"version": "1.2.0", "changelog": "新增 DeepSeek-R1 推理模型支持", "releasedAt": "2026-04-15", "size": 2048},
            {"version": "1.1.0", "changelog": "优化流式输出与上下文管理", "releasedAt": "2026-03-20", "size": 1980},
            {"version": "1.0.0", "changelog": "初始版本，接入 CxPlugin 框架", "releasedAt": "2026-02-01", "size": 1856},
        ], "screenshots": [], "rating": 4.8, "ratingCount": 256, "downloadCount": 15200, "installedCount": 8900,
        "likeCount": 3200, "installStatus": "none", "isFavorite": False, "featured": True, "homepage": "https://deepseek.com",
        "license": "MIT", "minAppVersion": "0.7.0", "createdAt": "2026-02-01", "updatedAt": "2026-04-15", "size": 2048,
    },
    {
        "id": "cxp-homeassistant", "type": "plugin", "name": "CxPlugin Home Assistant 桥接",
        "description": "通过 CxPlugin 框架将 LuomiNest 与 Home Assistant 智能家居平台深度集成，支持设备控制、场景自动化、状态监控与事件订阅。",
        "summary": "Home Assistant 智能家居 CxPlugin", "icon": "Home", "author": _A["a2"], "category": "integration",
        "tags": [_T["official"], _T["free"], _T["stable"]], "version": "2.0.1", "versions": [
            {"version": "2.0.1", "changelog": "修复设备同步与状态推送问题", "releasedAt": "2026-04-10", "size": 4096},
            {"version": "2.0.0", "changelog": "基于 CxPlugin 全新架构重写", "releasedAt": "2026-03-15", "size": 3800},
        ], "screenshots": [], "rating": 4.5, "ratingCount": 128, "downloadCount": 6800, "installedCount": 4200,
        "likeCount": 1800, "installStatus": "installed", "isFavorite": True, "featured": True, "license": "Apache-2.0",
        "createdAt": "2026-01-15", "updatedAt": "2026-04-10", "size": 4096,
    },
    {
        "id": "cxp-discord", "type": "plugin", "name": "CxPlugin Discord 通道",
        "description": "让 LuomiNest 通过 CxPlugin 框架接入 Discord 平台，支持多服务器管理、频道消息路由、斜杠命令与富文本消息推送。",
        "summary": "Discord 消息平台 CxPlugin 通道", "icon": "MessageSquare", "author": _A["a5"], "category": "integration",
        "tags": [_T["community"], _T["free"]], "version": "1.0.3", "versions": [
            {"version": "1.0.3", "changelog": "支持斜杠命令与消息回复", "releasedAt": "2026-04-05", "size": 1536},
        ], "screenshots": [], "rating": 4.2, "ratingCount": 89, "downloadCount": 3200, "installedCount": 1800,
        "likeCount": 680, "installStatus": "none", "isFavorite": False, "license": "MIT", "createdAt": "2026-03-01", "updatedAt": "2026-04-05", "size": 1536,
    },
    {
        "id": "cxp-websearch", "type": "plugin", "name": "CxPlugin 网页搜索工具",
        "description": "基于 CxPlugin 框架集成主流搜索引擎，为 AI 提供实时网页搜索能力，支持结果摘要、引用追踪与多引擎切换，可作为 Tool 注册。",
        "summary": "AI 网页搜索增强 CxPlugin 工具", "icon": "Search", "author": _A["a3"], "category": "tool",
        "tags": [_T["community"], _T["popular"], _T["free"]], "version": "1.5.0", "versions": [
            {"version": "1.5.0", "changelog": "新增图片搜索与结果缓存", "releasedAt": "2026-04-18", "size": 3072},
        ], "screenshots": [], "rating": 4.6, "ratingCount": 312, "downloadCount": 18900, "installedCount": 11200,
        "likeCount": 4500, "installStatus": "none", "isFavorite": False, "featured": True, "license": "MIT",
        "createdAt": "2025-12-01", "updatedAt": "2026-04-18", "size": 3072,
    },
    {
        "id": "cxp-tts", "type": "plugin", "name": "CxPlugin 语音合成引擎",
        "description": "基于 CxPlugin 框架的语音合成插件，集成 Edge TTS 与本地模型，支持多语言、多音色、语速情感调节，可注册为语音输出通道。",
        "summary": "多语言语音合成 CxPlugin 引擎", "icon": "Volume2", "author": _A["a1"], "category": "ai-model",
        "tags": [_T["official"], _T["free"]], "version": "1.1.0", "versions": [
            {"version": "1.1.0", "changelog": "新增情感控制与音色克隆", "releasedAt": "2026-04-12", "size": 5120},
        ], "screenshots": [], "rating": 4.4, "ratingCount": 167, "downloadCount": 9500, "installedCount": 5800,
        "likeCount": 2100, "installStatus": "installed", "isFavorite": False, "license": "MIT", "createdAt": "2026-01-20", "updatedAt": "2026-04-12", "size": 5120,
    },
    {
        "id": "cxp-sandbox", "type": "plugin", "name": "CxPlugin 代码执行沙箱",
        "description": "基于 CxPlugin 框架的安全代码执行环境，支持 Python、JavaScript 等语言，提供资源隔离与超时控制，为 AI 提供代码运行能力。",
        "summary": "安全代码执行 CxPlugin 沙箱", "icon": "Zap", "author": _A["a5"], "category": "tool",
        "tags": [_T["community"], _T["experimental"], _T["free"]], "version": "0.9.0", "versions": [
            {"version": "0.9.0", "changelog": "Beta 版本发布，支持 Python/JS", "releasedAt": "2026-04-01", "size": 8192},
        ], "screenshots": [], "rating": 3.9, "ratingCount": 45, "downloadCount": 2100, "installedCount": 980,
        "likeCount": 320, "installStatus": "none", "isFavorite": False, "license": "Apache-2.0", "createdAt": "2026-03-15", "updatedAt": "2026-04-01", "size": 8192,
    },
    {
        "id": "cxp-vrm", "type": "plugin", "name": "CxPlugin VRM 模型加载器",
        "description": "基于 CxPlugin 框架加载和渲染 VRM 格式 3D 虚拟形象，支持表情控制、动作播放与唇形同步，可作为 Avatar 渲染通道。",
        "summary": "VRM 3D 形象 CxPlugin 加载器", "icon": "User", "author": _A["a3"], "category": "avatar",
        "tags": [_T["community"], _T["new"], _T["experimental"]], "version": "0.5.0", "versions": [
            {"version": "0.5.0", "changelog": "初始 Alpha 版本，支持基础表情", "releasedAt": "2026-04-20", "size": 6144},
        ], "screenshots": [], "rating": 3.5, "ratingCount": 22, "downloadCount": 890, "installedCount": 340,
        "likeCount": 120, "installStatus": "none", "isFavorite": False, "license": "MIT", "createdAt": "2026-04-20", "updatedAt": "2026-04-20", "size": 6144,
    },
    {
        "id": "cxp-workflow", "type": "plugin", "name": "CxPlugin 自动化工作流",
        "description": "基于 CxPlugin 框架的可视化工作流编排引擎，支持条件分支、循环、并行执行等高级流程控制，可订阅事件触发自动化任务。",
        "summary": "可视化工作流 CxPlugin 编排引擎", "icon": "RefreshCw", "author": _A["a2"], "category": "productivity",
        "tags": [_T["official"], _T["premium"], _T["stable"]], "version": "1.3.0", "versions": [
            {"version": "1.3.0", "changelog": "新增并行执行节点与事件订阅", "releasedAt": "2026-04-08", "size": 3584},
        ], "screenshots": [], "rating": 4.7, "ratingCount": 198, "downloadCount": 12300, "installedCount": 7600,
        "likeCount": 3800, "installStatus": "none", "isFavorite": True, "featured": True, "license": "MIT",
        "createdAt": "2025-11-15", "updatedAt": "2026-04-08", "size": 3584,
    },
    {
        "id": "cxp-pdf-reader", "type": "plugin", "name": "CxPlugin PDF 智能阅读器",
        "description": "LuomiNest 首个学术阅读插件，支持 PDF/Word/TXT 文档阅读，内置 AI 助手可对文档进行总结、翻译、关键信息提取与问答。基于 CxPlugin 双轨架构:前端 Vue 提供阅读界面,后端 Python 提供 PDF/Word 解析与 LLM 调用。复用主项目 LLM Provider,无需单独配置 API。",
        "summary": "PDF/Word/TXT 学术阅读插件", "icon": "FileText", "author": _A["a1"], "category": "tool",
        "tags": [_T["official"], _T["free"], _T["new"]], "version": "1.0.0", "versions": [
            {"version": "1.0.0", "changelog": "首个版本:支持 PDF/Word/TXT 阅读、AI 总结/翻译/问答、多标签、大纲导航、全文搜索", "releasedAt": "2026-07-19", "size": 2048},
        ], "screenshots": [], "rating": 0.0, "ratingCount": 0, "downloadCount": 0, "installedCount": 0,
        "likeCount": 0, "installStatus": "none", "isFavorite": False, "featured": True, "license": "MIT",
        "homepage": "https://github.com/LuminousCX/LuomiNest", "minAppVersion": "0.7.6",
        "createdAt": "2026-07-19", "updatedAt": "2026-07-19", "size": 2048,
        "source": "local", "downloadUrl": None, "platform": "fullstack",
        "capabilities": ["document-reading", "ai-summary", "ai-translate", "ai-qa", "outline", "search"],
        "permissions": ["file_read", "file_write", "network", "admin_api", "tool_register"],
    },
]


# ─── 本地插件库清单 ─────────────────────────────────────────────
# 用户从市场"安装"本地插件时,install_service 会从此清单读取插件包路径。
# 当前所有插件均以源码形式存在于 backend/plugins/{plugin_id}/ 目录,
# 安装动作等价于"启用":前端 builtin 插件调用 enableFrontendPlugin,
# 后端插件由 cx_plugin_loader 扫描目录加载。
# 后期上传到 GitHub/云端时,只需将 downloadUrl 改为远程 URL,
# install_service 会自动下载 zip 并解压到 PLUGIN_DIR。

LOCAL_PLUGIN_REPO: list[dict[str, Any]] = [
    {
        "id": "cxp-pdf-reader",
        "name": "CxPlugin PDF 智能阅读器",
        "version": "1.0.0",
        "source": "local",
        "localPath": "plugins/cxp-pdf-reader",
        "downloadUrl": None,
        "description": "本地内置 PDF/Word/TXT 阅读插件,安装后自动启用",
        "platform": "fullstack",
        "frontendBuiltin": True,
    },
]


def get_local_builtin_plugin(item_id: str) -> dict[str, Any] | None:
    """根据 item_id 查找本地内置插件清单条目。

    用于 install 流程识别 builtin 插件,跳过远程下载,
    直接走"启用"路径(前端 enableFrontendPlugin + 后端 cx_plugin_lifecycle.enable_plugin)。
    """
    for entry in LOCAL_PLUGIN_REPO:
        if entry.get("id") == item_id:
            return entry
    return None


# ─── Skill 技能目录 ────────────────────────────────────────────

CATALOG_SKILLS: list[dict[str, Any]] = [
    {
        "id": "skill-frontend-design", "type": "skill", "name": "前端设计",
        "description": "为构建新 UI 或重塑现有界面提供独特的视觉设计指导，涵盖调色板、字体排版、布局结构与动效设计，避免模板化默认风格。",
        "summary": "独特视觉设计指导技能", "icon": "Palette", "author": _A["a1"], "category": "coding",
        "tags": [_T["official"], _T["free"], _T["popular"]], "version": "2.0.0", "versions": [
            {"version": "2.0.0", "changelog": "新增动效设计与排版指南", "releasedAt": "2026-04-16", "size": 1024},
            {"version": "1.5.0", "changelog": "优化设计原则与流程", "releasedAt": "2026-03-10", "size": 980},
        ], "screenshots": [], "rating": 4.9, "ratingCount": 456, "downloadCount": 28500, "installedCount": 19200,
        "likeCount": 6800, "installStatus": "installed", "isFavorite": True, "featured": True, "license": "MIT",
        "createdAt": "2025-10-01", "updatedAt": "2026-04-16", "size": 1024,
    },
    {
        "id": "skill-mcp-builder", "type": "skill", "name": "MCP 服务器构建",
        "description": "创建高质量 MCP（Model Context Protocol）服务器的完整指南，支持 Python（FastMCP）与 Node/TypeScript（MCP SDK），让 LLM 与外部服务交互。",
        "summary": "MCP 服务器开发构建技能", "icon": "Plug", "author": _A["a1"], "category": "coding",
        "tags": [_T["official"], _T["free"], _T["popular"]], "version": "1.8.0", "versions": [
            {"version": "1.8.0", "changelog": "新增 Node/TypeScript SDK 示例", "releasedAt": "2026-04-14", "size": 2048},
        ], "screenshots": [], "rating": 4.7, "ratingCount": 389, "downloadCount": 22100, "installedCount": 14800,
        "likeCount": 5200, "installStatus": "installed", "isFavorite": False, "featured": True, "license": "MIT",
        "createdAt": "2025-11-01", "updatedAt": "2026-04-14", "size": 2048,
    },
    {
        "id": "skill-doc-coauthoring", "type": "skill", "name": "文档协作",
        "description": "引导用户通过结构化工作流共同编写文档，支持提案、技术规范、决策文档等，提供内容迭代与读者验证流程。",
        "summary": "结构化文档协作写作技能", "icon": "FileText", "author": _A["a3"], "category": "document",
        "tags": [_T["official"], _T["free"], _T["new"]], "version": "1.4.0", "versions": [
            {"version": "1.4.0", "changelog": "新增决策文档模板", "releasedAt": "2026-04-11", "size": 1536},
        ], "screenshots": [], "rating": 4.5, "ratingCount": 234, "downloadCount": 14200, "installedCount": 8900,
        "likeCount": 3100, "installStatus": "none", "isFavorite": False, "license": "MIT", "createdAt": "2026-01-10", "updatedAt": "2026-04-11", "size": 1536,
    },
    {
        "id": "skill-pdf", "type": "skill", "name": "PDF 文档处理",
        "description": "全面的 PDF 处理技能，支持读取、提取文本/表格、合并拆分、旋转页面、添加水印、创建新 PDF、填写表单、加密解密与 OCR 识别。",
        "summary": "全功能 PDF 文档处理技能", "icon": "FileText", "author": _A["a1"], "category": "document",
        "tags": [_T["official"], _T["free"]], "version": "1.2.0", "versions": [
            {"version": "1.2.0", "changelog": "新增 OCR 识别与表单填充", "releasedAt": "2026-04-06", "size": 1280},
        ], "screenshots": [], "rating": 4.3, "ratingCount": 156, "downloadCount": 8700, "installedCount": 5200,
        "likeCount": 1900, "installStatus": "none", "isFavorite": True, "license": "Apache-2.0", "createdAt": "2026-02-15", "updatedAt": "2026-04-06", "size": 1280,
    },
    {
        "id": "skill-docx", "type": "skill", "name": "Word 文档处理",
        "description": "创建、读取、编辑 Word 文档（.docx）的完整技能，支持目录、标题、页码、信头等格式，支持图片插入与修订追踪。",
        "summary": "Word 文档创建编辑技能", "icon": "FileText", "author": _A["a2"], "category": "document",
        "tags": [_T["official"], _T["premium"], _T["popular"]], "version": "1.6.0", "versions": [
            {"version": "1.6.0", "changelog": "新增修订追踪与批注支持", "releasedAt": "2026-04-19", "size": 2560},
        ], "screenshots": [], "rating": 4.6, "ratingCount": 278, "downloadCount": 16800, "installedCount": 10400,
        "likeCount": 4200, "installStatus": "none", "isFavorite": False, "featured": True, "license": "MIT",
        "createdAt": "2025-12-20", "updatedAt": "2026-04-19", "size": 2560,
    },
    {
        "id": "skill-pptx", "type": "skill", "name": "PowerPoint 演示文稿",
        "description": "创建、读取、编辑 PowerPoint 演示文稿（.pptx）的技能，支持幻灯片布局、图表、缩略图生成与模板管理。",
        "summary": "PowerPoint 演示文稿技能", "icon": "Presentation", "author": _A["a2"], "category": "document",
        "tags": [_T["official"], _T["free"], _T["experimental"]], "version": "0.8.0", "versions": [
            {"version": "0.8.0", "changelog": "Beta 版本，支持基础幻灯片操作", "releasedAt": "2026-04-02", "size": 1792},
        ], "screenshots": [], "rating": 3.8, "ratingCount": 67, "downloadCount": 3400, "installedCount": 1800,
        "likeCount": 560, "installStatus": "none", "isFavorite": False, "license": "MIT", "createdAt": "2026-03-20", "updatedAt": "2026-04-02", "size": 1792,
    },
    {
        "id": "skill-canvas-design", "type": "skill", "name": "画布设计",
        "description": "使用设计哲学创建精美的 .png 与 .pdf 视觉艺术作品，支持海报、艺术品、设计稿等静态视觉输出，避免版权侵权。",
        "summary": "静态视觉艺术创作技能", "icon": "Image", "author": _A["a3"], "category": "design",
        "tags": [_T["community"], _T["popular"], _T["new"]], "version": "1.3.0", "versions": [
            {"version": "1.3.0", "changelog": "新增海报与艺术品模板", "releasedAt": "2026-04-13", "size": 2048},
        ], "screenshots": [], "rating": 4.4, "ratingCount": 201, "downloadCount": 11600, "installedCount": 7200,
        "likeCount": 2800, "installStatus": "none", "isFavorite": False, "license": "MIT", "createdAt": "2026-01-05", "updatedAt": "2026-04-13", "size": 2048,
    },
    {
        "id": "skill-algorithmic-art", "type": "skill", "name": "算法艺术",
        "description": "使用 p5.js 与种子随机数创建算法艺术，支持交互式参数探索、流场、粒子系统等生成式艺术，提供原创视觉输出。",
        "summary": "p5.js 生成式算法艺术技能", "icon": "Sparkles", "author": _A["a3"], "category": "design",
        "tags": [_T["community"], _T["free"], _T["experimental"]], "version": "1.1.0", "versions": [
            {"version": "1.1.0", "changelog": "新增流场与粒子系统", "releasedAt": "2026-04-09", "size": 1536},
        ], "screenshots": [], "rating": 4.2, "ratingCount": 134, "downloadCount": 7800, "installedCount": 4600,
        "likeCount": 1600, "installStatus": "none", "isFavorite": False, "license": "MIT", "createdAt": "2026-02-28", "updatedAt": "2026-04-09", "size": 1536,
    },
    {
        "id": "skill-brand-guidelines", "type": "skill", "name": "品牌设计规范",
        "description": "应用官方品牌颜色与字体排版到任何需要品牌视觉的制品，支持幻灯片、文档、报告、HTML 落地页等，确保视觉一致性。",
        "summary": "品牌视觉规范应用技能", "icon": "Palette", "author": _A["a1"], "category": "design",
        "tags": [_T["official"], _T["free"]], "version": "1.0.0", "versions": [
            {"version": "1.0.0", "changelog": "正式版发布，支持多主题", "releasedAt": "2026-04-05", "size": 1536},
        ], "screenshots": [], "rating": 4.4, "ratingCount": 98, "downloadCount": 6200, "installedCount": 3800,
        "likeCount": 1200, "installStatus": "none", "isFavorite": False, "license": "MIT",
        "createdAt": "2026-03-01", "updatedAt": "2026-04-05", "size": 1536,
    },
    {
        "id": "skill-react-best-practices", "type": "skill", "name": "React 最佳实践",
        "description": "React 与 Next.js 应用的全面性能优化指南，涵盖 40+ 规则，包括瀑布流消除、包体积优化、服务端性能、重渲染优化等 8 大类别。",
        "summary": "React/Next.js 性能优化技能", "icon": "Code", "author": _A["a4"], "category": "coding",
        "tags": [_T["community"], _T["popular"], _T["free"]], "version": "1.0.0", "versions": [
            {"version": "1.0.0", "changelog": "初始版本，40+ 规则", "releasedAt": "2026-04-01", "size": 1280},
        ], "screenshots": [], "rating": 4.0, "ratingCount": 56, "downloadCount": 3800, "installedCount": 2100,
        "likeCount": 680, "installStatus": "none", "isFavorite": False, "featured": True, "license": "MIT",
        "createdAt": "2026-03-15", "updatedAt": "2026-04-01", "size": 1280,
    },
    {
        "id": "skill-theme-factory", "type": "skill", "name": "主题工厂",
        "description": "为制品（幻灯片、文档、报告、HTML 落地页）应用主题的工具集，提供 10 个预设主题（颜色/字体），支持动态生成自定义主题。",
        "summary": "制品主题样式工具集技能", "icon": "Palette", "author": _A["a1"], "category": "coding",
        "tags": [_T["official"], _T["stable"], _T["free"]], "version": "1.2.0", "versions": [
            {"version": "1.2.0", "changelog": "新增动态主题生成", "releasedAt": "2026-04-10", "size": 2048},
        ], "screenshots": [], "rating": 4.2, "ratingCount": 87, "downloadCount": 5600, "installedCount": 3400,
        "likeCount": 1100, "installStatus": "installed", "isFavorite": False, "license": "MIT",
        "createdAt": "2026-01-25", "updatedAt": "2026-04-10", "size": 2048,
    },
    {
        "id": "skill-skill-creator", "type": "skill", "name": "技能创建器",
        "description": "创建、修改、优化技能的完整工具，支持技能评估、基准测试、性能分析与描述优化，帮助构建高质量可复用技能。",
        "summary": "技能创建与优化工具技能", "icon": "Wrench", "author": _A["a1"], "category": "coding",
        "tags": [_T["official"], _T["premium"], _T["experimental"]], "version": "0.8.0", "versions": [
            {"version": "0.8.0", "changelog": "Beta 版本，支持技能评估", "releasedAt": "2026-04-03", "size": 1536},
        ], "screenshots": [], "rating": 3.9, "ratingCount": 42, "downloadCount": 2800, "installedCount": 1500,
        "likeCount": 420, "installStatus": "none", "isFavorite": False, "license": "Apache-2.0",
        "createdAt": "2026-03-20", "updatedAt": "2026-04-03", "size": 1536,
    },
    {
        "id": "skill-internal-comms", "type": "skill", "name": "内部通讯",
        "description": "帮助撰写各类内部通讯的资源集，支持状态报告、领导层更新、公司简报、FAQ、事件报告、项目更新等格式化内容。",
        "summary": "内部通讯撰写辅助技能", "icon": "Mail", "author": _A["a2"], "category": "knowledge",
        "tags": [_T["community"], _T["free"]], "version": "1.1.0", "versions": [
            {"version": "1.1.0", "changelog": "新增事件报告模板", "releasedAt": "2026-04-08", "size": 1792},
        ], "screenshots": [], "rating": 4.3, "ratingCount": 134, "downloadCount": 8400, "installedCount": 5100,
        "likeCount": 1800, "installStatus": "none", "isFavorite": True, "license": "MIT",
        "createdAt": "2026-02-20", "updatedAt": "2026-04-08", "size": 1792,
    },
    {
        "id": "skill-content-creator", "type": "skill", "name": "内容创作",
        "description": "为博客、社交媒体、营销材料创建引人入胜的内容，聚焦受众参与度，支持标题撰写、社交内容、营销文案等。",
        "summary": "受众导向内容创作技能", "icon": "PenTool", "author": _A["a5"], "category": "knowledge",
        "tags": [_T["community"], _T["popular"], _T["new"]], "version": "1.0.0", "versions": [
            {"version": "1.0.0", "changelog": "正式版发布", "releasedAt": "2026-04-12", "size": 2048},
        ], "screenshots": [], "rating": 4.5, "ratingCount": 189, "downloadCount": 11600, "installedCount": 7200,
        "likeCount": 2600, "installStatus": "none", "isFavorite": False, "license": "MIT",
        "createdAt": "2026-01-08", "updatedAt": "2026-04-12", "size": 2048,
    },
    {
        "id": "skill-slack-gif-creator", "type": "skill", "name": "Slack GIF 创建",
        "description": "创建为 Slack 优化的动画 GIF，提供约束、验证工具与动画概念，支持缓动、帧合成、GIF 构建等专业功能。",
        "summary": "Slack 动画 GIF 创建技能", "icon": "Image", "author": _A["a4"], "category": "media",
        "tags": [_T["community"], _T["experimental"], _T["free"]], "version": "1.0.0", "versions": [
            {"version": "1.0.0", "changelog": "初始版本，支持缓动与帧合成", "releasedAt": "2026-04-15", "size": 1280},
        ], "screenshots": [], "rating": 4.1, "ratingCount": 78, "downloadCount": 4200, "installedCount": 2400,
        "likeCount": 890, "installStatus": "none", "isFavorite": False, "license": "MIT",
        "createdAt": "2026-03-10", "updatedAt": "2026-04-15", "size": 1280,
    },
]


# ─── Agent 智能体目录 ──────────────────────────────────────────

CATALOG_AGENTS: list[dict[str, Any]] = [
    {
        "id": "ag1", "type": "agent", "name": "智能客服助手",
        "description": "基于大语言模型的智能客服智能体，支持多轮对话、意图识别、知识库问答和工单自动创建，可自定义话术和业务流程。",
        "summary": "7x24 智能客服智能体", "icon": "Bot", "author": _A["a1"], "category": "assistant",
        "tags": [_T["official"], _T["free"], _T["popular"]], "version": "2.0.0", "versions": [
            {"version": "2.0.0", "changelog": "新增多轮对话管理", "releasedAt": "2026-04-18", "size": 3072},
            {"version": "1.5.0", "changelog": "优化意图识别", "releasedAt": "2026-03-10", "size": 2800},
        ], "screenshots": [], "rating": 4.8, "ratingCount": 342, "downloadCount": 19800, "installedCount": 12400,
        "likeCount": 5600, "installStatus": "installed", "isFavorite": True, "featured": True, "license": "MIT",
        "createdAt": "2025-09-15", "updatedAt": "2026-04-18", "size": 3072,
    },
    {
        "id": "ag2", "type": "agent", "name": "数据分析专家",
        "description": "专业的数据分析智能体，支持自然语言查询数据库、自动生成可视化报表、趋势预测和异常检测。",
        "summary": "自然语言驱动的数据分析", "icon": "BarChart3", "author": _A["a3"], "category": "analysis",
        "tags": [_T["official"], _T["free"], _T["popular"]], "version": "1.5.0", "versions": [
            {"version": "1.5.0", "changelog": "新增异常检测", "releasedAt": "2026-04-14", "size": 2560},
        ], "screenshots": [], "rating": 4.6, "ratingCount": 215, "downloadCount": 14200, "installedCount": 8900,
        "likeCount": 3400, "installStatus": "none", "isFavorite": False, "featured": True, "license": "MIT",
        "createdAt": "2025-11-20", "updatedAt": "2026-04-14", "size": 2560,
    },
    {
        "id": "ag3", "type": "agent", "name": "代码生成器",
        "description": "全栈代码生成智能体，支持从需求描述到完整项目的代码生成，涵盖前端、后端、数据库和部署配置。",
        "summary": "从需求到代码的全栈生成", "icon": "Terminal", "author": _A["a2"], "category": "development",
        "tags": [_T["official"], _T["free"], _T["popular"]], "version": "1.3.0", "versions": [
            {"version": "1.3.0", "changelog": "新增微服务架构模板", "releasedAt": "2026-04-12", "size": 2048},
        ], "screenshots": [], "rating": 4.5, "ratingCount": 189, "downloadCount": 11600, "installedCount": 7200,
        "likeCount": 2600, "installStatus": "none", "isFavorite": False, "license": "MIT",
        "createdAt": "2026-01-08", "updatedAt": "2026-04-12", "size": 2048,
    },
    {
        "id": "ag4", "type": "agent", "name": "创意设计师",
        "description": "AI 创意设计智能体，支持品牌视觉设计、UI/UX 原型、营销素材生成，可理解设计需求并输出多套方案。",
        "summary": "AI 驱动的创意设计助手", "icon": "Lightbulb", "author": _A["a5"], "category": "creative",
        "tags": [_T["community"], _T["premium"], _T["new"]], "version": "1.1.0", "versions": [
            {"version": "1.1.0", "changelog": "新增品牌配色方案", "releasedAt": "2026-04-08", "size": 1792},
        ], "screenshots": [], "rating": 4.3, "ratingCount": 134, "downloadCount": 8400, "installedCount": 5100,
        "likeCount": 1800, "installStatus": "none", "isFavorite": True, "license": "Apache-2.0",
        "createdAt": "2026-02-20", "updatedAt": "2026-04-08", "size": 1792,
    },
    {
        "id": "ag5", "type": "agent", "name": "教育导师",
        "description": "个性化教育智能体，支持自适应学习路径规划、知识点讲解、练习出题和学习进度追踪，覆盖 K12 和高等教育。",
        "summary": "个性化自适应学习导师", "icon": "GraduationCap", "author": _A["a4"], "category": "education",
        "tags": [_T["community"], _T["free"]], "version": "1.0.0", "versions": [
            {"version": "1.0.0", "changelog": "正式版发布", "releasedAt": "2026-04-05", "size": 1536},
        ], "screenshots": [], "rating": 4.4, "ratingCount": 98, "downloadCount": 6200, "installedCount": 3800,
        "likeCount": 1200, "installStatus": "none", "isFavorite": False, "license": "MIT",
        "createdAt": "2026-03-01", "updatedAt": "2026-04-05", "size": 1536,
    },
    {
        "id": "ag6", "type": "agent", "name": "市场研究员",
        "description": "智能市场研究智能体，自动收集行业数据、竞品分析和市场趋势，生成结构化研究报告和策略建议。",
        "summary": "自动化市场研究与分析", "icon": "TrendingUp", "author": _A["a3"], "category": "analysis",
        "tags": [_T["official"], _T["premium"]], "version": "0.9.0", "versions": [
            {"version": "0.9.0", "changelog": "Beta 版本", "releasedAt": "2026-04-01", "size": 1280},
        ], "screenshots": [], "rating": 4.0, "ratingCount": 56, "downloadCount": 3800, "installedCount": 2100,
        "likeCount": 680, "installStatus": "none", "isFavorite": False, "featured": True, "license": "MIT",
        "createdAt": "2026-03-15", "updatedAt": "2026-04-01", "size": 1280,
    },
    {
        "id": "ag7", "type": "agent", "name": "运维管家",
        "description": "智能运维智能体，支持服务器监控、日志分析、故障诊断和自动修复，提供 7x24 小时稳定运行保障。",
        "summary": "7x24 智能运维保障", "icon": "Shield", "author": _A["a1"], "category": "development",
        "tags": [_T["official"], _T["stable"], _T["free"]], "version": "1.2.0", "versions": [
            {"version": "1.2.0", "changelog": "新增自动修复策略", "releasedAt": "2026-04-10", "size": 2048},
        ], "screenshots": [], "rating": 4.2, "ratingCount": 87, "downloadCount": 5600, "installedCount": 3400,
        "likeCount": 1100, "installStatus": "installed", "isFavorite": False, "license": "MIT",
        "createdAt": "2026-01-25", "updatedAt": "2026-04-10", "size": 2048,
    },
    {
        "id": "ag8", "type": "agent", "name": "法律顾问",
        "description": "AI 法律咨询智能体，支持合同审查、法律条文检索、风险评估和合规建议，覆盖常见法律领域。",
        "summary": "AI 法律咨询与合规助手", "icon": "Scale", "author": _A["a2"], "category": "assistant",
        "tags": [_T["community"], _T["premium"], _T["experimental"]], "version": "0.8.0", "versions": [
            {"version": "0.8.0", "changelog": "Beta 版本", "releasedAt": "2026-04-03", "size": 1536},
        ], "screenshots": [], "rating": 3.9, "ratingCount": 42, "downloadCount": 2800, "installedCount": 1500,
        "likeCount": 420, "installStatus": "none", "isFavorite": False, "license": "Apache-2.0",
        "createdAt": "2026-03-20", "updatedAt": "2026-04-03", "size": 1536,
    },
]


# ─── 目录查询接口 ──────────────────────────────────────────────

def get_catalog_by_type(item_type: str) -> list[dict[str, Any]]:
    """按类型获取目录条目。

    Args:
        item_type: plugin / skill / agent

    Returns:
        对应类型的目录条目列表，未知类型返回空列表。
    """
    if item_type == "plugin":
        return CATALOG_PLUGINS
    if item_type == "skill":
        return CATALOG_SKILLS
    if item_type == "agent":
        return CATALOG_AGENTS
    return []


def get_all_catalog_items() -> list[dict[str, Any]]:
    """获取所有目录条目（plugin + skill + agent）。"""
    return [*CATALOG_PLUGINS, *CATALOG_SKILLS, *CATALOG_AGENTS]


def get_categories_by_type(item_type: str) -> list[dict[str, Any]]:
    """按类型获取分类列表。"""
    if item_type == "plugin":
        return PLUGIN_CATEGORIES
    if item_type == "skill":
        return SKILL_CATEGORIES
    if item_type == "agent":
        return AGENT_CATEGORIES
    return []


def get_catalog_item(item_id: str) -> dict[str, Any] | None:
    """按 ID 获取单个目录条目。"""
    for item in get_all_catalog_items():
        if item["id"] == item_id:
            return item
    return None

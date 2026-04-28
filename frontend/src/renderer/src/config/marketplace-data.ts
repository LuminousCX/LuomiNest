import type { MarketplaceCategory, MarketplaceTag, MarketplaceItem, MarketplaceAuthor } from '../types/marketplace'

export const PLUGIN_CATEGORIES: MarketplaceCategory[] = [
  { id: 'all', name: '全部', icon: 'LayoutGrid' },
  { id: 'ai-model', name: 'AI 模型', icon: 'Cpu', children: [
    { id: 'llm', name: '大语言模型' },
    { id: 'embedding', name: '嵌入模型' },
    { id: 'vision', name: '视觉模型' },
    { id: 'tts', name: '语音合成' },
    { id: 'stt', name: '语音识别' },
  ]},
  { id: 'tool', name: '工具', icon: 'Wrench', children: [
    { id: 'search', name: '搜索' },
    { id: 'code', name: '代码' },
    { id: 'file', name: '文件' },
    { id: 'web', name: '网页' },
    { id: 'database', name: '数据库' },
  ]},
  { id: 'integration', name: '集成', icon: 'Puzzle', children: [
    { id: 'messaging', name: '消息平台' },
    { id: 'iot', name: 'IoT 设备' },
    { id: 'api', name: 'API 接入' },
    { id: 'cloud', name: '云服务' },
  ]},
  { id: 'avatar', name: '形象', icon: 'Palette', children: [
    { id: 'live2d', name: 'Live2D' },
    { id: 'vrm', name: 'VRM' },
    { id: 'voice', name: '语音包' },
  ]},
  { id: 'productivity', name: '效率', icon: 'Zap', children: [
    { id: 'automation', name: '自动化' },
    { id: 'workflow', name: '工作流' },
    { id: 'schedule', name: '日程' },
  ]},
]

export const SKILL_CATEGORIES: MarketplaceCategory[] = [
  { id: 'all', name: '全部', icon: 'LayoutGrid' },
  { id: 'conversation', name: '对话', icon: 'MessageCircle', children: [
    { id: 'chat', name: '日常对话' },
    { id: 'roleplay', name: '角色扮演' },
    { id: 'creative', name: '创意写作' },
    { id: 'translate', name: '翻译' },
  ]},
  { id: 'knowledge', name: '知识', icon: 'BookOpen', children: [
    { id: 'qa', name: '问答' },
    { id: 'research', name: '研究' },
    { id: 'education', name: '教育' },
    { id: 'summarize', name: '摘要' },
  ]},
  { id: 'coding', name: '编程', icon: 'Code', children: [
    { id: 'debug', name: '调试' },
    { id: 'review', name: '代码审查' },
    { id: 'generate', name: '代码生成' },
    { id: 'refactor', name: '重构' },
  ]},
  { id: 'media', name: '媒体', icon: 'Image', children: [
    { id: 'image-gen', name: '图片生成' },
    { id: 'music', name: '音乐' },
    { id: 'video', name: '视频' },
  ]},
  { id: 'lifestyle', name: '生活', icon: 'Heart', children: [
    { id: 'health', name: '健康' },
    { id: 'cooking', name: '烹饪' },
    { id: 'travel', name: '旅行' },
  ]},
]

export const AGENT_CATEGORIES: MarketplaceCategory[] = [
  { id: 'all', name: '全部', icon: 'LayoutGrid' },
  { id: 'assistant', name: '助手', icon: 'Bot', children: [
    { id: 'customer-service', name: '客服助手' },
    { id: 'sales', name: '销售助手' },
    { id: 'personal', name: '个人助理' },
  ]},
  { id: 'creative', name: '创意', icon: 'Lightbulb', children: [
    { id: 'writing', name: '写作' },
    { id: 'design', name: '设计' },
    { id: 'music', name: '音乐' },
  ]},
  { id: 'analysis', name: '分析', icon: 'BarChart3', children: [
    { id: 'data-analysis', name: '数据分析' },
    { id: 'market-research', name: '市场研究' },
    { id: 'finance', name: '财务分析' },
  ]},
  { id: 'development', name: '开发', icon: 'Terminal', children: [
    { id: 'code-gen', name: '代码生成' },
    { id: 'testing', name: '测试' },
    { id: 'devops', name: '运维' },
  ]},
  { id: 'education', name: '教育', icon: 'GraduationCap', children: [
    { id: 'teaching', name: '教学' },
    { id: 'tutoring', name: '辅导' },
    { id: 'training', name: '培训' },
  ]},
]

export const COMMON_TAGS: MarketplaceTag[] = [
  { id: 'official', name: '官方', color: '#147EBC' },
  { id: 'community', name: '社区', color: '#6366f1' },
  { id: 'free', name: '免费', color: '#22c55e' },
  { id: 'premium', name: '付费', color: '#f59e0b' },
  { id: 'popular', name: '热门', color: '#f43f5e' },
  { id: 'new', name: '新品', color: '#3b82f6' },
  { id: 'experimental', name: '实验性', color: '#8b5cf6' },
  { id: 'stable', name: '稳定', color: '#147EBC' },
]

const MOCK_AUTHORS: MarketplaceAuthor[] = [
  { id: 'a1', name: 'LuminousCX', avatar: '', verified: true },
  { id: 'a2', name: 'AIStudio', avatar: '', verified: true },
  { id: 'a3', name: 'DevCommunity', avatar: '', verified: false },
  { id: 'a4', name: 'TechLab', avatar: '', verified: true },
  { id: 'a5', name: 'OpenSource', avatar: '', verified: false },
]

export const MOCK_PLUGINS: MarketplaceItem[] = [
  {
    id: 'p1', type: 'plugin', name: 'DeepSeek 接入', description: '接入 DeepSeek 系列大语言模型，支持 DeepSeek-V3、DeepSeek-R1 等模型，提供高质量的推理与对话能力。',
    summary: 'DeepSeek 系列模型接入插件', icon: 'Brain', author: MOCK_AUTHORS[0], category: 'ai-model',
    tags: [COMMON_TAGS[0], COMMON_TAGS[2], COMMON_TAGS[7]], version: '1.2.0', versions: [
      { version: '1.2.0', changelog: '新增 DeepSeek-R1 支持', releasedAt: '2026-04-15', size: 2048 },
      { version: '1.1.0', changelog: '优化流式输出性能', releasedAt: '2026-03-20', size: 1980 },
      { version: '1.0.0', changelog: '初始版本', releasedAt: '2026-02-01', size: 1856 },
    ], screenshots: [], rating: 4.8, ratingCount: 256, downloadCount: 15200, installedCount: 8900,
    installStatus: 'none', isFavorite: false, featured: true, homepage: 'https://deepseek.com',
    license: 'MIT', minAppVersion: '0.1.0', createdAt: '2026-02-01', updatedAt: '2026-04-15', size: 2048,
  },
  {
    id: 'p2', type: 'plugin', name: 'Home Assistant 桥接', description: '将 LuomiNest 与 Home Assistant 智能家居平台深度集成，支持设备控制、场景自动化和状态监控。',
    summary: 'Home Assistant 智能家居集成', icon: 'Home', author: MOCK_AUTHORS[1], category: 'integration',
    tags: [COMMON_TAGS[0], COMMON_TAGS[2], COMMON_TAGS[7]], version: '2.0.1', versions: [
      { version: '2.0.1', changelog: '修复设备同步问题', releasedAt: '2026-04-10', size: 4096 },
      { version: '2.0.0', changelog: '全新架构重写', releasedAt: '2026-03-15', size: 3800 },
    ], screenshots: [], rating: 4.5, ratingCount: 128, downloadCount: 6800, installedCount: 4200,
    installStatus: 'installed', isFavorite: true, featured: true, license: 'Apache-2.0',
    createdAt: '2026-01-15', updatedAt: '2026-04-10', size: 4096,
  },
  {
    id: 'p3', type: 'plugin', name: 'Discord 通道', description: '让 LuomiNest 通过 Discord 与用户交互，支持多服务器、频道管理和富文本消息。',
    summary: 'Discord 消息平台通道', icon: 'MessageSquare', author: MOCK_AUTHORS[2], category: 'integration',
    tags: [COMMON_TAGS[1], COMMON_TAGS[2]], version: '1.0.3', versions: [
      { version: '1.0.3', changelog: '支持斜杠命令', releasedAt: '2026-04-05', size: 1536 },
    ], screenshots: [], rating: 4.2, ratingCount: 89, downloadCount: 3200, installedCount: 1800,
    installStatus: 'none', isFavorite: false, license: 'MIT', createdAt: '2026-03-01', updatedAt: '2026-04-05', size: 1536,
  },
  {
    id: 'p4', type: 'plugin', name: '网页搜索工具', description: '集成主流搜索引擎，为 AI 提供实时网页搜索能力，支持结果摘要和引用追踪。',
    summary: 'AI 网页搜索增强工具', icon: 'Search', author: MOCK_AUTHORS[3], category: 'tool',
    tags: [COMMON_TAGS[1], COMMON_TAGS[4], COMMON_TAGS[2]], version: '1.5.0', versions: [
      { version: '1.5.0', changelog: '新增图片搜索', releasedAt: '2026-04-18', size: 3072 },
    ], screenshots: [], rating: 4.6, ratingCount: 312, downloadCount: 18900, installedCount: 11200,
    installStatus: 'none', isFavorite: false, featured: true, license: 'MIT',
    createdAt: '2025-12-01', updatedAt: '2026-04-18', size: 3072,
  },
  {
    id: 'p5', type: 'plugin', name: '语音合成引擎', description: '基于 Edge TTS 和本地模型的语音合成插件，支持多种语言和音色，可自定义语速和情感。',
    summary: '多语言语音合成引擎', icon: 'Volume2', author: MOCK_AUTHORS[0], category: 'ai-model',
    tags: [COMMON_TAGS[0], COMMON_TAGS[2]], version: '1.1.0', versions: [
      { version: '1.1.0', changelog: '新增情感控制', releasedAt: '2026-04-12', size: 5120 },
    ], screenshots: [], rating: 4.4, ratingCount: 167, downloadCount: 9500, installedCount: 5800,
    installStatus: 'installed', isFavorite: false, license: 'MIT', createdAt: '2026-01-20', updatedAt: '2026-04-12', size: 5120,
  },
  {
    id: 'p6', type: 'plugin', name: '代码执行沙箱', description: '安全的代码执行环境，支持 Python、JavaScript 等语言，为 AI 提供代码运行能力。',
    summary: '安全代码执行环境', icon: 'Zap', author: MOCK_AUTHORS[4], category: 'tool',
    tags: [COMMON_TAGS[1], COMMON_TAGS[6], COMMON_TAGS[2]], version: '0.9.0', versions: [
      { version: '0.9.0', changelog: 'Beta 版本发布', releasedAt: '2026-04-01', size: 8192 },
    ], screenshots: [], rating: 3.9, ratingCount: 45, downloadCount: 2100, installedCount: 980,
    installStatus: 'none', isFavorite: false, license: 'Apache-2.0', createdAt: '2026-03-15', updatedAt: '2026-04-01', size: 8192,
  },
  {
    id: 'p7', type: 'plugin', name: 'VRM 模型加载器', description: '加载和渲染 VRM 格式的 3D 虚拟形象，支持表情控制和动作播放。',
    summary: 'VRM 3D 形象加载器', icon: 'User', author: MOCK_AUTHORS[3], category: 'avatar',
    tags: [COMMON_TAGS[1], COMMON_TAGS[5], COMMON_TAGS[6]], version: '0.5.0', versions: [
      { version: '0.5.0', changelog: '初始 Alpha 版本', releasedAt: '2026-04-20', size: 6144 },
    ], screenshots: [], rating: 3.5, ratingCount: 22, downloadCount: 890, installedCount: 340,
    installStatus: 'none', isFavorite: false, license: 'MIT', createdAt: '2026-04-20', updatedAt: '2026-04-20', size: 6144,
  },
  {
    id: 'p8', type: 'plugin', name: '自动化工作流', description: '可视化工作流编排引擎，支持条件分支、循环、并行执行等高级流程控制。',
    summary: '可视化工作流编排引擎', icon: 'RefreshCw', author: MOCK_AUTHORS[1], category: 'productivity',
    tags: [COMMON_TAGS[0], COMMON_TAGS[3], COMMON_TAGS[7]], version: '1.3.0', versions: [
      { version: '1.3.0', changelog: '新增并行执行节点', releasedAt: '2026-04-08', size: 3584 },
    ], screenshots: [], rating: 4.7, ratingCount: 198, downloadCount: 12300, installedCount: 7600,
    installStatus: 'none', isFavorite: true, featured: true, license: 'MIT',
    createdAt: '2025-11-15', updatedAt: '2026-04-08', size: 3584,
  },
]

export const MOCK_SKILLS: MarketplaceItem[] = [
  {
    id: 's1', type: 'skill', name: '智能翻译官', description: '支持 50+ 语言的智能翻译技能，自动检测源语言，保留专业术语和上下文语义，支持批量翻译和对照阅读。',
    summary: '多语言智能翻译技能', icon: 'Globe', author: MOCK_AUTHORS[0], category: 'conversation',
    tags: [COMMON_TAGS[0], COMMON_TAGS[2], COMMON_TAGS[4]], version: '2.1.0', versions: [
      { version: '2.1.0', changelog: '新增方言支持', releasedAt: '2026-04-16', size: 1024 },
      { version: '2.0.0', changelog: '全新翻译引擎', releasedAt: '2026-03-10', size: 980 },
    ], screenshots: [], rating: 4.9, ratingCount: 456, downloadCount: 28500, installedCount: 19200,
    installStatus: 'installed', isFavorite: true, featured: true, license: 'MIT',
    createdAt: '2025-10-01', updatedAt: '2026-04-16', size: 1024,
  },
  {
    id: 's2', type: 'skill', name: '代码助手', description: '专业的编程辅助技能，支持代码生成、调试、审查、重构和文档编写，覆盖主流编程语言。',
    summary: '专业编程辅助技能', icon: 'Laptop', author: MOCK_AUTHORS[3], category: 'coding',
    tags: [COMMON_TAGS[0], COMMON_TAGS[2], COMMON_TAGS[4]], version: '1.8.0', versions: [
      { version: '1.8.0', changelog: '新增 Rust 支持', releasedAt: '2026-04-14', size: 2048 },
    ], screenshots: [], rating: 4.7, ratingCount: 389, downloadCount: 22100, installedCount: 14800,
    installStatus: 'installed', isFavorite: false, featured: true, license: 'MIT',
    createdAt: '2025-11-01', updatedAt: '2026-04-14', size: 2048,
  },
  {
    id: 's3', type: 'skill', name: '创意写作', description: '激发创造力的写作技能，涵盖小说、诗歌、剧本、文案等多种文体，支持风格模仿和续写。',
    summary: '多文体创意写作技能', icon: 'PenTool', author: MOCK_AUTHORS[2], category: 'conversation',
    tags: [COMMON_TAGS[1], COMMON_TAGS[2], COMMON_TAGS[5]], version: '1.4.0', versions: [
      { version: '1.4.0', changelog: '新增剧本模式', releasedAt: '2026-04-11', size: 1536 },
    ], screenshots: [], rating: 4.5, ratingCount: 234, downloadCount: 14200, installedCount: 8900,
    installStatus: 'none', isFavorite: false, license: 'MIT', createdAt: '2026-01-10', updatedAt: '2026-04-11', size: 1536,
  },
  {
    id: 's4', type: 'skill', name: '学术研究', description: '深度学术研究技能，支持文献检索、论文分析、研究方法指导和学术写作辅助。',
    summary: '学术研究辅助技能', icon: 'BookOpen', author: MOCK_AUTHORS[4], category: 'knowledge',
    tags: [COMMON_TAGS[1], COMMON_TAGS[2]], version: '1.2.0', versions: [
      { version: '1.2.0', changelog: '新增引用格式支持', releasedAt: '2026-04-06', size: 1280 },
    ], screenshots: [], rating: 4.3, ratingCount: 156, downloadCount: 8700, installedCount: 5200,
    installStatus: 'none', isFavorite: true, license: 'Apache-2.0', createdAt: '2026-02-15', updatedAt: '2026-04-06', size: 1280,
  },
  {
    id: 's5', type: 'skill', name: '图片生成', description: 'AI 图片生成技能，支持文生图、图生图、风格迁移等，集成 Stable Diffusion 和 DALL-E。',
    summary: 'AI 图片生成技能', icon: 'Palette', author: MOCK_AUTHORS[1], category: 'media',
    tags: [COMMON_TAGS[0], COMMON_TAGS[3], COMMON_TAGS[4]], version: '1.6.0', versions: [
      { version: '1.6.0', changelog: '新增 ControlNet 支持', releasedAt: '2026-04-19', size: 2560 },
    ], screenshots: [], rating: 4.6, ratingCount: 278, downloadCount: 16800, installedCount: 10400,
    installStatus: 'none', isFavorite: false, featured: true, license: 'MIT',
    createdAt: '2025-12-20', updatedAt: '2026-04-19', size: 2560,
  },
  {
    id: 's6', type: 'skill', name: '健康顾问', description: '基于权威医学知识的健康咨询技能，提供症状分析、健康建议和就医指导，仅供参考不替代医疗。',
    summary: '智能健康咨询技能', icon: 'HeartPulse', author: MOCK_AUTHORS[2], category: 'lifestyle',
    tags: [COMMON_TAGS[1], COMMON_TAGS[2], COMMON_TAGS[6]], version: '0.8.0', versions: [
      { version: '0.8.0', changelog: 'Beta 版本', releasedAt: '2026-04-02', size: 1792 },
    ], screenshots: [], rating: 3.8, ratingCount: 67, downloadCount: 3400, installedCount: 1800,
    installStatus: 'none', isFavorite: false, license: 'MIT', createdAt: '2026-03-20', updatedAt: '2026-04-02', size: 1792,
  },
  {
    id: 's7', type: 'skill', name: '角色扮演大师', description: '沉浸式角色扮演技能，内置数百个角色模板，支持自定义角色设定和多角色互动。',
    summary: '沉浸式角色扮演技能', icon: 'Users', author: MOCK_AUTHORS[4], category: 'conversation',
    tags: [COMMON_TAGS[1], COMMON_TAGS[4], COMMON_TAGS[5]], version: '1.3.0', versions: [
      { version: '1.3.0', changelog: '新增多人模式', releasedAt: '2026-04-13', size: 2048 },
    ], screenshots: [], rating: 4.4, ratingCount: 201, downloadCount: 11600, installedCount: 7200,
    installStatus: 'none', isFavorite: false, license: 'MIT', createdAt: '2026-01-05', updatedAt: '2026-04-13', size: 2048,
  },
  {
    id: 's8', type: 'skill', name: '数据分析师', description: '专业的数据分析技能，支持数据清洗、统计分析、可视化图表生成和报告撰写。',
    summary: '专业数据分析技能', icon: 'BarChart3', author: MOCK_AUTHORS[3], category: 'knowledge',
    tags: [COMMON_TAGS[0], COMMON_TAGS[2]], version: '1.1.0', versions: [
      { version: '1.1.0', changelog: '新增图表类型', releasedAt: '2026-04-09', size: 1536 },
    ], screenshots: [], rating: 4.2, ratingCount: 134, downloadCount: 7800, installedCount: 4600,
    installStatus: 'none', isFavorite: false, license: 'MIT', createdAt: '2026-02-28', updatedAt: '2026-04-09', size: 1536,
  },
]

export const MOCK_AGENTS: MarketplaceItem[] = [
  {
    id: 'ag1', type: 'agent', name: '智能客服助手', description: '基于大语言模型的智能客服智能体，支持多轮对话、意图识别、知识库问答和工单自动创建，可自定义话术和业务流程。',
    summary: '7x24 智能客服智能体', icon: 'Bot', author: MOCK_AUTHORS[0], category: 'assistant',
    tags: [COMMON_TAGS[0], COMMON_TAGS[2], COMMON_TAGS[4]], version: '2.0.0', versions: [
      { version: '2.0.0', changelog: '新增多轮对话管理', releasedAt: '2026-04-18', size: 3072 },
      { version: '1.5.0', changelog: '优化意图识别', releasedAt: '2026-03-10', size: 2800 },
    ], screenshots: [], rating: 4.8, ratingCount: 342, downloadCount: 19800, installedCount: 12400,
    installStatus: 'installed', isFavorite: true, featured: true, license: 'MIT',
    createdAt: '2025-09-15', updatedAt: '2026-04-18', size: 3072,
  },
  {
    id: 'ag2', type: 'agent', name: '数据分析专家', description: '专业的数据分析智能体，支持自然语言查询数据库、自动生成可视化报表、趋势预测和异常检测。',
    summary: '自然语言驱动的数据分析', icon: 'BarChart3', author: MOCK_AUTHORS[3], category: 'analysis',
    tags: [COMMON_TAGS[0], COMMON_TAGS[2], COMMON_TAGS[4]], version: '1.5.0', versions: [
      { version: '1.5.0', changelog: '新增异常检测', releasedAt: '2026-04-14', size: 2560 },
    ], screenshots: [], rating: 4.6, ratingCount: 215, downloadCount: 14200, installedCount: 8900,
    installStatus: 'none', isFavorite: false, featured: true, license: 'MIT',
    createdAt: '2025-11-20', updatedAt: '2026-04-14', size: 2560,
  },
  {
    id: 'ag3', type: 'agent', name: '代码生成器', description: '全栈代码生成智能体，支持从需求描述到完整项目的代码生成，涵盖前端、后端、数据库和部署配置。',
    summary: '从需求到代码的全栈生成', icon: 'Terminal', author: MOCK_AUTHORS[1], category: 'development',
    tags: [COMMON_TAGS[0], COMMON_TAGS[2], COMMON_TAGS[4]], version: '1.3.0', versions: [
      { version: '1.3.0', changelog: '新增微服务架构模板', releasedAt: '2026-04-12', size: 2048 },
    ], screenshots: [], rating: 4.5, ratingCount: 189, downloadCount: 11600, installedCount: 7200,
    installStatus: 'none', isFavorite: false, license: 'MIT',
    createdAt: '2026-01-08', updatedAt: '2026-04-12', size: 2048,
  },
  {
    id: 'ag4', type: 'agent', name: '创意设计师', description: 'AI 创意设计智能体，支持品牌视觉设计、UI/UX 原型、营销素材生成，可理解设计需求并输出多套方案。',
    summary: 'AI 驱动的创意设计助手', icon: 'Lightbulb', author: MOCK_AUTHORS[2], category: 'creative',
    tags: [COMMON_TAGS[1], COMMON_TAGS[3], COMMON_TAGS[5]], version: '1.1.0', versions: [
      { version: '1.1.0', changelog: '新增品牌配色方案', releasedAt: '2026-04-08', size: 1792 },
    ], screenshots: [], rating: 4.3, ratingCount: 134, downloadCount: 8400, installedCount: 5100,
    installStatus: 'none', isFavorite: true, license: 'Apache-2.0',
    createdAt: '2026-02-20', updatedAt: '2026-04-08', size: 1792,
  },
  {
    id: 'ag5', type: 'agent', name: '教育导师', description: '个性化教育智能体，支持自适应学习路径规划、知识点讲解、练习出题和学习进度追踪，覆盖 K12 和高等教育。',
    summary: '个性化自适应学习导师', icon: 'GraduationCap', author: MOCK_AUTHORS[4], category: 'education',
    tags: [COMMON_TAGS[1], COMMON_TAGS[2]], version: '1.0.0', versions: [
      { version: '1.0.0', changelog: '正式版发布', releasedAt: '2026-04-05', size: 1536 },
    ], screenshots: [], rating: 4.4, ratingCount: 98, downloadCount: 6200, installedCount: 3800,
    installStatus: 'none', isFavorite: false, license: 'MIT',
    createdAt: '2026-03-01', updatedAt: '2026-04-05', size: 1536,
  },
  {
    id: 'ag6', type: 'agent', name: '市场研究员', description: '智能市场研究智能体，自动收集行业数据、竞品分析和市场趋势，生成结构化研究报告和策略建议。',
    summary: '自动化市场研究与分析', icon: 'TrendingUp', author: MOCK_AUTHORS[3], category: 'analysis',
    tags: [COMMON_TAGS[0], COMMON_TAGS[3]], version: '0.9.0', versions: [
      { version: '0.9.0', changelog: 'Beta 版本', releasedAt: '2026-04-01', size: 1280 },
    ], screenshots: [], rating: 4.0, ratingCount: 56, downloadCount: 3800, installedCount: 2100,
    installStatus: 'none', isFavorite: false, featured: true, license: 'MIT',
    createdAt: '2026-03-15', updatedAt: '2026-04-01', size: 1280,
  },
  {
    id: 'ag7', type: 'agent', name: '运维管家', description: '智能运维智能体，支持服务器监控、日志分析、故障诊断和自动修复，提供 7x24 小时稳定运行保障。',
    summary: '7x24 智能运维保障', icon: 'Shield', author: MOCK_AUTHORS[0], category: 'development',
    tags: [COMMON_TAGS[0], COMMON_TAGS[7], COMMON_TAGS[2]], version: '1.2.0', versions: [
      { version: '1.2.0', changelog: '新增自动修复策略', releasedAt: '2026-04-10', size: 2048 },
    ], screenshots: [], rating: 4.2, ratingCount: 87, downloadCount: 5600, installedCount: 3400,
    installStatus: 'installed', isFavorite: false, license: 'MIT',
    createdAt: '2026-01-25', updatedAt: '2026-04-10', size: 2048,
  },
  {
    id: 'ag8', type: 'agent', name: '法律顾问', description: 'AI 法律咨询智能体，支持合同审查、法律条文检索、风险评估和合规建议，覆盖常见法律领域。',
    summary: 'AI 法律咨询与合规助手', icon: 'Scale', author: MOCK_AUTHORS[1], category: 'assistant',
    tags: [COMMON_TAGS[1], COMMON_TAGS[3], COMMON_TAGS[6]], version: '0.8.0', versions: [
      { version: '0.8.0', changelog: 'Beta 版本', releasedAt: '2026-04-03', size: 1536 },
    ], screenshots: [], rating: 3.9, ratingCount: 42, downloadCount: 2800, installedCount: 1500,
    installStatus: 'none', isFavorite: false, license: 'Apache-2.0',
    createdAt: '2026-03-20', updatedAt: '2026-04-03', size: 1536,
  },
]

export const MOCK_REVIEWS: Record<string, Array<{
  id: string; itemId: string; userId: string; userName: string; userAvatar?: string;
  rating: number; content: string; createdAt: string;
  replies?: Array<{ id: string; userId: string; userName: string; content: string; createdAt: string }>;
}>> = {
  p1: [
    { id: 'r1', itemId: 'p1', userId: 'u1', userName: '星辰用户', rating: 5, content: 'DeepSeek 接入非常流畅，推理速度很快，R1 模型的推理能力令人印象深刻。', createdAt: '2026-04-16', replies: [
      { id: 'rp1', userId: 'a1', userName: 'LuminousCX', content: '感谢支持！后续会持续优化性能。', createdAt: '2026-04-17' }
    ]},
    { id: 'r2', itemId: 'p1', userId: 'u2', userName: '技术爱好者', rating: 4, content: '整体不错，但流式输出偶尔会卡顿，希望能进一步优化。', createdAt: '2026-04-10' },
    { id: 'r3', itemId: 'p1', userId: 'u3', userName: 'AI研究员', rating: 5, content: 'R1 模型接入太方便了，省去了很多配置工作。', createdAt: '2026-04-05' },
  ],
  p4: [
    { id: 'r4', itemId: 'p4', userId: 'u4', userName: '效率达人', rating: 5, content: '搜索结果非常精准，摘要功能特别实用！', createdAt: '2026-04-19' },
    { id: 'r5', itemId: 'p4', userId: 'u5', userName: '日常用户', rating: 4, content: '很好用，就是偶尔搜索速度有点慢。', createdAt: '2026-04-15' },
  ],
  s1: [
    { id: 'r6', itemId: 's1', userId: 'u6', userName: '翻译工作者', rating: 5, content: '翻译质量很高，专业术语处理得很好，已经替代了我之前的翻译工具。', createdAt: '2026-04-17' },
    { id: 'r7', itemId: 's1', userId: 'u7', userName: '语言学习者', rating: 5, content: '方言支持太棒了！粤语翻译非常地道。', createdAt: '2026-04-16' },
  ],
  s2: [
    { id: 'r8', itemId: 's2', userId: 'u8', userName: '全栈开发者', rating: 5, content: '代码生成质量很高，Rust 支持终于来了！', createdAt: '2026-04-15' },
    { id: 'r9', itemId: 's2', userId: 'u9', userName: '初级程序员', rating: 4, content: '调试功能很有帮助，但有时候建议不够精确。', createdAt: '2026-04-12' },
  ],
}

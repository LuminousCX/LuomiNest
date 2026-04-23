import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { MarketItem, MarketReview, MarketCategory, MarketFilter, SortOption, MarketItemType } from '../types/marketplace'

const MOCK_PLUGIN_CATEGORIES: MarketCategory[] = [
  { id: 'all-plugin', name: '全部', icon: 'LayoutGrid', type: 'plugin', count: 42 },
  { id: 'productivity', name: '效率工具', icon: 'Zap', type: 'plugin', count: 12 },
  { id: 'communication', name: '通讯集成', icon: 'MessageSquare', type: 'plugin', count: 8 },
  { id: 'automation', name: '自动化', icon: 'Workflow', type: 'plugin', count: 7 },
  { id: 'data', name: '数据分析', icon: 'BarChart3', type: 'plugin', count: 6 },
  { id: 'media', name: '多媒体', icon: 'Image', type: 'plugin', count: 5 },
  { id: 'dev', name: '开发工具', icon: 'Code2', type: 'plugin', count: 4 }
]

const MOCK_SKILL_CATEGORIES: MarketCategory[] = [
  { id: 'all-skill', name: '全部', icon: 'LayoutGrid', type: 'skill', count: 36 },
  { id: 'writing', name: '写作创作', icon: 'PenTool', type: 'skill', count: 10 },
  { id: 'translation', name: '翻译语言', icon: 'Languages', type: 'skill', count: 6 },
  { id: 'coding', name: '编程辅助', icon: 'Terminal', type: 'skill', count: 8 },
  { id: 'reasoning', name: '推理分析', icon: 'Brain', type: 'skill', count: 5 },
  { id: 'creative', name: '创意设计', icon: 'Palette', type: 'skill', count: 4 },
  { id: 'education', name: '教育学习', icon: 'GraduationCap', type: 'skill', count: 3 }
]

function generateMockPlugins(): MarketItem[] {
  const plugins: MarketItem[] = [
    {
      id: 'plugin-1', type: 'plugin', name: 'WeChat Bridge', description: '将LuomiNest连接到微信平台，实现消息自动收发',
      longDescription: 'WeChat Bridge 是一个强大的通讯集成插件，它可以将你的 LuomiNest AI 伴侣无缝连接到微信平台。\n\n## 主要功能\n- 自动接收和回复微信消息\n- 支持文本、图片、文件等多种消息类型\n- 可配置自动回复规则和触发条件\n- 支持群聊消息监控和智能回复\n- 完整的消息历史记录和搜索',
      icon: 'MessageSquare', author: 'LuminousCX', version: '2.1.0', category: 'communication',
      tags: ['微信', '通讯', '自动化'], rating: 4.7, reviewCount: 128, downloadCount: 5420,
      size: '12.4 MB', updatedAt: '2026-04-15', screenshots: [],
      isInstalled: false, isFavorite: false, installStatus: 'idle', downloadProgress: 0,
      changelog: '## v2.1.0\n- 新增群聊智能回复\n- 优化消息队列性能\n- 修复文件传输问题',
      permissions: ['network', 'storage', 'notifications'], homepage: 'https://github.com/luominest/wechat-bridge'
    },
    {
      id: 'plugin-2', type: 'plugin', name: 'Task Scheduler', description: '智能任务调度引擎，支持定时执行和条件触发',
      longDescription: 'Task Scheduler 为 LuomiNest 提供强大的任务调度能力。\n\n## 主要功能\n- Cron 表达式定时任务\n- 事件驱动条件触发\n- 任务链式编排\n- 失败重试与告警\n- 可视化任务监控面板',
      icon: 'Clock', author: 'LuminousCX', version: '1.5.2', category: 'automation',
      tags: ['任务', '调度', '自动化'], rating: 4.5, reviewCount: 86, downloadCount: 3210,
      size: '8.7 MB', updatedAt: '2026-04-10', screenshots: [],
      isInstalled: true, isFavorite: true, installStatus: 'installed', downloadProgress: 100,
      changelog: '## v1.5.2\n- 新增任务链式编排\n- 优化调度引擎性能',
      permissions: ['storage', 'background'], homepage: ''
    },
    {
      id: 'plugin-3', type: 'plugin', name: 'DataLens', description: '数据可视化分析插件，支持多维度数据探索',
      longDescription: 'DataLens 让你的 AI 伴侣具备数据分析和可视化能力。\n\n## 主要功能\n- 自动生成数据图表\n- 多维度交叉分析\n- 自然语言查询数据\n- 导出 PDF/Excel 报告\n- 实时数据监控大屏',
      icon: 'BarChart3', author: 'DataViz Lab', version: '3.0.1', category: 'data',
      tags: ['数据', '可视化', '分析'], rating: 4.8, reviewCount: 203, downloadCount: 8760,
      size: '24.2 MB', updatedAt: '2026-04-18', screenshots: [],
      isInstalled: false, isFavorite: false, installStatus: 'idle', downloadProgress: 0,
      changelog: '## v3.0.1\n- 全新图表引擎\n- 支持自然语言查询',
      permissions: ['network', 'storage'], homepage: ''
    },
    {
      id: 'plugin-4', type: 'plugin', name: 'QuickNote', description: '快速笔记与知识管理，支持Markdown和双向链接',
      longDescription: 'QuickNote 是一个轻量级的知识管理插件。\n\n## 主要功能\n- Markdown 实时预览\n- 双向链接知识图谱\n- 标签分类与全文搜索\n- AI 辅助摘要生成\n- 多端同步',
      icon: 'FileText', author: 'NoteCraft', version: '1.2.0', category: 'productivity',
      tags: ['笔记', '知识管理', 'Markdown'], rating: 4.3, reviewCount: 67, downloadCount: 2150,
      size: '6.1 MB', updatedAt: '2026-04-08', screenshots: [],
      isInstalled: false, isFavorite: true, installStatus: 'idle', downloadProgress: 0,
      changelog: '## v1.2.0\n- 新增双向链接\n- AI 摘要生成',
      permissions: ['storage'], homepage: ''
    },
    {
      id: 'plugin-5', type: 'plugin', name: 'MediaForge', description: '多媒体内容处理引擎，支持图片/音频/视频转换',
      longDescription: 'MediaForge 为 LuomiNest 提供强大的多媒体处理能力。\n\n## 主要功能\n- 图片格式转换与压缩\n- 音频转写与合成\n- 视频截取与拼接\n- AI 图片生成集成\n- 批量处理与队列管理',
      icon: 'Image', author: 'MediaLab', version: '2.0.0', category: 'media',
      tags: ['多媒体', '图片', '音频'], rating: 4.1, reviewCount: 45, downloadCount: 1890,
      size: '32.5 MB', updatedAt: '2026-03-28', screenshots: [],
      isInstalled: false, isFavorite: false, installStatus: 'idle', downloadProgress: 0,
      changelog: '## v2.0.0\n- 全新处理引擎\n- 支持 AI 图片生成',
      permissions: ['network', 'storage', 'gpu'], homepage: ''
    },
    {
      id: 'plugin-6', type: 'plugin', name: 'DevKit Pro', description: '开发者工具集，集成代码执行、API调试和文档生成',
      longDescription: 'DevKit Pro 是面向开发者的全能工具集。\n\n## 主要功能\n- 沙箱代码执行环境\n- API 请求调试器\n- 自动文档生成\n- 代码审查与优化建议\n- Git 操作集成',
      icon: 'Code2', author: 'DevTools Inc', version: '1.8.3', category: 'dev',
      tags: ['开发', '代码', 'API'], rating: 4.6, reviewCount: 156, downloadCount: 6340,
      size: '18.9 MB', updatedAt: '2026-04-20', screenshots: [],
      isInstalled: true, isFavorite: false, installStatus: 'installed', downloadProgress: 100,
      changelog: '## v1.8.3\n- 新增 Git 操作集成\n- 优化沙箱性能',
      permissions: ['network', 'storage', 'compute'], homepage: ''
    },
    {
      id: 'plugin-7', type: 'plugin', name: 'Focus Mode', description: '专注模式与番茄钟，帮助你保持高效工作状态',
      longDescription: 'Focus Mode 提供科学的专注工作管理。\n\n## 主要功能\n- 番茄钟计时器\n- 专注统计与报告\n- 干扰屏蔽规则\n- AI 专注建议\n- 团队协作模式',
      icon: 'Target', author: 'ProductivityPlus', version: '1.0.5', category: 'productivity',
      tags: ['专注', '效率', '番茄钟'], rating: 4.2, reviewCount: 34, downloadCount: 980,
      size: '3.2 MB', updatedAt: '2026-04-05', screenshots: [],
      isInstalled: false, isFavorite: false, installStatus: 'idle', downloadProgress: 0,
      changelog: '## v1.0.5\n- 新增团队协作模式',
      permissions: ['notifications'], homepage: ''
    },
    {
      id: 'plugin-8', type: 'plugin', name: 'Discord Relay', description: 'Discord消息中继，让AI伴侣活跃在你的Discord服务器',
      longDescription: 'Discord Relay 连接 LuomiNest 与 Discord。\n\n## 主要功能\n- 多服务器消息中继\n- 斜杠命令交互\n- Embed 富文本回复\n- 频道权限管理\n- 事件监听与响应',
      icon: 'Hash', author: 'LuminousCX', version: '1.3.1', category: 'communication',
      tags: ['Discord', '通讯', '机器人'], rating: 4.4, reviewCount: 72, downloadCount: 2870,
      size: '9.8 MB', updatedAt: '2026-04-12', screenshots: [],
      isInstalled: false, isFavorite: false, installStatus: 'idle', downloadProgress: 0,
      changelog: '## v1.3.1\n- 新增斜杠命令\n- 优化消息队列',
      permissions: ['network', 'storage'], homepage: ''
    }
  ]
  return plugins
}

function generateMockSkills(): MarketItem[] {
  const skills: MarketItem[] = [
    {
      id: 'skill-1', type: 'skill', name: 'Creative Writer', description: '创意写作技能，支持小说、诗歌、剧本等多种文体',
      longDescription: 'Creative Writer 赋予 AI 伴侣出色的创意写作能力。\n\n## 主要功能\n- 多文体创作（小说、诗歌、散文、剧本）\n- 风格迁移与模仿\n- 情节生成与续写\n- 角色对话设计\n- 写作建议与润色',
      icon: 'PenTool', author: 'LuminousCX', version: '3.2.0', category: 'writing',
      tags: ['写作', '创意', '文学'], rating: 4.9, reviewCount: 312, downloadCount: 12450,
      size: '2.1 MB', updatedAt: '2026-04-19', screenshots: [],
      isInstalled: true, isFavorite: true, installStatus: 'installed', downloadProgress: 100,
      changelog: '## v3.2.0\n- 新增剧本创作模式\n- 优化风格迁移算法',
      permissions: [], homepage: ''
    },
    {
      id: 'skill-2', type: 'skill', name: 'Polyglot', description: '多语言翻译与本地化技能，支持50+语种互译',
      longDescription: 'Polyglot 是一个强大的多语言翻译技能。\n\n## 主要功能\n- 50+ 语种互译\n- 语境感知翻译\n- 专业术语库\n- 本地化适配\n- 实时对话翻译',
      icon: 'Languages', author: 'LangTech', version: '2.4.1', category: 'translation',
      tags: ['翻译', '多语言', '本地化'], rating: 4.7, reviewCount: 189, downloadCount: 8920,
      size: '4.5 MB', updatedAt: '2026-04-16', screenshots: [],
      isInstalled: false, isFavorite: false, installStatus: 'idle', downloadProgress: 0,
      changelog: '## v2.4.1\n- 新增5种小语种\n- 优化术语库匹配',
      permissions: [], homepage: ''
    },
    {
      id: 'skill-3', type: 'skill', name: 'CodePilot', description: '智能编程助手，支持代码生成、调试和重构',
      longDescription: 'CodePilot 让 AI 成为你的编程搭档。\n\n## 主要功能\n- 自然语言生成代码\n- Bug 检测与修复建议\n- 代码重构与优化\n- 单元测试生成\n- 多语言支持（Python/JS/Go/Rust等）',
      icon: 'Terminal', author: 'LuminousCX', version: '4.0.0', category: 'coding',
      tags: ['编程', '代码', '调试'], rating: 4.8, reviewCount: 267, downloadCount: 10230,
      size: '5.8 MB', updatedAt: '2026-04-21', screenshots: [],
      isInstalled: true, isFavorite: false, installStatus: 'installed', downloadProgress: 100,
      changelog: '## v4.0.0\n- 全新代码生成引擎\n- 支持 Rust 语言',
      permissions: [], homepage: ''
    },
    {
      id: 'skill-4', type: 'skill', name: 'DeepThink', description: '深度推理与分析技能，擅长复杂问题拆解和逻辑推演',
      longDescription: 'DeepThink 提供强大的推理分析能力。\n\n## 主要功能\n- 复杂问题拆解\n- 多步逻辑推演\n- 假设验证与反驳\n- 决策树分析\n- 概率评估',
      icon: 'Brain', author: 'ReasonLab', version: '2.1.0', category: 'reasoning',
      tags: ['推理', '分析', '逻辑'], rating: 4.6, reviewCount: 98, downloadCount: 4560,
      size: '3.2 MB', updatedAt: '2026-04-14', screenshots: [],
      isInstalled: false, isFavorite: true, installStatus: 'idle', downloadProgress: 0,
      changelog: '## v2.1.0\n- 新增概率评估模块',
      permissions: [], homepage: ''
    },
    {
      id: 'skill-5', type: 'skill', name: 'ArtDirector', description: '创意设计技能，辅助UI设计、配色方案和视觉创意',
      longDescription: 'ArtDirector 让 AI 具备设计思维。\n\n## 主要功能\n- UI/UX 设计建议\n- 配色方案生成\n- 布局推荐\n- 设计规范检查\n- 品牌视觉指导',
      icon: 'Palette', author: 'DesignAI', version: '1.7.2', category: 'creative',
      tags: ['设计', 'UI', '配色'], rating: 4.4, reviewCount: 76, downloadCount: 3210,
      size: '2.8 MB', updatedAt: '2026-04-09', screenshots: [],
      isInstalled: false, isFavorite: false, installStatus: 'idle', downloadProgress: 0,
      changelog: '## v1.7.2\n- 新增品牌视觉指导',
      permissions: [], homepage: ''
    },
    {
      id: 'skill-6', type: 'skill', name: 'Scholar', description: '学术研究助手，支持论文检索、摘要生成和引用管理',
      longDescription: 'Scholar 是你的 AI 学术研究伙伴。\n\n## 主要功能\n- 学术论文检索\n- 自动摘要生成\n- 引用格式管理\n- 研究趋势分析\n- 文献综述辅助',
      icon: 'GraduationCap', author: 'EduTech', version: '2.0.3', category: 'education',
      tags: ['学术', '研究', '论文'], rating: 4.5, reviewCount: 112, downloadCount: 5670,
      size: '3.6 MB', updatedAt: '2026-04-17', screenshots: [],
      isInstalled: false, isFavorite: false, installStatus: 'idle', downloadProgress: 0,
      changelog: '## v2.0.3\n- 新增文献综述辅助',
      permissions: [], homepage: ''
    },
    {
      id: 'skill-7', type: 'skill', name: 'StoryWeaver', description: '互动叙事引擎，创建沉浸式分支剧情体验',
      longDescription: 'StoryWeaver 让 AI 成为互动叙事大师。\n\n## 主要功能\n- 分支剧情生成\n- 角色关系网络\n- 世界观构建\n- 互动选项设计\n- 叙事节奏控制',
      icon: 'BookOpen', author: 'NarrativeAI', version: '1.4.0', category: 'writing',
      tags: ['叙事', '互动', '剧情'], rating: 4.3, reviewCount: 58, downloadCount: 2340,
      size: '1.9 MB', updatedAt: '2026-04-06', screenshots: [],
      isInstalled: false, isFavorite: false, installStatus: 'idle', downloadProgress: 0,
      changelog: '## v1.4.0\n- 新增世界观构建工具',
      permissions: [], homepage: ''
    },
    {
      id: 'skill-8', type: 'skill', name: 'CodeReviewer', description: '代码审查专家，自动检测代码异味和安全漏洞',
      longDescription: 'CodeReviewer 提供专业的代码审查能力。\n\n## 主要功能\n- 代码异味检测\n- 安全漏洞扫描\n- 性能瓶颈分析\n- 最佳实践建议\n- 自动修复建议',
      icon: 'ShieldCheck', author: 'SecDevOps', version: '2.2.1', category: 'coding',
      tags: ['代码审查', '安全', '质量'], rating: 4.6, reviewCount: 134, downloadCount: 5890,
      size: '3.1 MB', updatedAt: '2026-04-13', screenshots: [],
      isInstalled: false, isFavorite: false, installStatus: 'idle', downloadProgress: 0,
      changelog: '## v2.2.1\n- 新增安全漏洞扫描',
      permissions: [], homepage: ''
    }
  ]
  return skills
}

function generateMockReviews(itemId: string): MarketReview[] {
  const reviews: MarketReview[] = [
    { id: `${itemId}-r1`, itemId, userName: '星辰用户', userAvatar: '', rating: 5, content: '非常实用的工具，大大提升了我的工作效率！界面设计也很美观。', createdAt: '2026-04-18', likes: 24 },
    { id: `${itemId}-r2`, itemId, userName: '技术探索者', userAvatar: '', rating: 4, content: '功能很强大，不过有些高级功能需要一定的学习成本。总体来说值得推荐。', createdAt: '2026-04-15', likes: 12 },
    { id: `${itemId}-r3`, itemId, userName: '效率达人', userAvatar: '', rating: 5, content: '安装简单，使用方便，和 LuomiNest 的集成非常流畅。期待更多更新！', createdAt: '2026-04-12', likes: 8 },
    { id: `${itemId}-r4`, itemId, userName: '新手上路', userAvatar: '', rating: 3, content: '基础功能不错，但偶尔会出现一些小 bug，希望后续版本能修复。', createdAt: '2026-04-08', likes: 5 },
    { id: `${itemId}-r5`, itemId, userName: '深度用户', userAvatar: '', rating: 4, content: '日常使用完全没问题，API 响应速度也很快。建议增加更多自定义选项。', createdAt: '2026-04-03', likes: 15 }
  ]
  return reviews
}

export const useMarketplaceStore = defineStore('marketplace', () => {
  const activeTab = ref<MarketItemType>('plugin')
  const filter = ref<MarketFilter>({
    type: 'plugin',
    category: 'all-plugin',
    search: '',
    sort: 'popular',
    tags: [],
    onlyInstalled: false,
    onlyFavorites: false
  })

  const plugins = ref<MarketItem[]>(generateMockPlugins())
  const skills = ref<MarketItem[]>(generateMockSkills())
  const reviews = ref<MarketReview[]>([])
  const loading = ref(false)
  const installingItemId = ref<string | null>(null)

  const categories = computed(() => {
    return activeTab.value === 'plugin' ? MOCK_PLUGIN_CATEGORIES : MOCK_SKILL_CATEGORIES
  })

  const currentItems = computed(() => {
    const items = activeTab.value === 'plugin' ? plugins.value : skills.value
    let filtered = [...items]

    if (filter.value.category && filter.value.category !== `all-${activeTab.value}`) {
      filtered = filtered.filter(item => item.category === filter.value.category)
    }

    if (filter.value.search) {
      const q = filter.value.search.toLowerCase()
      filtered = filtered.filter(item =>
        item.name.toLowerCase().includes(q) ||
        item.description.toLowerCase().includes(q) ||
        item.tags.some(t => t.toLowerCase().includes(q)) ||
        item.author.toLowerCase().includes(q)
      )
    }

    if (filter.value.tags.length > 0) {
      filtered = filtered.filter(item =>
        filter.value.tags.some(tag => item.tags.includes(tag))
      )
    }

    if (filter.value.onlyInstalled) {
      filtered = filtered.filter(item => item.isInstalled)
    }

    if (filter.value.onlyFavorites) {
      filtered = filtered.filter(item => item.isFavorite)
    }

    switch (filter.value.sort) {
      case 'newest':
        filtered.sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
        break
      case 'rating':
        filtered.sort((a, b) => b.rating - a.rating)
        break
      case 'downloads':
        filtered.sort((a, b) => b.downloadCount - a.downloadCount)
        break
      case 'popular':
      default:
        filtered.sort((a, b) => (b.downloadCount + b.reviewCount * 10) - (a.downloadCount + a.reviewCount * 10))
        break
    }

    return filtered
  })

  const featuredItems = computed(() => {
    const items = activeTab.value === 'plugin' ? plugins.value : skills.value
    return items.filter(i => i.rating >= 4.5).slice(0, 4)
  })

  const allTags = computed(() => {
    const items = activeTab.value === 'plugin' ? plugins.value : skills.value
    const tagSet = new Set<string>()
    items.forEach(item => item.tags.forEach(tag => tagSet.add(tag)))
    return Array.from(tagSet)
  })

  const favoriteItems = computed(() => {
    return [...plugins.value, ...skills.value].filter(item => item.isFavorite)
  })

  const installedItems = computed(() => {
    return [...plugins.value, ...skills.value].filter(item => item.isInstalled)
  })

  const stats = computed(() => ({
    totalPlugins: plugins.value.length,
    totalSkills: skills.value.length,
    installedCount: installedItems.value.length,
    favoriteCount: favoriteItems.value.length
  }))

  function setActiveTab(tab: MarketItemType) {
    activeTab.value = tab
    filter.value.type = tab
    filter.value.category = `all-${tab}`
    filter.value.search = ''
    filter.value.tags = []
    filter.value.onlyInstalled = false
    filter.value.onlyFavorites = false
  }

  function setCategory(categoryId: string) {
    filter.value.category = categoryId
  }

  function setSearch(query: string) {
    filter.value.search = query
  }

  function setSort(sort: SortOption) {
    filter.value.sort = sort
  }

  function toggleTag(tag: string) {
    const idx = filter.value.tags.indexOf(tag)
    if (idx > -1) {
      filter.value.tags.splice(idx, 1)
    } else {
      filter.value.tags.push(tag)
    }
  }

  function toggleOnlyInstalled() {
    filter.value.onlyInstalled = !filter.value.onlyInstalled
    if (filter.value.onlyInstalled) filter.value.onlyFavorites = false
  }

  function toggleOnlyFavorites() {
    filter.value.onlyFavorites = !filter.value.onlyFavorites
    if (filter.value.onlyFavorites) filter.value.onlyInstalled = false
  }

  function toggleFavorite(itemId: string) {
    const item = findItem(itemId)
    if (item) {
      item.isFavorite = !item.isFavorite
    }
  }

  function findItem(itemId: string): MarketItem | undefined {
    return plugins.value.find(p => p.id === itemId) || skills.value.find(s => s.id === itemId)
  }

  async function installItem(itemId: string) {
    const item = findItem(itemId)
    if (!item || item.installStatus === 'downloading' || item.installStatus === 'installing') return

    installingItemId.value = itemId
    item.installStatus = 'downloading'
    item.downloadProgress = 0

    for (let i = 0; i <= 100; i += 5) {
      await new Promise(resolve => setTimeout(resolve, 50))
      item.downloadProgress = i
    }

    item.installStatus = 'installing'
    await new Promise(resolve => setTimeout(resolve, 600))

    item.installStatus = 'installed'
    item.isInstalled = true
    item.downloadCount += 1
    installingItemId.value = null
  }

  async function uninstallItem(itemId: string) {
    const item = findItem(itemId)
    if (!item || !item.isInstalled) return

    item.isInstalled = false
    item.installStatus = 'idle'
    item.downloadProgress = 0
  }

  async function fetchReviews(itemId: string) {
    loading.value = true
    try {
      await new Promise(resolve => setTimeout(resolve, 300))
      reviews.value = generateMockReviews(itemId)
    } finally {
      loading.value = false
    }
  }

  async function addReview(itemId: string, rating: number, content: string) {
    const newReview: MarketReview = {
      id: `${itemId}-r-${Date.now()}`,
      itemId,
      userName: '当前用户',
      userAvatar: '',
      rating,
      content,
      createdAt: new Date().toISOString().split('T')[0],
      likes: 0
    }
    reviews.value.unshift(newReview)

    const item = findItem(itemId)
    if (item) {
      const totalRating = item.rating * item.reviewCount + rating
      item.reviewCount += 1
      item.rating = Math.round((totalRating / item.reviewCount) * 10) / 10
    }
  }

  function likeReview(reviewId: string) {
    const review = reviews.value.find(r => r.id === reviewId)
    if (review) {
      review.likes += 1
    }
  }

  function resetFilters() {
    filter.value = {
      type: activeTab.value,
      category: `all-${activeTab.value}`,
      search: '',
      sort: 'popular',
      tags: [],
      onlyInstalled: false,
      onlyFavorites: false
    }
  }

  return {
    activeTab,
    filter,
    plugins,
    skills,
    reviews,
    loading,
    installingItemId,
    categories,
    currentItems,
    featuredItems,
    allTags,
    favoriteItems,
    installedItems,
    stats,
    setActiveTab,
    setCategory,
    setSearch,
    setSort,
    toggleTag,
    toggleOnlyInstalled,
    toggleOnlyFavorites,
    toggleFavorite,
    findItem,
    installItem,
    uninstallItem,
    fetchReviews,
    addReview,
    likeReview,
    resetFilters
  }
})

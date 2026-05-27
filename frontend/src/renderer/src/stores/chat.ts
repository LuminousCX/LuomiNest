import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import type { ChatMessage, ApiMessage, Conversation, ConversationListItem, ConversationSearchResult, ChatStreamChunk } from '../types'
import { useApi } from '../composables/useApi'
import { useAgentStore } from './agent'

const SEARCH_POSITIVE_KEYWORDS: Record<string, number> = {
  '什么时候': 4, '是哪天': 4, '是几号': 4, '哪一天': 4, '几号': 4,
  '在哪里': 3, '在哪': 3, '在哪举办': 3, '在哪个': 3,
  '多少': 3, '多少钱': 3, '价格': 3,
  '有没有': 1, '是否': 1, '会不会': 1, '能不能': 1,
  '怎么样': 2, '如何': 2, '好不好': 2,
  '距离': 4, '还有几': 4, '还剩': 4, '还差': 4,
  '搜索': 5, '查找': 5, '搜一下': 5, '帮我搜': 5, '帮我查': 5, '查一下': 5, '查查': 5, '搜一搜': 5,
  '今年': 2, '明年': 2, '去年': 2, '本周': 2, '上周': 2, '最近': 2, '最新': 2, '当前': 2, '目前': 2, '现在': 2, '今日': 2,
  '股价': 5, '股票': 5, '行情': 5, '涨幅': 5, '跌幅': 5, '基金': 5, '比特币': 5,
  '新闻': 4, '热点': 4, '头条': 4, '事件': 4, '事故': 4,
  '考试': 4, '报名': 4, '准考证': 4, '成绩': 4, '录取': 4, '分数线': 4, '软考': 4, '考研': 4, '高考': 4, '中考': 4, '国考': 4,
  '比赛': 4, '赛事': 4, '比分': 4, '积分': 4, '排名': 4, '赛程': 4, '世界杯': 4, '奥运会': 4, '欧冠': 4, 'NBA': 4,
  '上映': 3, '票房': 3, '评分': 3, '豆瓣': 3, 'IMDb': 3, '排行': 3, '榜单': 3, '推荐电影': 3, '好看': 3, '有什么好看': 3,
  '航班': 4, '高铁': 4, '火车': 4, '机票': 4, '车次': 4, '时刻表': 4, '晚点': 4,
  '政策': 3, '法规': 3, '规定': 3, '新规': 3, '出台': 3, '实施': 3,
  '发布': 3, '推出': 3, '上市': 3, '开售': 3, '预售': 3, '发售': 3, '新品': 3,
  '旅游': 3, '旅行': 3, '攻略': 3, '景点': 3, '酒店': 3, '民宿': 3, '签证': 3,
  'iPhone': 2, 'iPad': 2, 'MacBook': 2, '华为': 2, '小米': 2, '三星': 2, '特斯拉': 2, '比亚迪': 2, '蔚来': 2,
  '推荐': 2, '值不值得': 2, '值得': 2,
}

const SEARCH_KNOWLEDGE_BOUNDARY: Record<string, number> = {
  '2025年': 3, '2026年': 3, '2027年': 3, '2028年': 3, '2029年': 3,
}

const SEARCH_KNOWLEDGE_BOUNDARY_COMBOS: Array<{ prefix: RegExp; suffixes: string[]; weight: number; label: string }> = [
  { prefix: /今年/, suffixes: ['政策', '规定', '新规', '考试', '报名', '分数线', '录取', '赛事', '举办'], weight: 4, label: '今年+时效词' },
  { prefix: /最新/, suffixes: ['政策', '规定', '版本', '消息', '动态', '公告', '通知', '发布'], weight: 4, label: '最新+时效词' },
  { prefix: /当前/, suffixes: ['状态', '情况', '进度', '排名', '价格', '行情', '政策'], weight: 4, label: '当前+状态词' },
  { prefix: /目前/, suffixes: ['支持', '可用', '开放', '上线', '发布', '运行'], weight: 3, label: '目前+状态词' },
  { prefix: /什么时候/, suffixes: ['出', '发', '开', '上', '更新', '修复', '支持', '上线', '开放'], weight: 4, label: '何时更新' },
  { prefix: /有没有/, suffixes: ['出', '发', '开', '上', '更新', '修复', '支持'], weight: 3, label: '有无更新' },
]

const SEARCH_ENTITY_KEYWORDS: Record<string, number> = {
  'GPT': 3, 'Claude': 3, 'Gemini': 3, 'Llama': 3, 'DeepSeek': 3, 'Kimi': 3, 'Sora': 3, 'Copilot': 3,
  'ChatGPT': 2, 'OpenAI': 2, 'Anthropic': 2,
  '通义': 3, '文心': 3, '千问': 3, '智谱': 3, '豆包': 3,
  'Windows': 3, 'macOS': 3, 'iOS': 3, 'Android': 3, 'HarmonyOS': 3,
  '世博会': 4, '奥运会': 4, '世界杯': 4, '亚运会': 4, '冬奥会': 4, '欧洲杯': 4, '亚洲杯': 4, '全运会': 4,
  '双十一': 3, '618': 3, '黑五': 3,
  '国考': 3, '省考': 3, '事业编': 3, '公务员': 3, '教资': 3, '法考': 3, '注会': 3, '一建': 3, '二建': 3,
  '诺贝尔': 3, '奥斯卡': 3, '格莱美': 3,
  '两会': 3, '人大': 3, '政协': 3,
}

const SEARCH_COMPARISON_KEYWORDS: Record<string, number> = {
  '哪个好': 4, '怎么选': 4, '区别': 2, '对比': 2, '比较': 2, '差异': 2, '不同': 2, '优缺点': 2, '优劣': 2,
  '性价比': 3, '划算': 3, '值得买': 3, '买哪个': 3, '选哪个': 3,
  '排行': 3, '排名': 3, '榜单': 3, '口碑': 3, '评测': 3, '测评': 3,
}

const SEARCH_FACT_SPECIFIC_KEYWORDS: Record<string, number> = {
  '分数线': 4, '录取线': 4, '合格线': 4, '及格线': 4,
  '报名费': 3, '学费': 3, '票价': 3, '门票': 3, '收费': 3,
  '营业时间': 4, '开放时间': 4, '上班时间': 4,
  '官网': 3, '下载地址': 3, '下载链接': 3, '安装包': 3,
  '名额': 3, '招生人数': 3, '招聘人数': 3,
  '放假': 4, '放假安排': 4, '假期': 4, '调休': 4,
  '联系方式': 2, '客服': 2, '咨询电话': 2,
}

const SEARCH_REALTIME_KEYWORDS: Record<string, number> = {
  '汇率': 5, '换汇': 5, '外汇': 5,
  '油价': 5, '汽油价': 5, '金价': 5, '黄金价': 5,
  '房价': 4, '二手房': 4, '均价': 4,
  '限行': 4, '限号': 4, '尾号限行': 4,
  '停水': 4, '停电': 4, '停气': 4,
  '招聘': 3, '求职': 3, '岗位': 3, '薪资': 3, '待遇': 3,
  '疫苗': 3, '挂号': 3, '门诊': 3, '医保': 3,
  '出入境': 4, '入境政策': 4,
  '快递': 2, '物流': 2, '运费': 2,
}

const SEARCH_NEGATIVE_KEYWORDS: Record<string, number> = {
  '计算': 3, '算一下': 3, '帮我写': 3, '生成': 3, '创作': 3, '编一个': 3,
  '代码': 2, '编程': 2, 'python': 2, 'java': 2, 'javascript': 2, '函数': 2, '算法': 2, 'bug': 2,
  '翻译': 2, 'translate': 2,
  '你好': 3, '早上好': 3, '晚上好': 3, '晚安': 3, '谢谢': 3, '再见': 3,
}

const SEARCH_NEGATIVE_OVERRIDE: Array<{ pattern: RegExp; weight: number }> = [
  { pattern: /什么是.*?(GPT|Claude|Gemini|Llama|Sora|Copilot|DeepSeek|Kimi|豆包|通义|文心)/, weight: 4 },
  { pattern: /什么是.*?(202[5-9]|最新|新出|新规|新政)/, weight: 4 },
  { pattern: /(什么是|什么叫|介绍下|介绍一下).{0,5}?(GPT|Claude|Gemini|DeepSeek|Kimi|Sora|ChatGPT|OpenAI)/, weight: 4 },
]

const PURE_TIME_PATTERNS = /^(今天|现在|当前)(几号|几点|几时|星期几|周几|什么时间|什么日期)$/

const SEARCH_THRESHOLD = 4

function detectSearchIntent(message: string): boolean {
  const clean = message.replace(/[？?]/g, '').replace(/\s/g, '')
  if (!clean) return false

  if (PURE_TIME_PATTERNS.test(clean)) return false

  let score = 0

  for (const [kw, weight] of Object.entries(SEARCH_POSITIVE_KEYWORDS)) {
    if (clean.includes(kw)) score += weight
  }

  for (const [kw, weight] of Object.entries(SEARCH_KNOWLEDGE_BOUNDARY)) {
    if (clean.includes(kw)) score += weight
  }

  for (const combo of SEARCH_KNOWLEDGE_BOUNDARY_COMBOS) {
    if (combo.prefix.test(clean)) {
      for (const suffix of combo.suffixes) {
        if (clean.includes(suffix)) {
          score += combo.weight
          break
        }
      }
    }
  }

  for (const [kw, weight] of Object.entries(SEARCH_ENTITY_KEYWORDS)) {
    if (clean.includes(kw)) score += weight
  }

  for (const [kw, weight] of Object.entries(SEARCH_COMPARISON_KEYWORDS)) {
    if (clean.includes(kw)) score += weight
  }

  for (const [kw, weight] of Object.entries(SEARCH_FACT_SPECIFIC_KEYWORDS)) {
    if (clean.includes(kw)) score += weight
  }

  for (const [kw, weight] of Object.entries(SEARCH_REALTIME_KEYWORDS)) {
    if (clean.includes(kw)) score += weight
  }

  let negTotal = 0
  for (const [kw, weight] of Object.entries(SEARCH_NEGATIVE_KEYWORDS)) {
    if (clean.includes(kw)) negTotal += weight
  }

  if (negTotal > 0) {
    let overrideBonus = 0
    for (const rule of SEARCH_NEGATIVE_OVERRIDE) {
      if (rule.pattern.test(clean)) overrideBonus += rule.weight
    }
    negTotal = Math.max(0, negTotal - overrideBonus)
  }

  score -= negTotal

  return score >= SEARCH_THRESHOLD
}

const PERIODIC_EVENT_PATTERNS: Array<{ pattern: RegExp; type: string }> = [
  { pattern: /软考/, type: '考试' },
  { pattern: /考研/, type: '考试' },
  { pattern: /高考/, type: '考试' },
  { pattern: /中考/, type: '考试' },
  { pattern: /国考/, type: '考试' },
  { pattern: /省考/, type: '考试' },
  { pattern: /考公/, type: '考试' },
  { pattern: /事业编/, type: '考试' },
  { pattern: /教资|教师资格/, type: '考试' },
  { pattern: /法考/, type: '考试' },
  { pattern: /注会/, type: '考试' },
  { pattern: /一建|二建/, type: '考试' },
  { pattern: /公务员/, type: '考试' },
  { pattern: /选调/, type: '考试' },
  { pattern: /世界杯/, type: '赛事' },
  { pattern: /奥运会/, type: '赛事' },
  { pattern: /亚运会/, type: '赛事' },
  { pattern: /欧冠/, type: '赛事' },
  { pattern: /欧洲杯/, type: '赛事' },
  { pattern: /亚洲杯/, type: '赛事' },
  { pattern: /世博会/, type: '展会' },
  { pattern: /进博会/, type: '展会' },
  { pattern: /双十一|618/, type: '购物节' },
  { pattern: /春运/, type: '民生' },
  { pattern: /秋招|春招/, type: '招聘' },
  { pattern: /报名/, type: '报名' },
  { pattern: /录取/, type: '录取' },
  { pattern: /分数线/, type: '分数' },
]

function enrichQueryWithTimeContext(query: string): string {
  const hasYear = /20\d{2}年/.test(query)
  const hasHalf = /上半年|下半年/.test(query)
  if (hasYear && hasHalf) return query

  let matchedType: string | null = null
  for (const { pattern, type } of PERIODIC_EVENT_PATTERNS) {
    if (pattern.test(query)) {
      matchedType = type
      break
    }
  }
  if (!matchedType) return query

  // 清洗疑问词和冗余词，提取核心搜索词
  let coreQuery = query
  coreQuery = coreQuery.replace(/^(今天|现在|当前|目前|今年)/, '')
  coreQuery = coreQuery.replace(/什么时候|几号|几时|哪天|哪一天|是哪天|是几号/g, '')
  coreQuery = coreQuery.replace(/(还有几天|还剩几天|还有多久|还差几天)$/, '')
  coreQuery = coreQuery.replace(/多少|怎么样|好不好|有没有|是否/g, '')
  coreQuery = coreQuery.trim()
  if (!coreQuery) coreQuery = query

  const now = new Date()
  const year = now.getFullYear()
  const month = now.getMonth() + 1

  let enriched = coreQuery
  if (!hasYear) enriched = `${year}年${enriched}`

  if (!hasHalf && ['考试', '报名', '录取', '分数', '招聘'].includes(matchedType)) {
    // 高考/中考固定在6月举行，始终搜索上半年
    const firstHalfOnly = /高考|中考/.test(coreQuery)
    if (firstHalfOnly) enriched += '上半年'
    else if (month >= 5 && month <= 8) enriched += '下半年'
    else if (month >= 9) enriched += '下半年'
    else enriched += '上半年'
  }

  if (['考试', '报名', '录取', '分数'].includes(matchedType) && !enriched.includes('时间')) {
    enriched += '时间'
  }

  // 优化顺序：将"下半年/上半年"移到事件名后面、时间前面
  enriched = enriched.replace(/^(20\d{2}年)(.+?)(上半年|下半年)(时间)$/, '$1$3$2$4')

  return enriched
}

function extractSearchQuery(message: string): string {
  let query = message.trim()
  query = query.replace(/^(搜索|查找|搜一下|帮我搜|帮我查|查一下|查查|搜一搜|帮我搜索|帮我查找|帮我找|帮我找找|请问|麻烦问|问一下)\s*/, '')
  query = query.replace(/^(距离|离)\s*/, '')
  query = query.replace(/(还有几天|还剩几天|剩下几天|还有多久|还差几天)\s*$/, '')
  query = query.replace(/^(请问|麻烦|帮忙|你好|您好)\s*/, '')
  query = query.replace(/(和.{1,10}哪个好|和.{1,10}怎么选|还是.{1,5}好)\s*$/, '')
  query = enrichQueryWithTimeContext(query)
  return query || message.trim()
}

export const useChatStore = defineStore('chat', () => {
  const { apiGet, apiPost, apiDelete, apiStream, checkHealth } = useApi()
  const agentStore = useAgentStore()

  const agentConversations = ref<Record<string, ConversationListItem[]>>({})
  const agentCurrentConvId = ref<Record<string, string | null>>({})

  const convMessages = ref<Record<string, ChatMessage[]>>({})
  const convStreaming = ref<Record<string, boolean>>({})
  const convAbortControllers = ref<Record<string, AbortController>>({})
  const convStreamingContent = ref<Record<string, string>>({})
  const convStreamingReasoning = ref<Record<string, string>>({})
  const convLoading = ref<Record<string, boolean>>({})
  const convData = ref<Record<string, Conversation>>({})

  // 搜索跳转：点击搜索结果时暂存关键词，加载完对话后滚动到匹配消息
  const pendingSearchKeyword = ref('')
  const searchScrollTarget = ref<{ convId: string; keyword: string } | null>(null)

  // 推荐问题：当前显示推荐的消息ID，只有最后一条AI消息才显示推荐
  const currentSuggestionMessageId = ref<string | null>(null)

  const isBackendReady = ref(false)
  const lastError = ref<string | null>(null)
  const lastUsage = ref<{ promptTokens?: number; completionTokens?: number; totalTokens?: number } | null>(null)

  const activeAgentId = computed(() => agentStore.activeAgent?.id || '')

  const currentConvId = computed(() => agentCurrentConvId.value[activeAgentId.value] || '')

  const conversations = computed(() => agentConversations.value[activeAgentId.value] || [])

  const currentConversation = computed(() => {
    const convId = currentConvId.value
    if (!convId) return null
    return convData.value[convId] || null
  })

  const messages = computed(() => convMessages.value[currentConvId.value] || [])

  const isStreaming = computed(() => !!convStreaming.value[currentConvId.value])

  const isLoadingCurrentConversation = computed(() => !!convLoading.value[currentConvId.value])

  const streamingContent = computed({
    get: () => convStreamingContent.value[currentConvId.value] || '',
    set: (value) => {
      const convId = currentConvId.value
      if (convId) {
        convStreamingContent.value = { ...convStreamingContent.value, [convId]: value }
      }
    }
  })

  const streamingReasoning = computed({
    get: () => convStreamingReasoning.value[currentConvId.value] || '',
    set: (value) => {
      const convId = currentConvId.value
      if (convId) {
        convStreamingReasoning.value = { ...convStreamingReasoning.value, [convId]: value }
      }
    }
  })

  const currentMessages = computed(() => messages.value)

  const isConversationStreaming = (convId: string) => !!convStreaming.value[convId]

  const fetchConversations = async (agentId?: string) => {
    const targetAgentId = agentId || activeAgentId.value
    if (!targetAgentId) return

    try {
      const query = `?agent_id=${targetAgentId}`
      const rawConvs = await apiGet<any[]>(`/chat/conversations${query}`)
      const convs: ConversationListItem[] = rawConvs.map((conv: any) => ({
        id: conv.id,
        title: conv.title,
        agent_id: conv.agent_id,
        model: conv.model,
        provider: conv.provider,
        last_message: conv.last_message,
        created_at: conv.created_at || conv.createdAt || '',
        updated_at: conv.updated_at || conv.updatedAt || '',
      }))
      agentConversations.value = {
        ...agentConversations.value,
        [targetAgentId]: convs
      }
    } catch (error: unknown) {
      console.warn('[ChatStore] Failed to fetch conversations:', error)
      agentConversations.value = {
        ...agentConversations.value,
        [targetAgentId]: []
      }
    }
  }

  const loadConversation = async (convId: string) => {
    if (!activeAgentId.value) return

    // 加载对话时清除推荐
    currentSuggestionMessageId.value = null

    agentCurrentConvId.value = {
      ...agentCurrentConvId.value,
      [activeAgentId.value]: convId
    }

    if (convMessages.value[convId] && convMessages.value[convId].length > 0) {
      return
    }

    convLoading.value = { ...convLoading.value, [convId]: true }

    try {
      const conv = await apiGet<Conversation>(`/chat/conversations/${convId}`)
      convData.value = { ...convData.value, [convId]: conv }
      const mappedMessages: ChatMessage[] = []
      for (const m of (conv.messages || []) as ApiMessage[]) {
        const msg: ChatMessage = {
          id: m.id || `${Date.now()}-${Math.random().toString(36).slice(2)}`,
          role: m.role,
          content: m.content || '',
          timestamp: m.timestamp || Date.now(),
          done: true,
        }
        if (m.reasoning_content) {
          msg.reasoningContent = m.reasoning_content
        }
        if (m.interrupted || m.content === '[已中断]') {
          msg.interrupted = true
        }
        if (m.files) {
          msg.files = m.files
        } else if (m.file_name) {
          msg.files = [{ name: m.file_name, type: m.file_type }]
        }
        mappedMessages.push(msg)
      }
      convMessages.value = { ...convMessages.value, [convId]: mappedMessages }
    } catch (error) {
      if (!convMessages.value[convId]) {
        convMessages.value = { ...convMessages.value, [convId]: [] }
      }
    } finally {
      const newLoading = { ...convLoading.value }
      delete newLoading[convId]
      convLoading.value = newLoading
    }
  }

  const checkBackend = async () => {
    isBackendReady.value = await checkHealth()
    return isBackendReady.value
  }

  const createConversation = async (title?: string, agentId?: string, model?: string, provider?: string) => {
    const targetAgentId = agentId || activeAgentId.value
    if (!targetAgentId) return null

    const conv = await apiPost<Conversation>('/chat/conversations', {
      title: title || '新对话',
      agent_id: targetAgentId,
      model,
      provider,
    })
    convData.value = { ...convData.value, [conv.id]: conv }
    agentCurrentConvId.value = { ...agentCurrentConvId.value, [targetAgentId]: conv.id }
    convMessages.value = { ...convMessages.value, [conv.id]: [] }
    await fetchConversations(targetAgentId)
    return conv
  }

  const deleteConversation = async (convId: string, agentId?: string) => {
    const targetAgentId = agentId || activeAgentId.value
    if (!targetAgentId) return

    if (convStreaming.value[convId]) {
      cancelConversationRequest(convId)
    }

    await apiDelete(`/chat/conversations/${convId}`)

    const newMessages = { ...convMessages.value }
    delete newMessages[convId]
    convMessages.value = newMessages

    const newStreaming = { ...convStreaming.value }
    delete newStreaming[convId]
    convStreaming.value = newStreaming

    const newStreamingContent = { ...convStreamingContent.value }
    delete newStreamingContent[convId]
    convStreamingContent.value = newStreamingContent

    const newStreamingReasoning = { ...convStreamingReasoning.value }
    delete newStreamingReasoning[convId]
    convStreamingReasoning.value = newStreamingReasoning

    const newData = { ...convData.value }
    delete newData[convId]
    convData.value = newData

    const newLoading = { ...convLoading.value }
    delete newLoading[convId]
    convLoading.value = newLoading

    if (agentCurrentConvId.value[targetAgentId] === convId) {
      agentCurrentConvId.value = { ...agentCurrentConvId.value, [targetAgentId]: null }
    }

    await fetchConversations(targetAgentId)
  }

  const cancelConversationRequest = (convId?: string) => {
    const targetConvId = convId || currentConvId.value
    if (!targetConvId) return

    const controller = convAbortControllers.value[targetConvId]
    if (controller) {
      controller.abort()
      const newControllers = { ...convAbortControllers.value }
      delete newControllers[targetConvId]
      convAbortControllers.value = newControllers
    }

    convStreaming.value = { ...convStreaming.value, [targetConvId]: false }
    const currentMsgs = convMessages.value[targetConvId] || []
    const lastIndex = currentMsgs.length - 1
    if (lastIndex >= 0 && currentMsgs[lastIndex]?.role === 'assistant' && !currentMsgs[lastIndex].done) {
      convMessages.value = {
        ...convMessages.value,
        [targetConvId]: [...currentMsgs.slice(0, lastIndex), {
          ...currentMsgs[lastIndex],
          done: true,
          content: currentMsgs[lastIndex].content || '[已中断]',
          interrupted: true
        }]
      }
    }
    convStreamingContent.value = { ...convStreamingContent.value, [targetConvId]: '' }
    convStreamingReasoning.value = { ...convStreamingReasoning.value, [targetConvId]: '' }
  }

  const cancelCurrentRequest = (_agentId?: string) => {
    cancelConversationRequest()
  }

  const searchConversations = async (keyword: string, agentId?: string): Promise<ConversationSearchResult[]> => {
    if (!keyword.trim()) return []
    const targetAgentId = agentId || activeAgentId.value
    try {
      let query = `?keyword=${encodeURIComponent(keyword.trim())}`
      if (targetAgentId) query += `&agent_id=${targetAgentId}`
      return await apiGet<ConversationSearchResult[]>(`/chat/conversations/search${query}`)
    } catch (error) {
      console.warn('[ChatStore] Search failed:', error)
      return []
    }
  }

  const sendMessage = async (
    content: string,
    options?: {
      model?: string
      provider?: string
      temperature?: number
      maxTokens?: number
      topP?: number
      agentId?: string
      systemPrompt?: string
      fileContent?: string
      fileType?: string
      fileName?: string
    }
  ) => {
    const targetAgentId = options?.agentId || activeAgentId.value
    if (!targetAgentId) return

    // 发送消息时立即清除推荐
    currentSuggestionMessageId.value = null

    let convId = agentCurrentConvId.value[targetAgentId]

    if (!convId) {
      const conv = await createConversation(
        content.slice(0, 30),
        targetAgentId,
        options?.model,
        options?.provider
      )
      convId = conv?.id || null
      if (!convId) return
    }

    if (convStreaming.value[convId]) {
      cancelConversationRequest(convId)
    }

    lastError.value = null

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: content,
      timestamp: Date.now(),
      files: options?.fileContent && options?.fileName ? [{ name: options.fileName, type: options.fileType, content: options.fileContent }] : undefined,
    }
    convMessages.value = {
      ...convMessages.value,
      [convId]: [...(convMessages.value[convId] || []), userMessage]
    }

    const assistantMessage: ChatMessage = {
      id: `assistant-${Date.now()}`,
      role: 'assistant',
      content: '',
      reasoningContent: '',
      timestamp: Date.now(),
      done: false,
    }
    convMessages.value = {
      ...convMessages.value,
      [convId]: [...convMessages.value[convId], assistantMessage]
    }

    convStreaming.value = { ...convStreaming.value, [convId]: true }
    convStreamingContent.value = { ...convStreamingContent.value, [convId]: '' }
    convStreamingReasoning.value = { ...convStreamingReasoning.value, [convId]: '' }

    const apiMessages: { role: string; content: string }[] = []
    for (const msg of convMessages.value[convId]) {
      if (msg.role === 'system') continue
      if (msg.role === 'assistant' && !msg.done) continue
      apiMessages.push({ role: msg.role, content: msg.content })
    }

    const endpoint = `/chat/conversations/${convId}/messages`

    const requestBody: any = {
      messages: apiMessages,
      model: options?.model,
      provider: options?.provider,
      temperature: options?.temperature,
      max_tokens: options?.maxTokens,
      top_p: options?.topP,
      stream: true,
      timestamp: Date.now() / 1000,
    }

    if (targetAgentId) {
      requestBody.agent_id = targetAgentId
    }

    if (options?.fileContent) {
      requestBody.file_content = options.fileContent
      if (options.fileName) requestBody.file_name = options.fileName
      if (options.fileType) requestBody.file_type = options.fileType
    }

    // 搜索意图检测：如果用户消息需要联网搜索，先调用内置浏览器搜索
    try {
      const searchNeeded = await detectSearchIntent(content)
      if (searchNeeded) {
        const searchQuery = extractSearchQuery(content)
        const searchResults = await window.api.browserSearch.search(searchQuery)
        if (searchResults && searchResults.length > 0) {
          requestBody.search_results = searchResults.map((r: any) =>
            `${r.title}: ${r.snippet}`
          ).join('\n')
        }
      }
    } catch (err) {
      console.warn('[ChatStore] Browser search failed, continuing without search results:', err)
    }

    const controller = new AbortController()
    convAbortControllers.value = { ...convAbortControllers.value, [convId]: controller }

    const streamingConvId = convId

    await apiStream(
      endpoint,
      requestBody,
      (chunk: ChatStreamChunk) => {
        const prevContent = convStreamingContent.value[streamingConvId] || ''
        const newContent = prevContent + chunk.content
        convStreamingContent.value = { ...convStreamingContent.value, [streamingConvId]: newContent }

        const prevReasoning = convStreamingReasoning.value[streamingConvId] || ''
        const newReasoning = prevReasoning + (chunk.reasoning_content || '')
        convStreamingReasoning.value = { ...convStreamingReasoning.value, [streamingConvId]: newReasoning }

        const currentMsgList = convMessages.value[streamingConvId] || []
        const lastIndex = currentMsgList.length - 1
        if (lastIndex >= 0 && currentMsgList[lastIndex]?.role === 'assistant') {
          const updatedMsg: ChatMessage = {
            ...currentMsgList[lastIndex],
            content: newContent,
            reasoningContent: newReasoning,
          }
          // 如果 done 事件中携带了推荐问题，写入消息
          if (chunk.done && chunk.suggested_questions && chunk.suggested_questions.length > 0) {
            updatedMsg.suggestedQuestions = chunk.suggested_questions
          }
          convMessages.value = {
            ...convMessages.value,
            [streamingConvId]: [...currentMsgList.slice(0, lastIndex), updatedMsg]
          }
        }
        if (chunk.usage) {
          lastUsage.value = chunk.usage
        }
      },
      async () => {
        const newControllers = { ...convAbortControllers.value }
        delete newControllers[streamingConvId]
        convAbortControllers.value = newControllers

        const completeMsgList = convMessages.value[streamingConvId] || []
        const completeLastIndex = completeMsgList.length - 1
        if (completeLastIndex >= 0 && completeMsgList[completeLastIndex]?.role === 'assistant') {
          const completedMsg: ChatMessage = {
            ...completeMsgList[completeLastIndex],
            done: true
          }
          convMessages.value = {
            ...convMessages.value,
            [streamingConvId]: [...completeMsgList.slice(0, completeLastIndex), completedMsg]
          }
          // 只有这条消息有推荐问题时，才设置当前推荐消息ID
          if (completedMsg.suggestedQuestions && completedMsg.suggestedQuestions.length > 0) {
            currentSuggestionMessageId.value = completedMsg.id
          }
        }
        convStreaming.value = { ...convStreaming.value, [streamingConvId]: false }
        convStreamingContent.value = { ...convStreamingContent.value, [streamingConvId]: '' }
        convStreamingReasoning.value = { ...convStreamingReasoning.value, [streamingConvId]: '' }
        await fetchConversations(targetAgentId)
      },
      (err: string) => {
        const newControllers = { ...convAbortControllers.value }
        delete newControllers[streamingConvId]
        convAbortControllers.value = newControllers

        const errorMsgList = convMessages.value[streamingConvId] || []
        const errorLastIndex = errorMsgList.length - 1
        if (errorLastIndex >= 0 && errorMsgList[errorLastIndex]?.role === 'assistant') {
          convMessages.value = {
            ...convMessages.value,
            [streamingConvId]: [...errorMsgList.slice(0, errorLastIndex), {
              ...errorMsgList[errorLastIndex],
              content: errorMsgList[errorLastIndex].content
                ? `${errorMsgList[errorLastIndex].content}\n\n[Error] ${err}`
                : `[Error] ${err}`,
              done: true
            }]
          }
        }
        convStreaming.value = { ...convStreaming.value, [streamingConvId]: false }
        convStreamingContent.value = { ...convStreamingContent.value, [streamingConvId]: '' }
        convStreamingReasoning.value = { ...convStreamingReasoning.value, [streamingConvId]: '' }
        lastError.value = err
        fetchConversations(targetAgentId)
      },
      controller.signal
    )
  }

  const clearMessages = () => {
    agentCurrentConvId.value = { ...agentCurrentConvId.value, [activeAgentId.value]: null }
    lastError.value = null
  }

  const cleanupUnusedConversations = () => {
    const currentId = currentConvId.value
    const keysToDelete: string[] = []

    for (const convId of Object.keys(convMessages.value)) {
      if (convId === currentId) continue
      if (convStreaming.value[convId]) continue
      const msgs = convMessages.value[convId]
      if (!msgs || msgs.length === 0) {
        keysToDelete.push(convId)
      }
    }

    if (keysToDelete.length === 0) return

    const newMessages = { ...convMessages.value }
    const newStreaming = { ...convStreaming.value }
    const newStreamingContent = { ...convStreamingContent.value }
    const newStreamingReasoning = { ...convStreamingReasoning.value }
    const newData = { ...convData.value }
    const newLoading = { ...convLoading.value }

    for (const convId of keysToDelete) {
      delete newMessages[convId]
      delete newStreaming[convId]
      delete newStreamingContent[convId]
      delete newStreamingReasoning[convId]
      delete newData[convId]
      delete newLoading[convId]
    }

    convMessages.value = newMessages
    convStreaming.value = newStreaming
    convStreamingContent.value = newStreamingContent
    convStreamingReasoning.value = newStreamingReasoning
    convData.value = newData
    convLoading.value = newLoading
  }

  watch(() => activeAgentId.value, async (newAgentId) => {
    if (newAgentId) {
      if (!agentConversations.value[newAgentId]) {
        agentConversations.value = { ...agentConversations.value, [newAgentId]: [] }
      }

      await fetchConversations(newAgentId)

      const currentId = agentCurrentConvId.value[newAgentId]
      if (currentId) {
        if (!convMessages.value[currentId] || convMessages.value[currentId].length === 0) {
          await loadConversation(currentId)
        }
      } else if (agentConversations.value[newAgentId].length > 0) {
        const latestConv = agentConversations.value[newAgentId][0]
        if (latestConv?.id) {
          try {
            await loadConversation(latestConv.id)
          } catch (error) {
            console.warn(`[ChatStore] Failed to load latest conversation for agent ${newAgentId}:`, error)
          }
        }
      }
    }
  }, { immediate: true })

  return {
    conversations,
    currentConversation,
    currentConvId,
    messages,
    currentMessages,
    isStreaming,
    isBackendReady,
    isLoadingCurrentConversation,
    streamingContent,
    streamingReasoning,
    lastError,
    lastUsage,
    activeAgentId,
    convStreaming,
    convMessages,
    currentSuggestionMessageId,
    checkBackend,
    fetchConversations,
    createConversation,
    loadConversation,
    deleteConversation,
    sendMessage,
    clearMessages,
    cleanupUnusedConversations,
    cancelCurrentRequest,
    cancelConversationRequest,
    isConversationStreaming,
    searchConversations,
    pendingSearchKeyword,
    searchScrollTarget,
  }
})

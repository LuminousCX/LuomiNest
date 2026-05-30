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

const PERIODIC_EVENT_PATTERNS: Array<{ pattern: RegExp; type: string }> = [
  { pattern: /报名/, type: '报名' },
  { pattern: /录取/, type: '录取' },
  { pattern: /分数线/, type: '分数' },
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
]

export function detectSearchIntent(message: string): boolean {
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

export function extractSearchQuery(message: string): string {
  let query = message.trim()
  query = query.replace(/^(搜索|查找|搜一下|帮我搜|帮我查|查一下|查查|搜一搜|帮我搜索|帮我查找|帮我找|帮我找找|请问|麻烦问|问一下)\s*/, '')
  query = query.replace(/^(距离|离)\s*/, '')
  query = query.replace(/(还有几天|还剩几天|剩下几天|还有多久|还差几天)\s*$/, '')
  query = query.replace(/^(请问|麻烦|帮忙|你好|您好)\s*/, '')
  query = query.replace(/(和.{1,10}哪个好|和.{1,10}怎么选|还是.{1,5}好)\s*$/, '')
  query = enrichQueryWithTimeContext(query)
  return query || message.trim()
}

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
    const firstHalfOnly = /高考|中考/.test(coreQuery)
    if (firstHalfOnly) enriched += '上半年'
    else if (month >= 5 && month <= 8) enriched += '下半年'
    else if (month >= 9) enriched += '下半年'
    else enriched += '上半年'
  }

  if (['考试', '报名', '录取', '分数'].includes(matchedType) && !enriched.includes('时间')) {
    enriched += '时间'
  }

  enriched = enriched.replace(/^(20\d{2}年)(.+?)(上半年|下半年)(时间)$/, '$1$3$2$4')

  return enriched
}

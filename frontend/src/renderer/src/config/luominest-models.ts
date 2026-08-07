import type { PetModelInfo } from '@shared/ipc-types'

export type LuomiNestModelInfo = PetModelInfo

export interface LuomiNestAvatarBinding {
  modelId: string
  voice: string
  voiceLang: 'zh' | 'ja' | 'en'
  expressionMap: Record<string, string>
  defaultExpression: string
}

export const LUOMINEST_BUILTIN_MODELS: LuomiNestModelInfo[] = [
  {
    id: 'llny',
    name: 'Llny',
    url: 'luominest-avatar://llny/llny.model3.json',
    scale: 0.25,
    type: 'live2d',
    tags: ['Default', 'Cubism4', 'Built-in']
  },
  {
    id: 'hiyori',
    name: 'Hiyori',
    url: 'luominest-avatar://hiyori/Hiyori.model3.json',
    scale: 0.25,
    type: 'live2d',
    tags: ['Cubism4', 'Built-in']
  }
]

// llny 语义情绪ID → 模型原生表情名映射
// 用于 LLM 对话输出的 <exp:happy> 等语义标签驱动模型表情
// 模型原生表情名见 llny.model3.json 的 FileReferences.Expressions
const LLNY_EXPRESSION_MAP: Record<string, string> = {
  happy: '星星',
  sad: '哭',
  neutral: '- -',
  love: '脸红',
  surprise: '阿尼亚',
  angry: '生气',
  think: '眼镜',
  awkward: '脸黑',
  curious: '吐舌',
  shy: '脸红',
  excited: '比心',
  confused: '荷包蛋'
}

// hiyori 模型没有 expressions 定义（见 Hiyori.model3.json），
// LLM 语义情绪无法映射到表情，只能通过 PAD 面部参数微调
const HIYORI_EXPRESSION_MAP: Record<string, string> = {}

export const LUOMINEST_AVATAR_BINDINGS: Record<string, LuomiNestAvatarBinding> = {
  llny: {
    modelId: 'llny',
    voice: 'zh-CN-XiaoxiaoNeural',
    voiceLang: 'zh',
    expressionMap: LLNY_EXPRESSION_MAP,
    defaultExpression: '- -'
  },
  hiyori: {
    modelId: 'hiyori',
    voice: 'zh-CN-XiaoxiaoNeural',
    voiceLang: 'zh',
    expressionMap: HIYORI_EXPRESSION_MAP,
    defaultExpression: ''
  }
}

export const getAvatarBinding = (modelId: string): LuomiNestAvatarBinding | null => {
  return LUOMINEST_AVATAR_BINDINGS[modelId] ?? null
}

// 语义情绪ID → 模型原生表情名
// 若模型无该表情映射，返回空字符串（调用方据此跳过表情触发）
export const resolveExpression = (modelId: string, emotionId: string): string => {
  const binding = LUOMINEST_AVATAR_BINDINGS[modelId]
  if (!binding) return ''
  return binding.expressionMap[emotionId] ?? binding.defaultExpression
}

export const resolveExpressionByModelUrl = (modelUrl: string, emotionId: string): string => {
  const model = LUOMINEST_BUILTIN_MODELS.find(m => m.url === modelUrl)
  if (!model) return ''
  return resolveExpression(model.id, emotionId)
}

export const LUOMINEST_MODEL_ACCEPT_EXTENSIONS = '.model3.json'

export const validateLuomiNestModelUrl = (url: string): boolean => {
  return url.startsWith('luominest-avatar://') && url.endsWith('.model3.json')
}

export const validateLuomiNestModel3Json = (data: unknown): { valid: boolean; errors: string[] } => {
  const errors: string[] = []
  if (!data || typeof data !== 'object') {
    return { valid: false, errors: ['Invalid model3.json: not an object'] }
  }
  const obj = data as Record<string, unknown>
  if (!obj.FileReferences || typeof obj.FileReferences !== 'object') {
    errors.push('Missing FileReferences section')
  } else {
    const refs = obj.FileReferences as Record<string, unknown>
    if (!refs.Moc || typeof refs.Moc !== 'string') {
      errors.push('Missing FileReferences.Moc (model binary path)')
    }
    if (!refs.Textures || !Array.isArray(refs.Textures) || refs.Textures.length === 0) {
      errors.push('Missing FileReferences.Textures (texture list)')
    }
  }
  return { valid: errors.length === 0, errors }
}

export const getLuomiNestModelById = (id: string): LuomiNestModelInfo | undefined =>
  LUOMINEST_BUILTIN_MODELS.find(m => m.id === id)

export const getLuomiNestModelsByType = (type: LuomiNestModelInfo['type']): LuomiNestModelInfo[] =>
  LUOMINEST_BUILTIN_MODELS.filter(m => m.type === type)

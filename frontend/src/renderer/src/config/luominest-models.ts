import type { LuomiNestModelInfo } from '@/composables/useLuomiNestLive2D'

export const LUOMINEST_BUILTIN_MODELS: LuomiNestModelInfo[] = [
  {
    id: 'llny',
    name: 'Llny',
    url: '/live2d/llny/llny.model3.json',
    scale: 0.1,
    type: 'live2d',
    tags: ['Default', 'Cubism4', 'Built-in']
  },
  {
    id: 'hiyori',
    name: 'Hiyori',
    url: '/live2d/hiyori/Hiyori.model3.json',
    scale: 0.1,
    type: 'live2d',
    tags: ['Cubism4', 'Built-in']
  },
  {
    id: 'shizuku',
    name: 'Shizuku',
    url: '/live2d/shizuku/shizuku.model3.json',
    scale: 0.1,
    type: 'live2d',
    tags: ['Cubism4', 'Built-in']
  }
]

export const LUOMINEST_MODEL_ACCEPT_EXTENSIONS = '.model3.json'

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

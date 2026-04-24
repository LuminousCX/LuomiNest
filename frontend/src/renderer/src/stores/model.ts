import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ModelProvider, ModelInfo, ModelConfig, ProviderTemplate, TTSConfig, STTConfig } from '../types'
import { useApi } from '../composables/useApi'

const unwrapData = <T>(result: any): T => {
  if (result && typeof result === 'object' && 'data' in result) {
    return result.data as T
  }
  return result as T
}

const LOCAL_TEMPLATES: ProviderTemplate[] = [
  { id: 'openai', name: 'OpenAI', vendor: 'openai_compatible', baseUrl: 'https://api.openai.com/v1', defaultModel: 'gpt-4o-mini', description: 'GPT-4o / o3 等旗舰模型', category: 'cloud', color: '#10a37f', initials: 'OA' },
  { id: 'anthropic', name: 'Anthropic', vendor: 'openai_compatible', baseUrl: 'https://api.anthropic.com/v1', defaultModel: 'claude-sonnet-4-20250514', description: 'Claude Opus / Sonnet 系列', category: 'cloud', color: '#d4a574', initials: 'AN' },
  { id: 'deepseek', name: 'DeepSeek', vendor: 'openai_compatible', baseUrl: 'https://api.deepseek.com', defaultModel: 'deepseek-chat', description: 'DeepSeek V3 / R1 推理模型', category: 'cloud', color: '#4d6bfe', initials: 'DS' },
  { id: 'google', name: 'Google Gemini', vendor: 'openai_compatible', baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai', defaultModel: 'gemini-2.0-flash', description: 'Gemini 2.0 Flash / Pro', category: 'cloud', color: '#4285f4', initials: 'GG' },
  { id: 'mistral', name: 'Mistral AI', vendor: 'openai_compatible', baseUrl: 'https://api.mistral.ai/v1', defaultModel: 'mistral-small-latest', description: 'Mistral / Codestral 系列', category: 'cloud', color: '#ff7000', initials: 'MI' },
  { id: 'groq', name: 'Groq', vendor: 'openai_compatible', baseUrl: 'https://api.groq.com/openai/v1', defaultModel: 'llama-3.3-70b-versatile', description: 'LPU 超高速推理', category: 'cloud', color: '#f55036', initials: 'GQ' },
  { id: 'xai', name: 'xAI', vendor: 'openai_compatible', baseUrl: 'https://api.x.ai/v1', defaultModel: 'grok-3-mini-beta', description: 'Grok 系列模型', category: 'cloud', color: '#1d1d1d', initials: 'XA' },
  { id: 'moonshot', name: 'Moonshot (Kimi)', vendor: 'openai_compatible', baseUrl: 'https://api.moonshot.cn/v1', defaultModel: 'moonshot-v1-8k', description: '月之暗面 Kimi 长上下文', category: 'cloud', color: '#6c5ce7', initials: 'MK' },
  { id: 'zhipu', name: 'ZhiPu (智谱)', vendor: 'openai_compatible', baseUrl: 'https://open.bigmodel.cn/api/paas/v4', defaultModel: 'glm-4-flash', description: 'GLM-4 系列', category: 'cloud', color: '#3b5cff', initials: 'ZP' },
  { id: 'dashscope', name: 'DashScope (百炼)', vendor: 'openai_compatible', baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1', defaultModel: 'qwen-plus', description: '阿里云通义千问系列', category: 'cloud', color: '#ff6a00', initials: 'DQ' },
  { id: 'siliconflow', name: 'SiliconFlow', vendor: 'openai_compatible', baseUrl: 'https://api.siliconflow.cn/v1', defaultModel: 'Qwen/Qwen2.5-7B-Instruct', description: '硅基流动多模型平台', category: 'aggregator', color: '#7c3aed', initials: 'SF' },
  { id: 'openrouter', name: 'OpenRouter', vendor: 'openai_compatible', baseUrl: 'https://openrouter.ai/api/v1', defaultModel: 'openai/gpt-4o-mini', description: '聚合 200+ 模型网关', category: 'aggregator', color: '#6d28d9', initials: 'OR' },
  { id: 'together', name: 'Together AI', vendor: 'openai_compatible', baseUrl: 'https://api.together.xyz/v1', defaultModel: 'meta-llama/Llama-3.3-70B-Instruct-Turbo', description: '开源模型云端推理', category: 'aggregator', color: '#3b82f6', initials: 'TA' },
  { id: 'fireworks', name: 'Fireworks AI', vendor: 'openai_compatible', baseUrl: 'https://api.fireworks.ai/inference/v1', defaultModel: 'accounts/fireworks/models/llama-v3p3-70b-instruct', description: '高速开源模型推理', category: 'aggregator', color: '#ef4444', initials: 'FW' },
  { id: 'ollama', name: 'Ollama', vendor: 'ollama', baseUrl: 'http://localhost:11434/v1', defaultModel: 'qwen2.5:7b', description: '本地 Ollama 推理引擎', category: 'local', color: '#0d0d0d', initials: 'OL' },
  { id: 'lmstudio', name: 'LM Studio', vendor: 'openai_compatible', baseUrl: 'http://localhost:1234/v1', defaultModel: '', description: '本地 LM Studio 推理', category: 'local', color: '#1e40af', initials: 'LM' },
  { id: 'vllm', name: 'vLLM', vendor: 'openai_compatible', baseUrl: 'http://localhost:8000/v1', defaultModel: '', description: '本地 vLLM 高性能推理', category: 'local', color: '#059669', initials: 'VL' },
  { id: 'custom', name: 'Custom', vendor: 'openai_compatible', baseUrl: '', defaultModel: '', description: '自定义 OpenAI 兼容端点', category: 'aggregator', color: '#6b7280', initials: 'CU' },
]

const TTS_VOICES = ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer'] as const
const STT_LANGUAGES = [
  { value: 'zh-CN', label: '中文（简体）' },
  { value: 'zh-TW', label: '中文（繁体）' },
  { value: 'en-US', label: 'English' },
  { value: 'ja-JP', label: '日本語' },
  { value: 'ko-KR', label: '한국어' },
  { value: 'fr-FR', label: 'Français' },
  { value: 'de-DE', label: 'Deutsch' },
  { value: 'es-ES', label: 'Español' },
] as const

export const useModelStore = defineStore('model', () => {
  const { apiGet, apiPost, apiDelete, apiPatch } = useApi()

  const providers = ref<ModelProvider[]>([])
  const templates = ref<ProviderTemplate[]>([])
  const modelConfig = ref<ModelConfig>({
    defaultProvider: '',
    defaultModel: '',
    defaultTemperature: 0.7,
    defaultMaxTokens: 4096,
    defaultTopP: 0.9,
  })
  const ttsConfig = ref<TTSConfig>({
    provider: '',
    model: 'tts-1',
    voice: 'alloy',
    speed: 1.0,
    baseUrl: '',
    apiKeySet: false,
  })
  const sttConfig = ref<STTConfig>({
    provider: '',
    model: 'whisper-1',
    language: 'zh-CN',
    autoSend: false,
    autoSendDelay: 2000,
    baseUrl: '',
    apiKeySet: false,
  })
  const loading = ref(false)
  const saveStatus = ref<'idle' | 'saving' | 'saved' | 'error'>('idle')

  const defaultProvider = computed(() =>
    providers.value.find(p => p.isDefault)
  )

  const allModels = computed(() => {
    const models: (ModelInfo & { providerId: string })[] = []
    for (const provider of providers.value) {
      for (const model of provider.models) {
        models.push({ ...model, providerId: provider.id })
      }
    }
    return models
  })

  const allTemplates = computed(() => {
    const backendIds = new Set(templates.value.map(t => t.id))
    const unique = LOCAL_TEMPLATES.filter(t => !backendIds.has(t.id))
    return [...templates.value, ...unique]
  })

  const templatesByCategory = computed(() => {
    const cats: Record<string, ProviderTemplate[]> = { cloud: [], local: [], aggregator: [] }
    for (const t of allTemplates.value) {
      const key = t.category || 'cloud'
      if (!cats[key]) cats[key] = []
      cats[key].push(t)
    }
    return cats
  })

  const getProviderModels = (providerId: string): ModelInfo[] => {
    const provider = providers.value.find(p => p.id === providerId)
    return provider?.models || []
  }

  const resolveModel = computed(() => {
    const mainProvider = modelConfig.value.defaultProvider
    const mainModel = modelConfig.value.defaultModel
    const reasonerProvider = modelConfig.value.reasonerProvider
    const reasonerModel = modelConfig.value.reasonerModel

    if (mainProvider && mainModel) {
      return { provider: mainProvider, model: mainModel, type: 'main' as const }
    }
    if (reasonerProvider && reasonerModel) {
      return { provider: reasonerProvider, model: reasonerModel, type: 'reasoner' as const }
    }
    const first = providers.value[0]
    if (first) {
      return { provider: first.id, model: first.defaultModel, type: 'fallback' as const }
    }
    return null
  })

  const resolveReasonerModel = computed(() => {
    const rp = modelConfig.value.reasonerProvider
    const rm = modelConfig.value.reasonerModel
    if (rp && rm) {
      return { provider: rp, model: rm }
    }
    const mp = modelConfig.value.defaultProvider
    const mm = modelConfig.value.defaultModel
    if (mp && mm) {
      return { provider: mp, model: mm }
    }
    return null
  })

  const fetchProviders = async () => {
    loading.value = true
    try {
      const result = await apiGet<any[]>('/models/providers')
      const raw = Array.isArray(result) ? result : []
      providers.value = raw.map(p => ({
        id: p.id,
        name: p.name,
        vendor: p.vendor,
        baseUrl: p.baseUrl || p.base_url || '',
        apiKeySet: p.apiKeySet || p.api_key_set || false,
        defaultModel: p.defaultModel || p.default_model || '',
        isDefault: p.isDefault || p.is_default || false,
        models: p.models || [],
      }))

      for (const provider of providers.value) {
        if (provider.id && provider.models.length === 0) {
          fetchProviderModels(provider.id).catch(() => {})
        }
      }
    } catch {
      providers.value = []
    } finally {
      loading.value = false
    }
  }

  const fetchTemplates = async () => {
    try {
      const result = await apiGet<any[]>('/models/providers/templates')
      const raw = Array.isArray(result) ? result : []
      templates.value = raw.map(t => {
        const local = LOCAL_TEMPLATES.find(lt => lt.id === t.id)
        return {
          id: t.id,
          name: t.name,
          vendor: t.vendor,
          baseUrl: t.baseUrl || t.base_url || '',
          defaultModel: t.defaultModel || t.default_model || '',
          description: t.description || '',
          category: local?.category || 'cloud' as const,
          color: local?.color || '#6b7280',
          initials: local?.initials || t.name.slice(0, 2).toUpperCase(),
        }
      })
    } catch {
      templates.value = []
    }
  }

  const addProvider = async (provider: {
    id: string
    name: string
    vendor: string
    baseUrl: string
    apiKey: string
    defaultModel: string
    isDefault: boolean
  }) => {
    const result = await apiPost<ModelProvider>('/models/providers', {
      id: provider.id,
      name: provider.name,
      vendor: provider.vendor,
      baseUrl: provider.baseUrl,
      apiKey: provider.apiKey,
      defaultModel: provider.defaultModel,
      isDefault: provider.isDefault,
    })
    await fetchProviders()
    return result
  }

  const updateProvider = async (providerId: string, updates: {
    name?: string
    vendor?: string
    baseUrl?: string
    apiKey?: string
    defaultModel?: string
    isDefault?: boolean
  }) => {
    const result = await apiPatch<ModelProvider>(`/models/providers/${providerId}`, {
      name: updates.name,
      vendor: updates.vendor,
      baseUrl: updates.baseUrl,
      apiKey: updates.apiKey,
      defaultModel: updates.defaultModel,
      isDefault: updates.isDefault,
    })
    await fetchProviders()
    return result
  }

  const removeProvider = async (providerId: string) => {
    await apiDelete(`/models/providers/${providerId}`)
    providers.value = providers.value.filter(p => p.id !== providerId)
  }

  const fetchProviderModels = async (providerId: string) => {
    const result = await apiGet<ModelInfo[] | { data: ModelInfo[] }>(`/models/providers/${providerId}/models`)
    const models = unwrapData<ModelInfo[]>(result)
    const provider = providers.value.find(p => p.id === providerId)
    if (provider) {
      provider.models = models
    }
    return models
  }

  const fetchModelConfig = async () => {
    try {
      const result = await apiGet<any>('/models/config')
      const config = unwrapData<any>(result)
      if (config) {
        modelConfig.value = {
          defaultProvider: config.defaultProvider || config.default_provider || '',
          defaultModel: config.defaultModel || config.default_model || '',
          defaultTemperature: config.defaultTemperature ?? config.default_temperature ?? 0.7,
          defaultMaxTokens: config.defaultMaxTokens ?? config.default_max_tokens ?? 4096,
          defaultTopP: config.defaultTopP ?? config.default_top_p ?? 0.9,
          reasonerProvider: config.reasonerProvider || config.reasoner_provider,
          reasonerModel: config.reasonerModel || config.reasoner_model,
          reasonerTemperature: config.reasonerTemperature ?? config.reasoner_temperature,
          reasonerMaxTokens: config.reasonerMaxTokens ?? config.reasoner_max_tokens,
          reasonerEffort: config.reasonerEffort || config.reasoner_effort,
          ttsProvider: config.ttsProvider || config.tts_provider,
          ttsModel: config.ttsModel || config.tts_model || 'tts-1',
          ttsVoice: config.ttsVoice || config.tts_voice || 'alloy',
          ttsSpeed: config.ttsSpeed ?? config.tts_speed ?? 1.0,
          sttProvider: config.sttProvider || config.stt_provider,
          sttModel: config.sttModel || config.stt_model || 'whisper-1',
          sttLanguage: config.sttLanguage || config.stt_language || 'zh-CN',
          sttAutoSend: config.sttAutoSend ?? config.stt_auto_send ?? false,
          sttAutoSendDelay: config.sttAutoSendDelay ?? config.stt_auto_send_delay ?? 2000,
        }
      }
    } catch {
      // use defaults
    }

    loadTTSConfigFromLocal()
    loadSTTConfigFromLocal()
  }

  const updateModelConfig = async (config: Partial<ModelConfig>) => {
    saveStatus.value = 'saving'
    try {
      const body: any = {}
      if (config.defaultProvider !== undefined) body.provider = config.defaultProvider
      if (config.defaultModel !== undefined) body.model = config.defaultModel
      if (config.defaultTemperature !== undefined) body.temperature = config.defaultTemperature
      if (config.defaultMaxTokens !== undefined) body.maxTokens = config.defaultMaxTokens
      if (config.defaultTopP !== undefined) body.topP = config.defaultTopP
      if (config.reasonerProvider !== undefined) body.reasonerProvider = config.reasonerProvider
      if (config.reasonerModel !== undefined) body.reasonerModel = config.reasonerModel
      if (config.reasonerTemperature !== undefined) body.reasonerTemperature = config.reasonerTemperature
      if (config.reasonerMaxTokens !== undefined) body.reasonerMaxTokens = config.reasonerMaxTokens
      if (config.reasonerEffort !== undefined) body.reasonerEffort = config.reasonerEffort
      if (config.ttsProvider !== undefined) body.ttsProvider = config.ttsProvider
      if (config.ttsModel !== undefined) body.ttsModel = config.ttsModel
      if (config.ttsVoice !== undefined) body.ttsVoice = config.ttsVoice
      if (config.ttsSpeed !== undefined) body.ttsSpeed = config.ttsSpeed
      if (config.sttProvider !== undefined) body.sttProvider = config.sttProvider
      if (config.sttModel !== undefined) body.sttModel = config.sttModel
      if (config.sttLanguage !== undefined) body.sttLanguage = config.sttLanguage
      if (config.sttAutoSend !== undefined) body.sttAutoSend = config.sttAutoSend
      if (config.sttAutoSendDelay !== undefined) body.sttAutoSendDelay = config.sttAutoSendDelay

      try {
        await apiPatch('/models/config', body)
        await fetchModelConfig()
      } catch {
        modelConfig.value = { ...modelConfig.value, ...config }
      }
      saveStatus.value = 'saved'
      setTimeout(() => { saveStatus.value = 'idle' }, 2000)
    } catch {
      saveStatus.value = 'error'
      setTimeout(() => { saveStatus.value = 'idle' }, 3000)
    }
  }

  const saveTTSConfigToLocal = () => {
    const cfg = ttsConfig.value
    const data = {
      provider: cfg.provider,
      model: cfg.model,
      voice: cfg.voice,
      speed: cfg.speed,
      baseUrl: cfg.baseUrl,
    }
    localStorage.setItem('luominest-tts-config', JSON.stringify(data))
    window.api?.config?.setTTS(data).catch(() => {})
  }

  const loadTTSConfigFromLocal = () => {
    try {
      const raw = localStorage.getItem('luominest-tts-config')
      if (raw) {
        const saved = JSON.parse(raw)
        ttsConfig.value = {
          provider: saved.provider || modelConfig.value.ttsProvider || '',
          model: saved.model || modelConfig.value.ttsModel || 'tts-1',
          voice: saved.voice || modelConfig.value.ttsVoice || 'alloy',
          speed: saved.speed ?? modelConfig.value.ttsSpeed ?? 1.0,
          baseUrl: saved.baseUrl || '',
          apiKeySet: false,
        }
      } else {
        ttsConfig.value = {
          provider: modelConfig.value.ttsProvider || '',
          model: modelConfig.value.ttsModel || 'tts-1',
          voice: modelConfig.value.ttsVoice || 'alloy',
          speed: modelConfig.value.ttsSpeed ?? 1.0,
          baseUrl: '',
          apiKeySet: false,
        }
      }
    } catch {
      // use defaults
    }
  }

  const saveSTTConfigToLocal = () => {
    const cfg = sttConfig.value
    const data = {
      provider: cfg.provider,
      model: cfg.model,
      language: cfg.language,
      autoSend: cfg.autoSend,
      autoSendDelay: cfg.autoSendDelay,
      baseUrl: cfg.baseUrl,
    }
    localStorage.setItem('luominest-stt-config', JSON.stringify(data))
    window.api?.config?.setSTT(data).catch(() => {})
  }

  const loadSTTConfigFromLocal = () => {
    try {
      const raw = localStorage.getItem('luominest-stt-config')
      if (raw) {
        const saved = JSON.parse(raw)
        sttConfig.value = {
          provider: saved.provider || modelConfig.value.sttProvider || '',
          model: saved.model || modelConfig.value.sttModel || 'whisper-1',
          language: saved.language || modelConfig.value.sttLanguage || 'zh-CN',
          autoSend: saved.autoSend ?? modelConfig.value.sttAutoSend ?? false,
          autoSendDelay: saved.autoSendDelay ?? modelConfig.value.sttAutoSendDelay ?? 2000,
          baseUrl: saved.baseUrl || '',
          apiKeySet: false,
        }
      } else {
        sttConfig.value = {
          provider: modelConfig.value.sttProvider || '',
          model: modelConfig.value.sttModel || 'whisper-1',
          language: modelConfig.value.sttLanguage || 'zh-CN',
          autoSend: modelConfig.value.sttAutoSend ?? false,
          autoSendDelay: modelConfig.value.sttAutoSendDelay ?? 2000,
          baseUrl: '',
          apiKeySet: false,
        }
      }
    } catch {
      // use defaults
    }
  }

  const updateTTSConfig = async (updates: Partial<TTSConfig>) => {
    ttsConfig.value = { ...ttsConfig.value, ...updates }
    saveTTSConfigToLocal()

    const configUpdates: Partial<ModelConfig> = {}
    if (updates.provider !== undefined) configUpdates.ttsProvider = updates.provider
    if (updates.model !== undefined) configUpdates.ttsModel = updates.model
    if (updates.voice !== undefined) configUpdates.ttsVoice = updates.voice
    if (updates.speed !== undefined) configUpdates.ttsSpeed = updates.speed

    try {
      await updateModelConfig(configUpdates)
    } catch {
      // local save already done
    }
  }

  const updateSTTConfig = async (updates: Partial<STTConfig>) => {
    sttConfig.value = { ...sttConfig.value, ...updates }
    saveSTTConfigToLocal()

    const configUpdates: Partial<ModelConfig> = {}
    if (updates.provider !== undefined) configUpdates.sttProvider = updates.provider
    if (updates.model !== undefined) configUpdates.sttModel = updates.model
    if (updates.language !== undefined) configUpdates.sttLanguage = updates.language
    if (updates.autoSend !== undefined) configUpdates.sttAutoSend = updates.autoSend
    if (updates.autoSendDelay !== undefined) configUpdates.sttAutoSendDelay = updates.autoSendDelay

    try {
      await updateModelConfig(configUpdates)
    } catch {
      // local save already done
    }
  }

  return {
    providers,
    templates,
    modelConfig,
    ttsConfig,
    sttConfig,
    loading,
    saveStatus,
    defaultProvider,
    allModels,
    allTemplates,
    templatesByCategory,
    resolveModel,
    resolveReasonerModel,
    getProviderModels,
    fetchProviders,
    fetchTemplates,
    addProvider,
    updateProvider,
    removeProvider,
    fetchProviderModels,
    fetchModelConfig,
    updateModelConfig,
    updateTTSConfig,
    updateSTTConfig,
    TTS_VOICES,
    STT_LANGUAGES,
  }
})

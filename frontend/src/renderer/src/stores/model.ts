import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ModelProvider, ModelInfo, ModelConfig, ProviderTemplate } from '../types'
import { useApi } from '../composables/useApi'

const unwrapData = <T>(result: any): T => {
  if (result && typeof result === 'object' && 'data' in result) {
    return result.data as T
  }
  return result as T
}

export const useModelStore = defineStore('model', () => {
  const { apiGet, apiPost, apiDelete, apiPatch } = useApi()

  const providers = ref<ModelProvider[]>([])
  const templates = ref<ProviderTemplate[]>([])
  const modelConfig = ref<ModelConfig>({
    defaultProvider: 'ollama',
    defaultModel: 'qwen2.5:7b',
    defaultTemperature: 0.7,
    defaultMaxTokens: 4096,
    defaultTopP: 0.9,
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

  const getProviderModels = (providerId: string): ModelInfo[] => {
    const provider = providers.value.find(p => p.id === providerId)
    return provider?.models || []
  }

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
      templates.value = raw.map(t => ({
        id: t.id,
        name: t.name,
        vendor: t.vendor,
        baseUrl: t.baseUrl || t.base_url || '',
        defaultModel: t.defaultModel || t.default_model || '',
        description: t.description || '',
      }))
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
          defaultProvider: config.defaultProvider || config.default_provider || 'ollama',
          defaultModel: config.defaultModel || config.default_model || 'qwen2.5:7b',
          defaultTemperature: config.defaultTemperature ?? config.default_temperature ?? 0.7,
          defaultMaxTokens: config.defaultMaxTokens ?? config.default_max_tokens ?? 4096,
          defaultTopP: config.defaultTopP ?? config.default_top_p ?? 0.9,
          fastProvider: config.fastProvider || config.fast_provider,
          fastModel: config.fastModel || config.fast_model,
          fastTemperature: config.fastTemperature ?? config.fast_temperature,
          fastMaxTokens: config.fastMaxTokens ?? config.fast_max_tokens,
          reasonerProvider: config.reasonerProvider || config.reasoner_provider,
          reasonerModel: config.reasonerModel || config.reasoner_model,
          reasonerTemperature: config.reasonerTemperature ?? config.reasoner_temperature,
          reasonerMaxTokens: config.reasonerMaxTokens ?? config.reasoner_max_tokens,
          visionProvider: config.visionProvider || config.vision_provider,
          visionModel: config.visionModel || config.vision_model,
          visionTemperature: config.visionTemperature ?? config.vision_temperature,
        }
      }
    } catch {
      // use defaults
    }
  }

  const updateModelConfig = async (config: Partial<ModelConfig>) => {
    saveStatus.value = 'saving'
    try {
      await apiPatch('/models/config', {
        provider: config.defaultProvider,
        model: config.defaultModel,
        temperature: config.defaultTemperature,
        maxTokens: config.defaultMaxTokens,
        topP: config.defaultTopP,
      })
      await fetchModelConfig()
      saveStatus.value = 'saved'
      setTimeout(() => { saveStatus.value = 'idle' }, 2000)
    } catch {
      saveStatus.value = 'error'
      setTimeout(() => { saveStatus.value = 'idle' }, 3000)
    }
  }

  return {
    providers,
    templates,
    modelConfig,
    loading,
    saveStatus,
    defaultProvider,
    allModels,
    getProviderModels,
    fetchProviders,
    fetchTemplates,
    addProvider,
    updateProvider,
    removeProvider,
    fetchProviderModels,
    fetchModelConfig,
    updateModelConfig,
  }
})

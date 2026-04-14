import type {
  ModelAsset,
  ModelListResult,
  ModelConfiguration,
  ModelAnimation,
  ModelInteraction,
  ModelVersion,
  PreviewResponse,
  ModelType,
  ModelStatus
} from '../types'

const API_BASE = '/api/v1'

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(error.detail || `Request failed: ${response.status}`)
  }
  if (response.status === 204) return undefined as T
  return response.json()
}

export const modelApi = {
  async list(params?: {
    model_type?: ModelType
    status?: ModelStatus
    search?: string
    page?: number
    page_size?: number
  }): Promise<ModelListResult> {
    const query = new URLSearchParams()
    if (params?.model_type) query.set('model_type', params.model_type)
    if (params?.status) query.set('status', params.status)
    if (params?.search) query.set('search', params.search)
    if (params?.page) query.set('page', String(params.page))
    if (params?.page_size) query.set('page_size', String(params.page_size))
    const qs = query.toString()
    return request(`/models${qs ? `?${qs}` : ''}`)
  },

  async get(modelId: string): Promise<ModelAsset> {
    return request(`/models/${modelId}`)
  },

  async upload(file: File, data: {
    name: string
    model_type: string
    description?: string
    tags?: string
    is_public?: boolean
  }): Promise<ModelAsset> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('name', data.name)
    formData.append('model_type', data.model_type)
    if (data.description) formData.append('description', data.description)
    if (data.tags) formData.append('tags', data.tags)
    if (data.is_public !== undefined) formData.append('is_public', String(data.is_public))

    const response = await fetch(`${API_BASE}/models`, {
      method: 'POST',
      body: formData
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(error.detail || 'Upload failed')
    }
    return response.json()
  },

  async update(modelId: string, data: Partial<ModelAsset>): Promise<ModelAsset> {
    return request(`/models/${modelId}`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    })
  },

  async delete(modelId: string): Promise<void> {
    return request(`/models/${modelId}`, { method: 'DELETE' })
  },

  async getVersions(modelId: string): Promise<ModelVersion[]> {
    return request(`/models/${modelId}/versions`)
  },

  async uploadVersion(modelId: string, file: File, changeLog?: string): Promise<ModelVersion> {
    const formData = new FormData()
    formData.append('file', file)
    if (changeLog) formData.append('change_log', changeLog)
    const response = await fetch(`${API_BASE}/models/${modelId}/versions`, {
      method: 'POST',
      body: formData
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(error.detail || 'Upload version failed')
    }
    return response.json()
  },

  async preview(modelId: string, configId?: string, animationId?: string): Promise<PreviewResponse> {
    return request(`/models/${modelId}/preview`, {
      method: 'POST',
      body: JSON.stringify({
        model_id: modelId,
        configuration_id: configId,
        animation_id: animationId
      })
    })
  },

  async getConfigurations(modelId: string): Promise<ModelConfiguration[]> {
    return request(`/models/${modelId}/configurations`)
  },

  async createConfiguration(modelId: string, data: Partial<ModelConfiguration>): Promise<ModelConfiguration> {
    return request(`/models/${modelId}/configurations`, {
      method: 'POST',
      body: JSON.stringify(data)
    })
  },

  async updateConfiguration(configId: string, data: Partial<ModelConfiguration>): Promise<ModelConfiguration> {
    return request(`/models/configurations/${configId}`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    })
  },

  async deleteConfiguration(configId: string): Promise<void> {
    return request(`/models/configurations/${configId}`, { method: 'DELETE' })
  },

  async getAnimations(modelId: string): Promise<ModelAnimation[]> {
    return request(`/models/${modelId}/animations`)
  },

  async createAnimation(modelId: string, data: Partial<ModelAnimation>): Promise<ModelAnimation> {
    return request(`/models/${modelId}/animations`, {
      method: 'POST',
      body: JSON.stringify(data)
    })
  },

  async updateAnimation(animationId: string, data: Partial<ModelAnimation>): Promise<ModelAnimation> {
    return request(`/models/animations/${animationId}`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    })
  },

  async deleteAnimation(animationId: string): Promise<void> {
    return request(`/models/animations/${animationId}`, { method: 'DELETE' })
  },

  async getInteractions(modelId: string): Promise<ModelInteraction[]> {
    return request(`/models/${modelId}/interactions`)
  },

  async createInteraction(modelId: string, data: Partial<ModelInteraction>): Promise<ModelInteraction> {
    return request(`/models/${modelId}/interactions`, {
      method: 'POST',
      body: JSON.stringify(data)
    })
  },

  async updateInteraction(interactionId: string, data: Partial<ModelInteraction>): Promise<ModelInteraction> {
    return request(`/models/interactions/${interactionId}`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    })
  },

  async deleteInteraction(interactionId: string): Promise<void> {
    return request(`/models/interactions/${interactionId}`, { method: 'DELETE' })
  }
}

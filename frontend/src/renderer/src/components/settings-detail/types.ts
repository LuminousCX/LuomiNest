export interface SectionItem {
  label: string
  desc: string
  type: string
}

export interface TtsEngineInfo {
  id: string
  name: string
  online: boolean
  available: boolean
  category?: string
  needs_api_key?: boolean
  default_voices?: Record<string, string>
  voices?: Array<{ id: string; name: string; lang: string }>
  lang_map?: Record<string, string>
}

export interface TtsDeviceInfo {
  type: string
  name: string
  cuda_available: boolean
  cuda_version?: string
}

export interface TtsBindingInfo {
  model_id: string
  voice: string
  voice_lang: string
  default_expression: string
}

import type { ProviderLogo } from '../types'

export const PROVIDER_LOGOS: Record<string, ProviderLogo> = {
  ollama: { id: 'ollama', name: 'Ollama', color: '#6366f1', initials: 'Ol' },
  openai: { id: 'openai', name: 'OpenAI', color: '#10a37f', initials: 'OA' },
  deepseek: { id: 'deepseek', name: 'DeepSeek', color: '#4d6bfe', initials: 'DS' },
  moonshot: { id: 'moonshot', name: 'Kimi', color: '#1a1a2e', initials: 'Ki' },
  dashscope: { id: 'dashscope', name: 'DashScope', color: '#ff6a00', initials: 'DQ' },
  zhipu: { id: 'zhipu', name: 'ZhiPu', color: '#3b5cff', initials: 'ZP' },
  qwen: { id: 'qwen', name: 'Qwen', color: '#615bff', initials: 'Qw' },
  siliconflow: { id: 'siliconflow', name: 'SiliconFlow', color: '#7c3aed', initials: 'SF' },
  lmstudio: { id: 'lmstudio', name: 'LM Studio', color: '#0ea5e9', initials: 'LM' },
  gemini: { id: 'gemini', name: 'Gemini', color: '#4285f4', initials: 'Ge' },
  claude: { id: 'claude', name: 'Claude', color: '#d97706', initials: 'Cl' },
}

export const getProviderLogo = (providerId: string): ProviderLogo => {
  return PROVIDER_LOGOS[providerId] || { id: providerId, name: providerId, color: '#6b7280', initials: providerId.slice(0, 2).toUpperCase() }
}

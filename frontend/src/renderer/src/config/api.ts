/**
 * 解析 API 基础地址。
 * - 显式配置 VITE_API_BASE_URL 时优先使用（便于自定义反向代理/远程后端）。
 * - Electron 打包环境（window.api 存在）使用相对路径，避免 file:///null origin 下的 CORS 问题。
 * - 开发环境回退到本地后端地址。
 */

/** 开发环境默认后端地址 */
export const LUOMINEST_DEFAULT_API_BASE_URL = 'http://127.0.0.1:18000'

const resolveApiBaseUrl = (): string => {
  const configured = import.meta.env.VITE_API_BASE_URL as string | undefined
  if (configured) return configured

  const isElectron = typeof window !== 'undefined' && 'api' in window
  if (isElectron) return ''

  return LUOMINEST_DEFAULT_API_BASE_URL
}

const API_BASE_URL = resolveApiBaseUrl()

export const API_ENDPOINTS = {
  UPLOAD_FORWARD: `${API_BASE_URL}/api/upload/forward`,
  HEALTH: `${API_BASE_URL}/health`,
  V1: `${API_BASE_URL}/api/v1`,
  TTS_SYNTHESIZE: `${API_BASE_URL}/api/v1/chat/tts/synthesize`,
}

export { API_BASE_URL }

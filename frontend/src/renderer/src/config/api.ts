/**
 * 解析 API 基础地址。
 * - 显式配置 VITE_API_BASE_URL 时优先使用（便于自定义反向代理/远程后端）。
 * - 否则统一使用本地后端地址 http://127.0.0.1:18000。
 *
 * 说明：早期 Electron 打包环境（file:// origin）曾返回空相对路径以规避 CORS，
 * 但这会导致 API_ENDPOINTS.UPLOAD_FORWARD / TTS_SYNTHESIZE / HEALTH 等绝对地址
 * 解析到 file:// 资源而失败。后端在 frozen 模式下已将 "null"/"file://" 加入
 * CORS_ORIGINS（见 backend/app/core/config.py），因此 Electron 可直接使用完整 URL。
 */

/** 开发环境默认后端地址 */
export const LUOMINEST_DEFAULT_API_BASE_URL = 'http://127.0.0.1:18000'

const resolveApiBaseUrl = (): string => {
  const configured = import.meta.env.VITE_API_BASE_URL as string | undefined
  if (configured) return configured

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

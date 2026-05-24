const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:18000'

export const API_ENDPOINTS = {
  UPLOAD_FORWARD: `${API_BASE_URL}/api/upload/forward`,
  HEALTH: `${API_BASE_URL}/health`,
  V1: `${API_BASE_URL}/api/v1`,
}

export { API_BASE_URL }

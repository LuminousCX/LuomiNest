/**
 * JWT 令牌的 localStorage 存取唯一入口。
 * 原 LoginView / SettingsLoginSection / useWelcomeWizard 三处各自定义同一组 key，
 * 现收敛于此（key 字符串保持不变，登录态互通行为不变——见调查报告 §N3）。
 */

const JWT_ACCESS_TOKEN_KEY = 'lumi_jwt_access_token'
const JWT_REFRESH_TOKEN_KEY = 'lumi_jwt_refresh_token'

export function getStoredAccessToken(): string | null {
  return localStorage.getItem(JWT_ACCESS_TOKEN_KEY)
}

export function getStoredRefreshToken(): string | null {
  return localStorage.getItem(JWT_REFRESH_TOKEN_KEY)
}

export function setStoredTokens(accessToken: string, refreshToken?: string): void {
  localStorage.setItem(JWT_ACCESS_TOKEN_KEY, accessToken)
  if (refreshToken) localStorage.setItem(JWT_REFRESH_TOKEN_KEY, refreshToken)
}

export function clearStoredTokens(): void {
  localStorage.removeItem(JWT_ACCESS_TOKEN_KEY)
  localStorage.removeItem(JWT_REFRESH_TOKEN_KEY)
}

export function hasStoredAccessToken(): boolean {
  return getStoredAccessToken() !== null
}

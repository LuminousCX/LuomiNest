export interface Tab {
  id: string
  title: string
  url: string
  favicon?: string
  loading: boolean
  error?: TabError
  active: boolean
  createdAt: number
  lastActiveAt: number
  captchaDetected?: boolean
  sleeping?: boolean
}

export interface TabError {
  code: number
  title: string
  message: string
}

export interface BrowserBounds {
  x: number
  y: number
  width: number
  height: number
}

export interface BoundsConfig {
  sidebarWidth: number
  devPanelHeight: number
}

export interface NavigationState {
  canGoBack: boolean
  canGoForward: boolean
}

export interface FindResult {
  requestId: number
  activeMatchOrdinal: number
  matches: number
  selectionArea: Electron.Rectangle
}

export type TabEventType = 
  | 'created'
  | 'activated'
  | 'closed'
  | 'updated'
  | 'loading'
  | 'loaded'
  | 'error'
  | 'favicon'

export interface TabEvent {
  type: TabEventType
  tabId: string
  data?: Partial<Tab>
}

export interface BrowserConfig {
  defaultUrl: string
  homePage: string
  maxTabs: number
  sessionPartition: string
  sleepTimeout: number
}

export const DEFAULT_BROWSER_CONFIG: BrowserConfig = {
  defaultUrl: 'about:blank',
  homePage: 'about:blank',
  maxTabs: 50,
  sessionPartition: 'persist:luominest-browser',
  sleepTimeout: 300000
}

export const BROWSER_LAYOUT = {
  TITLE_BAR_HEIGHT: 34,
  TAB_BAR_HEIGHT: 38,
  NAV_BAR_HEIGHT: 52,
  BOOKMARK_BAR_HEIGHT: 34,
  get TOTAL_HEADER_HEIGHT() {
    return this.TITLE_BAR_HEIGHT + this.TAB_BAR_HEIGHT + this.NAV_BAR_HEIGHT + this.BOOKMARK_BAR_HEIGHT
  }
}

export const ERROR_CODES: Record<number, { title: string; message: string }> = {
  [-2]: { title: 'DNS 解析失败', message: '无法解析服务器地址，请检查域名是否正确' },
  [-3]: { title: '连接失败', message: '无法连接到服务器，请检查网络连接' },
  [-6]: { title: '文件未找到', message: '请求的资源不存在' },
  [-7]: { title: '连接超时', message: '服务器响应超时，请稍后重试' },
  [-21]: { title: '访问被拒绝', message: '您没有权限访问此页面' },
  [-100]: { title: '连接被重置', message: '网络连接被重置' },
  [-101]: { title: '连接被拒绝', message: '服务器拒绝了连接请求' },
  [-102]: { title: '网络已断开', message: '您的网络连接已断开' },
  [-105]: { title: 'DNS 解析失败', message: '无法解析服务器地址' },
  [-106]: { title: '网络已断开', message: '请检查网络设置' },
  [-118]: { title: '连接超时', message: '连接服务器超时' },
  [-200]: { title: '证书错误', message: '网站安全证书无效' },
  [-300]: { title: '无效地址', message: '网址格式不正确' },
  [-324]: { title: '连接被重置', message: '服务器重置了连接' },
  [-502]: { title: '网关错误', message: '服务器作为网关时收到无效响应' },
  [-503]: { title: '服务不可用', message: '服务器暂时无法处理请求' },
  [-504]: { title: '网关超时', message: '网关服务器响应超时' }
}

export function getErrorInfo(code: number): TabError {
  const known = ERROR_CODES[code]
  if (known) {
    return { code, ...known }
  }
  return {
    code,
    title: '加载失败',
    message: `页面加载失败 (错误码: ${code})`
  }
}

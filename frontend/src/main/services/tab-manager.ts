import { WebContentsView, BrowserWindow, session } from 'electron'

interface TabState {
  id: string
  title: string
  url: string
  active: boolean
  loading?: boolean
  error?: string
}

interface BoundsConfig {
  sidebarWidth: number
  devPanelHeight: number
}

let mainWindow: BrowserWindow | null = null
let currentView: WebContentsView | null = null
let currentTabId: string | null = null
const tabStates = new Map<string, TabState>()
let boundsConfig: BoundsConfig = {
  sidebarWidth: 60,
  devPanelHeight: 0
}

const TITLE_BAR_HEIGHT = 34
const TAB_BAR_HEIGHT = 38
const NAV_BAR_HEIGHT = 52
const BOOKMARK_BAR_HEIGHT = 34
const TOTAL_HEADER_HEIGHT = TITLE_BAR_HEIGHT + TAB_BAR_HEIGHT + NAV_BAR_HEIGHT + BOOKMARK_BAR_HEIGHT

const BROWSER_SESSION_PARTITION = 'persist:luminest-browser'

function getCleanUserAgent(): string {
  const chromeVersion = '131.0.0.0'
  const baseUA = `Mozilla/5.0 ({os_info}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${chromeVersion} Safari/537.36 Edg/${chromeVersion}`

  let osInfo = ''
  switch (process.platform) {
    case 'darwin':
      osInfo = 'Macintosh; Intel Mac OS X 10_15_7'
      break
    case 'win32':
      osInfo = 'Windows NT 10.0; Win64; x64'
      break
    case 'linux':
      osInfo = 'X11; Linux x86_64'
      break
    default:
      osInfo = 'Windows NT 10.0; Win64; x64'
  }

  return baseUA.replace('{os_info}', osInfo)
}

const REAL_USER_AGENT = getCleanUserAgent()

const STEALTH_INJECT_SCRIPT = `
(function() {
  try {
    Object.defineProperty(navigator, 'webdriver', {
      get: () => undefined,
      configurable: true
    });

    Object.defineProperty(navigator, 'languages', {
      get: () => ['zh-CN', 'zh', 'en-US', 'en'],
      configurable: true
    });

    if (window.chrome) {
      window.chrome.runtime = window.chrome.runtime || {};
    }
  } catch (e) {}
})();
`

export function setMainWindow(win: BrowserWindow): void {
  mainWindow = win
  initBrowserSession()
}

function initBrowserSession(): void {
  const browserSession = session.fromPartition(BROWSER_SESSION_PARTITION)

  browserSession.webRequest.onBeforeSendHeaders((details, callback) => {
    details.requestHeaders['User-Agent'] = REAL_USER_AGENT
    details.requestHeaders['Accept-Language'] = 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7'
    details.requestHeaders['sec-ch-ua'] = '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"'
    details.requestHeaders['sec-ch-ua-mobile'] = '?0'
    details.requestHeaders['sec-ch-ua-platform'] = '"Windows"'
    callback({ requestHeaders: details.requestHeaders })
  })

  browserSession.setUserAgent(REAL_USER_AGENT)
}

export function setBoundsConfig(config: Partial<BoundsConfig>): void {
  boundsConfig = { ...boundsConfig, ...config }
  updateCurrentViewBounds()
}

function getAvailableBounds(): { x: number; y: number; width: number; height: number } {
  if (!mainWindow) {
    return {
      x: boundsConfig.sidebarWidth,
      y: TOTAL_HEADER_HEIGHT,
      width: 800 - boundsConfig.sidebarWidth,
      height: 600 - TOTAL_HEADER_HEIGHT
    }
  }

  const [winWidth, winHeight] = mainWindow.getSize()

  return {
    x: boundsConfig.sidebarWidth,
    y: TOTAL_HEADER_HEIGHT,
    width: Math.max(100, winWidth - boundsConfig.sidebarWidth),
    height: Math.max(100, winHeight - TOTAL_HEADER_HEIGHT - boundsConfig.devPanelHeight)
  }
}

function updateCurrentViewBounds(): void {
  if (!mainWindow || !currentView) return

  const bounds = getAvailableBounds()
  currentView.setBounds(bounds)
}

function setupViewEventHandlers(view: WebContentsView, tabState: TabState): void {
  view.webContents.on('page-title-updated', (_e, title) => {
    tabState.title = title
    // 通知前端更新标签标题
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('browser:tab-updated', {
        id: tabState.id,
        title: title,
        url: tabState.url
      })
    }
  })

  view.webContents.on('did-navigate', (_e, navigatedUrl) => {
    tabState.url = navigatedUrl
    // 通知前端更新 URL
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('browser:tab-updated', {
        id: tabState.id,
        title: tabState.title,
        url: navigatedUrl
      })
    }
  })

  view.webContents.on('did-navigate-in-page', (_e, navigatedUrl) => {
    tabState.url = navigatedUrl
    // 通知前端更新 URL
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('browser:tab-updated', {
        id: tabState.id,
        title: tabState.title,
        url: navigatedUrl
      })
    }
  })

  view.webContents.on('page-favicon-updated', (_e, favicons) => {
    // 通知前端更新 favicon
    if (mainWindow && !mainWindow.isDestroyed() && favicons.length > 0) {
      mainWindow.webContents.send('browser:tab-favicon', {
        id: tabState.id,
        favicon: favicons[0]
      })
    }
  })

  view.webContents.setWindowOpenHandler((details) => {
    const { url } = details

    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('browser:create-tab', url)
    }

    return { action: 'deny' }
  })

  view.webContents.on('did-finish-load', () => {
    view.webContents.executeJavaScript(STEALTH_INJECT_SCRIPT).catch(() => {})
  })
}

function createBrowserView(): WebContentsView {
  const view = new WebContentsView({
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      webSecurity: true,
      partition: BROWSER_SESSION_PARTITION,
      webgl: true,
      plugins: true,
      enableWebSQL: false,
      spellcheck: false
    }
  })

  view.webContents.setUserAgent(REAL_USER_AGENT)
  view.webContents.session.setPermissionRequestHandler((_, permission, callback) => {
    if (permission === 'media' || permission === 'mediaKeySystem') {
      callback(false)
    } else {
      callback(true)
    }
  })

  return view
}

function addViewToWindow(view: WebContentsView): void {
  if (!mainWindow) return
  mainWindow.contentView.addChildView(view)
}

function removeViewFromWindow(view: WebContentsView): void {
  if (!mainWindow) return
  try {
    mainWindow.contentView.removeChildView(view)
  } catch {
    // View may already be removed
  }
}

export function createManagedTab(url = 'about:blank'): TabState {
  if (!mainWindow) throw new Error('Main window not initialized')

  const tabId = `tab-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`

  if (currentView && mainWindow) {
    removeViewFromWindow(currentView)
    currentView.webContents.close()
    currentView = null
  }

  tabStates.forEach((state) => {
    state.active = false
  })

  currentView = createBrowserView()
  addViewToWindow(currentView)

  const bounds = getAvailableBounds()
  currentView.setBounds(bounds)

  const tabState: TabState = {
    id: tabId,
    title: '加载中...',
    url,
    active: true,
    loading: true,
    error: undefined
  }

  setupViewEventHandlers(currentView, tabState)

  tabStates.set(tabId, tabState)
  currentTabId = tabId

  currentView.webContents.loadURL(url).then(() => {
    tabState.loading = false
    const title = currentView?.webContents.getTitle()
    if (title && title !== 'about:blank') {
      tabState.title = title
    }
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('browser:tab-updated', {
        id: tabState.id,
        title: tabState.title,
        url: tabState.url,
        loading: false
      })
    }
  }).catch((err) => {
    console.error('[LuomiNest] Failed to load URL:', err)
    tabState.loading = false
    tabState.title = '加载失败'
    tabState.error = err.code || 'ERR_FAILED'
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('browser:tab-updated', {
        id: tabState.id,
        title: '加载失败',
        url: tabState.url,
        loading: false,
        error: tabState.error
      })
    }
  })

  return { ...tabState }
}

export function activateTab(tabId: string): void {
  if (!mainWindow) return

  const targetState = tabStates.get(tabId)
  if (!targetState) {
    console.warn('[LuomiNest] Tab not found:', tabId)
    return
  }

  if (currentTabId === tabId) {
    return
  }

  tabStates.forEach((state) => {
    state.active = state.id === tabId
  })

  if (currentView) {
    removeViewFromWindow(currentView)
    currentView.webContents.close()
    currentView = null
  }

  currentView = createBrowserView()
  addViewToWindow(currentView)

  const bounds = getAvailableBounds()
  currentView.setBounds(bounds)

  setupViewEventHandlers(currentView, targetState)

  currentTabId = tabId

  currentView.webContents.loadURL(targetState.url).then(() => {
    const title = currentView?.webContents.getTitle()
    if (title && title !== 'about:blank') {
      targetState.title = title
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('browser:tab-updated', {
          id: targetState.id,
          title: title,
          url: targetState.url
        })
      }
    }
  }).catch((err) => {
    console.error('[LuomiNest] Failed to load URL:', err)
    targetState.title = '加载失败'
  })
}

export function closeManagedTab(tabId: string): void {
  const state = tabStates.get(tabId)
  if (!state) return

  tabStates.delete(tabId)

  if (currentTabId === tabId) {
    if (currentView && mainWindow) {
      removeViewFromWindow(currentView)
      currentView.webContents.close()
      currentView = null
    }

    currentTabId = null

    const remaining = Array.from(tabStates.keys())
    if (remaining.length > 0) {
      activateTab(remaining[remaining.length - 1])
    }
  }
}

export function getAllManagedTabs(): TabState[] {
  return Array.from(tabStates.values())
}

export function getActiveTab(): TabState | undefined {
  if (!currentTabId) return undefined
  return tabStates.get(currentTabId)
}

export function hideAllTabs(): void {
  if (!mainWindow || !currentView) return

  removeViewFromWindow(currentView)
  currentView.webContents.close()
  currentView = null
}

export function cleanupAllTabs(): void {
  if (currentView && mainWindow) {
    removeViewFromWindow(currentView)
    currentView.webContents.close()
    currentView = null
  }
  currentTabId = null
  tabStates.clear()
}

export function handleWindowResize(): void {
  updateCurrentViewBounds()
}

export function getBrowserSession() {
  return session.fromPartition(BROWSER_SESSION_PARTITION)
}

export async function getCookies(): Promise<Electron.Cookie[]> {
  const browserSession = session.fromPartition(BROWSER_SESSION_PARTITION)
  return browserSession.cookies.get({})
}

export async function clearBrowserData(): Promise<void> {
  const browserSession = session.fromPartition(BROWSER_SESSION_PARTITION)
  await browserSession.clearStorageData()
  await browserSession.clearCache()
}

import { BrowserWindow, WebContentsView } from 'electron'
import { Tab, TabError, BoundsConfig, getErrorInfo, DEFAULT_BROWSER_CONFIG, NavigationState } from './types'
import { initBrowserSession } from './session'
import {
  createBrowserView,
  calculateBounds,
  setViewBounds,
  attachView,
  detachView,
  injectStealthScript,
  isViewDestroyed
} from './view'

type TabUpdateCallback = (tabId: string, updates: Partial<Tab>) => void
type TabEventCallback = (event: string, data: any) => void

const CAPTCHA_PATTERNS = [
  /google\.com\/sorry\//i,
  /google\.com\/search.*btnI=/i,
  /google\.com\/search.*sorry/i,
  /recaptcha/i,
  /captcha/i,
  /accounts\.google\.com\/sorry/i
]

function isCaptchaUrl(url: string): boolean {
  return CAPTCHA_PATTERNS.some(pattern => pattern.test(url))
}

class TabManager {
  private window: BrowserWindow | null = null
  private tabs: Map<string, Tab> = new Map()
  private views: Map<string, WebContentsView> = new Map()
  private activeTabId: string | null = null
  private boundsConfig: BoundsConfig = {
    sidebarWidth: 60,
    devPanelHeight: 0
  }
  private onTabUpdate: TabUpdateCallback | null = null
  private onTabEvent: TabEventCallback | null = null
  private sleepCheckInterval: ReturnType<typeof setInterval> | null = null

  setWindow(window: BrowserWindow): void {
    this.window = window
    initBrowserSession()
    this.startSleepChecker()
  }

  setCallbacks(onUpdate: TabUpdateCallback, onEvent: TabEventCallback): void {
    this.onTabUpdate = onUpdate
    this.onTabEvent = onEvent
  }

  setBoundsConfig(config: Partial<BoundsConfig>): void {
    this.boundsConfig = { ...this.boundsConfig, ...config }
    this.updateActiveViewBounds()
  }

  private generateTabId(): string {
    return `tab-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
  }

  private notifyUpdate(tabId: string, updates: Partial<Tab>): void {
    const tab = this.tabs.get(tabId)
    if (tab) {
      Object.assign(tab, updates)
      this.onTabUpdate?.(tabId, updates)
    }
  }

  private updateActiveViewBounds(): void {
    if (!this.window || !this.activeTabId) return

    const view = this.views.get(this.activeTabId)
    if (view) {
      const bounds = calculateBounds(this.window, this.boundsConfig)
      setViewBounds(view, bounds)
    }
  }

  private setupViewEvents(view: WebContentsView, tabId: string): void {
    const webContents = view.webContents

    webContents.on('page-title-updated', (_e, title) => {
      if (title && title !== 'about:blank') {
        this.notifyUpdate(tabId, { title })
      }
    })

    webContents.on('did-navigate', (_e, url) => {
      const captchaDetected = isCaptchaUrl(url)
      this.notifyUpdate(tabId, {
        url,
        loading: false,
        error: undefined,
        captchaDetected
      })
      this.emitNavigationState(tabId)
    })

    webContents.on('did-navigate-in-page', (_e, url) => {
      const captchaDetected = isCaptchaUrl(url)
      this.notifyUpdate(tabId, { url, captchaDetected })
      this.emitNavigationState(tabId)
    })

    webContents.on('page-favicon-updated', (_e, favicons) => {
      if (favicons.length > 0) {
        this.notifyUpdate(tabId, { favicon: favicons[0] })
      }
    })

    webContents.setWindowOpenHandler((details) => {
      this.onTabEvent?.('new-tab-request', { url: details.url })
      return { action: 'deny' }
    })

    webContents.on('did-finish-load', async () => {
      this.notifyUpdate(tabId, { loading: false })
      await injectStealthScript(view)
      this.emitNavigationState(tabId)
    })

    webContents.on('did-fail-load', (_event, errorCode, _errorDescription, validatedURL) => {
      if (this.isAbortError(errorCode)) return

      const tab = this.tabs.get(tabId)
      if (!tab?.active) {
        this.notifyUpdate(tabId, { loading: false })
        return
      }

      const error = getErrorInfo(errorCode)
      this.notifyUpdate(tabId, { loading: false, error, title: error.title })
    })

    webContents.on('did-start-loading', () => {
      const tab = this.tabs.get(tabId)
      this.notifyUpdate(tabId, { loading: true, error: tab?.active ? undefined : tab?.error })
    })

    webContents.on('did-stop-loading', () => {
      this.notifyUpdate(tabId, { loading: false })
    })
  }

  private emitNavigationState(tabId: string): void {
    const view = this.views.get(tabId)
    if (!view || isViewDestroyed(view)) return
    const webContents = view.webContents
    const state: NavigationState = {
      canGoBack: webContents.navigationHistory.canGoBack(),
      canGoForward: webContents.navigationHistory.canGoForward()
    }
    this.onTabEvent?.('navigation-state', { tabId, ...state })
  }

  private isAbortError(code: number): boolean {
    return [-3, -27, -300, -301, -302].includes(code)
  }

  private startSleepChecker(): void {
    if (this.sleepCheckInterval) return
    this.sleepCheckInterval = setInterval(() => {
      this.checkSleepTabs()
    }, 60000)
  }

  private stopSleepChecker(): void {
    if (this.sleepCheckInterval) {
      clearInterval(this.sleepCheckInterval)
      this.sleepCheckInterval = null
    }
  }

  private checkSleepTabs(): void {
    const now = Date.now()
    const sleepTimeout = DEFAULT_BROWSER_CONFIG.sleepTimeout

    this.tabs.forEach((tab, tabId) => {
      if (tab.active || tab.sleeping || !tab.url) return
      if (tab.loading) return

      const idleTime = now - tab.lastActiveAt
      if (idleTime >= sleepTimeout) {
        this.sleepTab(tabId)
      }
    })
  }

  private sleepTab(tabId: string): void {
    const tab = this.tabs.get(tabId)
    if (!tab || tab.sleeping || tab.active) return

    const view = this.views.get(tabId)
    if (view) {
      try {
        if (!isViewDestroyed(view)) {
          view.webContents.close()
        }
      } catch {}
      this.views.delete(tabId)
    }

    this.notifyUpdate(tabId, { sleeping: true, loading: false })
    console.info(`[INFO][LuomiNestBrowser] Tab "${tab.title}" has entered sleep mode to conserve resources`)
  }

  private async wakeTab(tabId: string): Promise<void> {
    const tab = this.tabs.get(tabId)
    if (!tab || !tab.sleeping) return

    this.notifyUpdate(tabId, { sleeping: false, loading: true })

    const view = createBrowserView()
    this.setupViewEvents(view, tabId)
    this.views.set(tabId, view)

    if (this.window && tab.active) {
      attachView(this.window, view)
      const bounds = calculateBounds(this.window, this.boundsConfig)
      setViewBounds(view, bounds)

      try {
        view.webContents.setBackgroundThrottling(false)
      } catch {}
    }

    try {
      await view.webContents.loadURL(tab.url)
    } catch (err: any) {
      if (!err.message?.includes('ERR_ABORTED')) {
        const error = getErrorInfo(typeof err.code === 'number' ? err.code : -1)
        this.notifyUpdate(tabId, { loading: false, error, title: error.title })
      }
    }

    console.info(`[INFO][LuomiNestBrowser] Tab "${tab.title}" has been awakened from sleep mode`)
  }

  createTab(url: string = DEFAULT_BROWSER_CONFIG.defaultUrl): Tab {
    if (!this.window) {
      throw new Error('Window not initialized')
    }

    const tabId = this.generateTabId()

    if (this.activeTabId) {
      const currentTab = this.tabs.get(this.activeTabId)
      if (currentTab) {
        currentTab.active = false
        currentTab.lastActiveAt = Date.now()

        const currentView = this.views.get(this.activeTabId)
        if (currentView) {
          detachView(this.window, currentView)
          try {
            currentView.webContents.setBackgroundThrottling(true)
          } catch {}
        }
      }
    }

    const view = createBrowserView()
    this.setupViewEvents(view, tabId)

    const tab: Tab = {
      id: tabId,
      title: '加载中...',
      url,
      loading: true,
      active: true,
      createdAt: Date.now(),
      lastActiveAt: Date.now()
    }

    this.tabs.set(tabId, tab)
    this.views.set(tabId, view)
    this.activeTabId = tabId

    attachView(this.window, view)
    const bounds = calculateBounds(this.window, this.boundsConfig)
    setViewBounds(view, bounds)

    view.webContents.loadURL(url).catch((err) => {
      if (!err.message?.includes('ERR_ABORTED')) {
        const error = getErrorInfo(typeof err.code === 'number' ? err.code : -1)
        this.notifyUpdate(tabId, { loading: false, error, title: error.title })
      }
    })

    return { ...tab }
  }

  async activateTab(tabId: string): Promise<void> {
    if (!this.window) return

    const targetTab = this.tabs.get(tabId)
    if (!targetTab) return

    if (this.activeTabId && this.activeTabId !== tabId) {
      const currentTab = this.tabs.get(this.activeTabId)
      if (currentTab) {
        currentTab.active = false
        currentTab.lastActiveAt = Date.now()

        const currentView = this.views.get(this.activeTabId)
        if (currentView) {
          detachView(this.window, currentView)
          try {
            currentView.webContents.setBackgroundThrottling(true)
          } catch {}
        }
      }
    }

    targetTab.active = true
    targetTab.lastActiveAt = Date.now()
    this.activeTabId = tabId

    if (targetTab.sleeping) {
      await this.wakeTab(tabId)
      return
    }

    const targetView = this.views.get(tabId)
    if (targetView) {
      try {
        targetView.webContents.setBackgroundThrottling(false)
      } catch {}
      attachView(this.window, targetView)
      const bounds = calculateBounds(this.window, this.boundsConfig)
      setViewBounds(targetView, bounds)
    }

    this.onTabUpdate?.(tabId, { active: true })
    this.emitNavigationState(tabId)
  }

  closeTab(tabId: string): void {
    if (!this.window) return
    if (this.tabs.size <= 1) return

    const tab = this.tabs.get(tabId)
    if (!tab) return

    const view = this.views.get(tabId)
    if (view) {
      detachView(this.window, view)
      if (!isViewDestroyed(view)) {
        view.webContents.close()
      }
      this.views.delete(tabId)
    }

    this.tabs.delete(tabId)

    if (this.activeTabId === tabId) {
      const remainingTabs = Array.from(this.tabs.values())
      const nextTab = remainingTabs[remainingTabs.length - 1]
      if (nextTab) {
        this.activateTab(nextTab.id)
      } else {
        this.activeTabId = null
      }
    }
  }

  reloadTab(tabId?: string): void {
    const targetId = tabId || this.activeTabId
    if (!targetId) return

    const tab = this.tabs.get(targetId)
    if (tab?.sleeping) {
      this.wakeTab(targetId)
      return
    }

    const view = this.views.get(targetId)
    if (view && !isViewDestroyed(view)) {
      view.webContents.reload()
    }
  }

  goBack(tabId?: string): void {
    const targetId = tabId || this.activeTabId
    if (!targetId) return

    const view = this.views.get(targetId)
    if (view && !isViewDestroyed(view) && view.webContents.navigationHistory.canGoBack()) {
      view.webContents.navigationHistory.goBack()
    }
  }

  goForward(tabId?: string): void {
    const targetId = tabId || this.activeTabId
    if (!targetId) return

    const view = this.views.get(targetId)
    if (view && !isViewDestroyed(view) && view.webContents.navigationHistory.canGoForward()) {
      view.webContents.navigationHistory.goForward()
    }
  }

  getNavigationState(tabId?: string): NavigationState {
    const targetId = tabId || this.activeTabId
    if (!targetId) return { canGoBack: false, canGoForward: false }

    const tab = this.tabs.get(targetId)
    if (tab?.sleeping) return { canGoBack: true, canGoForward: false }

    const view = this.views.get(targetId)
    if (!view || isViewDestroyed(view)) return { canGoBack: false, canGoForward: false }

    return {
      canGoBack: view.webContents.navigationHistory.canGoBack(),
      canGoForward: view.webContents.navigationHistory.canGoForward()
    }
  }

  hideAll(): void {
    if (!this.window) return

    this.views.forEach((view) => {
      detachView(this.window!, view)
    })
  }

  showActive(): void {
    if (!this.window || !this.activeTabId) return

    const tab = this.tabs.get(this.activeTabId)
    if (!tab) return

    if (tab.sleeping) {
      this.wakeTab(this.activeTabId)
      return
    }

    const view = this.views.get(this.activeTabId)
    if (view) {
      try {
        view.webContents.setBackgroundThrottling(false)
      } catch {}
      attachView(this.window, view)
      const bounds = calculateBounds(this.window, this.boundsConfig)
      setViewBounds(view, bounds)
    }
  }

  getTab(tabId: string): Tab | undefined {
    return this.tabs.get(tabId)
  }

  getActiveTab(): Tab | undefined {
    if (!this.activeTabId) return undefined
    return this.tabs.get(this.activeTabId)
  }

  getAllTabs(): Tab[] {
    return Array.from(this.tabs.values())
  }

  cleanup(): void {
    if (!this.window) return

    this.stopSleepChecker()

    this.views.forEach((view) => {
      detachView(this.window!, view)
      if (!isViewDestroyed(view)) {
        view.webContents.close()
      }
    })

    this.views.clear()
    this.tabs.clear()
    this.activeTabId = null
  }

  handleResize(): void {
    this.updateActiveViewBounds()
  }
}

export const tabManager = new TabManager()

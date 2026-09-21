import { BrowserWindow, WebContentsView, WebContents, NativeImage } from 'electron'
import { Tab, TabError, BoundsConfig, getErrorInfo, DEFAULT_BROWSER_CONFIG, NavigationState } from './types'
import { initBrowserSession, setDownloadBlockedCallback } from './session'
import {
  createBrowserView,
  calculateBounds,
  setViewBounds,
  attachView,
  detachView,
  injectStealthScript,
  isViewDestroyed
} from './view'
import { createLuomiNestLogger } from '../luomi-logger'

const logger = createLuomiNestLogger('Browser')

type TabUpdateCallback = (tabId: string, updates: Partial<Tab>) => void
type TabEventCallback = (event: string, data: unknown) => void

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

/**
 * OAuth 登录常见域名（W4-6）。
 *
 * 核实结论：setWindowOpenHandler 对所有 window.open 一律 deny，并通过
 * 'new-tab-request' 事件 → main/index.ts 回调 → `tab:new-tab-request` push →
 * BrowserView.vue handleNewTabRequest 新建标签页打开，链路已完整覆盖——
 * 以下域名的弹窗同样会以新标签承载、不会被完全丢弃。
 * 因此无需（也不应）对 OAuth 域名改 allow 打开独立弹窗视图：那会脱离标签页
 * 管理，且 AI 独立会话分区未落地（修改书 W4-4 备选不做）。此名单保留为
 * 日志标记与后续策略扩展的挂载点。
 */
const OAUTH_WINDOW_OPEN_DOMAINS = [
  'accounts.google.com',
  'login.microsoftonline.com',
  'login.live.com',
  'github.com/login',
  'open.weixin.qq.com',
  'graph.qq.com',
  'open.dingtalk.com',
  'api.weibo.com',
  'auth.alipay.com',
  'access.line.me'
]

function isOAuthWindowOpenUrl(url: string): boolean {
  return OAUTH_WINDOW_OPEN_DOMAINS.some((fragment) => url.includes(fragment))
}

/** W4-5：唤醒休眠标签的等待上限（loadURL 挂起时不无限阻塞截图请求） */
const WAKE_TIMEOUT_MS = 20000
/** W4-5：降级激活截屏后等待合成器产出首帧的延迟 */
const CAPTURE_FALLBACK_DELAY_MS = 150

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
    // W4-6：下载拦截通知经 tab 事件通道转发（main/index.ts 统一 push 为
    // `tab:download-blocked`，后缀与 IpcChannels.tab.push.downloadBlocked 一致）
    setDownloadBlockedCallback((info) => this.onTabEvent?.('download-blocked', info))
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

    // contextIsolation: true 时 preload 无法修改页面原型链，
    // 改为在每次导航开始时通过 executeJavaScript 将 stealth 脚本注入到 main world
    webContents.on('did-start-navigation', (_e, _url, isInPlace, isMainFrame) => {
      if (isMainFrame && !isInPlace) {
        injectStealthScript(view).catch(() => {})
      }
    })

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
        captchaDetected,
        // 成功导航即脱离风控拦截态（W4-8），避免残留标记污染后续黄条文案
        riskBlocked: false
      })
      this.emitNavigationState(tabId)
    })

    webContents.on('did-navigate-in-page', (_e, url) => {
      const captchaDetected = isCaptchaUrl(url)
      this.notifyUpdate(tabId, { url, captchaDetected, riskBlocked: false })
      this.emitNavigationState(tabId)
    })

    webContents.on('page-favicon-updated', (_e, favicons) => {
      if (favicons.length > 0) {
        this.notifyUpdate(tabId, { favicon: favicons[0] })
      }
    })

    webContents.setWindowOpenHandler((details) => {
      // W4-6：window.open 一律 deny → 'new-tab-request' 由渲染层新开标签承载；
      // OAuth 弹窗域名（OAUTH_WINDOW_OPEN_DOMAINS）同样走该链路，见其注释核实结论
      if (isOAuthWindowOpenUrl(details.url)) {
        logger.info(`OAuth window.open 转发新标签打开: ${details.url}`)
      }
      this.onTabEvent?.('new-tab-request', { url: details.url })
      return { action: 'deny' }
    })

    webContents.on('did-finish-load', async () => {
      this.notifyUpdate(tabId, { loading: false })
      this.emitNavigationState(tabId)
    })

    webContents.on('did-fail-load', (_event, errorCode, _errorDescription, validatedURL) => {
      if (this.isAbortError(errorCode)) return

      // W4-8：412/403 视为站点风控拦截，与 captchaDetected 共用黄条展示「该网站风控拦截」
      const riskBlocked = errorCode === 412 || errorCode === 403

      const tab = this.tabs.get(tabId)
      if (!tab?.active) {
        // 后台标签不更新错误页，但风控标记仍需登记，切到该标签时黄条可提示
        if (riskBlocked) {
          this.notifyUpdate(tabId, { loading: false, riskBlocked: true, captchaDetected: true })
        } else {
          this.notifyUpdate(tabId, { loading: false })
        }
        return
      }

      const error = getErrorInfo(errorCode)
      if (riskBlocked) {
        this.notifyUpdate(tabId, {
          loading: false,
          error,
          title: error.title,
          riskBlocked: true,
          captchaDetected: true
        })
      } else {
        this.notifyUpdate(tabId, { loading: false, error, title: error.title })
      }
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
    logger.info(`Tab "${tab.title}" has entered sleep mode to conserve resources`)
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
    } catch (err: unknown) {
      const errMessage = err instanceof Error ? err.message : String(err)
      if (!errMessage?.includes('ERR_ABORTED')) {
        const errCode = (err instanceof Error && 'code' in err) ? (err as { code?: unknown }).code : undefined
        const error = getErrorInfo(typeof errCode === 'number' ? errCode : -1)
        this.notifyUpdate(tabId, { loading: false, error, title: error.title })
      }
    }

    logger.info(`Tab "${tab.title}" has been awakened from sleep mode`)
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
        this.onTabUpdate?.(this.activeTabId, { active: false })

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

  /** 停止指定/当前标签页加载。W4-7 只读白名单后，渲染层 NavBar 停止按钮改走
   * tab:stop 专用通道调用此处，替代原先经 execute_js 执行 window.stop() 的方式 */
  stopNavigation(tabId?: string): void {
    const targetId = tabId || this.activeTabId
    if (!targetId) return

    const view = this.views.get(targetId)
    if (view && !isViewDestroyed(view)) {
      view.webContents.stop()
    }
  }

  /** 在当前标签页导航到新 URL（不创建新标签） */
  navigateTo(url: string, tabId?: string): void {
    const targetId = tabId || this.activeTabId
    if (!targetId) return

    const tab = this.tabs.get(targetId)
    if (!tab) return

    // 休眠中的标签：直接更新 URL，唤醒时会自动加载
    if (tab.sleeping) {
      tab.url = url
      tab.loading = true
      tab.error = undefined
      this.notifyUpdate(targetId, { url, loading: true, error: undefined })
      this.wakeTab(targetId)
      return
    }

    const view = this.views.get(targetId)
    if (!view || isViewDestroyed(view)) return

    tab.url = url
    tab.loading = true
    tab.error = undefined
    this.notifyUpdate(targetId, { url, loading: true, error: undefined })

    view.webContents.loadURL(url).catch((err: unknown) => {
      const errMessage = err instanceof Error ? err.message : String(err)
      if (!errMessage?.includes('ERR_ABORTED')) {
        const errCode = (err instanceof Error && 'code' in err) ? (err as { code?: unknown }).code : undefined
        const error = getErrorInfo(typeof errCode === 'number' ? errCode : -1)
        this.notifyUpdate(targetId, { loading: false, error, title: error.title })
      }
    })
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

  /**
   * 获取指定标签页的 WebContents（供自动化执行器使用）
   * @param tabId 标签页 ID，默认当前活跃标签页
   * @returns WebContents 实例；休眠/已销毁/不存在时返回 null
   */
  getWebContents(tabId?: string): WebContents | null {
    const targetId = tabId || this.activeTabId
    if (!targetId) return null

    const tab = this.tabs.get(targetId)
    if (!tab || tab.sleeping) return null

    const view = this.views.get(targetId)
    if (!view || isViewDestroyed(view)) return null

    return view.webContents
  }

  /**
   * 确保有活跃标签页：若当前无活跃 tab 则创建一个空白页
   * @returns 活跃 Tab，窗口未初始化时返回 null
   */
  ensureActiveTab(): Tab | null {
    if (!this.window) return null

    if (this.activeTabId) {
      const tab = this.tabs.get(this.activeTabId)
      if (tab) return { ...tab }
    }

    // 无活跃标签页，创建一个
    const tab = this.createTab(DEFAULT_BROWSER_CONFIG.defaultUrl)
    return tab
  }

  /**
   * 确保目标标签页可用于截图/自动化并返回其 WebContents（W4-5）。
   *
   * - 休眠标签（webContents 已被 300s 闲置回收）先重建加载原 URL，
   *   解决 AI 经 WS 截后台/休眠 tab 拿黑帧或报「无可用标签页」的问题；
   * - 带超时保护：loadURL 挂起时不无限阻塞截图请求；
   * - 不主动改变标签页激活状态，restore() 仅在截图流程曾临时激活其他
   *   标签（captureTabPage 降级路径）时把激活状态切回去。
   */
  async acquireCaptureTarget(
    tabId?: string
  ): Promise<{ tabId: string; wc: WebContents; restore: () => Promise<void> } | null> {
    if (!this.window) return null

    const prevActiveId = this.activeTabId

    let targetTab: Tab | undefined
    let targetId: string
    if (tabId) {
      // 显式指定 tab 时不静默换页：不存在/不可用直接失败
      targetTab = this.tabs.get(tabId)
      if (!targetTab) return null
      targetId = tabId
    } else {
      targetTab = this.getActiveTab()
      if (!targetTab) {
        // 无任何可用标签页（或全部关闭）时按原语义兜底创建一个
        const ensured = this.ensureActiveTab()
        targetTab = ensured ? this.tabs.get(ensured.id) : undefined
        if (!targetTab) return null
      }
      targetId = targetTab.id
    }

    if (targetTab.sleeping) {
      // 唤醒时刷新活跃时间，避免刚重建就被休眠检查器立刻回收
      targetTab.lastActiveAt = Date.now()
      await Promise.race([
        this.wakeTab(targetId).catch(() => {}),
        new Promise<void>((resolve) => setTimeout(resolve, WAKE_TIMEOUT_MS))
      ])
    }

    const view = this.views.get(targetId)
    if (!view || isViewDestroyed(view)) return null

    const restore = async (): Promise<void> => {
      if (prevActiveId && prevActiveId !== this.activeTabId && this.tabs.has(prevActiveId)) {
        try {
          await this.activateTab(prevActiveId)
        } catch {
          // 恢复失败不影响截图结果
        }
      }
    }

    return { tabId: targetId, wc: view.webContents, restore }
  }

  /**
   * 截取标签页画面（W4-5 后台/休眠标签截图修复）：
   *
   * 1. 后台直截（首选）：capturePage({ stayHidden: true, stayAwake: true }) 允许
   *    隐藏页被捕获且不唤醒系统合成前台帧；截图期间临时关闭背景节流，避免
   *    隐藏页停止渲染产出过期/黑帧。全程不改变用户当前浏览的标签。
   * 2. 激活降级（兜底）：直截得到空帧/异常时，临时激活目标标签（attach 到窗口）
   *    截取可见帧，完成后经 restore() 恢复原本的激活状态。
   *
   * @returns 画面数据；标签页不可用或画面为空时返回 null
   */
  async captureTabPage(tabId?: string): Promise<NativeImage | null> {
    const target = await this.acquireCaptureTarget(tabId)
    if (!target) return null
    const { tabId: targetId, restore } = target

    const view = this.views.get(targetId)
    if (!view || isViewDestroyed(view)) return null
    const wc = view.webContents

    // 1) 后台直截
    try {
      try {
        wc.setBackgroundThrottling(false)
      } catch {}
      const image = await wc.capturePage(undefined, { stayHidden: true, stayAwake: true })
      if (!image.isEmpty()) {
        return image
      }
    } catch {
      // 空帧/异常 → 走激活降级
    } finally {
      try {
        wc.setBackgroundThrottling(targetId === this.activeTabId)
      } catch {}
    }

    // 2) 激活降级：临时激活截可见帧，finally 中恢复原激活状态
    try {
      await this.activateTab(targetId)
      const activatedView = this.views.get(targetId)
      if (!activatedView || isViewDestroyed(activatedView)) return null
      // 等待合成器在 attach 后产出首帧，避免截到过渡帧
      await new Promise((r) => setTimeout(r, CAPTURE_FALLBACK_DELAY_MS))
      const image = await activatedView.webContents.capturePage()
      return image.isEmpty() ? null : image
    } catch {
      return null
    } finally {
      await restore()
    }
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

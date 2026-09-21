import { WebContentsView, BrowserWindow, app } from 'electron'
import { DEFAULT_BROWSER_CONFIG, BROWSER_LAYOUT, BrowserBounds, BoundsConfig } from './types'
import { getStealthScript } from './session'

export function createBrowserView(): WebContentsView {
  const view = new WebContentsView({
    webPreferences: {
      // contextIsolation 必须保持开启：页面脚本与 Electron 注入面隔离，
      // 关闭它换取 stealth 的做法会让 XSS 有机会操纵 preload 暴露面。
      // 指纹伪装改走 CDP 在文档创建前注入主世界，见 installStealthViaCDP()。
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      webSecurity: true,
      partition: DEFAULT_BROWSER_CONFIG.sessionPartition,
      webgl: true,
      plugins: true,
      enableWebSQL: false,
      spellcheck: false,
      allowRunningInsecureContent: false,
      experimentalFeatures: false,
      enablePreferredSizeMode: false,
      navigateOnDragDrop: false,
    }
  })

  view.webContents.setVisualZoomLevelLimits(1, 3)
  installStealthViaCDP(view)

  return view
}

/**
 * 通过 CDP 在文档创建前把 stealth 脚本注入主世界。
 *
 * 之前的两个方案都有缺陷：preload 需要关闭 contextIsolation（安全面失控）；
 * did-start-navigation 后 executeJavaScript 注入时机偏晚（页面内联反爬脚本可能已执行）。
 * Page.addScriptToEvaluateOnNewDocument 在任何页面脚本运行前生效，两者兼得。
 */
export function installStealthViaCDP(view: WebContentsView): boolean {
  try {
    const { webContents } = view
    if (!webContents.debugger.isAttached()) {
      webContents.debugger.attach('1.3')
    }
    webContents.debugger
      .sendCommand('Page.enable')
      .catch(() => {})
    webContents.debugger
      .sendCommand('Page.addScriptToEvaluateOnNewDocument', {
        source: getStealthScript(),
      })
      .catch(() => {})
    return true
  } catch {
    // debugger 附加失败（如被其他调试器占用）时返回 false，
    // tab.ts 的 did-start-navigation 兜底注入仍然生效
    return false
  }
}

export function calculateBounds(
  window: BrowserWindow,
  config: BoundsConfig
): BrowserBounds {
  const [winWidth, winHeight] = window.getSize()
  
  return {
    x: config.sidebarWidth,
    y: BROWSER_LAYOUT.TOTAL_HEADER_HEIGHT,
    width: Math.max(100, winWidth - config.sidebarWidth),
    height: Math.max(100, winHeight - BROWSER_LAYOUT.TOTAL_HEADER_HEIGHT - config.devPanelHeight)
  }
}

export function setViewBounds(
  view: WebContentsView,
  bounds: BrowserBounds
): void {
  view.setBounds(bounds)
}

export function attachView(
  window: BrowserWindow,
  view: WebContentsView
): void {
  window.contentView.addChildView(view)
}

export function detachView(
  window: BrowserWindow,
  view: WebContentsView
): void {
  try {
    window.contentView.removeChildView(view)
  } catch {
  }
}

export async function injectStealthScript(view: WebContentsView): Promise<void> {
  try {
    await view.webContents.executeJavaScript(getStealthScript())
  } catch {
  }
}

export function isViewDestroyed(view: WebContentsView): boolean {
  try {
    return view.webContents.isDestroyed()
  } catch {
    return true
  }
}

export function setupNetworkConfig(): void {
  // 注意：全局安全开关（ignore-certificate-errors / disable-web-security /
  // allow-running-insecure-content / disable-features=IsolateOrigins,site-per-process）
  // 已移除——它们会全局影响主窗口、桌面宠物等所有窗口的安全态势。
  // 证书验证绕过已改为仅对浏览器自动化 session partition 生效，见 session.ts 的 initBrowserSession()。

  // 以下为隐蔽/自动化检测开关，不涉及安全特性，保留
  app.commandLine.appendSwitch('disable-blink-features', 'AutomationControlled')
  app.commandLine.appendSwitch('excludeSwitches', 'enable-automation')
  app.commandLine.appendSwitch('disable-extensions-except', '')
  app.commandLine.appendSwitch('disable-component-update')
  app.commandLine.appendSwitch('disable-background-networking')
  app.commandLine.appendSwitch('disable-sync')
  app.commandLine.appendSwitch('no-first-run')
  app.commandLine.appendSwitch('no-default-browser-check')
  app.commandLine.appendSwitch('disable-hang-monitor')
  app.commandLine.appendSwitch('disable-prompt-on-repost')
  app.commandLine.appendSwitch('disable-client-side-phishing-detection')
  app.commandLine.appendSwitch('disable-default-apps')
  app.commandLine.appendSwitch('disable-domain-reliability')
  app.commandLine.appendSwitch('disable-background-timer-throttling')
}

import { WebContentsView, BrowserWindow, app } from 'electron'
import { DEFAULT_BROWSER_CONFIG, BROWSER_LAYOUT, BrowserBounds, BoundsConfig } from './types'
import { getStealthScript } from './session'

export function createBrowserView(): WebContentsView {
  const view = new WebContentsView({
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      webSecurity: false,
      partition: DEFAULT_BROWSER_CONFIG.sessionPartition,
      webgl: true,
      plugins: true,
      enableWebSQL: false,
      spellcheck: false,
      allowRunningInsecureContent: true,
      experimentalFeatures: false,
      enablePreferredSizeMode: false
    }
  })
  
  view.webContents.setVisualZoomLevelLimits(1, 3)
  
  return view
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

import { session } from 'electron'
import { join } from 'path'
import { DEFAULT_BROWSER_CONFIG } from './types'

function getUserAgent(): string {
  const chromeVersion = process.versions.chrome || '131.0.0.0'
  const majorVersion = chromeVersion.split('.')[0]
  const platform = process.platform

  let osInfo = 'Windows NT 10.0; Win64; x64'
  if (platform === 'darwin') {
    osInfo = 'Macintosh; Intel Mac OS X 10_15_7'
  } else if (platform === 'linux') {
    osInfo = 'X11; Linux x86_64'
  }

  return `Mozilla/5.0 (${osInfo}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${chromeVersion} Safari/537.36 Edg/${chromeVersion}`
}

function getSecChUa(): string {
  const chromeVersion = process.versions.chrome || '131.0.0.0'
  const majorVersion = chromeVersion.split('.')[0]
  const notBrandVersion = Math.floor(Math.random() * 20) + 8
  return `"Chromium";v="${majorVersion}", "Microsoft Edge";v="${majorVersion}", "Not?A_Brand";v="${notBrandVersion}"`
}

function getSecChUaPlatform(): string {
  const platform = process.platform
  if (platform === 'darwin') return '"macOS"'
  if (platform === 'linux') return '"Linux"'
  return '"Windows"'
}

const USER_AGENT = getUserAgent()
const SEC_CH_UA = getSecChUa()
const SEC_CH_UA_PLATFORM = getSecChUaPlatform()

let initialized = false

export function initBrowserSession(): void {
  if (initialized) return

  const browserSession = session.fromPartition(DEFAULT_BROWSER_CONFIG.sessionPartition)

  browserSession.webRequest.onBeforeSendHeaders((details, callback) => {
    details.requestHeaders['User-Agent'] = USER_AGENT
    details.requestHeaders['Accept-Language'] = 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7'
    details.requestHeaders['sec-ch-ua'] = SEC_CH_UA
    details.requestHeaders['sec-ch-ua-mobile'] = '?0'
    details.requestHeaders['sec-ch-ua-platform'] = SEC_CH_UA_PLATFORM
    callback({ requestHeaders: details.requestHeaders })
  })

  browserSession.setUserAgent(USER_AGENT)

  const stealthPreloadPath = join(__dirname, 'stealth-preload.js')
  browserSession.setPreloads([stealthPreloadPath])

  browserSession.setPermissionRequestHandler((_webContents, permission, callback) => {
    const allowed = ['notifications', 'clipboard-read', 'clipboard-write', 'geolocation']
    callback(allowed.includes(permission))
  })

  initialized = true
  console.info('[INFO][LuomiNestBrowser] Session initialized with stealth measures')
}

export function getUserAgentString(): string {
  return USER_AGENT
}

export function clearBrowserData(): Promise<void> {
  const browserSession = session.fromPartition(DEFAULT_BROWSER_CONFIG.sessionPartition)
  return browserSession.clearData()
}

export function getCookies(): Promise<Electron.Cookie[]> {
  const browserSession = session.fromPartition(DEFAULT_BROWSER_CONFIG.sessionPartition)
  return browserSession.cookies.get({})
}

export function setCookie(cookie: Electron.CookiesSetDetails): Promise<void> {
  const browserSession = session.fromPartition(DEFAULT_BROWSER_CONFIG.sessionPartition)
  return browserSession.cookies.set(cookie)
}

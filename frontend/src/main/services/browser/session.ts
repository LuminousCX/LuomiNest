import { session } from 'electron'
import { DEFAULT_BROWSER_CONFIG } from './types'
import { createLuomiNestLogger } from '../luomi-logger'

const logger = createLuomiNestLogger('Browser')

const STEALTH_SCRIPT = `
(function() {
  'use strict';

  const originalDescriptor = Object.getOwnPropertyDescriptor(Navigator.prototype, 'webdriver');
  if (originalDescriptor) {
    Object.defineProperty(Navigator.prototype, 'webdriver', {
      get: () => undefined,
      configurable: true
    });
  }

  Object.defineProperty(navigator, 'languages', {
    get: () => ['zh-CN', 'zh', 'en-US', 'en'],
    configurable: true
  });

  if (window.chrome) {
    const nativeRuntime = window.chrome.runtime;
    window.chrome = {
      app: {
        isInstalled: false,
        InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' },
        RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' },
        getDetails: function() { return null; },
        getIsInstalled: function() { return false; }
      },
      csi: function() {
        return {
          onloadT: Date.now(),
          startE: Date.now(),
          pageT: Math.random() * 500 + 100,
          tran: 15
        };
      },
      loadTimes: function() {
        return {
          commitLoadTime: Date.now() / 1000,
          connectionInfo: 'h2',
          finishDocumentLoadTime: Date.now() / 1000,
          finishLoadTime: Date.now() / 1000,
          firstPaintAfterLoadTime: 0,
          firstPaintTime: Date.now() / 1000,
          navigationType: 'Other',
          npnNegotiatedProtocol: 'h2',
          requestTime: Date.now() / 1000 - 0.5,
          startLoadTime: Date.now() / 1000 - 0.3,
          wasAlternateProtocolAvailable: false,
          wasFetchedViaSpdy: true,
          wasNpnNegotiated: true
        };
      },
      runtime: nativeRuntime || {
        OnInstalledReason: { CHROME_UPDATE: 'chrome_update', INSTALL: 'install', SHARED_MODULE_UPDATE: 'shared_module_update', UPDATE: 'update' },
        OnRestartRequiredReason: { APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' },
        PlatformArch: { ARM: 'arm', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' },
        PlatformNaclArch: { ARM: 'arm', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' },
        PlatformOs: { ANDROID: 'android', CROS: 'cros', LINUX: 'linux', MAC: 'mac', OPENBSD: 'openbsd', WIN: 'win' },
        RequestUpdateCheckStatus: { NO_UPDATE: 'no_update', THROTTLED: 'throttled', UPDATE_AVAILABLE: 'update_available' },
        connect: function() { return { onDisconnect: { addListener: function() {} }, onMessage: { addListener: function() {} }, postMessage: function() {}, disconnect: function() {} }; },
        sendMessage: function() {}
      }
    };
  }

  const fakePlugins = [
    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format',
      length: 1, 0: { type: 'application/x-google-chrome-pdf', suffixes: 'pdf', description: 'Portable Document Format' } },
    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '',
      length: 1, 0: { type: 'application/pdf', suffixes: 'pdf', description: '' } },
    { name: 'Native Client', filename: 'internal-nacl-plugin', description: '',
      length: 2, 0: { type: 'application/x-nacl', suffixes: '', description: 'Native Client Executable' }, 1: { type: 'application/x-pnacl', suffixes: '', description: 'Portable Native Client Executable' } }
  ];

  const pluginArray = {
    length: fakePlugins.length,
    item: function(i) { return fakePlugins[i] || null; },
    namedItem: function(name) { return fakePlugins.find(p => p.name === name) || null; },
    refresh: function() {},
    [Symbol.iterator]: function*() { for (const p of fakePlugins) yield p; }
  };
  fakePlugins.forEach((p, i) => { Object.defineProperty(pluginArray, i, { get: () => fakePlugins[i], enumerable: true }); });

  Object.defineProperty(navigator, 'plugins', {
    get: () => pluginArray,
    configurable: true
  });

  const fakeMimeTypes = [];
  fakePlugins.forEach(p => {
    for (let i = 0; i < p.length; i++) {
      fakeMimeTypes.push({ ...p[i], enabledPlugin: p });
    }
  });

  const mimeTypeArray = {
    length: fakeMimeTypes.length,
    item: function(i) { return fakeMimeTypes[i] || null; },
    namedItem: function(name) { return fakeMimeTypes.find(m => m.type === name) || null; },
    [Symbol.iterator]: function*() { for (const m of fakeMimeTypes) yield m; }
  };
  fakeMimeTypes.forEach((m, i) => { Object.defineProperty(mimeTypeArray, i, { get: () => fakeMimeTypes[i], enumerable: true }); });

  Object.defineProperty(navigator, 'mimeTypes', {
    get: () => mimeTypeArray,
    configurable: true
  });

  const originalQuery = window.navigator.permissions.query;
  window.navigator.permissions.query = function(parameters) {
    if (parameters.name === 'notifications') {
      return Promise.resolve({ state: Notification.permission, onchange: null });
    }
    return originalQuery.call(window.navigator.permissions, parameters);
  };

  if (!navigator.connection) {
    Object.defineProperty(navigator, 'connection', {
      get: () => ({
        effectiveType: '4g',
        rtt: 50,
        downlink: 10,
        saveData: false,
        onchange: null,
        addEventListener: function() {},
        removeEventListener: function() {},
        dispatchEvent: function() { return true; }
      }),
      configurable: true
    });
  }

  const originalGetContext = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function(type, attributes) {
    const context = originalGetContext.apply(this, [type, attributes]);
    if (context && type === 'webgl') {
      const originalGetParam = context.getParameter;
      context.getParameter = function(param) {
        if (param === 37445) return 'Intel Inc.';
        if (param === 37446) return 'Intel Iris OpenGL Engine';
        return originalGetParam.call(this, param);
      };
    }
    if (context && type === 'webgl2') {
      const originalGetParam2 = context.getParameter;
      context.getParameter = function(param) {
        if (param === 37445) return 'Intel Inc.';
        if (param === 37446) return 'Intel Iris OpenGL Engine';
        return originalGetParam2.call(this, param);
      };
    }
    return context;
  };

  const originalAttachShadow = Element.prototype.attachShadow;
  Element.prototype.attachShadow = function() {
    return originalAttachShadow.apply(this, arguments);
  };

  try {
    const iframe = document.createElement('iframe');
    iframe.style.display = 'none';
    document.head.appendChild(iframe);
    if (iframe.contentWindow) {
      const nativeFn = iframe.contentWindow.navigator.constructor.prototype;
      Object.defineProperty(nativeFn, 'webdriver', { get: () => undefined, configurable: true });
    }
    iframe.remove();
  } catch (e) {}

  Object.defineProperty(navigator, 'hardwareConcurrency', {
    get: () => 8,
    configurable: true
  });

  Object.defineProperty(navigator, 'deviceMemory', {
    get: () => 8,
    configurable: true
  });

  const originalToString = Function.prototype.toString;
  const nativeToStringMap = new WeakMap();
  const patchedFunctions = [
    [window.navigator.permissions.query, 'function query() { [native code] }'],
    [HTMLCanvasElement.prototype.getContext, 'function getContext() { [native code] }'],
    [Element.prototype.attachShadow, 'function attachShadow() { [native code] }']
  ];
  patchedFunctions.forEach(([fn, str]) => {
    nativeToStringMap.set(fn, str);
  });
  Function.prototype.toString = function() {
    if (nativeToStringMap.has(this)) return nativeToStringMap.get(this);
    return originalToString.call(this);
  };
  nativeToStringMap.set(Function.prototype.toString, 'function toString() { [native code] }');

  Object.defineProperty(navigator, 'maxTouchPoints', {
    get: () => 0,
    configurable: true
  });
})();
`

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

  return `Mozilla/5.0 (${osInfo}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${chromeVersion} Safari/537.36`
}

function getSecChUa(): string {
  const chromeVersion = process.versions.chrome || '131.0.0.0'
  const majorVersion = chromeVersion.split('.')[0]
  // 品牌列表必须与真实 Chrome 保持同版本且稳定：随机版本号是指纹异常的明显特征，
  // 会触发 B 站等站点风控（412）。真实 Chrome 131+ 的 GREASE 品牌为 "Not_A Brand";v="24"。
  return `"Chromium";v="${majorVersion}", "Google Chrome";v="${majorVersion}", "Not_A Brand";v="24"`
}

function getSecChUaFullVersionList(): string {
  const chromeVersion = process.versions.chrome || '131.0.0.0'
  const majorVersion = chromeVersion.split('.')[0]
  return `"Chromium";v="${chromeVersion}", "Google Chrome";v="${chromeVersion}", "Not_A Brand";v="24.0.0.0"`
}

function getSecChUaPlatform(): string {
  const platform = process.platform
  if (platform === 'darwin') return '"macOS"'
  if (platform === 'linux') return '"Linux"'
  return '"Windows"'
}

const USER_AGENT = getUserAgent()
const SEC_CH_UA = getSecChUa()
const SEC_CH_UA_FULL_VERSION_LIST = getSecChUaFullVersionList()
const SEC_CH_UA_PLATFORM = getSecChUaPlatform()

let initialized = false

/** 下载被拦截时携带的信息 */
export interface DownloadBlockedInfo {
  filename: string
  url: string
}

type DownloadBlockedCallback = (info: DownloadBlockedInfo) => void

let downloadBlockedCallback: DownloadBlockedCallback | null = null

/**
 * 注册下载拦截通知回调（tab.ts 在 setWindow 时注册）。
 *
 * session.ts 不反向 import tab.ts（会成环），故以回调注入方式把
 * 「下载已取消」事件转交给 TabManager 的 tab 事件通道。
 */
export function setDownloadBlockedCallback(cb: DownloadBlockedCallback | null): void {
  downloadBlockedCallback = cb
}

export function initBrowserSession(): void {
  if (initialized) return

  const browserSession = session.fromPartition(DEFAULT_BROWSER_CONFIG.sessionPartition)

  // 仅修改 User-Agent，不干预其他请求头（避免破坏 B站等网站的 API 签名验证）
  browserSession.setUserAgent(USER_AGENT)

  browserSession.setPermissionRequestHandler((_webContents, permission, callback) => {
    const allowed = ['notifications', 'clipboard-read', 'clipboard-write', 'geolocation', 'media']
    callback(allowed.includes(permission))
  })

  // Client Hints 头对全部请求类型注入：真实 Chrome 在主文档/子资源/XHR/fetch 上
  // 都会携带 sec-ch-ua 系列头，仅主文档注入反而构成指纹异常（页面 API 读取到的
  // navigator.userAgentData 与请求头不一致），可能触发站点风控
  browserSession.webRequest.onBeforeSendHeaders((details, callback) => {
    const headers = { ...details.requestHeaders }
    headers['sec-ch-ua'] = SEC_CH_UA
    headers['sec-ch-ua-mobile'] = '?0'
    headers['sec-ch-ua-platform'] = SEC_CH_UA_PLATFORM
    headers['sec-ch-ua-full-version-list'] = SEC_CH_UA_FULL_VERSION_LIST
    headers['Accept-Language'] = 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7'

    // 针对 Bilibili 及防盗链站自动补充 Referer 头，防止图片、音视频及反爬 CDN 403 拦截
    const url = details.url || ''
    if (
      (url.includes('bilibili.com') || url.includes('hdslb.com')) &&
      !headers['Referer'] &&
      !headers['referer']
    ) {
      headers['Referer'] = 'https://www.bilibili.com/'
    }

    callback({ requestHeaders: headers })
  })

  // 仅浏览器自动化 partition：对 localhost 绕过证书验证（本地开发服务），
  // 其他域名使用 Chromium 默认证书验证（防止 MITM 攻击）
  browserSession.setCertificateVerifyProc((request, callback) => {
    const hostname = request.hostname || ''
    if (
      hostname === 'localhost' ||
      hostname === '127.0.0.1' ||
      hostname === '::1' ||
      hostname.endsWith('.localhost')
    ) {
      callback(0) // 接受本地服务的自签名证书
    } else {
      callback(-3) // 使用 Chromium 默认证书验证
    }
  })

  // 宽松 CSP 策略：允许 WebAssembly、Web Worker、Blob、Media 及常见 CDN
  // 避免 B站、YouTube、现代 Vue/React SPA 播放器与核心脚本崩溃
  const RELAXED_CSP = [
    "default-src * 'unsafe-inline' 'unsafe-eval' data: blob:;",
    "script-src * 'unsafe-inline' 'unsafe-eval' 'wasm-unsafe-eval' data: blob:;",
    "worker-src * 'unsafe-inline' 'unsafe-eval' data: blob:;",
    "child-src * 'unsafe-inline' 'unsafe-eval' data: blob:;",
    "style-src * 'unsafe-inline';",
    "img-src * data: blob: https: http:;",
    "media-src * data: blob: https: http:;",
    "font-src * data: https: http:;",
    "connect-src * ws: wss: http: https: data: blob:;",
    "object-src 'none';",
    "base-uri 'self';",
  ].join(' ')

  browserSession.webRequest.onHeadersReceived((details, callback) => {
    const headers: Record<string, string | string[]> = {}
    let modified = false
    for (const [key, value] of Object.entries(details.responseHeaders || {})) {
      const lowerKey = key.toLowerCase()
      if (
        lowerKey === 'content-security-policy' ||
        lowerKey === 'content-security-policy-report-only'
      ) {
        modified = true
        continue
      }
      // 移除 X-Frame-Options 以允许嵌入式渲染
      if (lowerKey === 'x-frame-options') {
        modified = true
        continue
      }
      headers[key] = value as string | string[]
    }

    if (modified) {
      // 注入兼容 WebAssembly 与 Worker 的宽松 CSP 替代原始限制策略
      headers['Content-Security-Policy'] = RELAXED_CSP
      callback({ responseHeaders: headers })
    } else {
      callback({})
    }
  })

  // W4-6：内置浏览器不提供下载落盘与下载管理 UI，统一取消下载并经 tab 事件
  // 通道通知渲染层 toast 提示「内置浏览器不支持下载，已取消」
  browserSession.on('will-download', (_event, item) => {
    const info: DownloadBlockedInfo = { filename: item.getFilename(), url: item.getURL() }
    try {
      item.cancel()
    } catch (e) {
      logger.warn('取消下载失败:', e)
    }
    logger.info(`已拦截下载: ${info.filename} (${info.url})`)
    downloadBlockedCallback?.(info)
  })

  initialized = true
  logger.info('Session initialized with stealth measures')
}

export function getStealthScript(): string {
  return STEALTH_SCRIPT
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

import { session } from 'electron'
import { DEFAULT_BROWSER_CONFIG } from './types'

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

  browserSession.setPermissionRequestHandler((_webContents, permission, callback) => {
    const allowed = ['notifications', 'clipboard-read', 'clipboard-write', 'geolocation']
    callback(allowed.includes(permission))
  })

  initialized = true
  console.info('[INFO][LuomiNestBrowser] Session initialized with stealth measures')
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

// 浏览器自动化 stealth preload 脚本
// 此文件在页面任何 JS 执行之前注入（通过 webPreferences.preload），
// 确保 navigator.webdriver 等检测点在被检测前就被覆盖。
// contextIsolation: true 意味着此脚本运行在隔离的世界中，
// 需要通过 contextBridge 或直接修改原型链来影响页面。

;(function () {
  'use strict'

  // 1. 移除 navigator.webdriver
  try {
    Object.defineProperty(Navigator.prototype, 'webdriver', {
      get: () => undefined,
      configurable: true,
    })
  } catch (e) {}

  // 2. 模拟 chrome.runtime（Electron 中不存在 window.chrome）
  if (!window.chrome) {
    window.chrome = {
      app: {
        isInstalled: false,
        InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' },
        RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' },
        getDetails: function () { return null },
        getIsInstalled: function () { return false },
      },
      csi: function () {
        return {
          onloadT: Date.now(),
          startE: Date.now(),
          pageT: Math.random() * 500 + 100,
          tran: 15,
        }
      },
      loadTimes: function () {
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
          wasNpnNegotiated: true,
        }
      },
      runtime: {
        OnInstalledReason: { CHROME_UPDATE: 'chrome_update', INSTALL: 'install', SHARED_MODULE_UPDATE: 'shared_module_update', UPDATE: 'update' },
        OnRestartRequiredReason: { APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' },
        PlatformArch: { ARM: 'arm', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' },
        PlatformNaclArch: { ARM: 'arm', MIPS: 'mips', MIPS64: 'mips64', X86_32: 'x86-32', X86_64: 'x86-64' },
        PlatformOs: { ANDROID: 'android', CROS: 'cros', LINUX: 'linux', MAC: 'mac', OPENBSD: 'openbsd', WIN: 'win' },
        RequestUpdateCheckStatus: { NO_UPDATE: 'no_update', THROTTLED: 'throttled', UPDATE_AVAILABLE: 'update_available' },
        connect: function () { return { onDisconnect: { addListener: function () {} }, onMessage: { addListener: function () {} }, postMessage: function () {}, disconnect: function () {} } },
        sendMessage: function () {},
      },
    }
  }

  // 3. 模拟 plugins
  try {
    const fakePlugins = [
      { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format', length: 1, 0: { type: 'application/x-google-chrome-pdf', suffixes: 'pdf', description: 'Portable Document Format' } },
      { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '', length: 1, 0: { type: 'application/pdf', suffixes: 'pdf', description: '' } },
      { name: 'Native Client', filename: 'internal-nacl-plugin', description: '', length: 2, 0: { type: 'application/x-nacl', suffixes: '', description: 'Native Client Executable' }, 1: { type: 'application/x-pnacl', suffixes: '', description: 'Portable Native Client Executable' } },
    ]
    const pluginArray = {
      length: fakePlugins.length,
      item: function (i) { return fakePlugins[i] || null },
      namedItem: function (name) { return fakePlugins.find(function (p) { return p.name === name }) || null },
      refresh: function () {},
      [Symbol.iterator]: function* () { for (const p of fakePlugins) yield p },
    }
    fakePlugins.forEach(function (p, i) { Object.defineProperty(pluginArray, i, { get: function () { return fakePlugins[i] }, enumerable: true }) })
    Object.defineProperty(navigator, 'plugins', { get: function () { return pluginArray }, configurable: true })
  } catch (e) {}

  // 4. 修复 permissions.query
  try {
    const originalQuery = window.navigator.permissions.query
    window.navigator.permissions.query = function (parameters) {
      if (parameters.name === 'notifications') {
        return Promise.resolve({ state: Notification.permission, onchange: null })
      }
      return originalQuery.call(window.navigator.permissions, parameters)
    }
  } catch (e) {}

  // 5. 强制 Shadow DOM 为 open 模式（关键！B站等 SPA 使用 closed Shadow DOM 导致渲染异常）
  try {
    const originalAttachShadow = Element.prototype.attachShadow
    Element.prototype.attachShadow = function (options) {
      return originalAttachShadow.call(this, { ...options, mode: 'open' })
    }
  } catch (e) {}

  // 6. 模拟 navigator.connection
  try {
    if (!navigator.connection) {
      Object.defineProperty(navigator, 'connection', {
        get: function () {
          return {
            effectiveType: '4g',
            rtt: 50,
            downlink: 10,
            saveData: false,
            onchange: null,
            addEventListener: function () {},
            removeEventListener: function () {},
            dispatchEvent: function () { return true },
          }
        },
        configurable: true,
      })
    }
  } catch (e) {}

  // 7. 伪造 WebGL 渲染器信息
  try {
    const originalGetContext = HTMLCanvasElement.prototype.getContext
    HTMLCanvasElement.prototype.getContext = function (type, attributes) {
      const context = originalGetContext.apply(this, [type, attributes])
      if (context && (type === 'webgl' || type === 'webgl2')) {
        const originalGetParam = context.getParameter
        context.getParameter = function (param) {
          if (param === 37445) return 'Intel Inc.'
          if (param === 37446) return 'Intel Iris OpenGL Engine'
          return originalGetParam.call(this, param)
        }
      }
      return context
    }
  } catch (e) {}

  // 8. 硬件信息
  try {
    Object.defineProperty(navigator, 'hardwareConcurrency', { get: function () { return 8 }, configurable: true })
    Object.defineProperty(navigator, 'deviceMemory', { get: function () { return 8 }, configurable: true })
    Object.defineProperty(navigator, 'maxTouchPoints', { get: function () { return 0 }, configurable: true })
    Object.defineProperty(navigator, 'languages', { get: function () { return ['zh-CN', 'zh', 'en-US', 'en'] }, configurable: true })
  } catch (e) {}

  // 9. 修复 Function.prototype.toString 检测
  try {
    const originalToString = Function.prototype.toString
    const nativeToStringMap = new WeakMap()
    const patchedFunctions = [
      [window.navigator.permissions ? window.navigator.permissions.query : null, 'function query() { [native code] }'],
      [HTMLCanvasElement.prototype.getContext, 'function getContext() { [native code] }'],
      [Element.prototype.attachShadow, 'function attachShadow() { [native code] }'],
    ]
    patchedFunctions.forEach(function (entry) {
      if (entry[0]) nativeToStringMap.set(entry[0], entry[1])
    })
    Function.prototype.toString = function () {
      if (nativeToStringMap.has(this)) return nativeToStringMap.get(this)
      return originalToString.call(this)
    }
    nativeToStringMap.set(Function.prototype.toString, 'function toString() { [native code] }')
  } catch (e) {}
})()

(function() {
  'use strict';

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

import { BrowserWindow, IpcMainInvokeEvent, app, dialog, net, shell, type OpenDialogOptions, nativeImage } from 'electron'
import { PATHS } from './paths'
import { toBackgroundUrl } from './bg-protocol'
import { configStore } from './config-store'
import { cacheManager } from './cache-manager'
import { tabManager, luomiAutomationExecutor, READ_ONLY_AUTOMATION_ACTIONS } from './browser'
import { getLumiAuthToken } from './backend/auth-token'
import { subscribeBackendStage } from './backend'
import { cloudAuth, renewCloudTokensNow } from './cloud'
import { cloudGroups } from './cloud/cloud-groups'
import { cloudPrefsSync } from './cloud/prefs-sync'
import { loadCloudTokens } from './cloud/token-store'
import { createLuomiNestLogger } from './luomi-logger'
import { logHub } from './log-hub'
import { handleIpc } from './typed-ipc'
import { IpcChannels } from '@shared/ipc-types'
import type { TTSConfig, STTConfig, ThemeConfig, CloudRoutingMode, OnboardingConfig, LogQueryParams, LogUploadResult } from '@shared/ipc-types'
import * as fs from 'fs'
import * as path from 'path'

const logger = createLuomiNestLogger('IpcHandlers')

/** log:upload 请求超时（15s） */
const LOG_UPLOAD_TIMEOUT_MS = 15_000

let _mainWindow: BrowserWindow | null = null

export function setMainWindow(win: BrowserWindow | null): void {
  _mainWindow = win
}

function getMainWindow(): BrowserWindow | null {
  return _mainWindow
}

export function registerIpcHandlers(mainWindow: BrowserWindow | null): void {
  setMainWindow(mainWindow)

  const assertTrustedSender = (event: IpcMainInvokeEvent): boolean => {
    const win = getMainWindow()
    if (!win || event.sender !== win.webContents) {
      return false
    }
    return true
  }

  handleIpc(IpcChannels.window.invoke.minimize, (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return
    getMainWindow()?.minimize()
  })
  handleIpc(IpcChannels.window.invoke.maximize, (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return
    const win = getMainWindow()
    if (win?.isMaximized()) {
      win.unmaximize()
    } else {
      win?.maximize()
    }
  })
  handleIpc(IpcChannels.window.invoke.close, (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return
    getMainWindow()?.close()
  })
  handleIpc(IpcChannels.window.invoke.isMaximized, (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return false
    return getMainWindow()?.isMaximized() ?? false
  })

  handleIpc(IpcChannels.app.invoke.getVersion, (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return undefined
    return app.getVersion()
  })
  handleIpc(IpcChannels.app.invoke.getName, (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return undefined
    return app.getName()
  })

  handleIpc(IpcChannels.app.invoke.getPaths, (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return undefined
    return {
      userData: PATHS.userData,
      cache: PATHS.cache,
      data: PATHS.data,
      config: PATHS.config,
      logs: PATHS.logs,
      live2d: PATHS.live2d,
    }
  })

  handleIpc(IpcChannels.app.invoke.getWelcomeCompleted, (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return undefined
    return configStore.getWelcomeCompleted()
  })

  handleIpc(IpcChannels.app.invoke.setWelcomeCompleted, (event: IpcMainInvokeEvent, value: boolean) => {
    if (!assertTrustedSender(event)) return
    if (typeof value !== 'boolean') return
    configStore.setWelcomeCompleted(value)
  })

  handleIpc(IpcChannels.app.invoke.getOnboarding, (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return undefined
    return configStore.getOnboarding()
  })

  handleIpc(IpcChannels.app.invoke.setOnboarding, (event: IpcMainInvokeEvent, updates: Partial<OnboardingConfig>) => {
    if (!assertTrustedSender(event)) return
    if (!updates || typeof updates !== 'object') return
    const safe: Partial<OnboardingConfig> = {}
    if (typeof updates.agreementVersion === 'string') safe.agreementVersion = updates.agreementVersion
    if (typeof updates.privacyVersion === 'string') safe.privacyVersion = updates.privacyVersion
    if (typeof updates.agreedAt === 'string') safe.agreedAt = updates.agreedAt
    if (typeof updates.tutorialDone === 'boolean') safe.tutorialDone = updates.tutorialDone
    configStore.setOnboarding(safe)
    // 引导同意记录属于云同步的显示偏好白名单，变更后触发节流上传
    cloudPrefsSync.notifyLocalPrefChange()
  })

  handleIpc(IpcChannels.auth.invoke.getToken, (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return undefined
    return getLumiAuthToken()
  })

  handleIpc(IpcChannels.config.invoke.getTheme, (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return undefined
    return configStore.getTheme()
  })
  handleIpc(IpcChannels.config.invoke.setTheme, (event: IpcMainInvokeEvent, theme: 'light' | 'dark' | 'system') => {
    if (!assertTrustedSender(event)) return
    configStore.setTheme(theme)
    // 主题属于云同步的显示偏好白名单，变更后触发节流上传
    cloudPrefsSync.notifyLocalPrefChange()
  })
  handleIpc(IpcChannels.config.invoke.getThemeConfig, (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return null
    return configStore.getThemeConfig()
  })
  handleIpc(IpcChannels.config.invoke.setThemeConfig, (event: IpcMainInvokeEvent, config: ThemeConfig) => {
    if (!assertTrustedSender(event)) return
    configStore.setThemeConfig(config)
  })
  handleIpc(IpcChannels.config.invoke.getTTS, (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return undefined
    return configStore.getTTSConfig()
  })
  handleIpc(IpcChannels.config.invoke.setTTS, (event: IpcMainInvokeEvent, updates: Partial<TTSConfig>) => {
    if (!assertTrustedSender(event)) return
    configStore.setTTSConfig(updates)
  })
  handleIpc(IpcChannels.config.invoke.getSTT, (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return undefined
    return configStore.getSTTConfig()
  })
  handleIpc(IpcChannels.config.invoke.setSTT, (event: IpcMainInvokeEvent, updates: Partial<STTConfig>) => {
    if (!assertTrustedSender(event)) return
    configStore.setSTTConfig(updates)
  })
  handleIpc(IpcChannels.config.invoke.getLocale, (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return undefined
    return configStore.getLocale()
  })
  handleIpc(IpcChannels.config.invoke.setLocale, (event: IpcMainInvokeEvent, locale: string) => {
    if (!assertTrustedSender(event)) return
    if (typeof locale !== 'string' || !locale) return
    configStore.setLocale(locale)
    // 语言属于云同步的显示偏好白名单，变更后触发节流上传
    cloudPrefsSync.notifyLocalPrefChange()
  })
  handleIpc(IpcChannels.config.invoke.getAll, (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return undefined
    return configStore.getAll()
  })

  handleIpc(IpcChannels.cloud.invoke.getPrefSyncEnabled, (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return undefined
    return configStore.getPrefSyncEnabled()
  })

  handleIpc(IpcChannels.cloud.invoke.setPrefSyncEnabled, (event: IpcMainInvokeEvent, enabled: boolean) => {
    if (!assertTrustedSender(event)) return
    if (typeof enabled !== 'boolean') return
    configStore.setPrefSyncEnabled(enabled)
  })

  handleIpc(IpcChannels.cache.invoke.getSize, (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return undefined
    return cacheManager.getCacheSizeMB()
  })
  handleIpc(IpcChannels.cache.invoke.getBreakdown, (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return undefined
    return cacheManager.getCacheBreakdown()
  })
  handleIpc(IpcChannels.cache.invoke.clearAll, (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return false
    cacheManager.clearAllCache()
    return true
  })
  handleIpc(IpcChannels.cache.invoke.clearDir, (event: IpcMainInvokeEvent, dirName: string) => {
    if (!assertTrustedSender(event)) return false
    if (typeof dirName !== 'string' || !dirName.trim()) return false
    cacheManager.clearCacheDir(dirName)
  })

  handleIpc(IpcChannels.tab.invoke.create, async (event: IpcMainInvokeEvent, url?: string) => {
    if (!assertTrustedSender(event)) return
    return tabManager.createTab(url)
  })
  handleIpc(IpcChannels.tab.invoke.activate, async (event: IpcMainInvokeEvent, tabId: string) => {
    if (!assertTrustedSender(event)) return
    if (typeof tabId !== 'string' || !tabId.trim()) return
    return tabManager.activateTab(tabId)
  })
  handleIpc(IpcChannels.tab.invoke.close, async (event: IpcMainInvokeEvent, tabId: string) => {
    if (!assertTrustedSender(event)) return
    if (typeof tabId !== 'string' || !tabId.trim()) return
    return tabManager.closeTab(tabId)
  })
  handleIpc(IpcChannels.tab.invoke.getAll, async (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return undefined
    return tabManager.getAllTabs()
  })
  handleIpc(IpcChannels.tab.invoke.getActive, async (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return undefined
    return tabManager.getActiveTab()
  })
  handleIpc(IpcChannels.tab.invoke.reload, async (event: IpcMainInvokeEvent, tabId?: string) => {
    if (!assertTrustedSender(event)) return
    return tabManager.reloadTab(tabId)
  })
  // 停止加载（W4-7）：原渲染层经 browserAutomation.execute('execute_js') 调
  // window.stop()，只读白名单后 execute_js 不可达，改走本专用通道 → webContents.stop()
  handleIpc(IpcChannels.tab.invoke.stop, async (event: IpcMainInvokeEvent, tabId?: string) => {
    if (!assertTrustedSender(event)) return
    return tabManager.stopNavigation(tabId)
  })
  handleIpc(IpcChannels.tab.invoke.navigate, async (event: IpcMainInvokeEvent, url: string, tabId?: string) => {
    if (!assertTrustedSender(event)) return
    return tabManager.navigateTo(url, tabId)
  })
  handleIpc(IpcChannels.tab.invoke.goBack, async (event: IpcMainInvokeEvent, tabId?: string) => {
    if (!assertTrustedSender(event)) return
    return tabManager.goBack(tabId)
  })
  handleIpc(IpcChannels.tab.invoke.goForward, async (event: IpcMainInvokeEvent, tabId?: string) => {
    if (!assertTrustedSender(event)) return
    return tabManager.goForward(tabId)
  })
  handleIpc(IpcChannels.tab.invoke.getNavigationState, async (event: IpcMainInvokeEvent, tabId?: string) => {
    if (!assertTrustedSender(event)) return
    return tabManager.getNavigationState(tabId)
  })
  handleIpc(IpcChannels.tab.invoke.hideAll, async (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return
    return tabManager.hideAll()
  })
  handleIpc(IpcChannels.tab.invoke.showActive, async (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return
    return tabManager.showActive()
  })
  handleIpc(IpcChannels.tab.invoke.setBoundsConfig, async (event: IpcMainInvokeEvent, config) => {
    if (!assertTrustedSender(event)) return
    return tabManager.setBoundsConfig(config)
  })
  handleIpc(IpcChannels.tab.invoke.cleanup, async (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return
    return tabManager.cleanup()
  })
  handleIpc(IpcChannels.tab.invoke.getCookies, async (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return
    const { getCookies } = await import('./browser')
    return getCookies()
  })
  handleIpc(IpcChannels.tab.invoke.clearData, async (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return
    const { clearBrowserData } = await import('./browser')
    return clearBrowserData()
  })

  handleIpc(IpcChannels.browser.invoke.search, async (event: IpcMainInvokeEvent, query: string) => {
    if (!assertTrustedSender(event)) return
    if (typeof query !== 'string' || !query.trim()) return
    const { browserSearch } = await import('./browser')
    return await browserSearch(query, getMainWindow())
  })

  handleIpc(IpcChannels.browser.invoke.fetchUrl, async (event: IpcMainInvokeEvent, url: string) => {
    if (!assertTrustedSender(event)) return
    if (typeof url !== 'string' || !url.trim()) return
    const { fetchUrl } = await import('./browser')
    return await fetchUrl(url, getMainWindow())
  })

  handleIpc(IpcChannels.browser.invoke.automation, async (event: IpcMainInvokeEvent, action: string, args: Record<string, any>) => {
    if (!assertTrustedSender(event)) {
      return { success: false, error: '未授权的调用方' }
    }
    if (typeof action !== 'string' || !action) {
      return { success: false, error: '缺少 action 参数' }
    }
    // W4-7：IPC 侧只读白名单——仅放行截图/标签页管理类动作，与 executor 内部
    // 白名单一致（双保险）；click/type/execute_js 等交互动作对渲染层不可达
    if (!READ_ONLY_AUTOMATION_ACTIONS.has(action)) {
      return { success: false, error: `动作 ${action} 不在 IPC 只读白名单内` }
    }
    return await luomiAutomationExecutor.execute(action, args || {})
  })

  handleIpc(IpcChannels.dialog.invoke.selectBackgroundImage, async (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return { success: false, error: '未授权的调用方' }

    const parentWindow = getMainWindow()
    const dialogOptions: OpenDialogOptions = {
      title: '选择背景图片',
      properties: ['openFile'],
      filters: [{ name: '图片', extensions: ['jpg', 'jpeg', 'png', 'gif', 'webp'] }]
    }
    const result = parentWindow
      ? await dialog.showOpenDialog(parentWindow, dialogOptions)
      : await dialog.showOpenDialog(dialogOptions)
    if (result.canceled || result.filePaths.length === 0) {
      return { success: false, cancelled: true }
    }

    const sourcePath = result.filePaths[0]
    // 背景图片统一保存到用户数据目录（userData/Backgrounds），与安装目录隔离
    const bgDir = PATHS.backgrounds

    try {
      if (!fs.existsSync(sourcePath)) {
        return { success: false, error: '源文件不存在' }
      }

      const stats = fs.statSync(sourcePath)
      const MAX_BG_SIZE = 10 * 1024 * 1024 // 10MB
      if (!stats.isFile()) {
        return { success: false, error: '选择的不是文件' }
      }
      if (stats.size === 0) {
        return { success: false, error: '选择的文件为空' }
      }
      if (stats.size > MAX_BG_SIZE) {
        return { success: false, error: '图片大小超过 10MB 限制' }
      }

      // 扩展名 + MIME 双重校验
      const ext = path.extname(sourcePath).toLowerCase()
      const allowedExts = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
      if (!allowedExts.includes(ext)) {
        return { success: false, error: '不支持的图片格式，请选择 jpg/png/gif/webp' }
      }

      // 复制前校验真实图像内容：仅扩展名不足以识别损坏或伪装的文件
      // 该实例随后复用于读取分辨率，避免对目标文件二次加载
      const sourceImage = nativeImage.createFromPath(sourcePath)
      if (sourceImage.isEmpty()) {
        return { success: false, error: '图片内容无效或文件已损坏，请重新选择' }
      }

      fs.mkdirSync(bgDir, { recursive: true })

      // 生成安全文件名：只保留中英文/数字/下划线/连字符，避免特殊字符导致协议或路径问题
      const rawBase = path.basename(sourcePath, ext)
        .replace(/[^\u4e00-\u9fa5a-zA-Z0-9_-]/g, '_')
        .slice(0, 40)
      const baseName = rawBase || 'upload'
      const destName = `bg-${baseName}-${Date.now()}${ext}`
      const destPath = path.join(bgDir, destName)

      // 若极短概率下文件名冲突，追加随机后缀
      let finalDestPath = destPath
      let finalDestName = destName
      if (fs.existsSync(finalDestPath)) {
        const randomSuffix = Math.random().toString(36).slice(2, 8)
        finalDestName = `bg-${baseName}-${Date.now()}-${randomSuffix}${ext}`
        finalDestPath = path.join(bgDir, finalDestName)
      }

      fs.copyFileSync(sourcePath, finalDestPath)
      logger.info(`[dialog:selectBackgroundImage] 背景图片已保存: ${finalDestPath}`)

      // 复用已校验的源图片实例读取实际分辨率，过小则提示用户
      const { width, height } = sourceImage.getSize()
      let warning: string | undefined
      if (width < 1280 || height < 720) {
        warning = `图片分辨率较低（${width}×${height}），作为全屏背景可能会模糊，建议使用高清原图`
        logger.warn(`[dialog:selectBackgroundImage] ${warning}`)
      }

      return { success: true, url: toBackgroundUrl(finalDestName), width, height, warning }
    } catch (err) {
      const message = err instanceof Error ? err.message : '复制背景图片失败'
      logger.error('[dialog:selectBackgroundImage] 处理失败:', message)
      return { success: false, error: message }
    }
  })

  handleIpc(IpcChannels.dialog.invoke.deleteBackgroundImage, async (event: IpcMainInvokeEvent, imageUrl: string) => {
    if (!assertTrustedSender(event)) return { success: false, error: '未授权的调用方' }
    if (typeof imageUrl !== 'string' || !imageUrl.startsWith('luominest-bg://')) {
      return { success: false, error: '无效的背景图片地址' }
    }

    try {
      // 兼容旧的双斜杠格式与新三斜杠格式：统一移除协议前缀及所有前导斜杠
      const fileName = decodeURIComponent(
        imageUrl.replace(/^luominest-bg:\/+/, '').replace(/^bg\//, '')
      )
      if (!fileName) {
        return { success: false, error: '无效的文件名' }
      }
      const filePath = path.join(PATHS.backgrounds, fileName)
      const resolvedBgDir = path.resolve(PATHS.backgrounds)
      if (!filePath.startsWith(resolvedBgDir + path.sep)) {
        return { success: false, error: '非法的文件路径' }
      }
      if (fs.existsSync(filePath)) {
        fs.unlinkSync(filePath)
        logger.info(`[dialog:deleteBackgroundImage] 背景图片已删除: ${filePath}`)
      }
      return { success: true }
    } catch (err) {
      const message = err instanceof Error ? err.message : '删除背景图片失败'
      logger.error('[dialog:deleteBackgroundImage] 处理失败:', message)
      return { success: false, error: message }
    }
  })

  handleIpc(IpcChannels.backend.invoke.subscribe, (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return
    const win = event.sender
    const unsubscribe = subscribeBackendStage((stage, detail) => {
      if (!win.isDestroyed()) {
        win.send(IpcChannels.backend.push.stage, { stage, detail })
      }
    })
    win.once('destroyed', () => unsubscribe())
  })

  handleIpc(IpcChannels.cloud.invoke.login, async (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return { state: 'loggedOut' }
    return cloudAuth.login()
  })

  handleIpc(IpcChannels.cloud.invoke.status, (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return { state: 'loggedOut' }
    return cloudAuth.getStatus()
  })

  handleIpc(IpcChannels.cloud.invoke.logout, async (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return { state: 'loggedOut' }
    return cloudAuth.logout()
  })

  handleIpc(IpcChannels.cloud.invoke.openVerification, async (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return false
    return cloudAuth.openVerificationPage()
  })

  handleIpc(IpcChannels.cloud.invoke.getRoutingMode, (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return 'off' as const
    return cloudAuth.getRoutingMode()
  })

  handleIpc(IpcChannels.cloud.invoke.setRoutingMode, (event: IpcMainInvokeEvent, mode: CloudRoutingMode) => {
    if (!assertTrustedSender(event)) return
    if (mode !== 'off' && mode !== 'all') return
    cloudAuth.setRoutingMode(mode)
  })

  handleIpc(IpcChannels.cloud.invoke.fetchModels, async (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return []
    return cloudAuth.fetchModels()
  })

  handleIpc(IpcChannels.cloud.invoke.getBackendStatus, async (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return null
    return cloudAuth.getBackendCloudStatus()
  })

  /* ── 云端群聊（cloud-groups；服务端未上线时各通道返回结构化错误，界面降级空态） ── */

  handleIpc(IpcChannels.cloud.invoke.groupList, async (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return { ok: false, error: { kind: 'not_logged_in' as const } }
    return cloudGroups.list()
  })

  handleIpc(IpcChannels.cloud.invoke.groupCreate, async (event: IpcMainInvokeEvent, name: unknown) => {
    if (!assertTrustedSender(event)) return { ok: false, error: { kind: 'not_logged_in' as const } }
    if (typeof name !== 'string' || !name.trim()) {
      return { ok: false, error: { kind: 'server' as const, message: 'invalid group name' } }
    }
    return cloudGroups.create(name)
  })

  handleIpc(IpcChannels.cloud.invoke.groupInvite, async (event: IpcMainInvokeEvent, groupId: unknown, userId: unknown) => {
    if (!assertTrustedSender(event)) return { ok: false, error: { kind: 'not_logged_in' as const } }
    if (typeof groupId !== 'string' || typeof userId !== 'string' || !groupId.trim() || !userId.trim()) {
      return { ok: false, error: { kind: 'server' as const, message: 'invalid groupId/userId' } }
    }
    return cloudGroups.invite(groupId, userId)
  })

  handleIpc(IpcChannels.cloud.invoke.groupMessages, async (event: IpcMainInvokeEvent, query: unknown) => {
    if (!assertTrustedSender(event)) return { ok: false, error: { kind: 'not_logged_in' as const } }
    const q = query && typeof query === 'object' ? (query as Record<string, unknown>) : {}
    if (typeof q.groupId !== 'string' || !q.groupId.trim()) {
      return { ok: false, error: { kind: 'server' as const, message: 'invalid groupId' } }
    }
    const sinceId = typeof q.sinceId === 'string' && q.sinceId ? q.sinceId : '0'
    const limit = typeof q.limit === 'number' && Number.isFinite(q.limit) ? q.limit : 50
    return cloudGroups.listMessages(q.groupId, sinceId, limit)
  })

  handleIpc(IpcChannels.cloud.invoke.groupSend, async (event: IpcMainInvokeEvent, groupId: unknown, content: unknown) => {
    if (!assertTrustedSender(event)) return { ok: false, error: { kind: 'not_logged_in' as const } }
    if (typeof groupId !== 'string' || typeof content !== 'string' || !content.trim()) {
      return { ok: false, error: { kind: 'server' as const, message: 'invalid groupId/content' } }
    }
    return cloudGroups.sendMessage(groupId, content)
  })

  /* ── 统一日志系统（log-hub） ─────────────────────────────────────────── */

  handleIpc(IpcChannels.log.invoke.append, (event: IpcMainInvokeEvent, entries: unknown) => {
    // fire-and-forget：仅校验调用方与入参形状，不向渲染层返回业务结果
    if (!assertTrustedSender(event)) return
    logHub.appendFromRenderer(entries as Array<unknown>)
  })

  handleIpc(IpcChannels.log.invoke.query, (event: IpcMainInvokeEvent, params: LogQueryParams) => {
    if (!assertTrustedSender(event)) return { total: 0, entries: [] }
    return logHub.query(params && typeof params === 'object' ? params : {})
  })

  handleIpc(IpcChannels.log.invoke.clear, (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return
    logHub.clear()
    logger.info('[log:clear] memory log buffer cleared')
  })

  handleIpc(IpcChannels.log.invoke.export, (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return ''
    try {
      return logHub.exportBuffer()
    } catch (err) {
      logger.error('[log:export] failed:', err)
      return ''
    }
  })

  handleIpc(IpcChannels.log.invoke.getSegments, (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return []
    return logHub.getLogSegments()
  })

  handleIpc(IpcChannels.log.invoke.openDir, async (event: IpcMainInvokeEvent) => {
    if (!assertTrustedSender(event)) return false
    const error = await shell.openPath(PATHS.logs)
    return !error
  })

  /**
   * log:upload —— 诊断日志手动上传（辰汐云端统一链路）。
   * 资格：仅辰汐通行证登录态可用（未登录返回 not_logged_in）；只由用户在日志页手动点击触发，绝不自动上传。
   * 隐私：上报前经 log-hub.buildUploadEntries 脱敏——丢弃 data 附件（截图 dataURL 等）、
   *       message 截断 2000 字符、抹除 Bearer / sk- / lcx_ 令牌片段。
   * 契约：POST /api/v1/logs/ingest（Bearer 通行证令牌），body
   *       { source:'luominest-desktop', appVersion, os, entries≤1000 }；
   *       服务端 Result 信封 code==0 成功，data={reportId, received}；429=限频；413 语义=过大。
   */
  handleIpc(IpcChannels.log.invoke.upload, async (event: IpcMainInvokeEvent): Promise<LogUploadResult> => {
    if (!assertTrustedSender(event)) return { ok: false, reason: 'server' }

    const tokens = loadCloudTokens()
    if (!tokens?.accessToken) {
      return { ok: false, reason: 'not_logged_in' }
    }

    const endpoint = configStore.getLogUploadEndpoint()
    const entries = logHub.buildUploadEntries()

    const postIngest = async (accessToken: string): Promise<{ status: number; payload: Record<string, unknown> | null }> => {
      try {
        const response = await net.fetch(endpoint, {
          method: 'POST',
          headers: { 'content-type': 'application/json', authorization: `Bearer ${accessToken}` },
          body: JSON.stringify({
            source: 'luominest-desktop',
            appVersion: app.getVersion(),
            os: `${process.platform} ${process.arch}`,
            entries,
          }),
          signal: AbortSignal.timeout(LOG_UPLOAD_TIMEOUT_MS),
        })
        const payload = (await response.json().catch(() => null)) as Record<string, unknown> | null
        return {
          status: response.status,
          payload: payload && typeof payload === 'object' && !Array.isArray(payload) ? payload : null,
        }
      } catch (err) {
        // 网络失败 / 15s 超时（TimeoutError）/ 其他异常统一归为 network
        logger.error('[log:upload] request failed:', err instanceof Error ? err.message : err)
        return { status: 0, payload: null }
      }
    }

    let result = await postIngest(tokens.accessToken)
    if (result.status === 401) {
      // 令牌过期：走现有续期路径后用新令牌重试一次（与 cloud-groups 同款自愈，不循环轰炸）
      logger.debug('[log:upload] got 401; renewing tokens and retrying once')
      const renewed = await renewCloudTokensNow()
      const next = loadCloudTokens()
      if (renewed && next?.accessToken) {
        result = await postIngest(next.accessToken)
      }
    }

    if (result.status === 0) return { ok: false, reason: 'network' }
    if (result.status === 401) return { ok: false, reason: 'unauthorized', status: result.status }
    if (result.status === 429) return { ok: false, reason: 'rate_limited', status: result.status }
    if (result.status === 413) return { ok: false, reason: 'too_large', status: result.status }
    if (result.status < 200 || result.status >= 300) {
      return { ok: false, reason: 'server', status: result.status }
    }

    // Result 信封解析：code!=0 视为业务失败（HTTP 可能仍是 200）
    const code = typeof result.payload?.code === 'number' ? result.payload.code : 0
    if (code !== 0) {
      logger.warn(`[log:upload] server rejected with envelope code=${code}`)
      return { ok: false, reason: 'server', status: result.status }
    }
    const data =
      result.payload?.data && typeof result.payload.data === 'object' && !Array.isArray(result.payload.data)
        ? (result.payload.data as Record<string, unknown>)
        : (result.payload ?? {})
    const reportId = typeof data.reportId === 'string' && data.reportId ? data.reportId : undefined
    logger.info(`[log:upload] uploaded ${entries.length} entries (reportId=${reportId ?? '-'})`)
    return { ok: true, reportId, status: result.status }
  })
}

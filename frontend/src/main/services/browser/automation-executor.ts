/**
 * LuomiNest 浏览器自动化执行器。
 *
 * 在 Electron Main 进程中运行，接收 WS Client 分发的自动化请求，
 * 通过 Electron 原生 API（webContents.executeJavaScript / sendInputEvent / capturePage）
 * 操作 WebContentsView 实现页面自动化。
 *
 * 元素定位策略：
 * - selector 为纯数字 → 按 data-luomi-index 属性查找（AI 友好）
 * - selector 为字符串 → 按 CSS 选择器查找
 *
 * 人类化输入：
 * - human: true（默认）→ 使用 LuminousHumanMouse/Keyboard（Phase 3 接入）
 * - human: false → 直接 sendInputEvent
 *
 * 只读化说明（2026-09）：AI 工具面只暴露 navigate_and_screenshot（browser_visit）
 * 与 screenshot；click/type/get_html 等动作保留在 executor 内部以兼容 WS 协议，
 * 不再对 AI 暴露。
 *
 * W4-7 只读白名单：execute() 入口统一收敛 IPC（browserAutomation.execute）与
 * WS（AI 侧）两个调用方，仅放行 READ_ONLY_AUTOMATION_ACTIONS 中的 6 个只读/
 * 标签页管理动作——click/type/execute_js 等 27 个交互动作自此对 IPC 与 AI
 * 双侧均不可达（渲染层 UI 所需的停止加载改走 tab:stop 专用通道，见 tab.ts
 * stopNavigation）。
 */
import { WebContents } from 'electron'

import { tabManager } from './tab'
import { luomiBrowserWSClient, AutomationResult } from './ws-client'
import { LUOMI_DOM_TREE_SCRIPT, getDomTreeCallScript } from './luomi-dom-tree'
import { createLuomiNestLogger } from '../luomi-logger'

const logger = createLuomiNestLogger('Browser')

/**
 * W4-7 只读白名单：允许从 IPC 与 WS（AI）入口执行的动作全集。
 * 命中 navigate_and_screenshot / screenshot 时 execute() 会先确保目标标签页
 * 可用（休眠自动唤醒，见 TabManager.acquireCaptureTarget）。
 */
export const READ_ONLY_AUTOMATION_ACTIONS: ReadonlySet<string> = new Set([
  'navigate_and_screenshot',
  'screenshot',
  'get_tabs',
  'switch_tab',
  'open_tab',
  'close_tab'
])

// 人类化输入接口（Phase 3 实现，此处仅定义类型）
export interface HumanInputLayer {
  click: (webContents: WebContents, x: number, y: number) => Promise<void>
  type: (webContents: WebContents, text: string) => Promise<void>
  scroll: (webContents: WebContents, deltaX: number, deltaY: number) => Promise<void>
  hover: (webContents: WebContents, x: number, y: number) => Promise<void>
}

type ActionHandler = (args: Record<string, unknown>, wc: WebContents) => Promise<{ success: boolean; data?: unknown; error?: string }>
type TabActionHandler = (args: Record<string, any>) => Promise<AutomationResult>

class LuomiAutomationExecutor {
  private handlers: Map<string, ActionHandler> = new Map()
  private tabHandlers: Map<string, TabActionHandler> = new Map()
  private humanLayer: HumanInputLayer | null = null

  constructor() {
    this.registerHandlers()
    this.registerTabHandlers()
    // 向 WS 客户端注册自己
    luomiBrowserWSClient.setHandler(this.execute.bind(this))
  }

  /** 注入人类化输入层（Phase 3 调用） */
  setHumanLayer(layer: HumanInputLayer): void {
    this.humanLayer = layer
  }

  /** 主入口：执行自动化动作 */
  async execute(action: string, args: Record<string, any>): Promise<AutomationResult> {
    // W4-7：只读白名单收敛——IPC 与 AI（WS）双侧统一在此拦截，白名单外一律拒绝
    if (!READ_ONLY_AUTOMATION_ACTIONS.has(action)) {
      logger.warn(`已拒绝白名单外的自动化动作: ${action}`)
      return { success: false, error: `动作 ${action} 不在只读白名单内，已拒绝执行` }
    }

    // 标签页管理类动作（不需要 webContents，直接操作 tabManager）
    const tabHandler = this.tabHandlers.get(action)
    if (tabHandler) {
      try {
        return await tabHandler(args)
      } catch (e: unknown) {
        logger.error(`动作 ${action} 执行异常:`, e)
        const errMsg = e instanceof Error ? e.message : String(e)
        return { success: false, error: errMsg }
      }
    }

    const handler = this.handlers.get(action)
    if (!handler) {
      return { success: false, error: `未知自动化动作: ${action}` }
    }

    // W4-5：截图类动作先确保目标标签页可用——休眠（webContents 已销毁）自动
    // 唤醒重建；其余动作维持原语义（休眠即报错）。截图完成后恢复原激活状态。
    const tabId = args.tab_id as string | undefined
    let wc: WebContents
    let restore: (() => Promise<void>) | null = null
    try {
      if (action === 'screenshot' || action === 'navigate_and_screenshot') {
        const target = await tabManager.acquireCaptureTarget(tabId)
        if (!target) {
          return {
            success: false,
            error: tabId ? `标签页不存在或不可用: ${tabId}` : '无可用标签页，且自动创建失败'
          }
        }
        wc = target.wc
        restore = target.restore
      } else {
        const existing = tabManager.getWebContents(tabId)
        if (!existing) {
          return { success: false, error: '无可用标签页或标签页正在休眠，请先创建标签页' }
        }
        wc = existing
      }

      return await handler(args, wc)
    } catch (e: unknown) {
      logger.error(`动作 ${action} 执行异常:`, e)
      const errMsg = e instanceof Error ? e.message : String(e)
      return { success: false, error: errMsg }
    } finally {
      if (restore) {
        await restore()
      }
    }
  }

  /** 判断是否使用人类化输入 */
  private useHuman(args: Record<string, any>): boolean {
    return args.human !== false && this.humanLayer !== null
  }

  /** 确保页面已注入 DOM 树构建脚本 */
  private async ensureDomTreeScript(wc: WebContents): Promise<void> {
    // 运行时检查而非缓存：loadURL/reload 会重建 JS 上下文，window.buildLuomiDomTree 丢失
    const injected = await wc.executeJavaScript('typeof window.buildLuomiDomTree === "function"')
    if (injected) return
    await wc.executeJavaScript(LUOMI_DOM_TREE_SCRIPT)
  }

  /**
   * 解析元素选择器，返回元素中心坐标
   * 支持 data-luomi-index 数字索引和 CSS 选择器
   */
  private async resolveElement(
    wc: WebContents,
    selector: string
  ): Promise<{ x: number; y: number; width: number; height: number; tag: string; text: string } | null> {
    const script = `
      (function(sel) {
        let el;
        if (/^\\d+$/.test(String(sel))) {
          el = document.querySelector('[data-luomi-index="' + sel + '"]');
        } else {
          el = document.querySelector(sel);
        }
        if (!el) return null;
        el.scrollIntoView({ block: 'center', behavior: 'instant' });
        const rect = el.getBoundingClientRect();
        return {
          x: rect.x + rect.width / 2,
          y: rect.y + rect.height / 2,
          width: rect.width,
          height: rect.height,
          tag: el.tagName.toLowerCase(),
          text: (el.innerText || el.textContent || '').slice(0, 100)
        };
      })(${JSON.stringify(selector)})
    `
    const result = await wc.executeJavaScript(script)
    return result
  }

  private registerHandlers(): void {
    // ===== 导航类 =====
    this.handlers.set('navigate', async (args, wc) => {
      const url = args.url as string
      if (!url) return { success: false, error: '缺少 url 参数' }
      await wc.loadURL(url)
      return { success: true, data: { url } }
    })

    // 复合动作：导航 → 等待加载（did-finish-load + 稳定期）→ 自动截图
    // 供 AI 工具 browser_visit 使用；超时也尽力截图并返回 ok:false + 已得信息
    this.handlers.set('navigate_and_screenshot', async (args, wc) => {
      const url = args.url as string
      if (!url) return { success: false, error: '缺少 url 参数' }

      // load 等待超时（默认 20s）；稳定期默认 1.5s（0~10s 可配）
      const timeoutMs = Math.min(60, Math.max(5, Number(args.timeout_seconds) || 20)) * 1000
      const stableMs = Math.min(10, Math.max(0, Number(args.wait_seconds ?? 1.5))) * 1000

      let loadError: string | null = null
      await new Promise<void>((resolve) => {
        let settled = false
        const finish = (): void => {
          if (settled) return
          settled = true
          clearTimeout(timer)
          wc.removeListener('did-finish-load', onLoad)
          wc.removeListener('did-fail-load', onFail)
          resolve()
        }
        const timer = setTimeout(() => {
          if (!loadError) loadError = `页面加载超时 (${timeoutMs / 1000}s)`
          finish()
        }, timeoutMs)
        const onLoad = () => finish()
        const onFail = (
          _e: unknown,
          errorCode: number,
          errorDescription: string,
          validatedUrl: string,
          isMainFrame: boolean
        ): void => {
          // -3 ERR_ABORTED：被新导航取代，非真实失败，继续等待
          if (!isMainFrame || errorCode === -3) return
          if (!loadError) {
            loadError = `页面加载失败 (${errorCode}): ${errorDescription}` + (validatedUrl ? ` — ${validatedUrl}` : '')
          }
        }
        wc.on('did-finish-load', onLoad)
        wc.on('did-fail-load', onFail)
        wc.loadURL(url).catch((err) => {
          const msg = err instanceof Error ? err.message : String(err)
          if (!msg.includes('ERR_ABORTED') && !loadError) loadError = msg
        })
      })

      // 渲染稳定期：load 完成后再等待片刻，让动态内容完成首帧渲染
      if (stableMs > 0) {
        await new Promise((r) => setTimeout(r, stableMs))
      }

      // 尽力截图：失败不阻断信息返回
      // W4-5：经 TabManager.captureTabPage 截图——stayAwake 后台截帧，
      // 空帧降级为临时激活截屏并恢复原激活状态，休眠标签已被 execute() 唤醒
      let screenshot: string | undefined
      try {
        const image = await tabManager.captureTabPage(args.tab_id as string | undefined)
        if (image) {
          screenshot = image.toDataURL()
        }
      } catch (e) {
        logger.warn('navigate_and_screenshot 截图失败:', e)
      }

      return {
        // WS 协议层恒为 success:true（success:false 会转为 RuntimeError），
        // 加载成败通过 data.ok 表达，超时/失败时仍携带截图与已得信息
        success: true,
        data: {
          ok: !loadError,
          final_url: wc.getURL(),
          title: wc.getTitle(),
          screenshot,
          ...(loadError ? { error: loadError } : {})
        }
      }
    })

    this.handlers.set('go_back', async (_args, wc) => {
      if (!wc.navigationHistory.canGoBack()) {
        return { success: false, error: '无法后退：历史记录为空' }
      }
      wc.navigationHistory.goBack()
      return { success: true }
    })

    this.handlers.set('go_forward', async (_args, wc) => {
      if (!wc.navigationHistory.canGoForward()) {
        return { success: false, error: '无法前进：历史记录为空' }
      }
      wc.navigationHistory.goForward()
      return { success: true }
    })

    this.handlers.set('reload', async (_args, wc) => {
      wc.reload()
      return { success: true }
    })

    this.handlers.set('get_url', async (_args, wc) => {
      return { success: true, data: { url: wc.getURL() } }
    })

    // ===== 交互类 =====
    this.handlers.set('click', async (args, wc) => {
      const selector = args.selector as string
      if (!selector) return { success: false, error: '缺少 selector 参数' }

      const el = await this.resolveElement(wc, selector)
      if (!el) return { success: false, error: `未找到元素: ${selector}` }

      if (this.useHuman(args) && this.humanLayer) {
        await this.humanLayer.click(wc, el.x, el.y)
      } else {
        wc.sendInputEvent({ type: 'mouseMove', x: el.x, y: el.y })
        wc.sendInputEvent({ type: 'mouseDown', x: el.x, y: el.y, button: 'left', clickCount: 1 })
        wc.sendInputEvent({ type: 'mouseUp', x: el.x, y: el.y, button: 'left', clickCount: 1 })
      }
      return { success: true, data: { tag: el.tag, text: el.text } }
    })

    this.handlers.set('type', async (args, wc) => {
      const selector = args.selector as string
      const text = args.text as string
      if (!selector) return { success: false, error: '缺少 selector 参数' }
      if (text === undefined || text === null) return { success: false, error: '缺少 text 参数' }

      const el = await this.resolveElement(wc, selector)
      if (!el) return { success: false, error: `未找到元素: ${selector}` }

      // 聚焦元素
      await wc.executeJavaScript(`
        (function(sel) {
          let el;
          if (/^\\d+$/.test(String(sel))) {
            el = document.querySelector('[data-luomi-index="' + sel + '"]');
          } else {
            el = document.querySelector(sel);
          }
          if (el) { el.focus(); el.click(); }
        })(${JSON.stringify(selector)})
      `)

      // 清空现有内容（可选）
      if (args.clear) {
        await wc.executeJavaScript(`
          (function(sel) {
            let el;
            if (/^\\d+$/.test(String(sel))) {
              el = document.querySelector('[data-luomi-index="' + sel + '"]');
            } else {
              el = document.querySelector(sel);
            }
            if (el) {
              el.value = '';
              el.dispatchEvent(new Event('input', { bubbles: true }));
            }
          })(${JSON.stringify(selector)})
        `)
      }

      if (this.useHuman(args) && this.humanLayer) {
        await this.humanLayer.type(wc, String(text))
      } else {
        for (const ch of String(text)) {
          wc.sendInputEvent({ type: 'char', keyCode: ch })
        }
      }
      return { success: true, data: { typed: String(text).length } }
    })

    this.handlers.set('press_key', async (args, wc) => {
      const key = args.key as string
      if (!key) return { success: false, error: '缺少 key 参数' }

      wc.sendInputEvent({ type: 'keyDown', keyCode: key })
      wc.sendInputEvent({ type: 'keyUp', keyCode: key })
      return { success: true, data: { key } }
    })

    this.handlers.set('scroll', async (args, wc) => {
      const deltaX = Number(args.deltaX) || 0
      const deltaY = Number(args.deltaY) || 300

      if (this.useHuman(args) && this.humanLayer) {
        await this.humanLayer.scroll(wc, deltaX, deltaY)
      } else {
        wc.sendInputEvent({ type: 'mouseWheel', x: 0, y: 0, deltaX, deltaY, wheelTicksY: deltaY / 100 })
      }
      return { success: true, data: { deltaX, deltaY } }
    })

    this.handlers.set('hover', async (args, wc) => {
      const selector = args.selector as string
      if (!selector) return { success: false, error: '缺少 selector 参数' }

      const el = await this.resolveElement(wc, selector)
      if (!el) return { success: false, error: `未找到元素: ${selector}` }

      if (this.useHuman(args) && this.humanLayer) {
        await this.humanLayer.hover(wc, el.x, el.y)
      } else {
        wc.sendInputEvent({ type: 'mouseMove', x: el.x, y: el.y })
      }
      return { success: true, data: { tag: el.tag } }
    })

    // ===== 提取类 =====
    this.handlers.set('get_dom_tree', async (args, wc) => {
      await this.ensureDomTreeScript(wc)
      const maxDepth = Number(args.maxDepth) || 10
      const maxElements = Number(args.maxElements) || 200
      const result = await wc.executeJavaScript(getDomTreeCallScript(maxDepth, maxElements))
      return { success: true, data: result }
    })

    this.handlers.set('get_text', async (args, wc) => {
      const selector = args.selector as string
      if (!selector) {
        // 无 selector 时返回整页文本
        const text = await wc.executeJavaScript('document.body.innerText')
        return { success: true, data: { text: String(text).slice(0, 5000) } }
      }

      const script = `
        (function(sel) {
          let el;
          if (/^\\d+$/.test(String(sel))) {
            el = document.querySelector('[data-luomi-index="' + sel + '"]');
          } else {
            el = document.querySelector(sel);
          }
          if (!el) return null;
          return { text: el.innerText || el.textContent || '', tag: el.tagName.toLowerCase() };
        })(${JSON.stringify(selector)})
      `
      const result = await wc.executeJavaScript(script)
      if (!result) return { success: false, error: `未找到元素: ${selector}` }
      return { success: true, data: { text: String(result.text).slice(0, 5000), tag: result.tag } }
    })

    this.handlers.set('screenshot', async (args, _wc) => {
      // W4-5：经 TabManager.captureTabPage 截图——休眠标签先唤醒，
      // capturePage 加 stayAwake 后台截帧，空帧降级激活截屏并还原激活状态
      const image = await tabManager.captureTabPage(args.tab_id as string | undefined)
      if (!image) {
        return { success: false, error: '截图失败：标签页不可用或画面为空' }
      }
      const dataUrl = image.toDataURL()
      return { success: true, data: { screenshot: dataUrl } }
    })

    this.handlers.set('get_page_title', async (_args, wc) => {
      return { success: true, data: { title: wc.getTitle() } }
    })

    // ===== 执行类 =====
    this.handlers.set('execute_js', async (args, wc) => {
      const script = args.script as string
      if (!script) return { success: false, error: '缺少 script 参数' }
      const result = await wc.executeJavaScript(script)
      return { success: true, data: { result } }
    })

    this.handlers.set('wait_for_load', async (args, wc) => {
      // 统一 timeout 单位：args.timeout 为秒，* 1000 转毫秒（与 wait_for_element/wait_for_url 一致）
      const timeout = Number(args.timeout) * 1000 || 30000
      // 若已在加载中，等待 did-finish-load；否则直接返回
      if (!wc.isLoading()) {
        return { success: true, data: { alreadyLoaded: true } }
      }

      return new Promise((resolve) => {
        const timer = setTimeout(() => {
          wc.removeListener('did-finish-load', onLoad)
          resolve({ success: false, error: `等待页面加载超时 (${timeout / 1000}s)` })
        }, timeout)

        const onLoad = () => {
          clearTimeout(timer)
          resolve({ success: true })
        }
        wc.once('did-finish-load', onLoad)
      })
    })

    // ===== 扩展交互类 =====
    this.handlers.set('double_click', async (args, wc) => {
      const selector = args.selector as string
      if (!selector) return { success: false, error: '缺少 selector 参数' }

      const el = await this.resolveElement(wc, selector)
      if (!el) return { success: false, error: `未找到元素: ${selector}` }

      if (this.useHuman(args) && this.humanLayer) {
        await this.humanLayer.click(wc, el.x, el.y)
        await new Promise((r) => setTimeout(r, 50 + Math.random() * 100))
        await this.humanLayer.click(wc, el.x, el.y)
      } else {
        // 双击：down(1)→up(1)→down(2)→up(2)
        wc.sendInputEvent({ type: 'mouseDown', x: el.x, y: el.y, button: 'left', clickCount: 1 })
        wc.sendInputEvent({ type: 'mouseUp', x: el.x, y: el.y, button: 'left', clickCount: 1 })
        wc.sendInputEvent({ type: 'mouseDown', x: el.x, y: el.y, button: 'left', clickCount: 2 })
        wc.sendInputEvent({ type: 'mouseUp', x: el.x, y: el.y, button: 'left', clickCount: 2 })
      }
      return { success: true, data: { tag: el.tag, text: el.text } }
    })

    this.handlers.set('right_click', async (args, wc) => {
      const selector = args.selector as string
      if (!selector) return { success: false, error: '缺少 selector 参数' }

      const el = await this.resolveElement(wc, selector)
      if (!el) return { success: false, error: `未找到元素: ${selector}` }

      wc.sendInputEvent({ type: 'mouseMove', x: el.x, y: el.y })
      wc.sendInputEvent({ type: 'mouseDown', x: el.x, y: el.y, button: 'right', clickCount: 1 })
      wc.sendInputEvent({ type: 'mouseUp', x: el.x, y: el.y, button: 'right', clickCount: 1 })
      return { success: true, data: { tag: el.tag } }
    })

    this.handlers.set('clear_input', async (args, wc) => {
      const selector = args.selector as string
      if (!selector) return { success: false, error: '缺少 selector 参数' }

      const script = `
        (function(sel) {
          let el;
          if (/^\\d+$/.test(String(sel))) {
            el = document.querySelector('[data-luomi-index="' + sel + '"]');
          } else {
            el = document.querySelector(sel);
          }
          if (!el) return false;
          el.focus();
          el.value = '';
          el.dispatchEvent(new Event('input', { bubbles: true }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
          return true;
        })(${JSON.stringify(selector)})
      `
      const ok = await wc.executeJavaScript(script)
      if (!ok) return { success: false, error: `未找到元素: ${selector}` }
      return { success: true }
    })

    this.handlers.set('select_option', async (args, wc) => {
      const selector = args.selector as string
      const value = args.value as string
      if (!selector) return { success: false, error: '缺少 selector 参数' }
      if (value === undefined || value === null) return { success: false, error: '缺少 value 参数' }

      const script = `
        (function(sel, val) {
          let el;
          if (/^\\d+$/.test(String(sel))) {
            el = document.querySelector('[data-luomi-index="' + sel + '"]');
          } else {
            el = document.querySelector(sel);
          }
          if (!el) return { found: false };
          if (el.tagName.toLowerCase() !== 'select') return { found: true, isSelect: false };
          el.value = val;
          el.dispatchEvent(new Event('change', { bubbles: true }));
          return { found: true, isSelect: true, value: el.value };
        })(${JSON.stringify(selector)}, ${JSON.stringify(String(value))})
      `
      const result = await wc.executeJavaScript(script)
      if (!result || !result.found) return { success: false, error: `未找到元素: ${selector}` }
      if (!result.isSelect) return { success: false, error: '目标元素不是 <select> 标签' }
      return { success: true, data: { value: result.value } }
    })

    // ===== 扩展提取类 =====
    this.handlers.set('get_attribute', async (args, wc) => {
      const selector = args.selector as string
      const attribute = args.attribute as string
      if (!selector) return { success: false, error: '缺少 selector 参数' }
      if (!attribute) return { success: false, error: '缺少 attribute 参数' }

      const script = `
        (function(sel, attr) {
          let el;
          if (/^\\d+$/.test(String(sel))) {
            el = document.querySelector('[data-luomi-index="' + sel + '"]');
          } else {
            el = document.querySelector(sel);
          }
          if (!el) return null;
          return { attribute: attr, value: el.getAttribute(attr), tag: el.tagName.toLowerCase() };
        })(${JSON.stringify(selector)}, ${JSON.stringify(attribute)})
      `
      const result = await wc.executeJavaScript(script)
      if (!result) return { success: false, error: `未找到元素: ${selector}` }
      return { success: true, data: result }
    })

    this.handlers.set('get_html', async (args, wc) => {
      const selector = args.selector as string
      if (!selector) {
        const html = await wc.executeJavaScript('document.body.outerHTML')
        return { success: true, data: { html: String(html).slice(0, 5000) } }
      }

      const script = `
        (function(sel) {
          let el;
          if (/^\\d+$/.test(String(sel))) {
            el = document.querySelector('[data-luomi-index="' + sel + '"]');
          } else {
            el = document.querySelector(sel);
          }
          if (!el) return null;
          return { html: el.outerHTML, tag: el.tagName.toLowerCase() };
        })(${JSON.stringify(selector)})
      `
      const result = await wc.executeJavaScript(script)
      if (!result) return { success: false, error: `未找到元素: ${selector}` }
      return { success: true, data: { html: String(result.html).slice(0, 5000), tag: result.tag } }
    })

    // ===== 扩展等待类 =====
    this.handlers.set('wait_for_element', async (args, wc) => {
      const selector = args.selector as string
      if (!selector) return { success: false, error: '缺少 selector 参数' }
      const timeout = Number(args.timeout) * 1000 || 30000
      const interval = 200
      const start = Date.now()

      const checkScript = `
        (function(sel) {
          let el;
          if (/^\\d+$/.test(String(sel))) {
            el = document.querySelector('[data-luomi-index="' + sel + '"]');
          } else {
            el = document.querySelector(sel);
          }
          return !!el;
        })(${JSON.stringify(selector)})
      `

      while (Date.now() - start < timeout) {
        const found = await wc.executeJavaScript(checkScript)
        if (found) return { success: true, data: { selector, waitedMs: Date.now() - start } }
        await new Promise((r) => setTimeout(r, interval))
      }
      return { success: false, error: `等待元素超时 (${timeout / 1000}s): ${selector}` }
    })

    this.handlers.set('wait_for_url', async (args, wc) => {
      const timeout = Number(args.timeout) * 1000 || 30000
      const urlPattern = args.url_pattern as string | undefined
      const startUrl = wc.getURL()

      // 预编译正则，避免每次导航回调重复构造，并在无效模式时提前报错
      let regex: RegExp | null = null
      if (urlPattern) {
        try {
          regex = new RegExp(urlPattern)
        } catch (e) {
          const errMsg = e instanceof Error ? e.message : String(e)
          return { success: false, error: `无效的 URL 匹配模式: ${errMsg}` }
        }
      }

      return new Promise((resolve) => {
        const timer = setTimeout(() => {
          wc.removeListener('did-navigate', onNavigate)
          resolve({ success: false, error: `等待 URL 变化超时 (${timeout / 1000}s)` })
        }, timeout)

        const onNavigate = (_event: unknown, url: string) => {
          if (!regex || regex.test(url)) {
            clearTimeout(timer)
            wc.removeListener('did-navigate', onNavigate)
            resolve({ success: true, data: { from: startUrl, to: url } })
          }
        }
        wc.on('did-navigate', onNavigate)
      })
    })

    // ===== 扩展执行类 =====
    this.handlers.set('get_history', async (_args, wc) => {
      const data: Record<string, unknown> = {
        canGoBack: wc.navigationHistory.canGoBack(),
        canGoForward: wc.navigationHistory.canGoForward(),
        currentUrl: wc.getURL(),
      }
      // 尝试获取历史条目（Electron 36+ navigationHistory.getAll）
      try {
        const entries = (wc.navigationHistory as unknown as { getAll: () => Array<{ url: string }> }).getAll()
        if (Array.isArray(entries)) {
          data.entries = entries.slice(-20)
          data.activeIndex = entries.findIndex((e: { url: string }) => e.url === wc.getURL())
        }
      } catch {
        // getAll 不可用则仅返回可后退/前进状态
      }
      return { success: true, data }
    })
  }

  private registerTabHandlers(): void {
    // ===== 标签页管理类（不操作 webContents，直接操作 tabManager） =====
    this.tabHandlers.set('get_tabs', async () => {
      const tabs = tabManager.getAllTabs()
      return {
        success: true,
        data: {
          tabs: tabs.map(t => ({
            id: t.id,
            title: t.title,
            url: t.url,
            active: !!t.active,
            sleeping: !!t.sleeping,
            loading: !!t.loading
          })),
          activeTabId: tabs.find(t => t.active)?.id ?? null,
          count: tabs.length
        }
      }
    })

    this.tabHandlers.set('switch_tab', async (args) => {
      const tabId = args.tab_id as string
      if (!tabId) return { success: false, error: '缺少 tab_id 参数' }

      const tab = tabManager.getTab(tabId)
      if (!tab) return { success: false, error: `标签页不存在: ${tabId}` }

      await tabManager.activateTab(tabId)
      return {
        success: true,
        data: {
          tabId,
          title: tab.title,
          url: tab.url
        }
      }
    })

    this.tabHandlers.set('open_tab', async (args) => {
      const url = (args.url as string) || ''
      const title = (args.title as string) || ''
      try {
        const tab = tabManager.createTab(url || undefined)
        if (title) {
          tab.title = title
        }
        return {
          success: true,
          data: {
            tab_id: tab.id,
            url: tab.url,
            title: tab.title
          }
        }
      } catch (e: unknown) {
        const errMsg = e instanceof Error ? e.message : String(e)
        return { success: false, error: errMsg }
      }
    })

    this.tabHandlers.set('close_tab', async (args) => {
      const tabId = args.tab_id as string
      if (!tabId) return { success: false, error: '缺少 tab_id 参数' }

      const tab = tabManager.getTab(tabId)
      if (!tab) return { success: false, error: `标签页不存在: ${tabId}` }

      tabManager.closeTab(tabId)
      return {
        success: true,
        data: { closed_tab_id: tabId }
      }
    })
  }
}

export const luomiAutomationExecutor = new LuomiAutomationExecutor()

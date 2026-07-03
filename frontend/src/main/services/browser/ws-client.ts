/**
 * LuomiNest 浏览器自动化 WebSocket 客户端。
 *
 * 在 Electron Main 进程中常驻运行，连接后端 ws://127.0.0.1:18000/ws/browser，
 * 接收后端 AI 工具发来的自动化请求，分发给 AutomationExecutor 执行，
 * 然后将结果回传后端。
 *
 * 特性：
 * 1. 指数退避自动重连（1s → 2s → 4s → 8s → ... → 30s 封顶）
 * 2. ping/pong 心跳响应
 * 3. 可插拔执行器：通过 setHandler 注册自动化执行回调
 */

const WS_URL = 'ws://127.0.0.1:18000/ws/browser'
const INITIAL_RECONNECT_DELAY = 1000
const MAX_RECONNECT_DELAY = 30000

export interface AutomationResult {
  success: boolean
  data?: any
  error?: string
}

export type AutomationHandler = (action: string, args: Record<string, any>) => Promise<AutomationResult>

class LuomiBrowserWSClient {
  private ws: WebSocket | null = null
  private reconnectDelay = INITIAL_RECONNECT_DELAY
  private shouldReconnect = false
  private handler: AutomationHandler | null = null
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null

  /** 注册自动化执行器（由 AutomationExecutor 在初始化时调用） */
  setHandler(handler: AutomationHandler): void {
    this.handler = handler
  }

  /** 启动 WS 客户端，开始连接后端 */
  start(): void {
    if (this.shouldReconnect) {
      console.log('[BrowserWS] Client already started')
      return
    }
    this.shouldReconnect = true
    this.connect()
  }

  /** 停止 WS 客户端，不再重连 */
  stop(): void {
    this.shouldReconnect = false
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.ws) {
      try {
        this.ws.close(1000, 'Client shutting down')
      } catch {
        // ignore
      }
      this.ws = null
    }
    console.log('[BrowserWS] Client stopped')
  }

  /** 当前是否已连接 */
  get isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN
  }

  private connect(): void {
    console.log(`[BrowserWS] Connecting to ${WS_URL}...`)

    try {
      this.ws = new WebSocket(WS_URL)
    } catch (e) {
      console.error('[BrowserWS] Failed to create WebSocket:', e)
      this.scheduleReconnect()
      return
    }

    this.ws.onopen = () => {
      console.log('[BrowserWS] Connected to backend')
      this.reconnectDelay = INITIAL_RECONNECT_DELAY
    }

    this.ws.onmessage = (event: MessageEvent) => {
      this.handleMessage(event.data as string)
    }

    this.ws.onerror = (event: Event) => {
      console.error('[BrowserWS] Connection error:', event)
    }

    this.ws.onclose = (event: CloseEvent) => {
      console.log(`[BrowserWS] Disconnected (code=${event.code}, reason=${event.reason})`)
      this.ws = null
      if (this.shouldReconnect) {
        this.scheduleReconnect()
      }
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
    }
    console.log(`[BrowserWS] Reconnecting in ${this.reconnectDelay}ms...`)
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      if (this.shouldReconnect) {
        this.connect()
      }
    }, this.reconnectDelay)

    // 指数退避，封顶 30s
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, MAX_RECONNECT_DELAY)
  }

  private async handleMessage(raw: string): Promise<void> {
    let message: any
    try {
      message = JSON.parse(raw)
    } catch {
      console.warn('[BrowserWS] Received invalid JSON:', raw.slice(0, 100))
      return
    }

    const msgType = message.type

    // 心跳：后端 ping → 前端 pong
    if (msgType === 'ping') {
      this.send({ type: 'pong' })
      return
    }

    // 自动化请求：分发到执行器
    if (msgType === 'automation_request') {
      const requestId = message.request_id
      const action = message.action
      const args = message.args || {}

      let result: AutomationResult
      if (this.handler) {
        try {
          result = await this.handler(action, args)
        } catch (e: any) {
          result = { success: false, error: e?.message || String(e) }
        }
      } else {
        result = { success: false, error: '自动化执行器尚未初始化' }
      }

      this.send({
        type: 'automation_response',
        request_id: requestId,
        success: result.success,
        data: result.data,
        error: result.error || '',
      })
      return
    }

    console.warn('[BrowserWS] Unknown message type:', msgType)
  }

  private send(message: any): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify(message))
      } catch (e) {
        console.error('[BrowserWS] Failed to send message:', e)
      }
    }
  }
}

export const luomiBrowserWSClient = new LuomiBrowserWSClient()

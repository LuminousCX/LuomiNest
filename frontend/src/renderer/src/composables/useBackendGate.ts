import { API_ENDPOINTS } from '../config/api'
import { createLuomiNestRendererLogger } from '../utils/logger'

/**
 * 后端就绪门闩（模块级单例）。
 *
 * 主进程采用「先建窗口、后启后端」的启动策略：渲染层挂载时后端往往还在
 * 初始化，此时发出的业务请求全部以 net::ERR_CONNECTION_REFUSED 失败（且
 * 失败不会自动重发）。这里统一在请求入口等待后端就绪：
 * - 就绪信号来自主进程的 backend stage 推送（spawning → waiting → ready）；
 * - preload 不可用（纯浏览器调试）时退化为轮询 /health；
 * - 超时兜底放行，保证后端异常时业务请求仍能以正常错误路径失败，
 *   而不是永久挂起。
 *
 * checkHealth 这类「探测后端是否活着」的请求必须绕过本门闩（否则死锁）。
 * 门闩仅覆盖首次启动语义：后端 restart 后 stage 不会回到未就绪，请求直接放行。
 */

const logger = createLuomiNestRendererLogger('BackendGate')

interface BackendStageEvent {
  stage: 'spawning' | 'waiting' | 'ready' | 'failed'
}

interface LuomiNestWindowApi {
  api?: {
    backend?: {
      subscribeStage?: (callback: (data: BackendStageEvent) => void) => () => void
    }
  }
}

/** 就绪等待上限：超过后放行请求，让业务错误走原有错误处理 */
const GATE_TIMEOUT_MS = 30000
/** 无主进程推送时的 /health 轮询间隔 */
const FALLBACK_POLL_INTERVAL_MS = 500

let ready = false
let gatePromise: Promise<boolean> | null = null

const resolveGate = (): Promise<boolean> =>
  new Promise((resolve) => {
    let settled = false
    let unsubscribe: (() => void) | undefined

    const settle = (isReady: boolean, reason: string): void => {
      if (settled) return
      settled = true
      window.clearTimeout(timer)
      try {
        unsubscribe?.()
      } catch {
        // ignore
      }
      if (!isReady) {
        logger.warn(`Backend gate released without readiness (${reason})`)
      }
      resolve(isReady)
    }

    const timer = window.setTimeout(() => settle(false, 'timeout'), GATE_TIMEOUT_MS)

    const win = window as unknown as LuomiNestWindowApi
    const subscribe = win.api?.backend?.subscribeStage
    if (subscribe) {
      unsubscribe = subscribe((data) => {
        if (data.stage === 'ready') {
          settle(true, 'stage-ready')
        }
        // failed：不提前放行，交给超时兜底（避免与后端自动重启竞态）
      })
      return
    }

    // 无 preload（纯浏览器调试）：直接轮询 /health
    const poll = async (): Promise<void> => {
      while (!settled) {
        try {
          const resp = await fetch(API_ENDPOINTS.HEALTH, { signal: AbortSignal.timeout(2000) })
          if (resp.ok) {
            settle(true, 'health-poll')
            return
          }
        } catch {
          // 后端未就绪，继续等
        }
        await new Promise((r) => setTimeout(r, FALLBACK_POLL_INTERVAL_MS))
      }
    }
    void poll()
  })

/**
 * 等待后端就绪。返回 true 表示确认就绪；false 表示超时兜底放行
 * （调用方应继续发起请求，由原有错误路径处理连接失败）。
 */
export const whenBackendReady = (): Promise<boolean> => {
  if (ready) return Promise.resolve(true)
  if (!gatePromise) {
    gatePromise = resolveGate().then((isReady) => {
      ready = isReady
      gatePromise = null
      return isReady
    })
  }
  return gatePromise
}

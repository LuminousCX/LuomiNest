import http from 'node:http'
import { CloudAuthError } from './auth-client'

/**
 * 本地回环直登接收器（授权码 + PKCE 的回调侧）：
 * 在 127.0.0.1 固定端口起一次性 HTTP 服务，等浏览器授权完成 302 回
 * /callback?code=…&state=…。端口绑定失败（被占/多实例）由 ready 拒绝，
 * 调用方据此自动降级 Device Flow。
 */
export class LoopbackBindError extends Error {
  readonly cause: unknown

  constructor(cause: unknown) {
    super('loopback bind failed')
    this.name = 'LoopbackBindError'
    this.cause = cause
  }
}

export interface DirectLoginSession {
  /** 端口绑定成功后 resolve（此刻打开授权页才不会白开）；绑定失败以 LoopbackBindError 拒绝 */
  ready: Promise<void>
  /** 授权码（已校验 state）；用户拒绝/超时/取消分别以对应错误拒绝 */
  code: Promise<string>
  /** 主动中止（登出/重新登录）：关闭服务并使 code 以 cancelled 拒绝 */
  cancel: () => void
}

/** 授权完成页（本地静态，无外部资源） */
const SUCCESS_PAGE =
  '<!doctype html><meta charset="utf-8"><title>LuomiNest</title>' +
  '<body style="font-family:system-ui,sans-serif;background:#101418;color:#e8eaed;' +
  'display:grid;place-items:center;height:100vh;margin:0"><p>授权完成，请返回应用。</p>'

export const startLoopbackServer = (
  port: number,
  expectedState: string,
  timeoutMs = 300_000
): DirectLoginSession => {
  let server: http.Server | null = null
  let timer: NodeJS.Timeout | null = null
  let settled = false
  let readyResolve!: () => void
  let readyReject!: (err: Error) => void
  let codeResolve!: (code: string) => void
  let codeReject!: (err: Error) => void

  const ready = new Promise<void>((resolve, reject) => {
    readyResolve = resolve
    readyReject = reject
  })
  const code = new Promise<string>((resolve, reject) => {
    codeResolve = resolve
    codeReject = reject
  })

  const cleanup = (): void => {
    if (settled) return
    settled = true
    if (timer) clearTimeout(timer)
    try {
      server?.close()
    } catch {
      // 服务未完全建立时的 close 异常可忽略（socket 随进程回收）
    }
  }

  server = http.createServer((req, res) => {
    try {
      const url = new URL(req.url ?? '/', 'http://127.0.0.1')
      res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' })
      res.end(SUCCESS_PAGE)
      if (settled) return
      const error = url.searchParams.get('error')
      const codeParam = url.searchParams.get('code')
      const state = url.searchParams.get('state')
      if (error) {
        cleanup()
        codeReject(new CloudAuthError(error))
        return
      }
      if (state !== expectedState || !codeParam) {
        cleanup()
        codeReject(new CloudAuthError('invalid_response', 'state mismatch'))
        return
      }
      cleanup()
      codeResolve(codeParam)
    } catch {
      // 响应已写出后的解析异常不影响主流程
    }
  })

  server.on('error', (err: Error) => {
    if (settled) return
    cleanup()
    readyReject(new LoopbackBindError(err))
    codeReject(new LoopbackBindError(err))
  })

  server.listen(port, '127.0.0.1', () => readyResolve())

  timer = setTimeout(() => {
    const err = new CloudAuthError('expired_token', 'direct login timeout')
    readyReject(err)
    cleanup()
    codeReject(err)
  }, timeoutMs)

  return {
    ready,
    code,
    cancel: () => {
      const wasActive = !settled
      cleanup()
      if (wasActive) codeReject(new CloudAuthError('cancelled'))
    },
  }
}

/**
 * LuomiNest 统一日志枢纽（主进程内存环形缓冲）
 *
 * 汇聚三路日志到同一缓冲（上限 1000 条）：
 * - main     ：electron-log hook（luomi-logger 模块 init 时挂接，过滤 file transport 保证每条只记一次）
 * - backend  ：backend/index.ts 的 routeBackendLog 在转发 electron-log 的同时显式喂入
 *              （经 withHubSource 打标，避免同一条日志被 hook 再次收录造成重复）
 * - renderer ：渲染层 utils/logger.ts 批量上报（log:append，main 侧强制 source='renderer'）
 *
 * 实时性：新条目按 300ms 节流合并为 log:onAppended 推送广播到全部窗口。
 * 冷启动：应用 ready 后从 main.log 尾部回读约 1000 行填充缓冲（解析失败的行降级为原文行）。
 *
 * 文件落盘仍由 electron-log 负责（main.log，5MB 轮转）；本模块不重复写文件，
 * 仅 log:export 时把当前缓冲整体导出为 export-<timestamp>.log（JSONL）。
 *
 * 依赖约束：本文件禁止 import paths.ts / luomi-logger.ts / config-store.ts
 * （luomi-logger → log-hub 已构成单向依赖，反向引入会形成模块环），
 * 日志目录就地内联计算（userData/Logs，与 paths.ts PATHS.logs 一致）。
 */
import { app, BrowserWindow } from 'electron'
import { join } from 'path'
import { readdirSync, statSync, writeFileSync, mkdirSync, openSync, readSync, closeSync } from 'fs'
import log from 'electron-log'
import { IpcChannels } from '@shared/ipc-types'
import type { LogEntry, LogLevel, LogQueryParams, LogQueryResult, LogSegmentInfo, LogSource, LogUploadEntry } from '@shared/ipc-types'

const RING_CAPACITY = 1000
/** 实时推送节流窗口（ms）：批量合并，避免高频日志刷屏 */
const PUSH_THROTTLE_MS = 300
/** 单次推送的最大条数（超出丢弃最旧的推送，缓冲内仍完整保留） */
const PUSH_BATCH_CAP = 500
/** 回读 main.log 尾部的字节数（约可覆盖 1000+ 行） */
const HYDRATE_TAIL_BYTES = 512 * 1024
/** 回读去重窗口：与缓冲尾部同级别同消息且时间差在该范围内视为同一条 */
const DEDUPE_MS = 10_000

const LOGS_DIR = (): string => {
  const dir = join(app.getPath('userData'), 'Logs')
  try {
    mkdirSync(dir, { recursive: true })
  } catch {
    // 目录创建失败时后续读写各自再兜底
  }
  return dir
}

/* ── 级别归一化 ─────────────────────────────────────────────────────────── */

const normalizeLevel = (raw: string): LogLevel => {
  const level = raw.toLowerCase()
  if (level === 'error' || level === 'critical' || level === 'fatal') return 'error'
  if (level === 'warn' || level === 'warning') return 'warn'
  if (level === 'debug' || level === 'verbose' || level === 'silly' || level === 'trace') return 'debug'
  return 'info'
}

/** 任意参数安全字符串化（Error 取堆栈、对象循环安全 JSON、其余 String） */
const stringifyArg = (arg: unknown): string => {
  if (typeof arg === 'string') return arg
  if (arg instanceof Error) return arg.stack || `${arg.name}: ${arg.message}`
  if (typeof arg === 'object' && arg !== null) {
    try {
      const seen = new WeakSet<object>()
      return (
        JSON.stringify(arg, (_key, value) => {
          if (typeof value === 'object' && value !== null) {
            if (seen.has(value)) return '[Circular]'
            seen.add(value)
          }
          return value
        }) ?? String(arg)
      )
    } catch {
      return String(arg)
    }
  }
  return String(arg)
}

export const serializeLogArgs = (args: unknown[]): string => args.map(stringifyArg).join(' ')

/* ── 环形缓冲 ───────────────────────────────────────────────────────────── */

let seqCounter = 0
const ring: LogEntry[] = []
let hydrated = false

/** hook 已启用但尚未回读完成前，先暂存实时条目，回读后去重并入（保证时序正确） */
const pendingBeforeHydration: LogEntry[] = []

const pushRing = (entry: LogEntry): void => {
  ring.push(entry)
  if (ring.length > RING_CAPACITY) ring.splice(0, ring.length - RING_CAPACITY)
  scheduleBroadcast(entry)
}

export const append = (
  level: LogLevel,
  source: LogSource,
  scope: string,
  message: string,
  data?: unknown
): void => {
  const entry: LogEntry = {
    seq: ++seqCounter,
    ts: new Date().toISOString(),
    level,
    source,
    scope: scope || 'App',
    message,
  }
  if (data !== undefined) entry.data = data

  if (!hydrated) {
    pendingBeforeHydration.push(entry)
    if (pendingBeforeHydration.length > RING_CAPACITY) pendingBeforeHydration.shift()
    return
  }
  pushRing(entry)
}

/**
 * 与缓冲尾部（回读去重窗口内）比较，同级别同消息且时间接近则视为重复，跳过。
 * 用于回读历史时剔除 hook 已实时收录的本次会话条目。
 */
const isDuplicateOfTail = (level: LogLevel, message: string, tsMs: number): boolean => {
  for (let i = ring.length - 1; i >= 0 && i >= ring.length - 300; i--) {
    const e = ring[i]
    if (e.message !== message || e.level !== level) continue
    const eMs = Date.parse(e.ts)
    if (Number.isFinite(eMs) && Math.abs(tsMs - eMs) <= DEDUPE_MS) return true
    // 缓冲按时间有序，遇到明显更早的同类消息即可停止
    if (Number.isFinite(eMs) && tsMs - eMs > DEDUPE_MS) return false
  }
  return false
}

/* ── 来源打标（避免 backend 转发日志被 hook 二次收录） ──────────────────── */

let sourceOverride: LogSource | null = null

/** 在 fn 执行期间，hook 收录的 electron-log 条目改记为指定来源（替代默认 'main'） */
export const withHubSource = <T>(source: LogSource, fn: () => T): T => {
  const prev = sourceOverride
  sourceOverride = source
  try {
    return fn()
  } finally {
    sourceOverride = prev
  }
}

/* ── electron-log hook ──────────────────────────────────────────────────── */

let hookInstalled = false

/**
 * 把主进程 electron-log 日志喂进环形缓冲。
 * 只在 file transport 钩一次（每条消息会依次经过 console/file 两个 transport 的 hook）。
 */
const installElectronLogHook = (): void => {
  if (hookInstalled) return
  hookInstalled = true
  log.hooks.push((message, _transport, transportName) => {
    if (transportName === 'file') {
      append(
        normalizeLevel(String(message.level)),
        sourceOverride ?? 'main',
        message.scope || 'Main',
        serializeLogArgs(message.data)
      )
    }
    return message
  })
}

/* ── 冷启动回读 main.log 尾部 ───────────────────────────────────────────── */

// luomi-logger 配置的文件格式：[{y}-{m}-{d} {h}:{i}:{s}.{ms}] [{level}] [{scope}] {text}
const MAIN_LOG_LINE_RE = /^\[([^\]]+)\]\s*\[([A-Za-z]+)\]\s*\[([^\]]*)\]\s?([\s\S]*)$/

/** 解析 electron-log 文件时间戳 "YYYY-MM-DD HH:mm:ss.SSS"（本地时区）为 ISO；失败回退当前时间 */
const parseMainLogTs = (tsRaw: string): string => {
  const m = tsRaw.match(/(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,3}))?/)
  if (m) {
    const ms = m[7] ? +m[7].padEnd(3, '0') : 0
    return new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6], ms).toISOString()
  }
  const parsed = new Date(tsRaw)
  return Number.isNaN(parsed.getTime()) ? new Date().toISOString() : parsed.toISOString()
}

const hydrateFromDisk = (): void => {
  try {
    const filePath = join(LOGS_DIR(), 'main.log')
    let stat
    try {
      stat = statSync(filePath)
    } catch {
      return
    }
    if (!stat.isFile() || stat.size === 0) return

    const start = Math.max(0, stat.size - HYDRATE_TAIL_BYTES)
    const fd = openSync(filePath, 'r')
    try {
      const length = stat.size - start
      const buffer = Buffer.alloc(length)
      readSync(fd, buffer, 0, length, start)
      const text = buffer.toString('utf8')
      const lines = text.split(/\r?\n/)
      // 首块可能从行中间截断：丢弃首行（若从头读则首行为完整行，仅极端情况损失一行）
      if (start > 0) lines.shift()

      for (const line of lines) {
        const raw = line.trimEnd()
        if (!raw.trim()) continue
        const match = raw.match(MAIN_LOG_LINE_RE)
        if (match) {
          const [, tsRaw, levelRaw, scopeRaw, message] = match
          const ts = parseMainLogTs(tsRaw)
          const level = normalizeLevel(levelRaw)
          const tsMs = Date.parse(ts)
          if (isDuplicateOfTail(level, message, tsMs)) continue
          pushRing({
            seq: ++seqCounter,
            ts,
            level,
            source: 'main',
            scope: scopeRaw.trim() || 'Main',
            message,
          })
        } else {
          // 解析失败的行降级为原文行（多行堆栈的续行会自然落在这里）
          pushRing({
            seq: ++seqCounter,
            ts: new Date().toISOString(),
            level: 'info',
            source: 'main',
            scope: 'main.log',
            message: raw,
          })
        }
      }
    } finally {
      closeSync(fd)
    }
  } catch {
    // 回读失败不影响运行，环内仍有本次会话的实时日志
  }
}

/* ── 实时推送（节流合并） ───────────────────────────────────────────────── */

let pushTimer: NodeJS.Timeout | null = null
const pendingBroadcast: LogEntry[] = []

const scheduleBroadcast = (entry: LogEntry): void => {
  if (!hydrated) return
  pendingBroadcast.push(entry)
  if (pushTimer) return
  pushTimer = setTimeout(flushBroadcast, PUSH_THROTTLE_MS)
}

const flushBroadcast = (): void => {
  pushTimer = null
  if (pendingBroadcast.length === 0) return
  const batch = pendingBroadcast.splice(0, PUSH_BATCH_CAP)
  for (const win of BrowserWindow.getAllWindows()) {
    if (win.isDestroyed()) continue
    try {
      win.webContents.send(IpcChannels.log.push.onAppended, batch)
    } catch {
      // 单窗口推送失败不影响其他窗口
    }
  }
}

/* ── 对外查询 / 管理 API ────────────────────────────────────────────────── */

export const query = (params: LogQueryParams): LogQueryResult => {
  const source = params.source && params.source !== 'all' ? params.source : null
  const level = params.level && params.level !== 'all' ? params.level : null
  const search = typeof params.search === 'string' ? params.search.trim().toLowerCase() : ''

  const filtered = ring.filter((e) => {
    if (source && e.source !== source) return false
    if (level && e.level !== level) return false
    if (search && !(`${e.message}\n${e.scope}`.toLowerCase().includes(search))) return false
    return true
  })

  const offset = Math.max(0, Math.floor(Number(params.offset) || 0))
  const limit = Math.min(1000, Math.max(1, Math.floor(Number(params.limit) || 200)))
  return {
    total: filtered.length,
    entries: filtered.slice(offset, offset + limit),
  }
}

export const clear = (): void => {
  ring.length = 0
}

export const exportBuffer = (): string => {
  const dir = LOGS_DIR()
  const stamp = new Date().toISOString().replace(/[:.]/g, '-').replace('T', '_').slice(0, 19)
  const filePath = join(dir, `export-${stamp}.log`)
  const jsonl = ring.map((e) => JSON.stringify(e)).join('\n')
  writeFileSync(filePath, jsonl + (jsonl ? '\n' : ''), 'utf-8')
  return filePath
}

/** 当前缓冲的 JSONL 序列化（log:export 复用） */
export const bufferToJsonl = (): string => ring.map((e) => JSON.stringify(e)).join('\n')

export const getBufferSnapshot = (): LogEntry[] => [...ring]

/* ── 诊断日志上传：脱敏清洗 ─────────────────────────────────────────────── */

/** 上报前 message 的最大长度（服务端契约配套的客户端侧截断） */
const UPLOAD_MESSAGE_MAX_CHARS = 2000
/** 单次上报条数上限（服务端契约：entries ≤ 1000） */
export const UPLOAD_ENTRIES_MAX = 1000

/**
 * 令牌形态抹除规则（上报隐私红线，命中片段整体替换为 '***'）：
 * - Bearer xxx        ：Authorization 头形态（token 段取 URL 安全字符集）
 * - sk-...            ：OpenAI 风格 API Key
 * - lcx_...           ：辰汐通行证（passport）令牌形态
 */
const REDACTION_PATTERNS: RegExp[] = [
  /Bearer\s+[A-Za-z0-9._~+/=-]+/gi,
  /\bsk-[A-Za-z0-9_-]{8,}\b/g,
  /\blcx_[A-Za-z0-9_-]+\b/g,
]

/** 抹除 message 中的令牌片段（多层规则依次替换，幂等） */
export const redactSecrets = (text: string): string => {
  let result = text
  for (const pattern of REDACTION_PATTERNS) {
    result = result.replace(pattern, '***')
  }
  return result
}

/**
 * 构建诊断日志上报条目（log:upload 专用，隐私脱敏最后关口）：
 * 1. 丢弃 data 字段——渲染层/自动化日志可能夹带截图 dataURL 等大对象与敏感负载；
 * 2. message 截断到 2000 字符并抹除 Bearer/sk-/lcx_ 令牌片段；
 * 3. 只输出服务端契约字段（seq/ts/level/source/scope/message），条数 ≤ 1000。
 */
export const buildUploadEntries = (): LogUploadEntry[] =>
  ring.slice(-UPLOAD_ENTRIES_MAX).map((entry) => ({
    seq: entry.seq,
    ts: entry.ts,
    level: entry.level,
    source: entry.source,
    scope: redactSecrets(entry.scope).slice(0, 200),
    message: redactSecrets(entry.message.slice(0, UPLOAD_MESSAGE_MAX_CHARS)),
  }))

export const getLogSegments = (): LogSegmentInfo[] => {
  const dir = LOGS_DIR()
  let names: string[]
  try {
    names = readdirSync(dir)
  } catch {
    return []
  }
  const segments: LogSegmentInfo[] = []
  for (const name of names) {
    // main.log / main.old.log（electron-log 轮转）/ backend.log*（loguru 轮转）/ export-*.log
    if (!/\.log(\.\w+)?$/.test(name)) continue
    try {
      const stat = statSync(join(dir, name))
      if (!stat.isFile()) continue
      segments.push({ name, size: stat.size, mtimeMs: stat.mtimeMs })
    } catch {
      // 竞态删除时跳过该文件
    }
  }
  return segments.sort((a, b) => b.mtimeMs - a.mtimeMs)
}

/**
 * 校验并收录渲染层上报的条目（不可信输入：main 侧强制 source='renderer'，逐条容错）。
 * 返回实际收录条数。
 */
export const appendFromRenderer = (
  entries: Array<Partial<LogEntry> | unknown>
): number => {
  if (!Array.isArray(entries)) return 0
  let accepted = 0
  for (const raw of entries.slice(0, 200)) {
    if (!raw || typeof raw !== 'object') continue
    const e = raw as Partial<LogEntry>
    if (typeof e.message !== 'string' || !e.message.trim()) continue
    const level: LogLevel =
      e.level === 'debug' || e.level === 'info' || e.level === 'warn' || e.level === 'error'
        ? e.level
        : 'info'
    append(level, 'renderer', typeof e.scope === 'string' && e.scope ? e.scope : 'Renderer', e.message, e.data)
    accepted++
  }
  return accepted
}

/* ── 初始化 ─────────────────────────────────────────────────────────────── */

let initialized = false

/**
 * 挂接 electron-log 并在应用 ready 后回读历史。
 * 由 luomi-logger 模块顶层调用（主进程最早加载的模块之一，保证 hook 尽早生效）。
 */
export const initLogHub = (): void => {
  if (initialized) return
  initialized = true
  installElectronLogHook()

  void app
    .whenReady()
    .then(() => {
      hydrateFromDisk()
      // 先恢复直通，再并入回读期间暂存的本次会话条目（保证其进入实时推送）
      hydrated = true
      for (const entry of pendingBeforeHydration.splice(0)) {
        if (isDuplicateOfTail(entry.level, entry.message, Date.parse(entry.ts))) continue
        pushRing(entry)
      }
    })
    .catch(() => {
      hydrated = true
    })
}

/** 统一日志枢纽对外接口（ipc-handlers 等调用方使用命名空间形式） */
export const logHub = {
  append,
  appendFromRenderer,
  query,
  clear,
  exportBuffer,
  bufferToJsonl,
  getBufferSnapshot,
  getLogSegments,
  buildUploadEntries,
  init: initLogHub,
}

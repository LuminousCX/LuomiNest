/**
 * 轻量 5 字段 cron 解析（纯前端展示层使用）
 *
 * 后端 /scheduled-tasks 只返回 schedule_cron 原始表达式，不提供展开后的触发时刻，
 * 因此前端自行解析：
 *  - parseCronDayTimes：展开一天内的触发小时（供 24h 时间轴打点）
 *  - cronNextRun：计算下一次执行时间（供"下次执行 / 剩余时间"展示）
 *
 * 支持的字段语法：星号、步进（星号加斜杠 n）、单值、区间（a-b）、带步进区间、逗号列表。星期字段 0/7 均表示周日。
 */

/** 展开单个 cron 字段为数值列表；无法解析返回 null */
const expandField = (field: string, min: number, max: number): number[] | null => {
  const trimmed = field.trim()
  if (!trimmed) return null
  const out = new Set<number>()

  for (const part of trimmed.split(',')) {
    const stepMatch = part.match(/^(\*|\d+(?:-\d+)?)\/(\d+)$/)
    let low: number
    let high: number
    let step = 1

    if (stepMatch) {
      const base = stepMatch[1]
      step = Math.max(1, Number(stepMatch[2]))
      if (base === '*') {
        low = min
        high = max
      } else {
        const range = base.match(/^(\d+)-(\d+)$/)
        if (range) {
          low = Number(range[1])
          high = Number(range[2])
        } else {
          low = Number(base)
          high = max
        }
      }
    } else if (part === '*') {
      low = min
      high = max
    } else {
      const range = part.match(/^(\d+)-(\d+)$/)
      if (range) {
        low = Number(range[1])
        high = Number(range[2])
      } else if (/^\d+$/.test(part)) {
        low = Number(part)
        high = low
      } else {
        return null
      }
    }

    if (!Number.isFinite(low) || !Number.isFinite(high) || low > high) return null
    for (let v = Math.max(low, min); v <= Math.min(high, max); v += step) {
      out.add(v)
    }
  }

  return out.size > 0 ? [...out].sort((a, b) => a - b) : null
}

export interface CronDayTimes {
  /** 小时字段覆盖全天（`*`），时间轴以"每小时"横带呈现 */
  everyHour: boolean
  /** 触发小时列表（0-23，升序；everyHour 时为空数组） */
  hours: number[]
  /** 展示用代表分钟（取触发分钟列表最小值） */
  minute: number
}

/**
 * 解析 cron 在一天内的触发时刻（忽略 日/月/星期 限制，仅供小时轴打点）。
 * 解析失败返回 null。
 */
export const parseCronDayTimes = (cron: string): CronDayTimes | null => {
  const parts = cron.trim().split(/\s+/)
  if (parts.length < 5) return null
  const minutes = expandField(parts[0], 0, 59)
  const hours = expandField(parts[1], 0, 23)
  if (!minutes || !hours) return null
  const everyHour = parts[1].trim() === '*'
  return {
    everyHour,
    hours: everyHour ? [] : hours,
    minute: minutes[0]
  }
}

/**
 * 计算 cron 下一次执行时间（标准 cron 语义：日 与 星期 同时受限时取并集）。
 * 无法解析或在一年内找不到触发点返回 null。
 */
export const cronNextRun = (cron: string, from: Date = new Date()): Date | null => {
  const parts = cron.trim().split(/\s+/)
  if (parts.length < 5) return null

  const minutes = expandField(parts[0], 0, 59)
  const hours = expandField(parts[1], 0, 23)
  const daysOfMonth = expandField(parts[2], 1, 31)
  const months = expandField(parts[3], 1, 12)
  // cron 星期：0/7 = 周日，统一映射到 JS getDay() 的 0-6
  const daysOfWeekRaw = expandField(parts[4], 0, 7)
  if (!minutes || !hours || !daysOfMonth || !months || !daysOfWeekRaw) return null
  const daysOfWeek = [...new Set(daysOfWeekRaw.map(d => (d === 7 ? 0 : d)))]

  const domRestricted = parts[2].trim() !== '*'
  const dowRestricted = parts[4].trim() !== '*'
  const base = new Date(from.getFullYear(), from.getMonth(), from.getDate())
  base.setSeconds(0, 0)

  for (let dayOffset = 0; dayOffset < 366; dayOffset++) {
    const date = new Date(base.getFullYear(), base.getMonth(), base.getDate() + dayOffset)
    if (!months.includes(date.getMonth() + 1)) continue

    const domOk = daysOfMonth.includes(date.getDate())
    const dowOk = daysOfWeek.includes(date.getDay())
    // 标准 cron：日与星期都受限时任一命中即可；否则受限项必须命中
    const dayOk = domRestricted && dowRestricted ? domOk || dowOk : domRestricted ? domOk : dowRestricted ? dowOk : true
    if (!dayOk) continue

    for (const h of hours) {
      for (const m of minutes) {
        const candidate = new Date(date.getFullYear(), date.getMonth(), date.getDate(), h, m)
        if (candidate.getTime() > from.getTime()) return candidate
      }
    }
  }
  return null
}

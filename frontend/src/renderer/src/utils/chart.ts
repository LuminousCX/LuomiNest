/**
 * 手写 SVG 图表工具：直方图 / 活跃度热力图。
 *
 * 设计约定：纯函数、不依赖 i18n（标签本地化由调用方处理）、
 * 单色系输出（颜色/透明度分层由调用方 CSS 控制）。
 */

export interface ChartTick {
  y: number
  value: number
  label: string
}

/** 直方图的一个数据桶（按天或按月聚合后的用量） */
export interface HistogramDatum {
  /** 短标签，用于 X 轴（如 '10-08' 或本地化月份名） */
  label: string
  /** 完整标签，用于 tooltip（如 '2026-10-08'） */
  fullLabel: string
  /** 调用次数 */
  value: number
  /** token 消耗 */
  tokens: number
}

export interface HistogramBar extends HistogramDatum {
  x: number
  y: number
  width: number
  height: number
  index: number
}

export interface HistogramModel {
  bars: HistogramBar[]
  ticks: ChartTick[]
  baselineY: number
  maxVal: number
  /** X 轴标签抽样步长（每 n 根柱显示 1 个标签） */
  labelEvery: number
}

export interface HistogramOptions {
  width?: number
  height?: number
  padding?: { top: number; bottom: number; left: number; right: number }
  /** X 轴最多显示的标签数（超出则抽样），默认 10 */
  maxLabelCount?: number
}

/** ── 日期小工具 ── */

/** Date → 本地日期 'YYYY-MM-DD' */
export const isoDate = (d: Date): string => {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** 两个 'YYYY-MM-DD' 之间的天数差（b - a） */
export const diffDays = (a: string, b: string): number => {
  const da = new Date(a + 'T00:00:00').getTime()
  const db = new Date(b + 'T00:00:00').getTime()
  return Math.round((db - da) / 86_400_000)
}

/** 数值紧凑格式：1.2K / 3.45M */
export const formatCompact = (n: number): string => {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}

const formatTick = (val: number): string => {
  if (val >= 1_000_000) return (val / 1_000_000).toFixed(1) + 'M'
  if (val >= 1_000) return (val / 1_000).toFixed(1) + 'K'
  return String(val)
}

/** 规整 Y 轴上限：留顶部呼吸空间并让刻度值可读 */
const niceMax = (rawMax: number): number => {
  if (rawMax <= 5) return 5
  if (rawMax <= 10) return 10
  if (rawMax <= 20) return 20
  if (rawMax <= 50) return 50
  if (rawMax <= 100) return 100
  const magnitude = Math.pow(10, Math.floor(Math.log10(rawMax)))
  return Math.ceil((rawMax * 1.15) / magnitude) * magnitude
}

/**
 * 由 by_day / tokens_by_day 构建 start..end 的逐日序列（缺失日期补 0）。
 *
 * @param start 起始 'YYYY-MM-DD'（含）；缺省时用数据里最早的一天
 * @param end   结束 'YYYY-MM-DD'（含）；缺省时用数据里最晚的一天
 */
export const buildDailySeries = (
  byDay: Record<string, number>,
  tokensByDay: Record<string, number>,
  start?: string,
  end?: string,
): HistogramDatum[] => {
  const keys = Object.keys(byDay).sort()
  const startISO = start ?? keys[0]
  const endISO = end ?? keys[keys.length - 1]
  if (!startISO || !endISO || startISO > endISO) return []

  const span = diffDays(startISO, endISO)
  if (span < 0 || span > 4000) return []

  const series: HistogramDatum[] = []
  const cursor = new Date(startISO + 'T00:00:00')
  for (let i = 0; i <= span; i++) {
    const key = isoDate(cursor)
    series.push({
      label: key.slice(5),
      fullLabel: key,
      value: byDay[key] ?? 0,
      tokens: tokensByDay[key] ?? 0,
    })
    cursor.setDate(cursor.getDate() + 1)
  }
  return series
}

/** 逐日序列按月聚合（用于 >90 天的窗口，避免柱子过密），label 为 'YYYY-MM' */
export const aggregateSeriesByMonth = (series: HistogramDatum[]): HistogramDatum[] => {
  const map = new Map<string, HistogramDatum>()
  for (const item of series) {
    const key = item.fullLabel.slice(0, 7)
    const acc = map.get(key)
    if (acc) {
      acc.value += item.value
      acc.tokens += item.tokens
    } else {
      map.set(key, { label: key, fullLabel: key, value: item.value, tokens: item.tokens })
    }
  }
  return [...map.values()]
}

/**
 * 生成垂直柱状直方图的几何信息（单色柱 + 极简坐标轴）。
 */
export const generateHistogramBars = (
  data: HistogramDatum[],
  options: HistogramOptions = {},
): HistogramModel => {
  const {
    width = 600,
    height = 240,
    padding = { top: 16, bottom: 28, left: 44, right: 8 },
    maxLabelCount = 10,
  } = options

  const chartW = Math.max(width - padding.left - padding.right, 10)
  const chartH = Math.max(height - padding.top - padding.bottom, 10)
  const baselineY = padding.top + chartH

  if (data.length === 0) {
    return { bars: [], ticks: [{ y: baselineY, value: 0, label: '0' }], baselineY, maxVal: 0, labelEvery: 1 }
  }

  const maxVal = niceMax(Math.max(...data.map(d => d.value), 0))
  const range = Math.max(maxVal, 1)

  // 柱宽 = 均分带宽扣除间隙；柱子密集时收窄间隙保持可读，柱子稀少时限制最大宽度
  const band = chartW / data.length
  const gapRatio = data.length > 40 ? 0.15 : 0.32
  const barWidth = Math.max(1, Math.min(48, +(band * (1 - gapRatio)).toFixed(2)))

  const bars: HistogramBar[] = data.map((d, i) => {
    const h = Math.max(0, Math.min(1, d.value / range)) * chartH
    const x = +(padding.left + i * band + (band - barWidth) / 2).toFixed(2)
    return {
      ...d,
      x,
      y: +(baselineY - h).toFixed(2),
      width: barWidth,
      height: +h.toFixed(2),
      index: i,
    }
  })

  const tickSteps: ChartTick[] = []
  for (const step of [0, 0.5, 1]) {
    const val = Math.round(range * step)
    tickSteps.push({ y: baselineY - step * chartH, value: val, label: formatTick(val) })
  }

  return {
    bars,
    ticks: tickSteps,
    baselineY,
    maxVal,
    labelEvery: Math.max(1, Math.ceil(data.length / Math.max(1, maxLabelCount))),
  }
}

/** ── GitHub 活跃度风格热力图 ── */

export interface HeatmapCell {
  /** 'YYYY-MM-DD' */
  date: string
  count: number
  tokens: number
  /** 用量等级 0（空）~ 4（峰值），由调用方映射为透明度分层 */
  level: 0 | 1 | 2 | 3 | 4
  /** 第几周（列） */
  week: number
  /** 星期（行），0 = 周日 */
  dow: number
  x: number
  y: number
}

export interface HeatmapMonthLabel {
  x: number
  label: string
}

export interface HeatmapModel {
  cells: HeatmapCell[]
  weeks: number
  cellSize: number
  gap: number
  /** 左侧星期标注宽度 */
  labelWidth: number
  /** 顶部月份标注高度 */
  labelHeight: number
  width: number
  height: number
  monthLabels: HeatmapMonthLabel[]
  maxCount: number
}

export interface HeatmapOptions {
  /** 统计最近多少天，默认 365 */
  days?: number
  /** 结束日期（含），默认今天 */
  endDate?: Date
  /** 固定格子边长；与 fitWidth 二选一，都缺省时为 11 */
  cellSize?: number
  /** 格子间隙，默认 2 */
  gap?: number
  /** 左侧星期标注宽度，默认 34 */
  labelWidth?: number
  /** 按容器宽度自适应格子边长（clamp 在 minCell..maxCell） */
  fitWidth?: number
  minCell?: number
  maxCell?: number
  /** 月份显示名（入参为 0-based 月份），由调用方做本地化 */
  monthName: (month: number) => string
}

/**
 * 构建 GitHub contribution 风格的按天热力图几何信息。
 * 7 行（周日起）× 按周列；未来日期不出格；等级按窗口内峰值分 4 档。
 */
export const buildHeatmap = (
  byDay: Record<string, number>,
  tokensByDay: Record<string, number>,
  options: HeatmapOptions,
): HeatmapModel => {
  const {
    days = 365,
    endDate = new Date(),
    cellSize: sizeIn,
    gap: gapIn = 2,
    labelWidth = 34,
    fitWidth,
    minCell = 8,
    maxCell = 13,
    monthName,
  } = options
  const labelHeight = 16

  const end = new Date(endDate)
  end.setHours(0, 0, 0, 0)
  const first = new Date(end)
  first.setDate(first.getDate() - (days - 1))
  // 回退到所在周的周日，保证列按周对齐
  first.setDate(first.getDate() - first.getDay())

  const totalDays = Math.round((end.getTime() - first.getTime()) / 86_400_000) + 1
  const weeks = Math.ceil(totalDays / 7)

  let cellSize = sizeIn
  if (cellSize == null) {
    if (fitWidth && fitWidth > labelWidth) {
      cellSize = Math.min(maxCell, Math.max(minCell, Math.floor((fitWidth - labelWidth - 2) / weeks) - gapIn))
    } else {
      cellSize = 11
    }
  }
  const gap = gapIn

  // 窗口内峰值（用于分档）
  let maxCount = 0
  for (const [key, v] of Object.entries(byDay)) {
    if (key >= isoDate(first) && key <= isoDate(end) && v > maxCount) maxCount = v
  }

  const cells: HeatmapCell[] = []
  const cursor = new Date(first)
  for (let i = 0; i < totalDays; i++) {
    const key = isoDate(cursor)
    if (cursor <= end) {
      const count = byDay[key] ?? 0
      const level: HeatmapCell['level'] =
        count <= 0 || maxCount <= 0
          ? 0
          : (Math.max(1, Math.min(4, Math.ceil((count / maxCount) * 4))) as HeatmapCell['level'])
      const week = Math.floor(i / 7)
      const dow = i % 7
      cells.push({
        date: key,
        count,
        tokens: tokensByDay[key] ?? 0,
        level,
        week,
        dow,
        x: labelWidth + week * (cellSize + gap),
        y: labelHeight + dow * (cellSize + gap),
      })
    }
    cursor.setDate(cursor.getDate() + 1)
  }

  // 月份标注：每列取首日，月份变化且与上个标注间隔 ≥ 2 周时标注
  const monthLabels: HeatmapMonthLabel[] = []
  let lastLabelWeek = -10
  for (let w = 0; w < weeks; w++) {
    const weekFirst = new Date(first)
    weekFirst.setDate(weekFirst.getDate() + w * 7)
    if (weekFirst > end) break
    const prevWeekFirst = new Date(weekFirst)
    prevWeekFirst.setDate(prevWeekFirst.getDate() - 7)
    const monthChanged = w === 0 || weekFirst.getMonth() !== prevWeekFirst.getMonth()
    if (monthChanged && (w === 0 || w - lastLabelWeek >= 2)) {
      monthLabels.push({
        x: labelWidth + w * (cellSize + gap),
        label: monthName(weekFirst.getMonth()),
      })
      lastLabelWeek = w
    }
  }

  return {
    cells,
    weeks,
    cellSize,
    gap,
    labelWidth,
    labelHeight,
    width: labelWidth + weeks * (cellSize + gap),
    height: labelHeight + 7 * (cellSize + gap),
    monthLabels,
    maxCount,
  }
}

/**
 * 计算环比变化率。
 *
 * @returns 变化率百分比（如 12.5 表示 +12.5%）
 */
export const calculateTrend = (current: number, previous: number): number => {
  if (previous === 0) return current > 0 ? 100 : 0
  return Number((((current - previous) / previous) * 100).toFixed(1))
}

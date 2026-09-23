import { i18n } from '../i18n'

export interface ChartPoint {
  x: number
  y: number
  value: number
}

export interface ChartTick {
  y: number
  value: number
  label: string
}

export interface AggregatedPoint {
  label: string
  value: number
  date: string
}

export interface AreaChartPaths {
  areaPath: string
  linePath: string
  points: ChartPoint[]
  ticks: ChartTick[]
  maxVal: number
}

export interface GenerateAreaChartOptions {
  width?: number
  height?: number
  padding?: { top: number; bottom: number; left: number; right: number }
  zeroBaseline?: boolean
}

/**
 * 根据数据点生成平滑三次贝塞尔面积图的 SVG 路径与刻度信息。
 *
 * @param data 数据数组，值域会自动映射到图表高度
 * @param options 图表尺寸、边距与基线配置
 * @returns 面积路径、平滑折线路径、映射坐标点、Y轴刻度线信息
 */
export const generateAreaChartPaths = (
  data: number[],
  options: GenerateAreaChartOptions = {},
): AreaChartPaths => {
  const {
    width = 400,
    height = 160,
    padding = { top: 20, bottom: 24, left: 36, right: 20 },
    zeroBaseline = true,
  } = options

  if (data.length === 0) {
    return { areaPath: '', linePath: '', points: [], ticks: [], maxVal: 0 }
  }

  const chartWidth = Math.max(width - padding.left - padding.right, 10)
  const chartHeight = Math.max(height - padding.top - padding.bottom, 10)
  const baselineY = padding.top + chartHeight

  const rawMax = Math.max(...data, 0)
  const rawMin = zeroBaseline ? 0 : Math.min(...data)

  // 计算规整的上限最大值，留出顶部呼吸空间并方便分割刻度
  let effectiveMax = rawMax
  if (effectiveMax <= 0) {
    effectiveMax = 5
  } else if (effectiveMax <= 5) {
    effectiveMax = 5
  } else if (effectiveMax <= 10) {
    effectiveMax = 10
  } else if (effectiveMax <= 20) {
    effectiveMax = 20
  } else if (effectiveMax <= 50) {
    effectiveMax = 50
  } else if (effectiveMax <= 100) {
    effectiveMax = 100
  } else {
    const magnitude = Math.pow(10, Math.floor(Math.log10(effectiveMax)))
    effectiveMax = Math.ceil((effectiveMax * 1.15) / magnitude) * magnitude
  }

  const range = Math.max(effectiveMax - rawMin, 1)

  // 生成 3 条水平参考线 (底部 0, 中间 50%, 顶部 100%)
  const tickSteps = [0, 0.5, 1]
  const ticks: ChartTick[] = tickSteps.map((step) => {
    const val = Math.round(rawMin + step * range)
    const y = padding.top + chartHeight - step * chartHeight
    let label = String(val)
    if (val >= 1_000_000) label = (val / 1_000_000).toFixed(1) + 'M'
    else if (val >= 1_000) label = (val / 1_000).toFixed(1) + 'K'
    return { y, value: val, label }
  })

  const points: ChartPoint[] = data.map((value, index) => {
    const x = padding.left + (data.length === 1 ? chartWidth / 2 : (index / (data.length - 1)) * chartWidth)
    const normalized = Math.max(0, Math.min(1, (value - rawMin) / range))
    const y = padding.top + chartHeight - normalized * chartHeight
    return { x, y, value }
  })

  if (points.length === 1) {
    const p = points[0]
    const areaPath = `M ${padding.left} ${baselineY} L ${padding.left} ${p.y} L ${padding.left + chartWidth} ${p.y} L ${padding.left + chartWidth} ${baselineY} Z`
    const linePath = `M ${padding.left} ${p.y} L ${padding.left + chartWidth} ${p.y}`
    return { areaPath, linePath, points, ticks, maxVal: effectiveMax }
  }

  // 使用平滑的三次贝塞尔曲线 (Cubic Spline)，避免单调性突变与过冲
  let linePath = `M ${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`

  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i === 0 ? 0 : i - 1]
    const p1 = points[i]
    const p2 = points[i + 1]
    const p3 = points[i + 2 >= points.length ? points.length - 1 : i + 2]

    const tension = 0.28 // 平滑张力因子
    const dx1 = (p2.x - p0.x) * tension
    const dy1 = (p2.y - p0.y) * tension
    const dx2 = (p3.x - p1.x) * tension
    const dy2 = (p3.y - p1.y) * tension

    const cp1x = p1.x + dx1
    let cp1y = p1.y + dy1
    const cp2x = p2.x - dx2
    let cp2y = p2.y - dy2

    // 局部极值钳位，防止曲线在两个相邻点间凹凸失控
    const minY = Math.min(p1.y, p2.y)
    const maxY = Math.max(p1.y, p2.y)
    const margin = Math.abs(p2.y - p1.y) * 0.35
    cp1y = Math.max(minY - margin, Math.min(maxY + margin, cp1y))
    cp2y = Math.max(minY - margin, Math.min(maxY + margin, cp2y))

    linePath += ` C ${cp1x.toFixed(2)} ${cp1y.toFixed(2)}, ${cp2x.toFixed(2)} ${cp2y.toFixed(2)}, ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`
  }

  const first = points[0]
  const last = points[points.length - 1]
  const areaPath = `${linePath} L ${last.x.toFixed(2)} ${baselineY.toFixed(2)} L ${first.x.toFixed(2)} ${baselineY.toFixed(2)} Z`

  return { areaPath, linePath, points, ticks, maxVal: effectiveMax }
}

/**
 * 计算两条同长度数据序列的环比变化率。
 *
 * @param current 当前周期数据
 * @param previous 上一周期数据
 * @returns 变化率百分比（如 12.5 表示 +12.5%）
 */
export const calculateTrend = (current: number, previous: number): number => {
  if (previous === 0) return current > 0 ? 100 : 0
  return Number((((current - previous) / previous) * 100).toFixed(1))
}

/**
 * 将 by_day 数据拆分为当前周期与上一周期，并计算总量与趋势。
 *
 * @param byDay Record<dateString, number>
 * @param days 周期天数
 * @returns 当前周期、上一周期、当前周期总量、环比变化率
 */
export const splitPeriods = (
  byDay: Record<string, number>,
  days: number,
): {
  current: { date: string; value: number }[]
  previous: { date: string; value: number }[]
  currentTotal: number
  previousTotal: number
  trend: number
} => {
  const sorted = Object.entries(byDay)
    .map(([date, value]) => ({ date, value }))
    .sort((a, b) => a.date.localeCompare(b.date))

  const current = sorted.slice(-days)
  const previous = sorted.slice(-days * 2, -days)

  const currentTotal = current.reduce((sum, item) => sum + item.value, 0)
  const previousTotal = previous.reduce((sum, item) => sum + item.value, 0)

  return {
    current,
    previous,
    currentTotal,
    previousTotal,
    trend: calculateTrend(currentTotal, previousTotal),
  }
}

/**
 * 将 by_day 数据按指定目标点数聚合，用于统一图表展示密度。
 *
 * @param byDay Record<dateString, number>
 * @param targetPoints 目标数据点数（默认 7）
 * @returns 聚合后的数据点数组
 */
export const aggregateByDay = (
  byDay: Record<string, number>,
  targetPoints = 7,
): AggregatedPoint[] => {
  const sorted = Object.entries(byDay)
    .map(([date, value]) => ({ date, value }))
    .sort((a, b) => a.date.localeCompare(b.date))

  if (sorted.length === 0) {
    return Array.from({ length: targetPoints }, () => ({ label: '-', value: 0, date: '' }))
  }

  if (sorted.length <= targetPoints) {
    return sorted.map((item) => {
      const date = item.date ? new Date(item.date) : null
      const label = date && !isNaN(date.getTime())
        ? i18n.global.t(`stats.wd${date.getDay()}`)
        : item.date.slice(5)
      return { ...item, label }
    })
  }

  const groupSize = Math.ceil(sorted.length / targetPoints)
  const groups: AggregatedPoint[] = []

  for (let i = 0; i < sorted.length; i += groupSize) {
    const chunk = sorted.slice(i, i + groupSize)
    const value = chunk.reduce((sum, item) => sum + item.value, 0)
    const firstDate = chunk[0]?.date ?? ''
    const lastDate = chunk[chunk.length - 1]?.date ?? ''
    const label = firstDate === lastDate
      ? firstDate.slice(5)
      : `${firstDate.slice(5)}~${lastDate.slice(5)}`
    groups.push({ label, value, date: lastDate })
  }

  return groups
}

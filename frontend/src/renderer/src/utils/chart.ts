export interface ChartPoint {
  x: number
  y: number
  value: number
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
}

export interface GenerateAreaChartOptions {
  width?: number
  height?: number
  padding?: { top: number; bottom: number; left: number; right: number }
}

/**
 * 根据数据点生成平滑面积图的 SVG 路径。
 *
 * @param data 数据数组（长度 >= 2），值域会自动映射到图表高度
 * @param options 图表尺寸与边距
 * @returns 面积路径、折线路径、以及映射后的坐标点
 */
export const generateAreaChartPaths = (
  data: number[],
  options: GenerateAreaChartOptions = {},
): AreaChartPaths => {
  if (data.length === 0) {
    return { areaPath: '', linePath: '', points: [] }
  }

  const {
    width = 400,
    height = 160,
    padding = { top: 16, bottom: 16, left: 0, right: 0 },
  } = options

  const chartWidth = width - padding.left - padding.right
  const chartHeight = height - padding.top - padding.bottom

  const maxValue = Math.max(...data, 1)
  const minValue = Math.min(...data)
  const range = Math.max(maxValue - minValue, 1)

  const points: ChartPoint[] = data.map((value, index) => {
    const x = padding.left + (data.length === 1 ? 0 : (index / (data.length - 1)) * chartWidth)
    const y = padding.top + chartHeight - ((value - minValue) / range) * chartHeight
    return { x, y, value }
  })

  if (points.length === 1) {
    const p = points[0]
    const areaPath = `M ${p.x} ${height} L ${p.x} ${p.y} L ${p.x + 1} ${p.y} L ${p.x + 1} ${height} Z`
    const linePath = `M ${p.x} ${p.y} L ${p.x + 1} ${p.y}`
    return { areaPath, linePath, points }
  }

  // 使用二次贝塞尔曲线生成平滑折线：M P0 Q mid(P0,P1) P1 T P2 T P3 ...
  const control = (a: ChartPoint, b: ChartPoint) => ({
    x: (a.x + b.x) / 2,
    y: (a.y + b.y) / 2,
  })

  let linePath = `M ${points[0].x} ${points[0].y} Q ${control(points[0], points[1]).x} ${control(points[0], points[1]).y} ${points[1].x} ${points[1].y}`
  for (let i = 2; i < points.length; i++) {
    linePath += ` T ${points[i].x} ${points[i].y}`
  }

  const last = points[points.length - 1]
  const first = points[0]
  const areaPath = `${linePath} L ${last.x} ${height} L ${first.x} ${height} Z`

  return { areaPath, linePath, points }
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
    const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
    return sorted.map((item) => {
      const date = item.date ? new Date(item.date) : null
      const label = date && !isNaN(date.getTime()) ? weekdays[date.getDay()] : item.date.slice(5)
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

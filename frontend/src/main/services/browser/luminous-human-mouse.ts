/**
 * Luminous 人类化鼠标移动与点击。
 *
 * 借鉴 CloakBrowser (MIT) 的贝塞尔曲线算法，完全重写实现。
 * 使用 Electron webContents.sendInputEvent 模拟人类鼠标操作：
 * - 贝塞尔曲线移动轨迹
 * - easeInOut 缓动
 * - 过冲（overshoot）+ 回调
 * - 突发暂停（burst pause）
 * - 轻微抖动（wobble）
 */
import { WebContents } from 'electron'

import {
  LuminousHumanConfig,
  luminousRand,
  luminousRandRange,
  luminousRandIntRange,
  luminousSleep,
} from './luminous-human-config'

interface LuminousPoint {
  x: number
  y: number
}

/** 三次贝塞尔曲线插值 */
function luminousBezier(p0: LuminousPoint, p1: LuminousPoint, p2: LuminousPoint, p3: LuminousPoint, t: number): LuminousPoint {
  const u = 1 - t
  const uu = u * u
  const uuu = uu * u
  const tt = t * t
  const ttt = tt * t
  return {
    x: uuu * p0.x + 3 * uu * t * p1.x + 3 * u * tt * p2.x + ttt * p3.x,
    y: uuu * p0.y + 3 * uu * t * p1.y + 3 * u * tt * p2.y + ttt * p3.y,
  }
}

/** 生成随机贝塞尔控制点（使轨迹自然弯曲） */
function luminousRandomControlPoints(start: LuminousPoint, end: LuminousPoint): [LuminousPoint, LuminousPoint] {
  const dx = end.x - start.x
  const dy = end.y - start.y
  const dist = Math.hypot(dx, dy) || 1
  // 垂直方向的偏移向量
  const px = -dy / dist
  const py = dx / dist
  const bias1 = luminousRand(-0.3, 0.3) * dist
  const bias2 = luminousRand(-0.3, 0.3) * dist
  return [
    { x: start.x + dx * 0.25 + px * bias1, y: start.y + dy * 0.25 + py * bias1 },
    { x: start.x + dx * 0.75 + px * bias2, y: start.y + dy * 0.75 + py * bias2 },
  ]
}

/** easeInOut 缓动函数 */
function luminousEaseInOut(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2
}

/**
 * 人类化鼠标移动：从当前位置沿贝塞尔曲线移动到目标
 * @param wc WebContents 实例
 * @param startX 起点 X
 * @param startY 起点 Y
 * @param endX 终点 X
 * @param endY 终点 Y
 * @param cfg 人类化配置
 */
export async function luminousHumanMove(
  wc: WebContents,
  startX: number,
  startY: number,
  endX: number,
  endY: number,
  cfg: LuminousHumanConfig
): Promise<void> {
  const dist = Math.hypot(endX - startX, endY - startY)

  // 距离很近时直接移动
  if (dist < 3) {
    wc.sendInputEvent({ type: 'mouseMove', x: endX, y: endY })
    return
  }

  // 计算移动步数（距离越大步数越多，但有上下限）
  const steps = Math.max(
    cfg.mouse_min_steps,
    Math.min(cfg.mouse_max_steps, Math.ceil(dist / cfg.mouse_steps_divisor))
  )

  // 过冲：偶尔超过目标然后回来
  const overshoot = Math.random() < cfg.mouse_overshoot_chance
  let targetX = endX
  let targetY = endY
  if (overshoot) {
    const overshootPx = luminousRandRange(cfg.mouse_overshoot_px)
    const angle = Math.atan2(endY - startY, endX - startX)
    targetX = endX + Math.cos(angle) * overshootPx
    targetY = endY + Math.sin(angle) * overshootPx
  }

  // 贝塞尔控制点
  const [cp1, cp2] = luminousRandomControlPoints({ x: startX, y: startY }, { x: targetX, y: targetY })

  // 突发移动：将步数分成若干 burst，每个 burst 之间有短暂暂停
  const burstSize = luminousRandIntRange(cfg.mouse_burst_size)
  const burstPause = luminousRandRange(cfg.mouse_burst_pause)

  for (let i = 0; i <= steps; i++) {
    const t = i / steps
    const eased = luminousEaseInOut(t)
    const point = luminousBezier({ x: startX, y: startY }, cp1, cp2, { x: targetX, y: targetY }, eased)

    // 轻微抖动
    const wobble = cfg.mouse_wobble_max
    const wx = point.x + luminousRand(-wobble, wobble)
    const wy = point.y + luminousRand(-wobble, wobble)

    wc.sendInputEvent({ type: 'mouseMove', x: Math.round(wx), y: Math.round(wy) })

    // burst 之间暂停
    if (i > 0 && i % burstSize === 0 && i < steps) {
      await luminousSleep(burstPause)
    } else {
      await luminousSleep(luminousRand(5, 15))
    }
  }

  // 过冲回调：移动到真实目标
  if (overshoot) {
    await luminousSleep(luminousRand(30, 80))
    await luminousHumanMove(wc, targetX, targetY, endX, endY, cfg)
  } else {
    // 确保最终位置精确
    wc.sendInputEvent({ type: 'mouseMove', x: Math.round(endX), y: Math.round(endY) })
  }
}

/**
 * 人类化鼠标点击：移动到目标后按下、停留、释放
 */
export async function luminousHumanClick(
  wc: WebContents,
  targetX: number,
  targetY: number,
  cfg: LuminousHumanConfig,
  button: 'left' | 'right' = 'left'
): Promise<void> {
  // 从随机起点移动到目标（模拟从地址栏区域出发）
  const startX = luminousRand(400, 700)
  const startY = luminousRand(45, 60)

  await luminousHumanMove(wc, startX, startY, targetX, targetY, cfg)

  // 瞄准延迟（到达后短暂停顿）
  await luminousSleep(luminousRandRange(cfg.click_aim_delay))

  // 按下
  wc.sendInputEvent({ type: 'mouseDown', x: targetX, y: targetY, button, clickCount: 1 })

  // 按住一段时间
  await luminousSleep(luminousRandRange(cfg.click_hold))

  // 释放
  wc.sendInputEvent({ type: 'mouseUp', x: targetX, y: targetY, button, clickCount: 1 })
}

/**
 * 人类化鼠标悬停：移动到目标并停留
 */
export async function luminousHumanHover(
  wc: WebContents,
  targetX: number,
  targetY: number,
  cfg: LuminousHumanConfig
): Promise<void> {
  const startX = luminousRand(400, 700)
  const startY = luminousRand(45, 60)
  await luminousHumanMove(wc, startX, startY, targetX, targetY, cfg)
  // 悬停停留
  await luminousSleep(luminousRand(200, 500))
}

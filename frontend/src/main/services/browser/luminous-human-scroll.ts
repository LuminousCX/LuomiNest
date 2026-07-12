/**
 * Luminous 人类化滚动。
 *
 * 借鉴 CloakBrowser (MIT) 的加速/减速算法，完全重写实现。
 * 使用 Electron webContents.sendInputEvent 模拟人类滚轮操作：
 * - 加速阶段（delta 逐渐增大）
 * - 匀速阶段
 * - 减速阶段（delta 逐渐减小）
 * - 过冲回弹（偶尔滚过头然后回滚）
 * - 停顿沉淀
 */
import { WebContents } from 'electron'

import {
  LuminousHumanConfig,
  luminousRand,
  luminousRandRange,
  luminousRandIntRange,
  luminousSleep,
} from './luminous-human-config'

/**
 * 人类化滚动：模拟滚轮加速 → 匀速 → 减速过程
 * @param wc WebContents 实例
 * @param deltaX 水平滚动总量（正向右）
 * @param deltaY 垂直滚动总量（正向下）
 * @param cfg 人类化配置
 */
export async function luminousHumanScroll(
  wc: WebContents,
  deltaX: number,
  deltaY: number,
  cfg: LuminousHumanConfig
): Promise<void> {
  // 只处理垂直滚动（水平滚动少见，逻辑相同）
  const totalDelta = Math.abs(deltaY)
  if (totalDelta < 10) {
    wc.sendInputEvent({ type: 'mouseWheel', x: 0, y: 0, deltaX, deltaY })
    return
  }

  const direction = deltaY > 0 ? 1 : -1

  // 过冲：偶尔超过目标然后回弹
  const overshoot = Math.random() < cfg.scroll_overshoot_chance
  let targetTotal = totalDelta
  if (overshoot) {
    targetTotal = totalDelta + luminousRandRange(cfg.scroll_overshoot_px)
  }

  // 分配加速/匀速/减速步数
  const accelSteps = luminousRandIntRange(cfg.scroll_accel_steps)
  const decelSteps = luminousRandIntRange(cfg.scroll_decel_steps)
  const baseDelta = luminousRandRange(cfg.scroll_delta_base)
  // 匀速阶段的步数（根据总量推算）
  const cruiseSteps = Math.max(1, Math.ceil(targetTotal / baseDelta) - accelSteps - decelSteps)

  // 加速阶段：delta 从小到大
  for (let i = 1; i <= accelSteps; i++) {
    const delta = Math.round((baseDelta * i) / (accelSteps + 1) * direction)
    wc.sendInputEvent({ type: 'mouseWheel', x: 0, y: 0, deltaX: 0, deltaY: delta, wheelTicksY: delta / 100 })
    await luminousSleep(luminousRandRange(cfg.scroll_pause_fast))
  }

  // 匀速阶段
  for (let i = 0; i < cruiseSteps; i++) {
    const delta = Math.round(baseDelta * direction + luminousRand(-20, 20))
    wc.sendInputEvent({ type: 'mouseWheel', x: 0, y: 0, deltaX: 0, deltaY: delta, wheelTicksY: delta / 100 })
    await luminousSleep(luminousRandRange(cfg.scroll_pause_fast))
  }

  // 减速阶段：delta 从大到小
  for (let i = decelSteps; i >= 1; i--) {
    const delta = Math.round((baseDelta * i) / (decelSteps + 1) * direction)
    wc.sendInputEvent({ type: 'mouseWheel', x: 0, y: 0, deltaX: 0, deltaY: delta, wheelTicksY: delta / 100 })
    await luminousSleep(luminousRandRange(cfg.scroll_pause_slow))
  }

  // 过冲回弹
  if (overshoot) {
    await luminousSleep(luminousRandRange(cfg.scroll_settle_delay))
    const rollback = luminousRandRange(cfg.scroll_overshoot_px) * -direction
    const rollbackSteps = 2
    for (let i = 0; i < rollbackSteps; i++) {
      const delta = Math.round((rollback / rollbackSteps) + luminousRand(-10, 10))
      wc.sendInputEvent({ type: 'mouseWheel', x: 0, y: 0, deltaX: 0, deltaY: delta, wheelTicksY: delta / 100 })
      await luminousSleep(luminousRandRange(cfg.scroll_pause_slow))
    }
  }

  // 沉淀延迟
  await luminousSleep(luminousRandRange(cfg.scroll_settle_delay))
}

/**
 * Luminous 人类化输入配置。
 *
 * 借鉴 CloakBrowser (MIT) 的参数语义，完全重写实现。
 * 所有数值参数集中管理，提供 default（正常人类速度）和 careful（更慢更谨慎）两个预设。
 */

export interface LuminousHumanConfig {
  // 键盘
  typing_delay: number
  typing_delay_spread: number
  typing_pause_chance: number
  typing_pause_range: [number, number]
  key_hold: [number, number]
  mistype_chance: number
  mistype_delay_notice: [number, number]
  mistype_delay_correct: [number, number]

  // 鼠标 — 移动
  mouse_steps_divisor: number
  mouse_min_steps: number
  mouse_max_steps: number
  mouse_wobble_max: number
  mouse_overshoot_chance: number
  mouse_overshoot_px: [number, number]
  mouse_burst_size: [number, number]
  mouse_burst_pause: [number, number]

  // 鼠标 — 点击
  click_aim_delay: [number, number]
  click_hold: [number, number]

  // 鼠标 — 空闲
  idle_drift_px: number

  // 滚动
  scroll_delta_base: [number, number]
  scroll_pause_fast: [number, number]
  scroll_pause_slow: [number, number]
  scroll_accel_steps: [number, number]
  scroll_decel_steps: [number, number]
  scroll_overshoot_chance: number
  scroll_overshoot_px: [number, number]
  scroll_settle_delay: [number, number]
}

export type LuminousHumanPreset = 'default' | 'careful'

const DEFAULT_CONFIG: LuminousHumanConfig = {
  // 键盘 — 正常打字速度
  typing_delay: 70,
  typing_delay_spread: 40,
  typing_pause_chance: 0.1,
  typing_pause_range: [400, 1000],
  key_hold: [15, 35],
  mistype_chance: 0.02,
  mistype_delay_notice: [100, 300],
  mistype_delay_correct: [50, 150],

  // 鼠标 — 移动
  mouse_steps_divisor: 8,
  mouse_min_steps: 25,
  mouse_max_steps: 80,
  mouse_wobble_max: 1.5,
  mouse_overshoot_chance: 0.15,
  mouse_overshoot_px: [3, 6],
  mouse_burst_size: [3, 5],
  mouse_burst_pause: [8, 18],

  // 鼠标 — 点击
  click_aim_delay: [60, 140],
  click_hold: [60, 150],

  // 鼠标 — 空闲
  idle_drift_px: 3,

  // 滚动
  scroll_delta_base: [80, 130],
  scroll_pause_fast: [30, 80],
  scroll_pause_slow: [80, 200],
  scroll_accel_steps: [2, 3],
  scroll_decel_steps: [2, 3],
  scroll_overshoot_chance: 0.1,
  scroll_overshoot_px: [50, 150],
  scroll_settle_delay: [300, 600],
}

const CAREFUL_CONFIG: LuminousHumanConfig = {
  ...DEFAULT_CONFIG,
  // 键盘 — 更慢
  typing_delay: 100,
  typing_delay_spread: 50,
  typing_pause_chance: 0.15,
  typing_pause_range: [500, 1200],
  key_hold: [20, 45],
  mistype_chance: 0.03,
  mistype_delay_notice: [150, 400],
  mistype_delay_correct: [80, 200],

  // 鼠标 — 更谨慎
  mouse_overshoot_chance: 0.10,
  mouse_burst_pause: [12, 25],

  // 鼠标 — 点击（更长瞄准和按住）
  click_aim_delay: [80, 200],
  click_hold: [80, 200],

  // 滚动 — 更慢
  scroll_pause_fast: [100, 200],
  scroll_pause_slow: [250, 600],
  scroll_settle_delay: [400, 800],
}

const PRESETS: Record<LuminousHumanPreset, LuminousHumanConfig> = {
  default: DEFAULT_CONFIG,
  careful: CAREFUL_CONFIG,
}

export const resolveLuminousConfig = (
  preset: LuminousHumanPreset = 'default',
  overrides?: Partial<LuminousHumanConfig>
): LuminousHumanConfig => {
  const base = PRESETS[preset]
  if (!overrides) return { ...base }
  return { ...base, ...overrides }
}

// ===== 工具函数 =====

export const luminousRand = (min: number, max: number): number => {
  return min + Math.random() * (max - min)
}

export const luminousRandInt = (min: number, max: number): number => {
  return Math.floor(luminousRand(min, max + 1))
}

export const luminousRandRange = (range: [number, number]): number => {
  return luminousRand(range[0], range[1])
}

export const luminousRandIntRange = (range: [number, number]): number => {
  return luminousRandInt(range[0], range[1])
}

export const luminousSleep = (ms: number): Promise<void> => {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

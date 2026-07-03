/**
 * Luminous 人类化键盘输入。
 *
 * 借鉴 CloakBrowser (MIT) 的打字延迟和误打模拟算法，完全重写实现。
 * 使用 Electron webContents.sendInputEvent 模拟人类键盘输入：
 * - 逐字符输入 + 随机延迟
 * - 偶尔思考暂停
 * - 误打模拟（偶尔打错字 → 注意到 → 退格纠正）
 */
import { WebContents } from 'electron'

import {
  LuminousHumanConfig,
  luminousRand,
  luminousRandRange,
  luminousSleep,
} from './luminous-human-config'

// 相邻键位映射（QWERTY 布局），用于生成合理的误打
const NEIGHBOR_KEYS: Record<string, string> = {
  'a': 'qwsz', 'b': 'vghn', 'c': 'xdfv', 'd': 'serfcx', 'e': 'wsdr',
  'f': 'drtgvc', 'g': 'ftyhbv', 'h': 'gyujnb', 'i': 'ujko', 'j': 'huikmn',
  'k': 'jilm', 'l': 'kop', 'm': 'njk', 'n': 'bhjm', 'o': 'iklp',
  'p': 'ol', 'q': 'wa', 'r': 'edft', 's': 'awedxz', 't': 'rfgy',
  'u': 'yhji', 'v': 'cfgb', 'w': 'qase', 'x': 'zsdc', 'y': 'tghu',
  'z': 'asx',
}

/** 获取一个可能的误打字符 */
function getMistypeChar(ch: string): string {
  const lower = ch.toLowerCase()
  const neighbors = NEIGHBOR_KEYS[lower]
  if (!neighbors) return ch
  const mistype = neighbors[Math.floor(Math.random() * neighbors.length)]
  // 保持原始大小写
  return ch === lower ? mistype : mistype.toUpperCase()
}

/**
 * 人类化键盘输入：逐字符输入，含延迟、暂停、误打
 * @param wc WebContents 实例
 * @param text 要输入的文本
 * @param cfg 人类化配置
 */
export async function luminousHumanType(
  wc: WebContents,
  text: string,
  cfg: LuminousHumanConfig
): Promise<void> {
  const chars = Array.from(text)

  for (let i = 0; i < chars.length; i++) {
    const ch = chars[i]

    // 偶尔思考暂停（在词间更常见）
    if (Math.random() < cfg.typing_pause_chance) {
      await luminousSleep(luminousRandRange(cfg.typing_pause_range))
    }

    // 误打模拟：偶尔打错字 → 注意到 → 退格 → 打正确的字
    if (ch.match(/[a-zA-Z]/) && Math.random() < cfg.mistype_chance) {
      const wrong = getMistypeChar(ch)

      // 打出错误字符
      wc.sendInputEvent({ type: 'char', keyCode: wrong })
      await luminousSleep(luminousRandRange(cfg.key_hold))

      // 注意到错误（延迟）
      await luminousSleep(luminousRandRange(cfg.mistype_delay_notice))

      // 退格删除
      wc.sendInputEvent({ type: 'keyDown', keyCode: 'Backspace' })
      wc.sendInputEvent({ type: 'keyUp', keyCode: 'Backspace' })
      await luminousSleep(luminousRandRange(cfg.mistype_delay_correct))

      // 打正确的字符
      wc.sendInputEvent({ type: 'char', keyCode: ch })
    } else {
      // 正常输入
      wc.sendInputEvent({ type: 'char', keyCode: ch })
    }

    // 字符间延迟（基础延迟 + 随机抖动）
    const delay = cfg.typing_delay + luminousRand(-cfg.typing_delay_spread, cfg.typing_delay_spread)
    await luminousSleep(Math.max(20, delay))
  }
}

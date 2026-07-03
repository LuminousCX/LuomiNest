/**
 * Luminous 人类化输入层。
 *
 * 将 mouse/keyboard/scroll 三个底层模块组装为 HumanInputLayer 接口实现，
 * 供 LuomiAutomationExecutor 注入。注入后，所有自动化动作（human !== false）
 * 将走人类化分支：贝塞尔曲线鼠标移动、逐字符延迟输入、加速/减速滚动。
 *
 * 借鉴 CloakBrowser (MIT) 的算法语义，完全重写实现，命名为 Luminous 品牌。
 */
import { WebContents } from 'electron'

import { HumanInputLayer } from './automation-executor'
import {
  LuminousHumanConfig,
  LuminousHumanPreset,
  resolveLuminousConfig,
} from './luminous-human-config'
import { luminousHumanClick, luminousHumanHover } from './luminous-human-mouse'
import { luminousHumanType } from './luminous-human-keyboard'
import { luminousHumanScroll } from './luminous-human-scroll'

/**
 * 人类化输入层实现。
 * 持有一份解析后的配置，所有方法共用同一份 cfg。
 */
export class LuminousHumanLayer implements HumanInputLayer {
  private readonly cfg: LuminousHumanConfig

  constructor(preset: LuminousHumanPreset = 'default') {
    this.cfg = resolveLuminousConfig(preset)
  }

  async click(webContents: WebContents, x: number, y: number): Promise<void> {
    // luminousHumanClick 内部自带随机起点 + 贝塞尔移动 + 瞄准延迟 + 按下/释放
    await luminousHumanClick(webContents, x, y, this.cfg, 'left')
  }

  async type(webContents: WebContents, text: string): Promise<void> {
    await luminousHumanType(webContents, text, this.cfg)
  }

  async scroll(webContents: WebContents, deltaX: number, deltaY: number): Promise<void> {
    await luminousHumanScroll(webContents, deltaX, deltaY, this.cfg)
  }

  async hover(webContents: WebContents, x: number, y: number): Promise<void> {
    await luminousHumanHover(webContents, x, y, this.cfg)
  }
}

/**
 * 工厂函数：创建人类化输入层实例。
 * @param preset 预设名（'default' 正常人类速度 / 'careful' 更慢更谨慎）
 */
export const createLuminousHumanLayer = (preset: LuminousHumanPreset = 'default'): LuminousHumanLayer => {
  return new LuminousHumanLayer(preset)
}

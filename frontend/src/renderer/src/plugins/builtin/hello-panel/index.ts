/**
 * hello-panel — LuomiNest 前端插件示例入口。
 *
 * 演示如何通过 CxPluginContext 注册视图、命令、主题贡献点。
 * 该插件仅用于验证前端插件系统端到端可用，不提供实际业务功能。
 */

import type { CxPluginModule } from '../../types'
import HelloPanelView from './HelloPanelView.vue'

export const activate: CxPluginModule['activate'] = (context) => {
  const logger = context.getLogger()

  // 注册视图贡献点 — 贡献一个面板页面
  context.registerView({
    path: 'panel',
    name: 'panel',
    title: '示例面板',
    icon: 'Sparkles',
    showInSidebar: true,
    sidebarGroup: 'bottom',
    component: HelloPanelView,
  })

  // 注册命令贡献点 — 可通过命令面板或代码触发
  context.registerCommand({
    id: 'say-hello',
    title: '示例：打个招呼',
    keybinding: 'CmdOrCtrl+Shift+H',
    handler: () => {
      const message = `[hello-panel] Hello from LuomiNest frontend plugin at ${new Date().toLocaleTimeString()}`
      logger.info(message)
      return message
    },
  })

  logger.info('hello-panel plugin activated')
}

export const deactivate: CxPluginModule['deactivate'] = () => {
  // 贡献点由 loader 自动通过 unregisterAllByPlugin 清理，
  // 此处仅做模块级资源释放（本示例无资源需要释放）
}

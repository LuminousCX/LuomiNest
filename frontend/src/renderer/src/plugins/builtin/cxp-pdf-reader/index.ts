/**
 * cxp-pdf-reader — LuomiNest CxPlugin PDF 智能阅读器入口。
 *
 * 通过 CxPluginContext 注册 PDF 阅读视图与"打开 PDF 阅读器"命令。
 * 支持 PDF / Word / TXT 三种文档类型，并集成 AI 总结/翻译/问答能力。
 *
 * 贡献点：
 * - 视图：reader（侧边栏底部入口）
 * - 命令：open-pdf-reader（快捷键 CmdOrCtrl+Shift+R）
 */

import type { CxPluginModule } from '../../types'
import PdfReaderView from './views/PdfReaderView.vue'

export const activate: CxPluginModule['activate'] = (context) => {
  const logger = context.getLogger()

  // 注册视图贡献点 — 贡献 PDF 阅读页面
  context.registerView({
    path: 'reader',
    name: 'reader',
    title: 'PDF 阅读',
    icon: 'FileText',
    showInSidebar: true,
    sidebarGroup: 'bottom',
    component: PdfReaderView,
  })

  // 注册命令贡献点 — 通过快捷键或命令面板触发，跳转到 PDF 阅读视图
  context.registerCommand({
    id: 'open-pdf-reader',
    title: '打开 PDF 阅读器',
    keybinding: 'CmdOrCtrl+Shift+R',
    handler: () => {
      window.location.hash = '#/plugins/cxp-pdf-reader/reader'
      logger.info('[cxp-pdf-reader] open-pdf-reader command triggered')
    },
  })

  logger.info('cxp-pdf-reader plugin activated')
}

export const deactivate: CxPluginModule['deactivate'] = () => {
  // 贡献点由 loader 自动通过 unregisterAllByPlugin 清理，
  // 此处无需手动释放资源
}

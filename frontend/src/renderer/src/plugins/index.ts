/**
 * LuomiNest 前端插件系统公共入口。
 *
 * 导出 loader、贡献点注册中心、类型，以及路由集成辅助函数。
 * 应用启动时调用 cxFrontendPluginLoader.init() 完成发现与激活。
 *
 * 路由集成：
 * - initPluginRoutes(router) 在 router 创建后调用，将已激活插件贡献的视图注册为动态路由
 * - 监听贡献点变化时自动 addRoute/removeRoute（通过 watchEffect）
 */

import type { Router } from 'vue-router'
import { cxContributionRegistry } from './contributions'

export * from './types'
export { cxContributionRegistry } from './contributions'
export { cxFrontendPluginLoader } from './loader'

// 已注册到 router 的路由 name 集合（用于注销时 removeRoute）
const _registeredRouteNames = new Set<string>()

/**
 * 将当前所有插件视图注册到 router。
 * 在 cxFrontendPluginLoader.init() 完成后调用一次即可，
 * 后续插件激活/停用时由 loader 内部通过贡献点 registry 触发，需配合 watchPluginRoutes 监听。
 */
export const initPluginRoutes = (router: Router): void => {
  // 初始注册：将所有已有视图加入路由
  for (const route of cxContributionRegistry.getAllViewRoutes()) {
    if (!_registeredRouteNames.has(route.name as string)) {
      router.addRoute(route)
      _registeredRouteNames.add(route.name as string)
    }
  }
}

/**
 * 监听插件视图变化，同步到 router。
 * 返回一个卸载函数（取消监听）。
 *
 * 实现说明：由于贡献点 registry 是响应式的，
 * 调用方可在组件 setup 中用 watchEffect 包裹，或在此处自行轮询。
 * 为避免循环依赖，这里采用显式同步函数，由 loader 在激活/停用时调用。
 */
export const syncPluginRoutes = (router: Router): void => {
  // 收集当前应有的路由 name 集合
  const desiredNames = new Set(
    cxContributionRegistry.pluginViews.map((v) => v.fullName)
  )
  // 移除不再存在的路由
  for (const name of [..._registeredRouteNames]) {
    if (!desiredNames.has(name)) {
      router.removeRoute(name)
      _registeredRouteNames.delete(name)
    }
  }
  // 添加新增的路由
  for (const entry of cxContributionRegistry.pluginViews) {
    if (!_registeredRouteNames.has(entry.fullName) && entry.component) {
      router.addRoute(cxContributionRegistry.viewEntryToRoute(entry))
      _registeredRouteNames.add(entry.fullName)
    }
  }
}

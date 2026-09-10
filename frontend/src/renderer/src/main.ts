import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { watch } from 'vue'
import App from './App.vue'
import router from './router'
import { i18n } from './i18n'
import { useLocaleStore } from './stores/locale'
import { cxFrontendPluginLoader, initPluginRoutes, syncPluginRoutes, cxContributionRegistry } from './plugins'
import './styles/main.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(i18n)

// 初始化语言偏好：同步 <html lang> 与 vue-i18n locale，并异步读取 IPC 权威配置
useLocaleStore(pinia)

// 初始化前端插件系统：发现 builtin 插件 → 激活未禁用的 → 注册贡献的路由
;(async () => {
  try {
    await cxFrontendPluginLoader.init()
    initPluginRoutes(router)
    syncPluginRoutes(router)
    // 监听贡献点变化：插件启用/禁用时自动同步路由表
    watch(
      () => cxContributionRegistry.pluginViews.length,
      () => syncPluginRoutes(router)
    )
  } catch (e) {
    console.error('[LuomiNest] Frontend plugin system init failed:', e)
  }
})()

app.mount('#app')

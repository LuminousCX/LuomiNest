import { createRouter, createWebHashHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/welcome'
  },
  {
    path: '/welcome',
    name: 'Welcome',
    component: () => import('../views/WelcomeView.vue'),
    meta: { title: 'Welcome - LuomiNest', icon: 'Sparkles' }
  },
  {
    path: '/splash',
    name: 'Splash',
    component: () => import('../views/SplashView.vue'),
    meta: { title: 'Loading - LuomiNest' }
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/LoginView.vue'),
    meta: { title: 'Login - LuomiNest' }
  },
  {
    path: '/workbench',
    name: 'Workbench',
    component: () => import('../views/WorkbenchView.vue'),
    meta: { title: '工作台 - LuomiNest', icon: 'Sparkles' }
  },
  {
    path: '/workspace',
    name: 'Workspace',
    component: () => import('../views/WorkspaceView.vue'),
    meta: { title: '对话 - LuomiNest', icon: 'MessageCircle' }
  },
  {
    path: '/chat/platform',
    name: 'ChatPlatform',
    component: () => import('../views/chat/PlatformView.vue'),
    meta: { title: '平台接入 - LuomiNest', icon: 'Globe' }
  },
  {
    path: '/chat/devices',
    name: 'ChatDevices',
    component: () => import('../views/chat/DevicesView.vue'),
    meta: { title: '设备与群组 - LuomiNest', icon: 'Wifi' }
  },
  {
    path: '/desktop-pet',
    name: 'DesktopPet',
    component: () => import('../views/DesktopPetView.vue'),
    meta: { title: 'LuomiNest Desktop Pet' }
  },
  {
    path: '/settings/ai-model',
    name: 'SettingsAIModel',
    component: () => import('../views/settings/AIModelSettings.vue'),
    meta: { title: '模型配置 - LuomiNest', icon: 'Cpu' }
  },
  {
    path: '/settings/stt',
    name: 'SettingsSTT',
    component: () => import('../views/settings/AIModelSettings.vue'),
    meta: { title: '语音识别 - LuomiNest', icon: 'Mic', initialTile: 'stt' }
  },
  {
    path: '/settings/about',
    name: 'SettingsAbout',
    component: () => import('../views/settings/AboutView.vue'),
    meta: { title: '关于开发者 - LuomiNest' }
  },
  {
    path: '/settings/license',
    name: 'SettingsLicense',
    component: () => import('../views/settings/LicenseView.vue'),
    meta: { title: '开源协议 - LuomiNest' }
  },
  {
    path: '/settings/privacy-detail',
    name: 'SettingsPrivacyDetail',
    component: () => import('../views/settings/PrivacyDetailView.vue'),
    meta: { title: '用户隐私 - LuomiNest' }
  },
  {
    path: '/avatar',
    name: 'Avatar',
    component: () => import('../views/AvatarView.vue'),
    meta: { title: '皮套工坊 - LuomiNest', icon: 'Palette' }
  },
  {
    path: '/panel/usage',
    redirect: '/panel/data-stats'
  },
  {
    path: '/panel/data-stats',
    name: 'PanelDataStats',
    component: () => import('../views/panel/DataStatsView.vue'),
    meta: { title: '数据统计 - LuomiNest', icon: 'BarChart3' }
  },
  {
    path: '/panel/console',
    name: 'PanelConsole',
    component: () => import('../views/panel/ConsoleView.vue'),
    meta: { title: '控制台 - LuomiNest', icon: 'Terminal' }
  },
  {
    path: '/tasks',
    name: 'Tasks',
    component: () => import('../views/TasksView.vue'),
    meta: { title: '计划视图 - LuomiNest', icon: 'CheckSquare' }
  },
  {
    path: '/plan/smart-home',
    name: 'PlanSmartHome',
    component: () => import('../views/plan/SmartHomeView.vue'),
    meta: { title: '智能家居 - LuomiNest', icon: 'Home' }
  },
  {
    path: '/workflow',
    name: 'Workflow',
    component: () => import('../views/WorkflowView.vue'),
    meta: { title: '工作流 - LuomiNest', icon: 'GitBranch' }
  },
  {
    path: '/browser',
    name: 'Browser',
    component: () => import('../views/BrowserView.vue'),
    meta: { title: '浏览器 - LuomiNest', icon: 'Globe' }
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('../views/SettingsView.vue'),
    meta: { title: '设置 - LuomiNest', icon: 'Settings' }
  },
  {
    path: '/settings/:section',
    name: 'SettingsDetail',
    component: () => import('../views/settings/SettingsDetailView.vue'),
    meta: { title: '设置 - LuomiNest', icon: 'Settings' }
  },
  {
    path: '/memory',
    name: 'Memory',
    component: () => import('../views/MemoryView.vue'),
    meta: { title: '记忆中枢 - LuomiNest', icon: 'Brain' }
  },
  {
    path: '/market',
    name: 'Market',
    component: () => import('../views/MarketView.vue'),
    meta: { title: '扩展 - LuomiNest', icon: 'Package' }
  },
  {
    path: '/market/plugins',
    redirect: '/market?tab=plugin'
  },
  {
    path: '/market/agents',
    redirect: '/market?tab=agent'
  },
  {
    path: '/market/detail/:type/:id',
    name: 'MarketDetail',
    component: () => import('../views/MarketDetailView.vue'),
    meta: { title: '市场详情 - LuomiNest', icon: 'Package' }
  },
  {
    path: '/agent/create',
    name: 'AgentCreate',
    component: () => import('../views/AgentCreateView.vue'),
    meta: { title: '创建智能体 - LuomiNest', icon: 'Sparkles' }
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

// 公开路由 allowlist — 无需登录态即可访问
// DesktopPet 为独立展示窗口：仅渲染 Live2D + IPC send 通信，不依赖 auth token，
// 且其 webContents !== mainWindow.webContents，无法通过 assertTrustedSender 校验，
// 故加入公开路由 allowlist，避免被路由守卫重定向到登录页（导致桌宠窗口显示主页面而非 Live2D）。
const PUBLIC_ROUTES = new Set(['Welcome', 'Splash', 'Login', 'DesktopPet'])

// Token 缓存：避免每次导航都走 IPC。登录/登出时通过 invalidateAuthToken() 清除
let _cachedAuthToken: string | null | undefined

const invalidateAuthToken = () => {
  _cachedAuthToken = undefined
}

// 暴露给 LoginView 等组件在登录成功后调用，强制下次 beforeEach 重新读取 token
if (typeof window !== 'undefined' && window.api?.auth) {
  window.__lumiInvalidateAuthToken = invalidateAuthToken
}

const hasAuthToken = async (): Promise<boolean> => {
  if (_cachedAuthToken === undefined) {
    try {
      _cachedAuthToken = await window.api.auth.getToken() ?? null
    } catch {
      _cachedAuthToken = null
    }
  }
  return _cachedAuthToken !== null
}

// 欢迎向导完成状态缓存（启动时读取一次，完成向导后由 useWelcomeWizard 调用 invalidate）
let _welcomeCompleted: boolean | undefined

const isWelcomeCompleted = async (): Promise<boolean> => {
  if (_welcomeCompleted === undefined) {
    try {
      _welcomeCompleted = (await window.api.app?.getWelcomeCompleted?.()) === true
    } catch {
      _welcomeCompleted = false
    }
  }
  return _welcomeCompleted === true
}

// 供 useWelcomeWizard 在完成/跳过向导后调用，刷新缓存
if (typeof window !== 'undefined') {
  ;(window as unknown as { __lumiInvalidateWelcome?: () => void }).__lumiInvalidateWelcome = () => {
    _welcomeCompleted = undefined
  }
}

router.beforeEach(async (to) => {
  const title = to.meta.title as string | undefined
  if (title) {
    document.title = title
  }

  // 已完成欢迎向导的用户访问 /welcome → 跳过到 /splash
  if (to.name === 'Welcome' && await isWelcomeCompleted()) {
    return { name: 'Splash' }
  }

  // 公开路由直接放行
  if (PUBLIC_ROUTES.has(to.name as string)) {
    // 已登录用户访问 /login → 重定向到工作区，避免重复登录
    if (to.name === 'Login' && await hasAuthToken()) {
      return { name: 'Workspace' }
    }
    return true
  }

  // 受保护路由：无 token → 重定向到登录页，携带 redirect 参数
  if (!(await hasAuthToken())) {
    return { name: 'Login', query: { redirect: to.fullPath } }
  }

  return true
})

export default router

import { createRouter, createWebHashHistory } from 'vue-router'
import { i18n } from '../i18n'
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
    meta: { titleKey: 'route.welcome', icon: 'Sparkles' }
  },
  {
    path: '/splash',
    name: 'Splash',
    component: () => import('../views/SplashView.vue'),
    meta: { titleKey: 'route.loading' }
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/LoginView.vue'),
    meta: { titleKey: 'route.login' }
  },
  {
    path: '/workbench',
    name: 'Workbench',
    component: () => import('../views/WorkbenchView.vue'),
    meta: { titleKey: 'route.workbench', icon: 'Sparkles' }
  },
  {
    path: '/workspace',
    name: 'Workspace',
    component: () => import('../views/WorkspaceView.vue'),
    meta: { titleKey: 'route.workspace', icon: 'MessageCircle' }
  },
  {
    path: '/chat/platform',
    name: 'ChatPlatform',
    component: () => import('../views/chat/PlatformView.vue'),
    meta: { titleKey: 'route.platform', icon: 'Globe' }
  },
  {
    path: '/chat/devices',
    name: 'ChatDevices',
    component: () => import('../views/chat/DevicesView.vue'),
    meta: { titleKey: 'route.devices', icon: 'Wifi' }
  },
  {
    path: '/desktop-pet',
    name: 'DesktopPet',
    component: () => import('../views/DesktopPetView.vue'),
    meta: { titleKey: 'route.desktopPet' }
  },
  {
    path: '/desktop-pet-chat',
    name: 'DesktopPetChat',
    component: () => import('../views/DesktopPetChatView.vue'),
    meta: { titleKey: 'route.petChat' }
  },
  {
    path: '/settings/ai-model',
    name: 'SettingsAIModel',
    component: () => import('../views/settings/AIModelSettings.vue'),
    meta: { titleKey: 'route.models', icon: 'Cpu' }
  },
  {
    path: '/settings/about',
    name: 'SettingsAbout',
    component: () => import('../views/settings/AboutView.vue'),
    meta: { titleKey: 'route.about' }
  },
  {
    path: '/settings/license',
    name: 'SettingsLicense',
    component: () => import('../views/settings/LicenseView.vue'),
    meta: { titleKey: 'route.license' }
  },
  {
    path: '/settings/privacy-detail',
    name: 'SettingsPrivacyDetail',
    component: () => import('../views/settings/PrivacyDetailView.vue'),
    meta: { titleKey: 'route.privacyDetail' }
  },
  {
    path: '/settings/terms-detail',
    name: 'SettingsTermsDetail',
    component: () => import('../views/settings/TermsDetailView.vue'),
    meta: { titleKey: 'route.termsDetail' }
  },
  {
    path: '/avatar',
    name: 'Avatar',
    component: () => import('../views/AvatarView.vue'),
    meta: { titleKey: 'route.avatar', icon: 'Palette' }
  },
  {
    path: '/panel/usage',
    redirect: '/panel/data-stats'
  },
  {
    path: '/panel/data-stats',
    name: 'PanelDataStats',
    component: () => import('../views/panel/DataStatsView.vue'),
    meta: { titleKey: 'route.stats', icon: 'BarChart3' }
  },
  {
    path: '/panel/console',
    name: 'PanelConsole',
    component: () => import('../views/panel/ConsoleView.vue'),
    meta: { titleKey: 'route.console', icon: 'Terminal' }
  },
  {
    path: '/panel/logs',
    name: 'PanelLogs',
    component: () => import('../views/panel/LogsView.vue'),
    meta: { titleKey: 'log.route.title', icon: 'ScrollText' }
  },
  {
    path: '/tasks',
    name: 'Tasks',
    component: () => import('../views/TasksView.vue'),
    meta: { titleKey: 'route.tasks', icon: 'CheckSquare' }
  },
  {
    path: '/plan/smart-home',
    name: 'PlanSmartHome',
    component: () => import('../views/plan/SmartHomeView.vue'),
    meta: { titleKey: 'route.smartHome', icon: 'Home' }
  },
  {
    path: '/workflow',
    name: 'Workflow',
    component: () => import('../views/WorkflowView.vue'),
    meta: { titleKey: 'route.workflow', icon: 'GitBranch' }
  },
  {
    path: '/browser',
    name: 'Browser',
    component: () => import('../views/BrowserView.vue'),
    meta: { titleKey: 'route.browser', icon: 'Globe' }
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('../views/SettingsView.vue'),
    meta: { titleKey: 'route.settings', icon: 'Settings' }
  },
  {
    path: '/settings/:section',
    name: 'SettingsDetail',
    component: () => import('../views/settings/SettingsDetailView.vue'),
    meta: { titleKey: 'route.settings', icon: 'Settings' }
  },
  {
    path: '/memory',
    name: 'Memory',
    component: () => import('../views/MemoryView.vue'),
    meta: { titleKey: 'route.memory', icon: 'Brain' }
  },
  {
    path: '/market',
    name: 'Market',
    component: () => import('../views/MarketView.vue'),
    meta: { titleKey: 'route.market', icon: 'Package' }
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
    meta: { titleKey: 'route.marketDetail', icon: 'Package' }
  },
  {
    path: '/agent/create',
    name: 'AgentCreate',
    component: () => import('../views/AgentCreateView.vue'),
    meta: { titleKey: 'route.agentCreate', icon: 'Sparkles' }
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
// TermsDetail / PrivacyDetail：法务文本页公开可读，且首启向导（StepAgreement）未持有
// 登录态时也会经 router push 打开它们查看完整协议，公开放行避免被守卫打断向导流程。
const PUBLIC_ROUTES = new Set([
  'Welcome',
  'Splash',
  'Login',
  'DesktopPet',
  'DesktopPetChat',
  'SettingsTermsDetail',
  'SettingsPrivacyDetail'
])

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
  // 窗口标题按当前语言求值（语言切换后下一次导航生效）
  if (to.meta.titleKey) {
    document.title = i18n.global.t(String(to.meta.titleKey))
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

  // 受保护路由：未登录则跳转登录页（token 由主进程自动生成并持久化，正常启动时直接放行）
  if (!(await hasAuthToken())) {
    return { name: 'Login', query: { redirect: to.fullPath } }
  }

  return true
})

export default router

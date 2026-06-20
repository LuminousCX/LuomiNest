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
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('../views/DashboardView.vue'),
    meta: { title: '控制台 - LuomiNest', icon: 'LayoutDashboard' }
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
  {
    path: '/inspire',
    name: 'Inspire',
    component: () => import('../views/InspireView.vue'),
    meta: { title: '灵感 - LuomiNest', icon: 'Lightbulb' }
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

router.beforeEach((to) => {
  const title = to.meta.title as string | undefined
  if (title) {
    document.title = title
  }
})

export default router

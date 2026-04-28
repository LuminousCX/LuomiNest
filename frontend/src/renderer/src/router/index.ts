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
    path: '/workspace',
    name: 'Workspace',
    component: () => import('../views/WorkspaceView.vue'),
    meta: { title: '工作台 - LuomiNest', icon: 'MessageCircle' }
  },
  {
    path: '/workflow',
    name: 'Workflow',
    component: () => import('../views/WorkflowView.vue'),
    meta: { title: '工作流画布 - LuomiNest', icon: 'GitBranch' }
  },
  {
    path: '/inspire',
    name: 'Inspire',
    component: () => import('../views/InspireView.vue'),
    meta: { title: '灵感 - LuomiNest', icon: 'Lightbulb' }
  },
  {
    path: '/tasks',
    name: 'Tasks',
    component: () => import('../views/TasksView.vue'),
    meta: { title: '任务 - LuomiNest', icon: 'CheckSquare' }
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
    path: '/settings/ai-model',
    name: 'SettingsAIModel',
    component: () => import('../views/settings/AIModelSettings.vue'),
    meta: { title: 'AI 模型设置 - LuomiNest', icon: 'Cpu' }
  },
  {
    path: '/settings/:section',
    name: 'SettingsDetail',
    component: () => import('../views/settings/SettingsDetailView.vue'),
    meta: { title: '设置 - LuomiNest', icon: 'Settings' }
  },
  {
    path: '/avatar',
    name: 'Avatar',
    component: () => import('../views/AvatarView.vue'),
    meta: { title: '皮套工坊 - LuomiNest', icon: 'Palette' }
  },
  {
    path: '/memory',
    name: 'Memory',
    component: () => import('../views/MemoryView.vue'),
    meta: { title: '记忆中枢 - LuomiNest', icon: 'Brain' }
  },
  {
    path: '/profile',
    name: 'Profile',
    component: () => import('../views/UserProfileView.vue'),
    meta: { title: '个人信息 - LuomiNest', icon: 'UserCircle' }
  },
  {
    path: '/social',
    name: 'Social',
    component: () => import('../views/SocialView.vue'),
    meta: { title: 'AI社交 - LuomiNest', icon: 'Users' }
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
    path: '/market/skills',
    redirect: '/market?tab=skill'
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
    path: '/desktop-pet',
    name: 'DesktopPet',
    component: () => import('../views/DesktopPetView.vue'),
    meta: { title: 'LuomiNest Desktop Pet', icon: 'Palette' }
  },
  {
    path: '/agent/create',
    name: 'AgentCreate',
    component: () => import('../views/AgentCreateView.vue'),
    meta: { title: '创建智能体 - LuomiNest', icon: 'Sparkles' }
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

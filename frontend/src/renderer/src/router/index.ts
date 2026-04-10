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
    path: '/social',
    name: 'Social',
    component: () => import('../views/SocialView.vue'),
    meta: { title: 'AI社交 - LuomiNest', icon: 'Users' }
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

router.beforeEach((to, _from, next) => {
  const title = to.meta.title as string | undefined
  if (title) {
    document.title = title
  }
  next()
})

export default router

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  MessageCircle,
  MessageSquare,
  Globe,
  Wifi,
  Settings2,
  Cpu,
  Palette,
  BarChart3,
  Terminal,
  CheckSquare,
  CalendarDays,
  Home,
  GitBranch,
  Search,
  Settings,
  Bell,
  Sparkles,
  Package,
  PanelLeftClose,
  PanelLeftOpen,
  Brain,
  Bot,
  User,
} from 'lucide-vue-next'
import type { Component } from 'vue'
import { useTaskStreamStore } from '../stores/taskStream'
import { useAgentStore } from '../stores/agent'
import { useChatStore } from '../stores/chat'
import { useChatTrashStore } from '../stores/chat-trash'
import { cxContributionRegistry } from '../plugins'
import { resolvePluginIcon } from '../plugins/plugin-icons'
import BranchedMenu from './common/BranchedMenu.vue'
import type { BranchedMenuItem } from './common/BranchedMenu.vue'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const taskStreamStore = useTaskStreamStore()
const agentStore = useAgentStore()
const chatStore = useChatStore()
const chatTrashStore = useChatTrashStore()

const isNavCollapsed = ref(true)
const navMenuRef = ref<InstanceType<typeof BranchedMenu> | null>(null)

// 会话数据预取（原 LumiSidebar 职责，合并后由本组件承担）
onMounted(async () => {
  await agentStore.fetchAgents()
  if (agentStore.activeAgent?.id) {
    await chatStore.fetchConversations(agentStore.activeAgent.id)
    chatTrashStore.fetchTrash(agentStore.activeAgent.id)
  }
})

// 插件贡献的侧边栏视图（响应式，插件激活/停用时自动更新）
const pluginSidebarViews = computed(() => cxContributionRegistry.sidebarPluginViews.value)

interface NavChild {
  id: string
  label: string
  icon: Component
}

interface NavGroup {
  id: string
  label: string
  icon: Component
  children: NavChild[]
}

// 标签走 vue-i18n，语言切换时 computed 重新求值
const navGroups = computed<NavGroup[]>(() => [
  {
    id: 'chat',
    label: t('nav.chat'),
    icon: MessageCircle,
    children: [
      { id: '/workbench', label: t('nav.workbench'), icon: Bot },
      { id: '/workspace', label: t('nav.workspace'), icon: MessageSquare },
      { id: '/chat/platform', label: t('nav.platform'), icon: Globe },
      { id: '/chat/devices', label: t('nav.devices'), icon: Wifi },
    ],
  },
  {
    id: 'panel',
    label: t('nav.panel'),
    icon: Settings2,
    children: [
      { id: '/settings/ai-model', label: t('nav.modelConfig'), icon: Cpu },
      { id: '/avatar', label: t('nav.avatarWorkshop'), icon: Palette },
      { id: '/panel/data-stats', label: t('nav.dataStats'), icon: BarChart3 },
      { id: '/memory', label: t('nav.memoryHub'), icon: Brain },
      { id: '/market', label: t('nav.market'), icon: Package },
      { id: '/panel/console', label: t('nav.console'), icon: Terminal },
    ],
  },
  {
    id: 'plan',
    label: t('nav.plan'),
    icon: CheckSquare,
    children: [
      { id: '/tasks', label: t('nav.taskSchedule'), icon: CalendarDays },
      { id: '/plan/smart-home', label: t('nav.smartHome'), icon: Home },
      { id: '/workflow', label: t('nav.workflow'), icon: GitBranch },
    ],
  },
])

interface NavItem {
  id: string
  label: string
  icon: Component
  route: string
}

const navItems = computed<NavItem[]>(() => [
  { id: 'browser', label: t('nav.browser'), icon: Globe, route: '/browser' },
  { id: 'settings', label: t('nav.settings'), icon: Settings, route: '/settings' },
])

const PENDING_NAV_TARGETS: Record<string, 'browser' | 'workflow'> = {
  '/browser': 'browser',
  '/workflow': 'workflow',
}

const isPathPending = (path: string): boolean => {
  const target = PENDING_NAV_TARGETS[path]
  if (!target) return false
  return taskStreamStore.pendingNavigation[target]
}

const isPathActive = (path: string): boolean => {
  return route.path === path || route.path.startsWith(path + '/')
}

// 路由驱动的激活值（ BranchedMenu 以精确匹配消费）
const activeChildPath = computed(() => {
  for (const group of navGroups.value) {
    for (const child of group.children) {
      if (isPathActive(child.id)) return child.id
    }
  }
  return ''
})

const activeToolPath = computed(() => navItems.value.find((i) => isPathActive(i.route))?.route ?? '')

const activePluginPath = computed(
  () => pluginSidebarViews.value.find((p) => isPathActive(p.fullPath))?.fullPath ?? '',
)

// 菜单项：分组区 + 工具区 + 插件区共用 BranchedMenu 渲染
const groupMenuItems = computed<BranchedMenuItem[]>(() =>
  navGroups.value.map((group) => ({
    label: group.label,
    icon: group.icon,
    children: group.children.map((child) => ({
      value: child.id,
      label: child.label,
      icon: child.icon,
      pending: isPathPending(child.id),
    })),
  })),
)

const toolMenuItems = computed<BranchedMenuItem[]>(() =>
  navItems.value.map((item) => ({
    label: item.label,
    icon: item.icon,
    value: item.route,
    pending: isPathPending(item.route),
  })),
)

const pluginMenuItems = computed<BranchedMenuItem[]>(() =>
  pluginSidebarViews.value.map((pview) => ({
    label: pview.title,
    icon: resolvePluginIcon(pview.icon),
    value: pview.fullPath,
  })),
)

const activeGroup = computed(() => {
  for (const group of navGroups.value) {
    for (const child of group.children) {
      if (isPathActive(child.id)) return group.id
    }
  }
  return null
})

// 折叠横栏点击分组图标：展开侧栏并打开该分组
const expandAndOpen = (groupId: string) => {
  if (isNavCollapsed.value) {
    isNavCollapsed.value = false
  }
  const index = navGroups.value.findIndex((g) => g.id === groupId)
  if (index >= 0) {
    nextTick(() => navMenuRef.value?.openSection(index))
  }
}

const handleNavigate = (path: string) => {
  const target = PENDING_NAV_TARGETS[path]
  if (target) {
    taskStreamStore.clearPendingNavigation(target)
  }
  router.push(path)
}
</script>

<template>
  <div :class="['sidebar-nav-panel', { collapsed: isNavCollapsed }]">
    <div class="nav-header">
      <div class="brand">
        <div class="brand-avatar">
          <User :size="22" />
        </div>
        <div v-if="!isNavCollapsed" class="brand-info">
          <span class="brand-name">LuomiNest</span>
          <span class="brand-tag">LuminousCX</span>
        </div>
      </div>
      <div v-if="!isNavCollapsed" class="header-actions">
        <button class="header-action-btn" :aria-label="t('nav.announcements')" :title="t('nav.announcements')">
          <Bell :size="16" />
          <span class="header-action-dot"></span>
        </button>
      </div>
      <button class="collapse-toggle-btn" :aria-label="isNavCollapsed ? t('nav.expandSidebar') : t('nav.collapseSidebar')" :title="isNavCollapsed ? t('nav.expandSidebar') : t('nav.collapseSidebar')" @click="isNavCollapsed = !isNavCollapsed">
        <PanelLeftOpen v-if="isNavCollapsed" :size="18" />
        <PanelLeftClose v-else :size="18" />
      </button>
    </div>

    <div v-if="!isNavCollapsed" class="nav-search">
      <Search :size="14" class="nav-search-icon" />
      <input
        type="text"
        :placeholder="t('nav.searchPlaceholder')"
        class="nav-search-input"
        readonly
        @click="router.push('/workspace')"
      />
      <Sparkles :size="14" class="nav-search-sparkle" />
    </div>

    <div class="nav-content">
      <div v-if="!isNavCollapsed" class="nav-section">
        <div class="section-label">{{ t('nav.sectionNavigate') }}</div>
        <BranchedMenu
          ref="navMenuRef"
          :items="groupMenuItems"
          :active="activeChildPath"
          :default-open="-1"
          accordion
          :row-height="34"
          :indent="44"
          :trunk="14"
          :radius="10"
          :line-width="1.5"
          :draw-duration="400"
          :fold-duration="300"
          @select="handleNavigate"
        />
      </div>

      <div v-if="!isNavCollapsed && toolMenuItems.length" class="nav-section">
        <div class="section-label">{{ t('nav.sectionTools') }}</div>
        <BranchedMenu
          :items="toolMenuItems"
          :active="activeToolPath"
          :default-open="-1"
          :row-height="32"
          :indent="44"
          :trunk="14"
          :radius="10"
          :line-width="1.5"
          :draw-duration="400"
          :fold-duration="300"
          @select="handleNavigate"
        />
      </div>

      <div v-if="!isNavCollapsed && pluginMenuItems.length" class="nav-section">
        <div class="section-label">{{ t('nav.sectionPlugins') }}</div>
        <BranchedMenu
          :items="pluginMenuItems"
          :active="activePluginPath"
          :default-open="-1"
          :row-height="32"
          :indent="44"
          :trunk="14"
          :radius="10"
          :line-width="1.5"
          :draw-duration="400"
          :fold-duration="300"
          @select="handleNavigate"
        />
      </div>

      <!-- 折叠横栏：仅保留分组图标，点击展开并定位 -->
      <div v-if="isNavCollapsed" class="nav-rail">
        <button
          v-for="group in navGroups"
          :key="group.id"
          :class="['rail-btn', { active: activeGroup === group.id }]"
          :title="group.label"
          :aria-label="group.label"
          @click="expandAndOpen(group.id)"
        >
          <component :is="group.icon" :size="18" />
        </button>
      </div>
    </div>

    <div class="nav-footer">
      <button class="footer-btn" :title="t('nav.settings')" @click="router.push('/settings')">
        <Settings :size="15" />
        <span v-if="!isNavCollapsed">{{ t('nav.settings') }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.sidebar-nav-panel {
  width: calc(var(--space-9) * 5);
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--surface);
  box-shadow: var(--shadow-sm);
  z-index: var(--z-base);
  flex-shrink: 0;
  overflow: hidden;
  position: relative;
  transition: width var(--transition-normal);
}

.sidebar-nav-panel.collapsed {
  width: calc(var(--space-8) + var(--space-3));
}

.sidebar-nav-panel::after {
  content: '';
  position: absolute;
  top: var(--space-3);
  bottom: var(--space-3);
  right: 0;
  width: 1px;
  background: var(--divider-vertical);
}

.sidebar-nav-panel.collapsed::after {
  display: none;
}

.nav-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4) var(--space-2);
  flex-shrink: 0;
}

.sidebar-nav-panel.collapsed .nav-header {
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-2) var(--space-2);
  align-items: center;
  justify-content: center;
}

.brand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.brand-avatar {
  width: var(--nav-item-height);
  height: var(--nav-item-height);
  border-radius: var(--radius-full);
  background: var(--surface-hover);
  border: 1px solid var(--border-light);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.brand-info {
  display: flex;
  flex-direction: column;
}

.brand-name {
  font-size: var(--text-lg);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  line-height: var(--leading-snug);
}

.brand-tag {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  font-weight: var(--font-medium);
  letter-spacing: 0.3px;
}

.header-actions {
  display: flex;
  gap: var(--space-1);
}

.header-action-btn {
  width: calc(var(--space-6) + var(--space-2));
  height: calc(var(--space-6) + var(--space-2));
  border: none;
  background: var(--surface-hover);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-secondary);
  transition: background var(--transition-fast), color var(--transition-fast);
  position: relative;
}

.header-action-btn:hover {
  background: var(--surface-active);
  color: var(--text-primary);
}

.header-action-dot {
  position: absolute;
  top: var(--radius-xs);
  right: var(--radius-xs);
  width: var(--radius-xs);
  height: var(--radius-xs);
  background: var(--lumi-danger);
  border-radius: var(--radius-full);
}

.collapse-toggle-btn {
  width: calc(var(--space-5) + var(--space-2));
  height: calc(var(--space-5) + var(--space-2));
  border: none;
  background: transparent;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-muted);
  transition: background var(--transition-fast), color var(--transition-fast);
}

.collapse-toggle-btn:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.sidebar-nav-panel.collapsed .collapse-toggle-btn {
  order: -1;
}

.nav-search {
  padding: 0 var(--space-3);
  position: relative;
  margin-bottom: var(--space-1);
}

.nav-search:focus-within .nav-search-icon {
  color: var(--text-secondary);
}

.nav-search-icon {
  position: absolute;
  left: var(--space-5);
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  pointer-events: none;
}

.nav-search-input {
  width: 100%;
  height: calc(var(--space-5) + var(--space-3));
  border: none;
  background: var(--surface-hover);
  border-radius: var(--radius-md);
  padding: 0 var(--space-7) 0 calc(var(--space-6) + var(--space-1));
  font-size: var(--text-sm);
  color: var(--text-primary);
  cursor: pointer;
}

.nav-search-input::placeholder {
  color: var(--text-muted);
}

.nav-search-sparkle {
  position: absolute;
  right: var(--space-5);
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
}

.nav-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: var(--space-1) 0;
  scrollbar-width: thin;
}

.sidebar-nav-panel.collapsed .nav-content {
  padding: var(--space-1) 0 0;
  overflow: visible;
}

.nav-section {
  padding: 0 var(--space-2);
}

.nav-section + .nav-section {
  margin-top: var(--space-1);
  padding-top: var(--space-1);
  border-top: 1px solid var(--divider-horizontal);
}

.section-label {
  padding: var(--space-2) var(--space-2) var(--radius-xs);
  font-size: var(--text-2xs);
  font-weight: var(--font-bold);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 1.2px;
  user-select: none;
  opacity: 0.65;
}

/* ===== 折叠横栏 ===== */
.nav-rail {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: calc(var(--space-1) / 2);
  padding: 0 var(--space-2);
}

.rail-btn {
  width: calc(var(--space-6) + var(--space-2));
  height: calc(var(--space-6) + var(--space-2));
  border: none;
  background: transparent;
  border-radius: var(--nav-item-radius);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-muted);
  transition: background var(--transition-fast), color var(--transition-fast);
}

.rail-btn:hover {
  background: var(--nav-item-hover-bg);
  color: var(--text-primary);
}

.rail-btn.active {
  color: var(--nav-item-active-color);
  background: var(--nav-item-active-bg);
}

.nav-footer {
  padding: var(--space-2);
  border-top: 1px solid var(--divider-horizontal);
  flex-shrink: 0;
}

.sidebar-nav-panel.collapsed .nav-footer {
  border-top: none;
}

.footer-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-2);
  border: none;
  background: transparent;
  border-radius: var(--nav-item-radius);
  cursor: pointer;
  color: var(--text-muted);
  font-size: var(--text-sm);
  transition: background var(--transition-fast), color var(--transition-fast);
}

.sidebar-nav-panel.collapsed .footer-btn {
  padding: var(--space-2) 0;
}

.footer-btn:hover {
  background: var(--nav-item-hover-bg);
  color: var(--text-primary);
}

/* Focus visible */
.header-action-btn:focus-visible,
.collapse-toggle-btn:focus-visible,
.rail-btn:focus-visible,
.footer-btn:focus-visible {
  outline: var(--space-1) solid var(--focus-ring);
  outline-offset: calc(var(--space-1) / 2);
}
</style>

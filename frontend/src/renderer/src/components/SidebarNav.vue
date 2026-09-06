<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
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
  ChevronRight,
  Bell,
  Sparkles,
  Package,
  PanelLeftClose,
  PanelLeftOpen,
  Brain,
  Bot,
  User,
} from 'lucide-vue-next'
import { useTaskStreamStore } from '../stores/taskStream'
import { cxContributionRegistry } from '../plugins'
import { resolvePluginIcon } from '../plugins/plugin-icons'

const route = useRoute()
const router = useRouter()
const taskStreamStore = useTaskStreamStore()

const isNavCollapsed = ref(true)

// 插件贡献的侧边栏视图（响应式，插件激活/停用时自动更新）
const pluginSidebarViews = computed(() => cxContributionRegistry.sidebarPluginViews.value)

const isPluginViewActive = (fullPath: string) => {
  return route.path === fullPath || route.path.startsWith(fullPath + '/')
}

const handlePluginNavigate = (fullPath: string) => {
  router.push(fullPath)
}

interface NavChild {
  id: string
  label: string
  icon: typeof MessageCircle
}

interface NavGroup {
  id: string
  label: string
  icon: typeof MessageCircle
  children: NavChild[]
}

interface NavItem {
  id: string
  label: string
  icon: typeof MessageCircle
  route: string
  badge?: string
}

const expandedGroups = ref<Set<string>>(new Set(['chat']))

const navGroups: NavGroup[] = [
  {
    id: 'chat',
    label: '聊天',
    icon: MessageCircle,
    children: [
      { id: '/workbench', label: '工作台', icon: Bot },
      { id: '/workspace', label: '对话', icon: MessageSquare },
      { id: '/chat/platform', label: '平台接入', icon: Globe },
      { id: '/chat/devices', label: '设备与群组', icon: Wifi },
    ],
  },
  {
    id: 'panel',
    label: '控制面板',
    icon: Settings2,
    children: [
      { id: '/settings/ai-model', label: '模型配置', icon: Cpu },
      { id: '/avatar', label: '皮套工坊', icon: Palette },
      { id: '/panel/data-stats', label: '数据统计', icon: BarChart3 },
      { id: '/memory', label: '记忆中枢', icon: Brain },
      { id: '/market', label: '扩展市场', icon: Package },
      { id: '/panel/console', label: '控制台', icon: Terminal },
    ],
  },
  {
    id: 'plan',
    label: '计划任务',
    icon: CheckSquare,
    children: [
      { id: '/tasks', label: '计划视图', icon: CalendarDays },
      { id: '/plan/smart-home', label: '智能家居', icon: Home },
      { id: '/workflow', label: '工作流', icon: GitBranch },
    ],
  },
]

const navItems: NavItem[] = [
  { id: 'browser', label: '浏览器', icon: Globe, route: '/browser' },
  { id: 'settings', label: '设置', icon: Settings, route: '/settings' },
]

const activeGroup = computed(() => {
  for (const group of navGroups) {
    for (const child of group.children) {
      if (route.path === child.id || route.path.startsWith(child.id + '/')) {
        return group.id
      }
    }
  }
  return null
})

const isItemActive = (item: NavItem) => {
  return route.path === item.route || route.path.startsWith(item.route + '/')
}

const isChildActive = (childId: string) => {
  return route.path === childId || route.path.startsWith(childId + '/')
}

const toggleGroup = (groupId: string) => {
  if (isNavCollapsed.value) {
    isNavCollapsed.value = false
    expandedGroups.value = new Set([groupId])
    return
  }
  const next = new Set(expandedGroups.value)
  if (next.has(groupId)) {
    // 已展开则收缩
    next.delete(groupId)
  } else {
    // 严格手风琴:展开新分组时,自动收缩其他已展开分组
    next.clear()
    next.add(groupId)
  }
  expandedGroups.value = next
}

watch(isNavCollapsed, (collapsed) => {
  if (collapsed) {
    expandedGroups.value = new Set()
  }
})

watch(activeGroup, (groupId) => {
  if (groupId && !expandedGroups.value.has(groupId)) {
    // 严格手风琴:路由进入某分组子项时,仅展开该分组,收缩其他
    expandedGroups.value = new Set([groupId])
  }
}, { immediate: true })

const PENDING_NAV_TARGETS: Record<string, 'browser' | 'workflow'> = {
  '/browser': 'browser',
  '/workflow': 'workflow',
}

const isPathPending = (path: string): boolean => {
  const target = PENDING_NAV_TARGETS[path]
  if (!target) return false
  return taskStreamStore.pendingNavigation[target]
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
        <button class="header-action-btn" aria-label="消息公告" title="消息公告">
          <Bell :size="16" />
          <span class="header-action-dot"></span>
        </button>
      </div>
      <button class="collapse-toggle-btn" :aria-label="isNavCollapsed ? '展开侧栏' : '收起侧栏'" :title="isNavCollapsed ? '展开侧栏' : '收起侧栏'" @click="isNavCollapsed = !isNavCollapsed">
        <PanelLeftOpen v-if="isNavCollapsed" :size="18" />
        <PanelLeftClose v-else :size="18" />
      </button>
    </div>

    <div v-if="!isNavCollapsed" class="nav-search">
      <Search :size="14" class="nav-search-icon" />
      <input
        type="text"
        placeholder="搜索..."
        class="nav-search-input"
        readonly
        @click="router.push('/workspace')"
      />
      <Sparkles :size="14" class="nav-search-sparkle" />
    </div>

    <div class="nav-content">
      <div class="nav-section">
        <div v-if="!isNavCollapsed" class="section-label">导航</div>

        <div v-for="group in navGroups" :key="group.id" class="nav-group">
          <button
            :class="['group-header', { active: activeGroup === group.id, expanded: expandedGroups.has(group.id) }]"
            @click="toggleGroup(group.id)"
          >
            <div class="group-header-left">
              <component :is="group.icon" :size="17" class="group-icon" />
              <span v-if="!isNavCollapsed" class="group-label">{{ group.label }}</span>
            </div>
            <ChevronRight
              v-if="!isNavCollapsed"
              :size="14"
              :class="['group-chevron', { rotated: expandedGroups.has(group.id) }]"
            />
          </button>

          <Transition name="tree-expand">
            <div v-if="!isNavCollapsed && expandedGroups.has(group.id)" class="group-children">
              <div
                v-for="(child, idx) in group.children"
                :key="child.id"
                :class="['tree-child', { active: isChildActive(child.id), last: idx === group.children.length - 1 }]"
                :style="{ '--tree-index': idx }"
                @click="handleNavigate(child.id)"
              >
                <div class="tree-line">
                  <div class="tree-branch"></div>
                  <div class="tree-node"></div>
                </div>
                <component :is="child.icon" :size="14" class="child-icon" />
                <span class="child-label">{{ child.label }}</span>
                <span v-if="isPathPending(child.id)" class="nav-pending-dot"></span>
              </div>
            </div>
          </Transition>
        </div>
      </div>

      <div v-if="!isNavCollapsed" class="nav-section">
        <div class="section-label">工具</div>
        <div class="nav-items">
          <button
            v-for="item in navItems"
            :key="item.id"
            :class="['nav-item', { active: isItemActive(item) }]"
            @click="handleNavigate(item.route)"
          >
            <component :is="item.icon" :size="17" class="nav-item-icon" />
            <span class="nav-item-label">{{ item.label }}</span>
            <span v-if="item.badge" class="nav-item-badge">{{ item.badge }}</span>
            <span v-if="isPathPending(item.route)" class="nav-pending-dot"></span>
          </button>
        </div>
      </div>

      <div v-if="!isNavCollapsed && pluginSidebarViews.length" class="nav-section">
        <div class="section-label">插件</div>
        <div class="nav-items">
          <button
            v-for="pview in pluginSidebarViews"
            :key="pview.fullName"
            :class="['nav-item', { active: isPluginViewActive(pview.fullPath) }]"
            @click="handlePluginNavigate(pview.fullPath)"
          >
            <component :is="resolvePluginIcon(pview.icon)" :size="17" class="nav-item-icon" />
            <span class="nav-item-label">{{ pview.title }}</span>
          </button>
        </div>
      </div>
    </div>

    <div class="nav-footer">
      <button class="footer-btn" title="设置" @click="router.push('/settings')">
        <Settings :size="15" />
        <span v-if="!isNavCollapsed">设置</span>
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

.nav-group {
  margin-bottom: calc(var(--space-1) / 2);
}

.group-header {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) var(--space-2);
  border: none;
  background: transparent;
  border-radius: var(--nav-item-radius);
  cursor: pointer;
  color: var(--text-secondary);
  transition: background var(--transition-fast), color var(--transition-fast);
  position: relative;
  overflow: hidden;
}

.sidebar-nav-panel.collapsed .group-header {
  padding: var(--space-2) 0;
  justify-content: center;
  border-radius: var(--radius-lg);
}

.group-header:hover {
  background: var(--nav-item-hover-bg);
  color: var(--text-primary);
}

.group-header.active {
  color: var(--nav-item-active-color);
  background: var(--nav-item-active-bg);
}

.group-header.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: var(--radius-xs);
  bottom: var(--radius-xs);
  width: calc(var(--space-1) / 1.5);
  border-radius: 0 var(--radius-xs) var(--radius-xs) 0;
  background: var(--nav-item-active-color);
  opacity: 0.7;
}

.group-header-left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  position: relative;
  z-index: 1;
}

.group-icon {
  flex-shrink: 0;
  opacity: 0.8;
}

.group-header.active .group-icon {
  opacity: 1;
}

.group-label {
  font-size: var(--text-base);
  font-weight: var(--font-medium);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.group-header.active .group-label {
  font-weight: var(--font-semibold);
}

.group-chevron {
  position: relative;
  z-index: 1;
  flex-shrink: 0;
  opacity: 0.5;
  transition: transform var(--transition-fast), opacity var(--transition-fast);
}

.group-header:hover .group-chevron {
  opacity: 0.8;
}

.group-header.active .group-chevron {
  color: var(--nav-item-active-color);
  opacity: 0.8;
}

.group-chevron.rotated {
  transform: rotate(90deg);
}

.group-children {
  padding: calc(var(--space-1) / 2) 0;
}

.tree-child {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--radius-xs) var(--space-2) var(--radius-xs) var(--space-6);
  cursor: pointer;
  border-radius: var(--nav-item-radius);
  color: var(--text-muted);
  transition: background var(--transition-fast), color var(--transition-fast);
  position: relative;
  overflow: hidden;
  font-size: var(--text-base);
  opacity: 0;
  transform: translateY(calc(var(--space-1) * -1));
  /* 使用 CSS 变量控制 stagger，避免硬编码 nth-child，减少合成层数量与代码冗余 */
  animation: tree-item-in var(--duration-leave) var(--ease-default) forwards;
  animation-delay: calc(var(--tree-stagger-step, 35ms) * var(--tree-index, 0));
}

@keyframes tree-item-in {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 用户偏好减少动态效果时，跳过进入动画，直接保持可见，
   避免初始 opacity:0 / transform 残留导致导航子项不可见 */
@media (prefers-reduced-motion: reduce) {
  .tree-child {
    opacity: 1;
    transform: none;
    animation: none;
  }
}

.tree-child:hover {
  background: var(--nav-item-hover-bg);
  color: var(--text-primary);
}

.tree-child.active {
  color: var(--nav-item-active-color);
  background: var(--nav-item-active-bg);
  font-weight: var(--font-medium);
}

.tree-child.active .child-icon {
  color: var(--nav-item-active-color);
}

.tree-line {
  position: absolute;
  left: var(--space-3);
  top: 0;
  bottom: 0;
  width: var(--space-3);
  pointer-events: none;
}

.tree-line::before {
  content: '';
  position: absolute;
  left: var(--space-1);
  top: 0;
  bottom: 0;
  width: 1px;
  background: var(--border);
}

.tree-branch {
  position: absolute;
  left: var(--space-1);
  top: 50%;
  width: calc(var(--space-1) + 1px);
  height: 1px;
  background: var(--border);
  transform: translateY(-50%);
}

.tree-node {
  position: absolute;
  left: calc(var(--space-1) + var(--space-1) + 1px);
  top: 50%;
  width: calc(var(--space-1) + 1px);
  height: calc(var(--space-1) + 1px);
  border-radius: var(--radius-full);
  background: var(--border);
  transform: translate(-50%, -50%);
}

.tree-child.last .tree-line::before {
  bottom: 50%;
}

.child-icon {
  flex-shrink: 0;
  color: inherit;
}

.child-label {
  font-size: var(--text-base);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.nav-items {
  display: flex;
  flex-direction: column;
  gap: calc(var(--space-1) / 2);
}

.nav-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-2);
  border: none;
  background: transparent;
  border-radius: var(--nav-item-radius);
  cursor: pointer;
  color: var(--text-muted);
  transition: background var(--transition-fast), color var(--transition-fast);
  position: relative;
  overflow: hidden;
}

.nav-item:hover {
  background: var(--nav-item-hover-bg);
  color: var(--text-primary);
}

.nav-item.active {
  color: var(--nav-item-active-color);
  background: var(--nav-item-active-bg);
}

.nav-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: var(--radius-xs);
  bottom: var(--radius-xs);
  width: calc(var(--space-1) / 1.5);
  border-radius: 0 var(--radius-xs) var(--radius-xs) 0;
  background: var(--nav-item-active-color);
  opacity: 0.7;
}

.nav-item-icon {
  flex-shrink: 0;
  position: relative;
  z-index: 1;
}

.nav-item-label {
  font-size: var(--text-base);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  position: relative;
  z-index: 1;
}

.nav-item-badge {
  font-size: var(--text-2xs);
  padding: var(--badge-padding);
  border-radius: var(--radius-full);
  background: var(--lumi-brand);
  color: var(--text-inverse);
  font-weight: var(--font-semibold);
  position: relative;
  z-index: 1;
}

.nav-pending-dot {
  position: absolute;
  top: 50%;
  right: var(--space-2);
  transform: translateY(-50%);
  width: var(--radius-xs);
  height: var(--radius-xs);
  border-radius: var(--radius-full);
  background: var(--lumi-accent);
  box-shadow: 0 0 0 2px var(--surface);
  z-index: 2;
  animation: nav-pending-pulse 1.6s var(--ease-in-out) infinite;
}

@keyframes nav-pending-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.45; }
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

/* Tree expand transition */
.tree-expand-enter-active {
  animation: tree-expand-in var(--duration-leave) var(--ease-in-out);
}

.tree-expand-leave-active {
  animation: tree-expand-out var(--duration-fast) var(--ease-in-out);
}

@keyframes tree-expand-in {
  from { opacity: 0; max-height: 0; }
  to { opacity: 1; max-height: 300px; }
}

@keyframes tree-expand-out {
  from { opacity: 1; max-height: 300px; }
  to { opacity: 0; max-height: 0; }
}

/* Focus visible */
.header-action-btn:focus-visible,
.collapse-toggle-btn:focus-visible,
.group-header:focus-visible,
.nav-item:focus-visible,
.footer-btn:focus-visible {
  outline: var(--space-1) solid var(--focus-ring);
  outline-offset: calc(var(--space-1) / 2);
}

</style>

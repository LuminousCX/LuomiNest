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
} from 'lucide-vue-next'
import LumiBrandStar from './common/LumiBrandStar.vue'

const route = useRoute()
const router = useRouter()

const isNavCollapsed = ref(true)

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
    next.delete(groupId)
  } else {
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
    expandedGroups.value = new Set([...expandedGroups.value, groupId])
  }
}, { immediate: true })

const handleNavigate = (path: string) => {
  router.push(path)
}
</script>

<template>
  <div :class="['sidebar-nav-panel', { collapsed: isNavCollapsed }]">
    <div class="nav-header">
      <div class="brand">
        <div class="brand-avatar">
          <LumiBrandStar :size="22" :animated="false" />
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
                @click="handleNavigate(child.id)"
              >
                <div class="tree-line">
                  <div class="tree-branch"></div>
                  <div class="tree-node"></div>
                </div>
                <component :is="child.icon" :size="14" class="child-icon" />
                <span class="child-label">{{ child.label }}</span>
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
            @click="router.push(item.route)"
          >
            <component :is="item.icon" :size="17" class="nav-item-icon" />
            <span class="nav-item-label">{{ item.label }}</span>
            <span v-if="item.badge" class="nav-item-badge">{{ item.badge }}</span>
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
  width: 240px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--surface);
  flex-shrink: 0;
  overflow: hidden;
  position: relative;
  transition: width 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.sidebar-nav-panel.collapsed {
  width: 52px;
}

.sidebar-nav-panel::after {
  content: '';
  position: absolute;
  top: 12px;
  bottom: 12px;
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
  padding: 14px 16px 10px;
  flex-shrink: 0;
}

.sidebar-nav-panel.collapsed .nav-header {
  flex-direction: column;
  gap: 8px;
  padding: 14px 8px 10px;
  align-items: center;
  justify-content: center;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-avatar {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, var(--lumi-primary), var(--lumi-primary-soft));
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 3px 10px var(--lumi-primary-border);
  color: var(--text-inverse);
}

.brand-info {
  display: flex;
  flex-direction: column;
}

.brand-name {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.brand-tag {
  font-size: 10px;
  color: var(--text-muted);
  font-weight: 500;
  letter-spacing: 0.3px;
}

.header-actions {
  display: flex;
  gap: 4px;
}

.header-action-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: var(--surface-hover);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-secondary);
  transition: background 0.15s ease-in-out;
  position: relative;
}

.header-action-btn:hover {
  background: var(--surface-active);
  color: var(--text-primary);
}

.header-action-dot {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 6px;
  height: 6px;
  background: var(--lumi-danger);
  border-radius: 50%;
}

.collapse-toggle-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-muted);
  transition: background 0.15s ease-in-out, color 0.15s ease-in-out;
}

.collapse-toggle-btn:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.sidebar-nav-panel.collapsed .collapse-toggle-btn {
  order: -1;
}

.nav-search {
  padding: 0 12px;
  position: relative;
  margin-bottom: 4px;
}

.nav-search:focus-within .nav-search-icon {
  color: var(--text-secondary);
}

.nav-search-icon {
  position: absolute;
  left: 20px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  pointer-events: none;
}

.nav-search-input {
  width: 100%;
  height: 32px;
  border: none;
  background: var(--surface-hover);
  border-radius: var(--radius-md);
  padding: 0 32px 0 28px;
  font-size: 12px;
  color: var(--text-primary);
  cursor: pointer;
}

.nav-search-input::placeholder {
  color: var(--text-muted);
}

.nav-search-sparkle {
  position: absolute;
  right: 20px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
}

.nav-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 4px 0;
  scrollbar-width: thin;
}

.sidebar-nav-panel.collapsed .nav-content {
  padding: 4px 0 0;
  overflow: visible;
}

.nav-section {
  padding: 0 8px;
}

.nav-section + .nav-section {
  margin-top: 4px;
  padding-top: 4px;
  border-top: 1px solid var(--divider-horizontal);
}

.section-label {
  padding: 10px 10px 6px;
  font-size: 10px;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 1.2px;
  user-select: none;
  opacity: 0.65;
}

.nav-group {
  margin-bottom: 2px;
}

.group-header {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border: none;
  background: transparent;
  border-radius: var(--radius-md);
  cursor: pointer;
  color: var(--text-secondary);
  transition: background 0.2s ease-in-out, color 0.2s ease-in-out;
  position: relative;
  overflow: hidden;
}

.sidebar-nav-panel.collapsed .group-header {
  padding: 8px 0;
  justify-content: center;
  border-radius: var(--radius-lg);
}

.group-header:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.group-header.active {
  color: var(--lumi-primary);
  background: var(--lumi-primary-subtle);
}

.group-header.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 6px;
  bottom: 6px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--lumi-primary);
  opacity: 0.7;
}

.group-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
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
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.group-header.active .group-label {
  font-weight: 600;
}

.group-chevron {
  position: relative;
  z-index: 1;
  flex-shrink: 0;
  opacity: 0.5;
  transition: transform 0.2s ease-in-out, opacity 0.2s ease-in-out;
}

.group-header:hover .group-chevron {
  opacity: 0.8;
}

.group-header.active .group-chevron {
  color: var(--lumi-primary);
  opacity: 0.8;
}

.group-chevron.rotated {
  transform: rotate(90deg);
}

.group-children {
  padding: 2px 0 2px 0;
}

.tree-child {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px 6px 22px;
  cursor: pointer;
  border-radius: var(--radius-md);
  color: var(--text-muted);
  transition: background 0.2s ease-in-out, color 0.2s ease-in-out;
  position: relative;
  overflow: hidden;
  font-size: 13px;
  opacity: 0;
  transform: translateY(-4px);
  animation: tree-item-in 0.2s cubic-bezier(0.4, 0, 0.2, 1) forwards;
}

@keyframes tree-item-in {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.tree-child:nth-child(1) { animation-delay: 0.02s; }
.tree-child:nth-child(2) { animation-delay: 0.04s; }
.tree-child:nth-child(3) { animation-delay: 0.06s; }
.tree-child:nth-child(4) { animation-delay: 0.08s; }
.tree-child:nth-child(5) { animation-delay: 0.10s; }
.tree-child:nth-child(6) { animation-delay: 0.12s; }

.tree-child:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.tree-child.active {
  color: var(--lumi-primary);
  background: var(--lumi-primary-subtle);
  font-weight: 500;
}

.tree-child.active .child-icon {
  color: var(--lumi-primary);
}

.tree-line {
  position: absolute;
  left: 12px;
  top: 0;
  bottom: 0;
  width: 12px;
  pointer-events: none;
}

.tree-branch {
  position: absolute;
  left: 4px;
  top: 0;
  height: 50%;
  width: 1px;
  background: var(--border);
}

.tree-child.last .tree-branch {
  height: 50%;
}

.tree-node {
  position: absolute;
  left: 4px;
  top: 50%;
  width: 5px;
  height: 1px;
  background: var(--border);
}

.tree-child.last .tree-node {
  top: 0;
  height: 50%;
  width: 1px;
  left: 4px;
}

.child-icon {
  flex-shrink: 0;
  color: inherit;
}

.child-label {
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.nav-items {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border: none;
  background: transparent;
  border-radius: var(--radius-md);
  cursor: pointer;
  color: var(--text-muted);
  transition: background 0.2s ease-in-out, color 0.2s ease-in-out;
  position: relative;
  overflow: hidden;
}

.nav-item:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.nav-item.active {
  color: var(--lumi-primary);
  background: var(--lumi-primary-subtle);
}

.nav-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 6px;
  bottom: 6px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--lumi-primary);
  opacity: 0.7;
}

.nav-item-icon {
  flex-shrink: 0;
  position: relative;
  z-index: 1;
}

.nav-item-label {
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  position: relative;
  z-index: 1;
}

.nav-item-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: var(--radius-full);
  background: var(--lumi-primary);
  color: var(--text-inverse);
  font-weight: 600;
  position: relative;
  z-index: 1;
}

.nav-footer {
  padding: 8px;
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
  gap: 8px;
  padding: 8px;
  border: none;
  background: transparent;
  border-radius: var(--radius-md);
  cursor: pointer;
  color: var(--text-muted);
  font-size: 12px;
  transition: background 0.2s ease-in-out, color 0.2s ease-in-out;
}

.sidebar-nav-panel.collapsed .footer-btn {
  padding: 8px 0;
}

.footer-btn:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

/* Tree expand transition */
.tree-expand-enter-active {
  animation: tree-expand-in 0.2s ease-in-out;
}

.tree-expand-leave-active {
  animation: tree-expand-out 0.15s ease-in-out;
}

@keyframes tree-expand-in {
  from { opacity: 0; max-height: 0; }
  to { opacity: 1; max-height: 300px; }
}

@keyframes tree-expand-out {
  from { opacity: 1; max-height: 300px; }
  to { opacity: 0; max-height: 0; }
}
</style>

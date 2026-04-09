<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  MessageCircle,
  GitBranch,
  Lightbulb,
  CheckSquare,
  Globe,
  Plus,
  Search,
  ChevronDown,
  ChevronRight,
  Settings,
  Sparkles,
  Bot,
  Palette,
  Brain,
  Users
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()

const isBrowserMode = computed(() => route.path.startsWith('/browser'))

const navItems = [
  { id: '/workspace', label: '对话', icon: MessageCircle },
  { id: '/workflow', label: '工作流', icon: GitBranch },
  { id: '/inspire', label: '灵感', icon: Lightbulb },
  { id: '/tasks', label: '任务', icon: CheckSquare },
  { id: '/avatar', label: '皮套', icon: Palette },
  { id: '/memory', label: '记忆', icon: Brain },
  { id: '/social', label: '社交', icon: Users },
  { id: '/browser', label: '浏览器', icon: Globe }
]

const agents = ref([
  {
    id: 1,
    name: '代可行',
    desc: '热爱手搓的程序员',
    avatar: '',
    color: '#0d9488',
    active: true
  },
  {
    id: 2,
    name: '无言',
    desc: '寡言的自由撰稿人',
    avatar: '',
    color: '#6366f1',
    active: false
  },
  {
    id: 3,
    name: '林且慢',
    desc: '少年系系的辅导员',
    avatar: '',
    color: '#f59e0b',
    active: false
  },
  {
    id: 4,
    name: '自定义',
    desc: '创建全新 Agent',
    avatar: '',
    color: '#f43f5e',
    active: false,
    isCustom: true
  }
])

const expandedAgents = ref([1])

const toggleAgent = (id: number) => {
  const idx = expandedAgents.value.indexOf(id)
  if (idx > -1) {
    expandedAgents.value.splice(idx, 1)
  } else {
    expandedAgents.value.push(id)
  }
}

const selectAgent = (agent: typeof agents.value[0]) => {
  agents.value.forEach(a => a.active = false)
  agent.active = true
}
</script>

<template>
  <div class="lumi-sidebar" :class="{ 'is-browser': isBrowserMode }">
    <div class="sidebar-icon-rail">
      <div class="rail-top">
        <button class="avatar-btn" title="辰汐账户">
          <div class="avatar-ring">
            <span class="avatar-initial">L</span>
          </div>
        </button>
        <nav class="icon-nav">
          <button
            v-for="item in navItems"
            :key="item.id"
            :class="['icon-btn', { active: route.path === item.id }]"
            :title="item.label"
            @click="router.push(item.id)"
          >
            <component :is="item.icon" :size="20" />
          </button>
        </nav>
      </div>
      <div class="rail-bottom">
        <button class="icon-btn" title="设置" @click="router.push('/settings')">
          <Settings :size="20" />
        </button>
      </div>
    </div>

    <Transition name="panel-slide">
      <div v-if="!isBrowserMode" class="sidebar-agent-panel">
        <div class="panel-header">
          <div class="search-box">
            <Search :size="15" class="search-icon" />
            <input type="text" placeholder="搜索" class="search-input" />
          </div>
        </div>

        <button class="new-agent-btn">
          <Plus :size="16" />
          <span>新建 Agent</span>
        </button>

        <div class="agent-list">
          <div
            v-for="agent in agents"
            :key="agent.id"
            class="agent-item-wrapper"
          >
            <button
              :class="['agent-item', { active: agent.active, 'is-custom': agent.isCustom }]"
              @click="selectAgent(agent)"
            >
              <div class="agent-avatar" :style="{ background: agent.color + '18', color: agent.color }">
                <Bot v-if="!agent.isCustom" :size="20" />
                <Sparkles v-else :size="20" />
              </div>
              <div class="agent-info">
                <span class="agent-name">{{ agent.name }}</span>
                <span class="agent-desc">{{ agent.desc }}</span>
              </div>
              <button
                v-if="!agent.isCustom"
                class="expand-btn"
                @click.stop="toggleAgent(agent.id)"
              >
                <ChevronDown v-if="expandedAgents.includes(agent.id)" :size="14" />
                <ChevronRight v-else :size="14" />
              </button>
            </button>
          </div>
        </div>

        <div class="panel-footer">
          <div class="update-notice">
            <Sparkles :size="14" />
            <span>新版本下载中...</span>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.lumi-sidebar {
  display: flex;
  height: 100%;
  background: var(--workspace-sidebar);
  border-right: 1px solid var(--workspace-border);
  transition: all var(--transition-normal);
}

.lumi-sidebar.is-browser {
  border-right-color: var(--browser-border);
  background: var(--browser-surface);
}

.sidebar-icon-rail {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  width: 60px;
  height: 100%;
  padding: 12px 0;
  border-right: 1px solid var(--workspace-border);
  flex-shrink: 0;
}

.is-browser .sidebar-icon-rail {
  border-right-color: var(--browser-border);
}

.rail-top {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.rail-bottom {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.avatar-btn {
  width: 40px;
  height: 40px;
  padding: 0;
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: transform var(--transition-fast);
}

.avatar-btn:hover {
  transform: scale(1.05);
}

.avatar-ring {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, var(--lumi-primary), #14b8a6);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(13, 148, 136, 0.3);
}

.avatar-initial {
  font-size: 16px;
  font-weight: 700;
  color: white;
}

.icon-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 8px;
  width: 100%;
  padding: 0 8px;
}

.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
  position: relative;
}

.icon-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-secondary);
}

.is-browser .icon-btn:hover {
  background: var(--browser-elevated);
  color: var(--browser-text);
}

.icon-btn.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.icon-btn.active::before {
  content: '';
  position: absolute;
  left: -8px;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  border-radius: 2px;
  background: var(--lumi-primary);
}

.sidebar-agent-panel {
  width: 260px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--workspace-sidebar);
  overflow: hidden;
}

.panel-header {
  padding: 12px 14px 8px;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--workspace-panel);
  border-radius: var(--radius-md);
  border: 1px solid transparent;
  transition: all var(--transition-fast);
}

.search-box:focus-within {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

.search-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.search-input {
  flex: 1;
  background: transparent;
  font-size: 13px;
  color: var(--text-secondary);
}

.search-input::placeholder {
  color: var(--text-muted);
}

.new-agent-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 8px 14px;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  border: 1px dashed var(--workspace-border);
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.new-agent-btn:hover {
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
}

.agent-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 10px;
}

.agent-item-wrapper {
  margin-bottom: 2px;
}

.agent-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 10px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  text-align: left;
  position: relative;
}

.agent-item:hover {
  background: var(--workspace-hover);
}

.agent-item.active {
  background: var(--lumi-primary-light);
}

.agent-item.active::after {
  content: '';
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--lumi-primary);
}

.agent-avatar {
  width: 38px;
  height: 38px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.agent-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.agent-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.agent-desc {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.expand-btn {
  padding: 4px;
  color: var(--text-muted);
  border-radius: 4px;
  flex-shrink: 0;
  transition: all var(--transition-fast);
}

.expand-btn:hover {
  background: var(--workspace-panel);
  color: var(--text-secondary);
}

.agent-item.is-custom .agent-name {
  color: var(--lumi-accent);
}

.panel-footer {
  padding: 12px 14px;
  border-top: 1px solid var(--workspace-border);
}

.update-notice {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--text-muted);
}

.update-notice svg {
  color: var(--lumi-primary);
}

.panel-slide-enter-active,
.panel-slide-leave-active {
  transition: all var(--transition-normal);
}

.panel-slide-enter-from,
.panel-slide-leave-to {
  opacity: 0;
  transform: translateX(-16px);
  width: 0;
}
</style>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
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
  Users,
  Trash2,
  Check,
  Store
} from 'lucide-vue-next'
import { useAgentStore } from '../stores/agent'

const route = useRoute()
const router = useRouter()
const agentStore = useAgentStore()

const hideAgentPanelRoutes = ['/browser', '/social', '/settings', '/marketplace']

const isBrowserMode = computed(() => hideAgentPanelRoutes.some(r => route.path.startsWith(r)))

const navItems = [
  { id: '/workspace', label: '对话', icon: MessageCircle },
  { id: '/workflow', label: '工作流', icon: GitBranch },
  { id: '/inspire', label: '灵感', icon: Lightbulb },
  { id: '/tasks', label: '任务', icon: CheckSquare },
  { id: '/marketplace', label: '市场', icon: Store },
  { id: '/avatar', label: '皮套', icon: Palette },
  { id: '/memory', label: '记忆', icon: Brain },
  { id: '/social', label: '社交', icon: Users },
  { id: '/browser', label: '浏览器', icon: Globe }
]

const searchQuery = ref('')

const agents = computed(() => {
  const storeAgents = agentStore.agents
    .filter(a => {
      if (a.isMain) return false
      if (!searchQuery.value) return true
      const q = searchQuery.value.toLowerCase()
      return a.name.toLowerCase().includes(q) || a.description.toLowerCase().includes(q)
    })
    .map(a => ({
      id: a.id,
      name: a.name,
      desc: a.description,
      avatar: a.avatar || '',
      color: a.color,
      active: agentStore.activeAgent?.id === a.id,
      isDefault: a.id.startsWith('default-')
    }))
  return [
    ...storeAgents,
    {
      id: '__custom__',
      name: '自定义',
      desc: '创建全新 Agent',
      avatar: '',
      color: '#f43f5e',
      active: false,
      isCustom: true,
      isDefault: false
    }
  ]
})

const expandedAgents = ref<string[]>([])

const toggleAgent = (id: string) => {
  const idx = expandedAgents.value.indexOf(id)
  if (idx > -1) {
    expandedAgents.value.splice(idx, 1)
  } else {
    expandedAgents.value.push(id)
  }
}

const selectAgent = (agent: typeof agents.value[0]) => {
  if (agent.isCustom) {
    showCreateDialog.value = true
    return
  }
  const found = agentStore.agents.find(a => a.id === agent.id)
  if (found) {
    agentStore.setActiveAgent(found)
    router.push('/workspace')
  }
}

const handleDeleteAgent = async (agentId: string) => {
  try {
    await agentStore.deleteAgent(agentId)
  } catch (e: any) {
    console.error('Failed to delete agent:', e)
  }
}

const showCreateDialog = ref(false)
const newAgentForm = ref({
  name: '',
  description: '',
  systemPrompt: '',
  color: '#0d9488'
})
const agentColors = ['#0d9488', '#6366f1', '#f59e0b', '#f43f5e', '#8b5cf6', '#06b6d4', '#84cc16', '#ec4899']

const handleCreateAgent = async () => {
  if (!newAgentForm.value.name.trim()) return
  try {
    await agentStore.createAgent({
      name: newAgentForm.value.name.trim(),
      description: newAgentForm.value.description.trim(),
      systemPrompt: newAgentForm.value.systemPrompt.trim(),
      color: newAgentForm.value.color,
      capabilities: ['chat'],
    })
    showCreateDialog.value = false
    newAgentForm.value = { name: '', description: '', systemPrompt: '', color: '#0d9488' }
    router.push('/workspace')
  } catch (e: any) {
    console.error('Failed to create agent:', e)
  }
}

onMounted(async () => {
  await agentStore.fetchAgents()
})
</script>

<template>
  <div class="lumi-sidebar">
    <div class="sidebar-icon-rail">
      <div class="rail-top">
        <button class="avatar-btn" aria-label="LuminousChenXi 账户">
          <div class="avatar-ring">
            <span class="avatar-initial">L</span>
          </div>
        </button>
        <nav class="icon-nav">
          <button
            v-for="item in navItems"
            :key="item.id"
            :class="['icon-btn', { active: route.path === item.id || (item.id === '/marketplace' && route.path.startsWith('/marketplace')) }]"
            :aria-label="item.label"
            @click="router.push(item.id)"
          >
            <component :is="item.icon" :size="20" />
          </button>
        </nav>
      </div>
      <div class="rail-bottom">
        <button class="icon-btn" aria-label="设置" @click="router.push('/settings')">
          <Settings :size="20" />
        </button>
      </div>
    </div>

    <Transition name="panel-slide">
      <div v-if="!isBrowserMode" class="sidebar-agent-panel">
        <div class="panel-header">
          <div class="search-box">
            <Search :size="15" class="search-icon" />
            <input v-model="searchQuery" type="text" placeholder="搜索" class="search-input" />
          </div>
        </div>

        <button class="new-agent-btn" aria-label="新建 Agent" @click="showCreateDialog = true">
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
                v-if="!agent.isCustom && !agent.isDefault"
                class="expand-btn"
                :aria-label="expandedAgents.includes(agent.id) ? '收起' : '展开'"
                @click.stop="toggleAgent(agent.id)"
              >
                <ChevronDown v-if="expandedAgents.includes(agent.id)" :size="14" />
                <ChevronRight v-else :size="14" />
              </button>
            </button>

            <Transition name="expand">
              <div v-if="expandedAgents.includes(agent.id) && !agent.isCustom && !agent.isDefault" class="agent-expanded">
                <button class="expanded-action delete" @click.stop="handleDeleteAgent(agent.id)">
                  <Trash2 :size="13" />
                  <span>删除</span>
                </button>
              </div>
            </Transition>
          </div>
        </div>

        <div class="panel-footer">
          <div class="update-notice">
            <Sparkles :size="14" />
            <span>LuomiNest v0.1.0</span>
          </div>
        </div>
      </div>
    </Transition>

    <Transition name="selection-fade">
      <div v-if="showCreateDialog" class="create-dialog-overlay" @click.self="showCreateDialog = false">
        <div class="create-dialog">
          <h3>创建自定义 Agent</h3>
          <div class="form-group">
            <label class="form-label">
              名称
              <span class="required-mark">*</span>
            </label>
            <input v-model="newAgentForm.name" type="text" class="form-input" placeholder="如: 小助手" />
          </div>
          <div class="form-group">
            <label class="form-label">描述</label>
            <input v-model="newAgentForm.description" type="text" class="form-input" placeholder="如: 通用对话助手" />
          </div>
          <div class="form-group">
            <label class="form-label">系统提示词</label>
            <textarea
              v-model="newAgentForm.systemPrompt"
              class="form-input form-textarea"
              placeholder="定义 Agent 的角色和行为..."
              rows="4"
            ></textarea>
          </div>
          <div class="form-group">
            <label class="form-label">颜色</label>
            <div class="color-picker">
              <button
                v-for="color in agentColors"
                :key="color"
                :class="['color-dot', { active: newAgentForm.color === color }]"
                :style="{ background: color }"
                @click="newAgentForm.color = color"
              ></button>
            </div>
          </div>
          <div class="dialog-actions">
            <button class="dialog-btn cancel" @click="showCreateDialog = false">取消</button>
            <button
              :class="['dialog-btn confirm', { disabled: !newAgentForm.name.trim() }]"
              :disabled="!newAgentForm.name.trim()"
              @click="handleCreateAgent"
            >
              <Check :size="16" />
              创建
            </button>
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
  background: var(--surface);
  box-shadow: var(--shadow-sm);
  transition: all var(--transition-normal);
}

.sidebar-icon-rail {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  width: 60px;
  height: 100%;
  padding: 12px 0;
  flex-shrink: 0;
  position: relative;
}

.sidebar-icon-rail::after {
  content: '';
  position: absolute;
  top: 12px;
  bottom: 12px;
  right: 0;
  width: 1px;
  background: var(--divider-vertical);
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
  background: var(--surface-hover);
  color: var(--text-secondary);
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
  background: var(--surface);
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
  background: var(--bg-secondary);
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
  border: 1px dashed var(--border);
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
  background: var(--surface-hover);
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
  background: var(--bg-secondary);
  color: var(--text-secondary);
}

.agent-item.is-custom .agent-name {
  color: var(--lumi-accent);
}

.agent-expanded {
  display: flex;
  gap: 4px;
  padding: 4px 10px 8px 58px;
}

.expanded-action {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  transition: all var(--transition-fast);
}

.expanded-action.delete {
  color: var(--text-muted);
}

.expanded-action.delete:hover {
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
}

.expand-enter-active,
.expand-leave-active {
  transition: all 0.2s ease-in-out;
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}

.panel-footer {
  padding: 12px 14px;
  position: relative;
}

.panel-footer::before {
  content: '';
  position: absolute;
  top: 0;
  left: 14px;
  right: 14px;
  height: 1px;
  background: var(--divider-soft);
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

.create-dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.create-dialog {
  background: var(--workspace-card);
  border-radius: var(--radius-xl);
  padding: 28px;
  width: 400px;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: var(--shadow-lg);
}

.create-dialog h3 {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.form-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 2px;
}

.required-mark {
  color: var(--lumi-accent);
  font-weight: 700;
  margin-left: 2px;
}

.form-input {
  width: 100%;
  padding: 10px 14px;
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-primary);
  transition: all var(--transition-fast);
}

.form-input:focus {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

.form-input::placeholder {
  color: var(--text-muted);
}

.form-textarea {
  resize: vertical;
  min-height: 80px;
}

.color-picker {
  display: flex;
  gap: 8px;
}

.color-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  cursor: pointer;
  transition: all var(--transition-fast);
  border: 2px solid transparent;
}

.color-dot:hover {
  transform: scale(1.15);
}

.color-dot.active {
  border-color: var(--text-primary);
  box-shadow: 0 0 0 2px white, 0 0 0 4px currentColor;
}

.dialog-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  margin-top: 20px;
}

.dialog-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 20px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.dialog-btn.cancel {
  color: var(--text-muted);
  background: var(--workspace-panel);
}

.dialog-btn.cancel:hover {
  background: var(--workspace-hover);
}

.dialog-btn.confirm {
  color: white;
  background: var(--lumi-primary);
}

.dialog-btn.confirm:hover {
  background: var(--lumi-primary-hover);
}

.dialog-btn.confirm.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.selection-fade-enter-active {
  animation: lumi-fade-in 0.3s ease-out;
}

.selection-fade-leave-active {
  animation: lumi-fade-in 0.2s ease-out reverse;
}
</style>

<script setup lang="ts">
import { ref, onMounted, nextTick, watch, computed } from 'vue'
import {
  Send,
  Paperclip,
  Mic,
  Wand2,
  ChevronDown,
  Sparkles,
  Bot,
  AtSign,
  Link2,
  MoreHorizontal,
  Loader2,
  Settings,
  AlertTriangle,
  StopCircle,
  RotateCcw,
  Clock,
  MessageSquare,
  Trash2,
  X,
  Plus
} from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import { useChatStore } from '../stores/chat'
import { useAgentStore } from '../stores/agent'
import { useModelStore } from '../stores/model'
import { getProviderLogo } from '../config/provider-logos'

const router = useRouter()
const chatStore = useChatStore()
const agentStore = useAgentStore()
const modelStore = useModelStore()

const inputText = ref('')
const messagesContainer = ref<HTMLElement | null>(null)
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const showModelDropdown = ref(false)
const showHistoryPanel = ref(false)

const agentCards = computed(() => {
  const agents = agentStore.agents.map(a => ({
    id: a.id,
    name: a.name,
    desc: a.description,
    color: a.color,
    avatar: a.avatar,
    selected: agentStore.activeAgent?.id === a.id
  }))
  return [
    ...agents,
    {
      id: '__custom__',
      name: '自定义',
      desc: '创建全新 Agent',
      color: '#f43f5e',
      avatar: null,
      selected: false
    }
  ]
})

const messages = computed(() => chatStore.messages)
const isStreaming = computed(() => chatStore.isStreaming)
const isBackendReady = computed(() => chatStore.isBackendReady)

const currentModel = computed(() => {
  const agent = agentStore.activeAgent
  if (agent?.model) return agent.model
  return modelStore.modelConfig.defaultModel || '未配置模型'
})

const currentProvider = computed(() => {
  const agent = agentStore.activeAgent
  if (agent?.provider) return agent.provider
  return modelStore.modelConfig.defaultProvider || ''
})

const currentProviderLogo = computed(() => getProviderLogo(currentProvider.value))

const hasProvider = computed(() => modelStore.providers.length > 0)

const availableModelOptions = computed(() => {
  const options: { providerId: string; providerName: string; providerLogo: ReturnType<typeof getProviderLogo>; modelId: string; modelName: string }[] = []
  for (const provider of modelStore.providers) {
    const logo = getProviderLogo(provider.id)
    if (provider.models.length > 0) {
      for (const model of provider.models) {
        options.push({
          providerId: provider.id,
          providerName: provider.name,
          providerLogo: logo,
          modelId: model.id,
          modelName: model.name,
        })
      }
    } else {
      options.push({
        providerId: provider.id,
        providerName: provider.name,
        providerLogo: logo,
        modelId: provider.defaultModel,
        modelName: provider.defaultModel,
      })
    }
  }
  return options
})

const agentConversations = computed(() => {
  const agentId = agentStore.activeAgent?.id
  if (!agentId) return chatStore.conversations
  return chatStore.conversations.filter(c => c.agentId === agentId || !c.agentId)
})

const selectAgent = async (agent: { id: string; name: string; desc: string; color: string }) => {
  if (agent.id === '__custom__') {
    showCreateAgentDialog.value = true
    return
  }
  const found = agentStore.agents.find(a => a.id === agent.id)
  if (found) {
    agentStore.setActiveAgent(found)
    chatStore.clearMessages()
    await chatStore.fetchConversations()
  }
}

const selectModel = (providerId: string, modelId: string) => {
  if (agentStore.activeAgent) {
    agentStore.updateAgent(agentStore.activeAgent.id, {
      provider: providerId,
      model: modelId,
    })
  }
  showModelDropdown.value = false
}

const sendMessage = async () => {
  if (!inputText.value.trim() || isStreaming.value) return
  if (!isBackendReady.value) return

  const content = inputText.value
  inputText.value = ''
  resetTextareaHeight()

  const agent = agentStore.activeAgent

  if (!chatStore.currentConversation) {
    await chatStore.createConversation(
      content.slice(0, 30),
      agent?.id,
      agent?.model || modelStore.modelConfig.defaultModel || undefined,
      agent?.provider || modelStore.modelConfig.defaultProvider || undefined,
    )
  }

  const options: any = {
    model: agent?.model || modelStore.modelConfig.defaultModel || undefined,
    provider: agent?.provider || modelStore.modelConfig.defaultProvider || undefined,
    temperature: modelStore.modelConfig.defaultTemperature,
    maxTokens: modelStore.modelConfig.defaultMaxTokens,
    topP: modelStore.modelConfig.defaultTopP,
  }
  if (agent?.systemPrompt) options.systemPrompt = agent.systemPrompt

  await chatStore.sendMessage(content, options)
  await nextTick()
  scrollToBottom()
}

const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const resetTextareaHeight = () => {
  if (textareaRef.value) {
    textareaRef.value.style.height = 'auto'
  }
}

const autoResize = () => {
  if (textareaRef.value) {
    textareaRef.value.style.height = 'auto'
    textareaRef.value.style.height = `${Math.min(textareaRef.value.scrollHeight, 120)}px`
  }
}

const formatMessage = (text: string): string => {
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
  return escaped
    .replace(/\n/g, '<br>')
    .replace(/•\s*/g, '<span class="bullet">•</span>&nbsp;')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
}

const formatTime = (dateStr: string) => {
  try {
    const d = new Date(dateStr)
    const now = new Date()
    const isToday = d.toDateString() === now.toDateString()
    if (isToday) {
      return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    }
    return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

const handleLoadConversation = async (convId: string) => {
  await chatStore.loadConversation(convId)
  showHistoryPanel.value = false
  await nextTick()
  scrollToBottom()
}

const handleDeleteConversation = async (convId: string) => {
  await chatStore.deleteConversation(convId)
}

const startNewConversation = () => {
  chatStore.clearMessages()
  showHistoryPanel.value = false
}

watch(messages, () => {
  nextTick(scrollToBottom)
}, { deep: true })

const showCreateAgentDialog = ref(false)
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
    showCreateAgentDialog.value = false
    newAgentForm.value = { name: '', description: '', systemPrompt: '', color: '#0d9488' }
  } catch (e: any) {
    console.error('Failed to create agent:', e)
  }
}

const handleDeleteAgent = async (agentId: string) => {
  try {
    await agentStore.deleteAgent(agentId)
  } catch (e: any) {
    console.error('Failed to delete agent:', e)
  }
}

const handleClickOutsideModel = (e: MouseEvent) => {
  const target = e.target as HTMLElement
  if (!target.closest('.model-dropdown-container')) {
    showModelDropdown.value = false
  }
}

onMounted(async () => {
  await chatStore.checkBackend()
  if (chatStore.isBackendReady) {
    await Promise.all([
      agentStore.fetchAgents(),
      modelStore.fetchProviders(),
      modelStore.fetchModelConfig(),
      chatStore.fetchConversations(),
    ])
  }
  document.addEventListener('click', handleClickOutsideModel)
})
</script>

<template>
  <div class="workspace-view">
    <div class="workspace-header">
      <div class="header-left">
        <span class="header-badge">
          <Sparkles :size="14" />
          LuomiNest
        </span>
        <span class="header-stats">
          <span class="provider-icon-mini" :style="{ background: currentProviderLogo.color }">
            {{ currentProviderLogo.initials }}
          </span>
          {{ currentModel }}
        </span>
      </div>
      <div class="header-right">
        <button v-if="!isBackendReady" class="header-icon-btn warning" title="后端未连接" @click="chatStore.checkBackend()">
          <AlertTriangle :size="18" />
        </button>
        <button class="header-icon-btn" title="历史记录" @click="showHistoryPanel = !showHistoryPanel">
          <Clock :size="18" />
        </button>
        <button class="header-icon-btn" title="设置" @click="router.push('/settings/ai-model')">
          <Settings :size="18" />
        </button>
      </div>
    </div>

    <div v-if="!isBackendReady" class="backend-warning">
      <div class="warning-content">
        <AlertTriangle :size="20" />
        <div class="warning-text">
          <p class="warning-title">后端服务未连接</p>
          <p class="warning-desc">请确保 LuomiNest 后端服务已启动 (端口 18000)</p>
        </div>
        <button class="retry-btn" @click="chatStore.checkBackend()">
          <RotateCcw :size="14" />
          重试
        </button>
      </div>
    </div>

    <div v-if="!hasProvider && isBackendReady" class="backend-warning info">
      <div class="warning-content">
        <Wand2 :size="20" />
        <div class="warning-text">
          <p class="warning-title">尚未配置模型供应商</p>
          <p class="warning-desc">请先前往设置页面添加 Ollama 或其他模型供应商</p>
        </div>
        <button class="retry-btn" @click="router.push('/settings/ai-model')">
          去设置
        </button>
      </div>
    </div>

    <div class="agent-selector-row">
      <div class="agent-cards-scroll">
        <button
          v-for="(card, idx) in agentCards"
          :key="card.id"
          :class="['agent-card', { selected: card.selected }]"
          :style="{ animationDelay: `${idx * 60}ms` }"
          @click="selectAgent(card)"
        >
          <div class="card-avatar" :style="{ background: card.color + '14', color: card.color, borderColor: card.selected ? card.color : 'transparent' }">
            <Bot v-if="card.id !== '__custom__'" :size="26" />
            <Sparkles v-else :size="26" />
          </div>
          <div class="card-info">
            <span class="card-name">{{ card.name }}</span>
            <span class="card-desc">{{ card.desc }}</span>
          </div>
          <button
            v-if="card.id !== '__custom__' && !card.id.startsWith('default-')"
            class="card-delete"
            title="删除 Agent"
            @click.stop="handleDeleteAgent(card.id)"
          >
            <MoreHorizontal :size="14" />
          </button>
        </button>
      </div>
      <Transition name="selection-fade">
        <div v-if="agentStore.activeAgent" class="selection-toast">
          我选择「{{ agentStore.activeAgent.name }}」作为我的Agent
        </div>
      </Transition>
    </div>

    <div class="main-content-area">
      <div ref="messagesContainer" class="chat-area" :class="{ 'with-history': showHistoryPanel }">
        <div class="messages-container">
          <div
            v-for="msg in messages"
            :key="msg.id"
            :class="['message-row', msg.role]"
          >
            <div class="message-avatar" v-if="msg.role === 'assistant'">
              <div class="avatar-assistant">
                <Bot :size="16" />
              </div>
            </div>
            <div class="message-bubble">
              <div class="message-content" v-html="formatMessage(msg.content)"></div>
              <div v-if="msg.role === 'assistant' && !msg.done && isStreaming" class="streaming-cursor">
                <span class="cursor-blink"></span>
              </div>
            </div>
          </div>

          <div v-if="messages.length === 0" class="empty-state">
            <div class="empty-icon">
              <Bot :size="48" />
            </div>
            <p class="empty-title">选择一个Agent开始对话</p>
            <p class="empty-desc">或直接在下方输入框中提问</p>
            <div class="empty-quick-actions">
              <button class="quick-action" @click="inputText = '你好，请介绍一下你自己'">打个招呼</button>
              <button class="quick-action" @click="inputText = '帮我写一段 Python 代码'">写段代码</button>
              <button class="quick-action" @click="inputText = '解释一下什么是大语言模型'">了解 LLM</button>
            </div>
          </div>
        </div>
      </div>

      <Transition name="history-slide">
        <div v-if="showHistoryPanel" class="history-panel">
          <div class="history-header">
            <h3>对话历史</h3>
            <div class="history-header-actions">
              <button class="history-action-btn" title="新建对话" @click="startNewConversation">
                <Plus :size="16" />
              </button>
              <button class="history-action-btn" title="关闭" @click="showHistoryPanel = false">
                <X :size="16" />
              </button>
            </div>
          </div>
          <div class="history-list">
            <button
              v-for="conv in agentConversations"
              :key="conv.id"
              :class="['history-item', { active: chatStore.currentConversation?.id === conv.id }]"
              @click="handleLoadConversation(conv.id)"
            >
              <MessageSquare :size="14" class="history-item-icon" />
              <div class="history-item-info">
                <span class="history-item-title">{{ conv.title }}</span>
                <span class="history-item-time">{{ formatTime(conv.updatedAt) }}</span>
              </div>
              <button class="history-item-delete" title="删除" @click.stop="handleDeleteConversation(conv.id)">
                <Trash2 :size="12" />
              </button>
            </button>
            <div v-if="agentConversations.length === 0" class="history-empty">
              <Clock :size="24" />
              <p>暂无对话记录</p>
            </div>
          </div>
        </div>
      </Transition>
    </div>

    <div class="input-area">
      <div class="input-wrapper">
        <textarea
          ref="textareaRef"
          v-model="inputText"
          placeholder="可以描述任务或提问任何问题"
          rows="1"
          class="chat-input"
          :disabled="isStreaming || !isBackendReady"
          @keydown.enter.exact.prevent="sendMessage"
          @input="autoResize"
        ></textarea>
        <div class="input-toolbar">
          <div class="toolbar-left">
            <div class="model-dropdown-container">
              <button class="tool-btn" title="选择模型" @click.stop="showModelDropdown = !showModelDropdown">
                <span class="provider-icon-mini" :style="{ background: currentProviderLogo.color }">
                  {{ currentProviderLogo.initials }}
                </span>
                <span class="model-btn-text">{{ currentModel }}</span>
                <ChevronDown :size="14" />
              </button>
              <Transition name="dropdown-fade">
                <div v-if="showModelDropdown" class="model-dropdown">
                  <div class="dropdown-header">选择模型</div>
                  <div class="dropdown-list">
                    <button
                      v-for="opt in availableModelOptions"
                      :key="`${opt.providerId}-${opt.modelId}`"
                      :class="['dropdown-item', { active: currentProvider === opt.providerId && currentModel === opt.modelId }]"
                      @click="selectModel(opt.providerId, opt.modelId)"
                    >
                      <span class="provider-icon-mini" :style="{ background: opt.providerLogo.color }">
                        {{ opt.providerLogo.initials }}
                      </span>
                      <div class="dropdown-item-info">
                        <span class="dropdown-item-model">{{ opt.modelName }}</span>
                        <span class="dropdown-item-provider">{{ opt.providerName }}</span>
                      </div>
                    </button>
                    <div v-if="availableModelOptions.length === 0" class="dropdown-empty">
                      暂无可用模型，请先配置供应商
                    </div>
                  </div>
                </div>
              </Transition>
            </div>
            <button class="tool-btn" title="技能">
              <Link2 :size="16" />
              <span>技能</span>
              <ChevronDown :size="14" />
            </button>
          </div>
          <div class="toolbar-right">
            <button class="tool-btn icon-only" title="附件">
              <Paperclip :size="16" />
            </button>
            <button class="tool-btn icon-only" title="语音">
              <Mic :size="16" />
            </button>
            <button
              :class="['send-btn', { disabled: isStreaming || !inputText.trim() || !isBackendReady }]"
              title="发送"
              @click="sendMessage"
            >
              <Loader2 v-if="isStreaming" :size="17" class="spin-animation" />
              <Send v-else :size="17" />
            </button>
          </div>
        </div>
      </div>
      <div class="input-footer">
        <span>内容由AI生成，请仔细核对</span>
      </div>
    </div>

    <Transition name="selection-fade">
      <div v-if="showCreateAgentDialog" class="add-dialog-overlay" @click.self="showCreateAgentDialog = false">
        <div class="add-dialog">
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
            <button class="dialog-btn cancel" @click="showCreateAgentDialog = false">取消</button>
            <button
              :class="['dialog-btn confirm', { disabled: !newAgentForm.name.trim() }]"
              :disabled="!newAgentForm.name.trim()"
              @click="handleCreateAgent"
            >
              创建
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.workspace-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--workspace-bg);
  overflow: hidden;
}

.workspace-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  flex-shrink: 0;
  position: relative;
}

.workspace-header::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 24px;
  right: 24px;
  height: 1px;
  background: var(--divider-soft);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 500;
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
}

.header-stats {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
}

.provider-icon-mini {
  width: 18px;
  height: 18px;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 8px;
  font-weight: 700;
  color: white;
  flex-shrink: 0;
}

.header-right {
  display: flex;
  gap: 4px;
}

.header-icon-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.header-icon-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-secondary);
}

.header-icon-btn.warning {
  color: var(--lumi-accent);
  animation: pulse-warning 2s ease-in-out infinite;
}

@keyframes pulse-warning {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.backend-warning {
  margin: 8px 24px;
  padding: 12px 16px;
  border-radius: var(--radius-md);
  background: var(--lumi-accent-light);
  border: 1px solid rgba(244, 63, 94, 0.2);
  flex-shrink: 0;
}

.backend-warning.info {
  background: rgba(13, 148, 136, 0.08);
  border-color: rgba(13, 148, 136, 0.2);
}

.warning-content {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--lumi-accent);
}

.backend-warning.info .warning-content {
  color: var(--lumi-primary);
}

.warning-text {
  flex: 1;
}

.warning-title {
  font-size: 13px;
  font-weight: 600;
}

.warning-desc {
  font-size: 11px;
  opacity: 0.8;
  margin-top: 2px;
}

.retry-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 500;
  color: var(--lumi-accent);
  background: rgba(244, 63, 94, 0.1);
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.backend-warning.info .retry-btn {
  color: var(--lumi-primary);
  background: rgba(13, 148, 136, 0.1);
}

.retry-btn:hover {
  background: rgba(244, 63, 94, 0.2);
}

.backend-warning.info .retry-btn:hover {
  background: rgba(13, 148, 136, 0.2);
}

.agent-selector-row {
  padding: 16px 24px 0;
  position: relative;
  flex-shrink: 0;
}

.agent-cards-scroll {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 12px;
  scrollbar-width: none;
}

.agent-cards-scroll::-webkit-scrollbar {
  display: none;
}

.agent-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px 10px 10px;
  border-radius: var(--radius-lg);
  border: 1.5px solid transparent;
  background: var(--workspace-card);
  cursor: pointer;
  transition: all var(--transition-normal);
  flex-shrink: 0;
  animation: lumi-fade-in 0.4s ease-out both;
  box-shadow: var(--shadow-xs);
  position: relative;
}

.agent-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

.agent-card.selected {
  border-color: var(--lumi-primary);
  background: white;
  box-shadow: 0 4px 20px rgba(13, 148, 136, 0.12);
}

.card-avatar {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px solid transparent;
  transition: border-color var(--transition-fast);
}

.card-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  text-align: left;
}

.card-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.card-desc {
  font-size: 11px;
  color: var(--text-muted);
  max-width: 120px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-delete {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 20px;
  height: 20px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  opacity: 0;
  transition: all var(--transition-fast);
}

.agent-card:hover .card-delete {
  opacity: 1;
}

.card-delete:hover {
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
}

.selection-toast {
  margin-top: 10px;
  text-align: center;
  font-size: 13px;
  color: var(--lumi-accent);
  background: var(--lumi-accent-light);
  padding: 8px 20px;
  border-radius: var(--radius-full);
  display: inline-block;
  width: 100%;
}

.selection-fade-enter-active {
  animation: lumi-fade-in 0.3s ease-out;
}

.selection-fade-leave-active {
  animation: lumi-fade-in 0.2s ease-out reverse;
}

.main-content-area {
  flex: 1;
  display: flex;
  overflow: hidden;
  position: relative;
}

.chat-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  transition: all var(--transition-normal);
}

.messages-container {
  max-width: 800px;
  margin: 0 auto;
}

.message-row {
  margin-bottom: 20px;
  animation: lumi-slide-up 0.3s ease-out both;
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.message-avatar {
  flex-shrink: 0;
  margin-top: 4px;
}

.avatar-assistant {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.message-bubble {
  max-width: 85%;
  position: relative;
}

.message-content {
  font-size: 14px;
  line-height: 1.75;
  color: var(--text-primary);
  padding: 16px 20px;
  border-radius: var(--radius-lg);
  background: var(--workspace-card);
  box-shadow: var(--shadow-xs);
}

.message-content :deep(.bullet) {
  color: var(--lumi-primary);
  font-weight: 600;
}

.message-content :deep(code) {
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 13px;
  background: var(--workspace-panel);
  color: var(--lumi-primary);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}

.message-content :deep(strong) {
  font-weight: 600;
  color: var(--text-primary);
}

.message-row.assistant .message-bubble {
  border-top-left-radius: 4px;
}

.message-row.user {
  justify-content: flex-end;
}

.message-row.user .message-bubble {
  border-top-right-radius: 4px;
  background: linear-gradient(135deg, var(--lumi-primary), #14b8a6);
  color: white;
}

.message-row.user .message-content {
  color: white;
  background: transparent;
  box-shadow: none;
}

.streaming-cursor {
  display: inline-block;
  margin-left: 2px;
}

.cursor-blink {
  display: inline-block;
  width: 2px;
  height: 16px;
  background: var(--lumi-primary);
  animation: blink 1s step-end infinite;
  vertical-align: text-bottom;
}

@keyframes blink {
  50% { opacity: 0; }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}

.empty-icon {
  width: 80px;
  height: 80px;
  border-radius: var(--radius-xl);
  background: var(--lumi-primary-light);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--lumi-primary);
  margin-bottom: 20px;
}

.empty-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 6px;
}

.empty-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 24px;
}

.empty-quick-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: center;
}

.quick-action {
  padding: 8px 16px;
  border-radius: var(--radius-full);
  font-size: 13px;
  color: var(--text-secondary);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  transition: all var(--transition-fast);
  cursor: pointer;
}

.quick-action:hover {
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
}

.history-panel {
  width: 280px;
  flex-shrink: 0;
  border-left: 1px solid var(--workspace-border);
  background: var(--workspace-card);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid var(--workspace-border);
}

.history-header h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.history-header-actions {
  display: flex;
  gap: 4px;
}

.history-action-btn {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.history-action-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-secondary);
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  text-align: left;
  transition: all var(--transition-fast);
  position: relative;
}

.history-item:hover {
  background: var(--workspace-hover);
}

.history-item.active {
  background: var(--lumi-primary-light);
}

.history-item-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.history-item.active .history-item-icon {
  color: var(--lumi-primary);
}

.history-item-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.history-item-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-item-time {
  font-size: 11px;
  color: var(--text-muted);
}

.history-item-delete {
  width: 24px;
  height: 24px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  opacity: 0;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.history-item:hover .history-item-delete {
  opacity: 1;
}

.history-item-delete:hover {
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
}

.history-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  color: var(--text-muted);
  gap: 8px;
}

.history-empty p {
  font-size: 13px;
}

.history-slide-enter-active {
  animation: history-slide-in 0.3s ease-out;
}

.history-slide-leave-active {
  animation: history-slide-in 0.2s ease-out reverse;
}

@keyframes history-slide-in {
  from {
    opacity: 0;
    transform: translateX(20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.input-area {
  padding: 12px 24px 16px;
  flex-shrink: 0;
}

.input-wrapper {
  background: var(--workspace-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-sm), var(--shadow-inset);
  overflow: hidden;
  transition: all var(--transition-fast);
}

.input-wrapper:focus-within {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow), var(--shadow-lg);
}

.chat-input {
  width: 100%;
  padding: 14px 20px;
  font-size: 14px;
  resize: none;
  min-height: 48px;
  max-height: 120px;
  background: transparent;
  color: var(--text-primary);
  line-height: 1.5;
}

.chat-input::placeholder {
  color: var(--text-muted);
}

.chat-input:disabled {
  opacity: 0.6;
}

.input-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px 12px;
  position: relative;
}

.input-toolbar::before {
  content: '';
  position: absolute;
  top: 0;
  left: 16px;
  right: 16px;
  height: 1px;
  background: var(--divider-soft);
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 4px;
}

.tool-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
  white-space: nowrap;
}

.tool-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-secondary);
}

.tool-btn.icon-only {
  padding: 6px;
}

.model-btn-text {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.model-dropdown-container {
  position: relative;
}

.model-dropdown {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 0;
  width: 280px;
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  z-index: 50;
  overflow: hidden;
}

.dropdown-header {
  padding: 10px 14px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  border-bottom: 1px solid var(--workspace-border);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.dropdown-list {
  max-height: 240px;
  overflow-y: auto;
  padding: 4px;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 8px 10px;
  border-radius: var(--radius-md);
  text-align: left;
  transition: all var(--transition-fast);
}

.dropdown-item:hover {
  background: var(--workspace-hover);
}

.dropdown-item.active {
  background: var(--lumi-primary-light);
}

.dropdown-item-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.dropdown-item-model {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dropdown-item-provider {
  font-size: 11px;
  color: var(--text-muted);
}

.dropdown-item.active .dropdown-item-model {
  color: var(--lumi-primary);
}

.dropdown-empty {
  padding: 20px 14px;
  text-align: center;
  font-size: 12px;
  color: var(--text-muted);
}

.dropdown-fade-enter-active {
  animation: dropdown-in 0.2s ease-out;
}

.dropdown-fade-leave-active {
  animation: dropdown-in 0.15s ease-out reverse;
}

@keyframes dropdown-in {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.send-btn {
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  background: var(--lumi-primary);
  color: white;
  cursor: pointer;
  transition: all var(--transition-fast);
  margin-left: 4px;
}

.send-btn:hover {
  background: var(--lumi-primary-hover);
  transform: scale(1.05);
}

.send-btn:active {
  transform: scale(0.95);
}

.send-btn.disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.spin-animation {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.input-footer {
  text-align: center;
  margin-top: 8px;
}

.input-footer span {
  font-size: 11px;
  color: var(--text-muted);
}

.add-dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.add-dialog {
  background: var(--workspace-card);
  border-radius: var(--radius-xl);
  padding: 28px;
  width: 440px;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: var(--shadow-lg);
}

.add-dialog h3 {
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
</style>

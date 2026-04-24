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
  Plus,
  Copy,
  Check,
  Search,
  Zap,
  Server,
  PanelRightOpen,
  PanelRightClose,
  Square,
} from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import { useChatStore } from '../stores/chat'
import { useAgentStore } from '../stores/agent'
import { useModelStore } from '../stores/model'
import { useSkillStore } from '../stores/skill'
import { getProviderLogo } from '../config/provider-logos'
import { marked } from 'marked'

marked.setOptions({
  breaks: true,
  gfm: true,
})

const router = useRouter()
const chatStore = useChatStore()
const agentStore = useAgentStore()
const modelStore = useModelStore()
const skillStore = useSkillStore()

const inputText = ref('')
const messagesContainer = ref<HTMLElement | null>(null)
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const showModelDropdown = ref(false)
const showHistoryPanel = ref(true)
const showSkillDropdown = ref(false)
const showSearchPanel = ref(false)
const searchQuery = ref('')
const searchResults = ref<any[]>([])
const copiedId = ref<string | null>(null)

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
  const resolved = modelStore.resolveModel
  return resolved?.model || '未配置模型'
})

const currentProvider = computed(() => {
  const agent = agentStore.activeAgent
  if (agent?.provider) return agent.provider
  const resolved = modelStore.resolveModel
  return resolved?.provider || ''
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
  return chatStore.conversations
})

const activeSkills = computed(() => skillStore.skills.filter(s => s.isActive))

const selectAgent = async (agent: { id: string; name: string; desc: string; color: string }) => {
  if (agent.id === '__custom__') {
    showCreateAgentDialog.value = true
    return
  }
  const found = agentStore.agents.find(a => a.id === agent.id)
  if (found) {
    agentStore.setActiveAgent(found)
    // 不要清空消息，让watch监听器处理状态切换
    await chatStore.fetchConversations(found.id)
    // 如果有对话历史，加载最新的对话
    if (chatStore.conversations.length > 0) {
      const latestConv = chatStore.conversations[0]
      await chatStore.loadConversation(latestConv.id)
    }
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
  if (!inputText.value.trim()) return
  if (!isBackendReady.value) return

  const content = inputText.value
  inputText.value = ''
  resetTextareaHeight()

  const agent = agentStore.activeAgent
  const resolved = modelStore.resolveModel

  if (!chatStore.currentConversation) {
    await chatStore.createConversation(
      content.slice(0, 30),
      agent?.id,
      agent?.model || resolved?.model || undefined,
      agent?.provider || resolved?.provider || undefined,
    )
  }

  const options: any = {
    model: agent?.model || resolved?.model || undefined,
    provider: agent?.provider || resolved?.provider || undefined,
    temperature: modelStore.modelConfig.defaultTemperature,
    maxTokens: modelStore.modelConfig.defaultMaxTokens,
    topP: modelStore.modelConfig.defaultTopP,
  }
  if (agent?.systemPrompt) options.systemPrompt = agent.systemPrompt
  if (agent?.id) options.agentId = agent.id

  await chatStore.sendMessage(content, options)
  await nextTick()
  scrollToBottom()
}

const cancelStreaming = () => {
  chatStore.cancelCurrentRequest()
}

const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTo({ top: messagesContainer.value.scrollHeight, behavior: 'smooth' })
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

const renderMarkdown = (text: string): string => {
  if (!text) return ''
  return marked.parse(text) as string
}

const contextUsage = computed(() => {
  // 修复：倒序渲染问题 - 改用正序查找最后一条完成的助手消息
  const lastAssistantMsg = messages.value.findLast(m => m.role === 'assistant' && m.done)
  return lastAssistantMsg?.usage || chatStore.lastUsage || null
})

const contextPercent = computed(() => {
  if (!contextUsage.value?.totalTokens || !modelStore.modelConfig.defaultMaxTokens) return 0
  return Math.min(100, Math.round((contextUsage.value.totalTokens / modelStore.modelConfig.defaultMaxTokens) * 100))
})

const copyMessage = async (msgId: string, content: string) => {
  try {
    await navigator.clipboard.writeText(content)
    copiedId.value = msgId
    setTimeout(() => { copiedId.value = null }, 2000)
  } catch {}
}

const formatTime = (dateStr: string) => {
  // 修复：历史记录实时更新 - 处理Invalid Date问题
  if (!dateStr || dateStr === 'undefined' || dateStr === 'null') {
    return '刚刚'
  }
  
  try {
    const d = new Date(dateStr)
    if (isNaN(d.getTime())) {
      return '刚刚'
    }
    
    const now = new Date()
    const isToday = d.toDateString() === now.toDateString()
    
    if (isToday) {
      return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
    }
    return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch (error) {
    return '刚刚'
  }
}

const handleLoadConversation = async (convId: string) => {
  await chatStore.loadConversation(convId)
  await nextTick()
  scrollToBottom()
}

const handleDeleteConversation = async (convId: string) => {
  await chatStore.deleteConversation(convId, agentStore.activeAgent?.id)
}

const startNewConversation = () => {
  chatStore.clearMessages()
}

const handleSearch = async () => {
  if (!searchQuery.value.trim()) return
  try {
    searchResults.value = await skillStore.executeSkill('search', { query: searchQuery.value })
  } catch {
    searchResults.value = []
  }
}

const insertSkillToInput = (skillName: string) => {
  inputText.value += `<tool_call name="${skillName}">\n{}\n</tool_call`
  showSkillDropdown.value = false
  if (textareaRef.value) textareaRef.value.focus()
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
  if (!target.closest('.skill-dropdown-container')) {
    showSkillDropdown.value = false
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
      skillStore.fetchSkills(),
      skillStore.fetchMcpServers(),
    ])
  }
  document.addEventListener('click', handleClickOutsideModel)
})
</script>

<template>
  <div class="workspace-layout">
    <div class="workspace-main">
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
            <button class="header-icon-btn" :class="{ active: showSearchPanel }" title="搜索知识库" @click="showSearchPanel = !showSearchPanel">
              <Search :size="18" />
            </button>
            <button class="header-icon-btn" :class="{ active: showHistoryPanel }" title="历史记录" @click="showHistoryPanel = !showHistoryPanel">
              <PanelRightOpen v-if="!showHistoryPanel" :size="18" />
              <PanelRightClose v-else :size="18" />
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

        <div class="chat-area">
          <div ref="messagesContainer" class="messages-scroll">
            <div class="messages-container">
              <TransitionGroup name="msg-appear" tag="div">
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
                  <div class="message-body">
                    <div class="message-sender" v-if="msg.role === 'assistant'">{{ agentStore.activeAgent?.name || 'LuomiNest' }}</div>
                    <div v-if="msg.role === 'assistant'" class="message-content markdown-body" v-html="renderMarkdown(msg.content)"></div>
                    <div v-else class="message-content user-message">{{ msg.content }}</div>
                    <div v-if="msg.role === 'assistant' && !msg.done && isStreaming && msg.id === messages[messages.length - 1].id" class="loading-status">
                      <Loader2 :size="16" class="spin-animation" />
                      <span>正在分析问题...</span>
                    </div>
                    <div v-if="msg.role === 'assistant' && msg.done" class="message-actions">
                      <button class="msg-action-btn" title="复制" @click="copyMessage(msg.id, msg.content)">
                        <Check v-if="copiedId === msg.id" :size="13" />
                        <Copy v-else :size="13" />
                        <span>{{ copiedId === msg.id ? '已复制' : '复制' }}</span>
                      </button>
                    </div>
                  </div>
                </div>
              </TransitionGroup>

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
        </div>

        <div class="input-area">
          <div class="input-wrapper">
            <textarea
              ref="textareaRef"
              v-model="inputText"
              placeholder="可以描述任务或提问任何问题"
              rows="1"
              class="chat-input"
              :disabled="!isBackendReady"
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
                <div class="skill-dropdown-container">
                  <button class="tool-btn" title="技能与工具" @click.stop="showSkillDropdown = !showSkillDropdown">
                    <Zap :size="16" />
                    <span>技能</span>
                    <ChevronDown :size="14" />
                  </button>
                  <Transition name="dropdown-fade">
                    <div v-if="showSkillDropdown" class="skill-dropdown">
                      <div class="dropdown-header">
                        <Zap :size="14" />
                        可用技能
                      </div>
                      <div class="dropdown-list">
                        <button
                          v-for="skill in activeSkills"
                          :key="skill.name"
                          class="dropdown-item"
                          @click="insertSkillToInput(skill.name)"
                        >
                          <div class="skill-icon-badge" :class="skill.category">
                            <Zap v-if="skill.category === 'utility'" :size="14" />
                            <Search v-else-if="skill.category === 'knowledge'" :size="14" />
                            <Bot v-else-if="skill.category === 'agent'" :size="14" />
                            <Link2 v-else :size="14" />
                          </div>
                          <div class="dropdown-item-info">
                            <span class="dropdown-item-model">{{ skill.name }}</span>
                            <span class="dropdown-item-provider">{{ skill.description }}</span>
                          </div>
                          <span v-if="skill.isBuiltin" class="skill-badge builtin">内置</span>
                          <span v-else class="skill-badge custom">自定义</span>
                        </button>
                        <div v-if="skillStore.mcpServers.length > 0" class="dropdown-section">
                          <div class="dropdown-section-title">
                            <Server :size="12" />
                            MCP 服务器
                          </div>
                          <div
                            v-for="server in skillStore.mcpServers"
                            :key="server.name"
                            class="dropdown-item mcp-server-item"
                          >
                            <Server :size="14" class="mcp-icon" />
                            <div class="dropdown-item-info">
                              <span class="dropdown-item-model">{{ server.name }}</span>
                              <span class="dropdown-item-provider">{{ server.transport }}</span>
                            </div>
                            <span class="skill-badge mcp">MCP</span>
                          </div>
                        </div>
                        <div v-if="activeSkills.length === 0 && skillStore.mcpServers.length === 0" class="dropdown-empty">
                          暂无可用技能
                        </div>
                      </div>
                    </div>
                  </Transition>
                </div>
              </div>
              <div class="toolbar-right">
                <button class="tool-btn icon-only" title="附件">
                  <Paperclip :size="16" />
                </button>
                <button class="tool-btn icon-only" title="语音">
                  <Mic :size="16" />
                </button>
                <button
                  v-if="isStreaming"
                  class="send-btn stop"
                  title="停止生成"
                  @click="cancelStreaming"
                >
                  <Square :size="16" />
                </button>
                <button
                  v-else
                  :class="['send-btn', { disabled: !inputText.trim() || !isBackendReady }]"
                  title="发送"
                  @click="sendMessage"
                >
                  <Send :size="17" />
                </button>
              </div>
            </div>
          </div>
          <div class="input-footer">
            <div v-if="contextUsage" class="context-usage">
              <div class="context-bar">
                <div class="context-bar-fill" :style="{ width: contextPercent + '%' }" :class="{ warn: contextPercent > 70, danger: contextPercent > 90 }"></div>
              </div>
              <span class="context-text">{{ contextUsage.totalTokens?.toLocaleString() || 0 }} tokens · {{ contextPercent }}%</span>
            </div>
            <span v-else>内容由AI生成，请仔细核对</span>
          </div>
        </div>
      </div>
    </div>

    <Transition name="panel-slide">
      <div v-if="showHistoryPanel" class="right-panel">
        <div class="panel-tabs">
          <button
            :class="['panel-tab', { active: !showSearchPanel }]"
            @click="showSearchPanel = false"
          >
            <Clock :size="14" />
            历史
          </button>
          <button
            :class="['panel-tab', { active: showSearchPanel }]"
            @click="showSearchPanel = true"
          >
            <Search :size="14" />
            搜索
          </button>
        </div>

        <div v-if="!showSearchPanel" class="panel-content">
          <div class="panel-header-bar">
            <div class="panel-header-info">
              <span v-if="agentStore.activeAgent" class="panel-agent-tag" :style="{ background: agentStore.activeAgent.color + '14', color: agentStore.activeAgent.color }">
                {{ agentStore.activeAgent.name }}
              </span>
              <span class="panel-count">{{ agentConversations.length }} 个对话</span>
            </div>
            <button class="panel-action-btn" title="新建对话" @click="startNewConversation">
              <Plus :size="16" />
            </button>
          </div>
          <div class="history-list">
            <div
              v-for="conv in agentConversations"
              :key="conv.id"
              :class="['history-item', { active: chatStore.currentConversation?.id === conv.id }]"
              @click="handleLoadConversation(conv.id)"
            >
              <MessageSquare :size="14" class="history-item-icon" />
              <div class="history-item-info">
                <span class="history-item-title">{{ conv.title }}</span>
                <span class="history-item-meta">
                  <span class="history-item-time">{{ formatTime(conv.updatedAt) }}</span>
                  <span v-if="conv.lastMessage" class="history-item-preview">{{ conv.lastMessage }}</span>
                </span>
              </div>
              <button class="history-item-delete" title="删除" @click.stop="handleDeleteConversation(conv.id)">
                <Trash2 :size="12" />
              </button>
            </div>
            <div v-if="agentConversations.length === 0" class="history-empty">
              <Clock :size="24" />
              <p>暂无对话记录</p>
            </div>
          </div>
        </div>

        <div v-else class="panel-content">
          <div class="search-box">
            <Search :size="16" class="search-icon" />
            <input
              v-model="searchQuery"
              type="text"
              placeholder="搜索知识库..."
              class="search-input"
              @keydown.enter="handleSearch"
            />
          </div>
          <div class="search-results">
            <div v-for="(result, idx) in searchResults" :key="idx" class="search-result-item">
              <div class="search-result-source">{{ result.source }}</div>
              <div class="search-result-content">{{ result.content }}</div>
              <div class="search-result-score">相关度: {{ (result.score * 100).toFixed(1) }}%</div>
            </div>
            <div v-if="searchResults.length === 0 && searchQuery" class="history-empty">
              <Search :size="24" />
              <p>输入关键词搜索知识库</p>
            </div>
          </div>
        </div>
      </div>
    </Transition>

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
.workspace-layout {
  display: flex;
  height: 100%;
  overflow: hidden;
  background: var(--workspace-bg);
}

.workspace-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.workspace-view {
  display: flex;
  flex-direction: column;
  height: 100%;
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

.header-icon-btn.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
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
  flex-shrink: 0;
  position: relative;
  overflow: hidden;
}

.backend-warning::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--lumi-accent);
  border-radius: 0 3px 3px 0;
}

.backend-warning.info {
  background: rgba(13, 148, 136, 0.06);
}

.backend-warning.info::before {
  background: var(--lumi-primary);
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
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
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

.chat-area {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.messages-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  scroll-behavior: smooth;
}

.messages-container {
  max-width: 800px;
  margin: 0 auto;
}

.message-row {
  margin-bottom: 24px;
  animation: msg-slide-in 0.35s cubic-bezier(0.22, 1, 0.36, 1) both;
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

@keyframes msg-slide-in {
  from { opacity: 0; transform: translateY(14px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.message-avatar {
  flex-shrink: 0;
  margin-top: 2px;
}

.avatar-assistant {
  width: 30px;
  height: 30px;
  border-radius: var(--radius-sm);
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 250ms ease-in-out;
}

.message-row:hover .avatar-assistant {
  transform: scale(1.08);
}

.message-body {
  max-width: 85%;
  min-width: 0;
  position: relative;
}

.message-sender {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.message-content {
  font-size: 14px;
  line-height: 1.75;
  color: var(--text-primary);
}

.message-row.user {
  justify-content: flex-end;
}

.message-row.user .message-body {
  max-width: 70%;
}

.user-message {
  padding: 12px 18px;
  border-radius: var(--radius-lg);
  border-top-right-radius: 4px;
  background: linear-gradient(135deg, rgba(13, 148, 136, 0.08), rgba(13, 148, 136, 0.04));
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  transition: all 250ms ease-in-out;
}

.message-row:hover .user-message {
  background: linear-gradient(135deg, rgba(13, 148, 136, 0.12), rgba(13, 148, 136, 0.06));
}

.message-actions {
  display: flex;
  gap: 4px;
  margin-top: 6px;
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.message-row:hover .message-actions {
  opacity: 1;
}

.msg-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.msg-action-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-secondary);
}

.streaming-cursor {
  display: inline-block;
  margin-left: 2px;
}

.loading-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  color: var(--text-muted);
  font-size: 13px;
}

.loading-status .spin-animation {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
  animation: lumi-fade-in 0.5s ease-out both;
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
  transition: transform 300ms ease-in-out;
}

.empty-icon:hover {
  transform: scale(1.05) rotate(-3deg);
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
  box-shadow: var(--shadow-xs);
  transition: all 300ms ease-in-out;
  cursor: pointer;
}

.quick-action:hover {
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.right-panel {
  width: 300px;
  flex-shrink: 0;
  background: var(--workspace-card);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-left: 1px solid var(--divider-vertical);
}

.panel-tabs {
  display: flex;
  border-bottom: 1px solid var(--divider-soft);
  flex-shrink: 0;
}

.panel-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 12px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted);
  transition: all var(--transition-fast);
  position: relative;
}

.panel-tab:hover {
  color: var(--text-secondary);
  background: var(--workspace-hover);
}

.panel-tab.active {
  color: var(--lumi-primary);
}

.panel-tab.active::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 20%;
  right: 20%;
  height: 2px;
  background: var(--lumi-primary);
  border-radius: 2px 2px 0 0;
}

.panel-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  flex-shrink: 0;
}

.panel-header-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.panel-agent-tag {
  padding: 2px 8px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: 500;
}

.panel-count {
  font-size: 11px;
  color: var(--text-muted);
}

.panel-action-btn {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.panel-action-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-secondary);
}

.history-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 8px;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  text-align: left;
  transition: all 300ms ease-in-out;
  position: relative;
  cursor: pointer;
}

.history-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%) scaleY(0);
  width: 3px;
  height: 60%;
  border-radius: 0 3px 3px 0;
  background: var(--lumi-primary);
  transition: transform 300ms ease-in-out;
}

.history-item:hover {
  background: var(--workspace-hover);
}

.history-item:hover::before {
  transform: translateY(-50%) scaleY(1);
}

.history-item.active {
  background: var(--lumi-primary-light);
}

.history-item.active::before {
  transform: translateY(-50%) scaleY(1);
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

.history-item-meta {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.history-item-time {
  font-size: 11px;
  color: var(--text-muted);
}

.history-item-preview {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  opacity: 0.7;
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

.panel-slide-enter-active {
  animation: panel-slide-in 0.3s ease-out;
}

.panel-slide-leave-active {
  animation: panel-slide-in 0.2s ease-out reverse;
}

@keyframes panel-slide-in {
  from {
    opacity: 0;
    transform: translateX(20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  flex-shrink: 0;
  border-bottom: 1px solid var(--divider-soft);
}

.search-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.search-input {
  flex: 1;
  background: var(--workspace-panel);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  font-size: 13px;
  color: var(--text-primary);
}

.search-input::placeholder {
  color: var(--text-muted);
}

.search-results {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.search-result-item {
  padding: 12px;
  border-radius: var(--radius-md);
  background: var(--workspace-panel);
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 300ms ease-in-out;
}

.search-result-item:hover {
  background: var(--workspace-hover);
}

.search-result-source {
  font-size: 11px;
  color: var(--lumi-primary);
  font-weight: 500;
  margin-bottom: 4px;
}

.search-result-content {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.search-result-score {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 4px;
}

.input-area {
  padding: 12px 24px 16px;
  flex-shrink: 0;
  position: relative;
  z-index: 100;
}

.input-wrapper {
  background: var(--workspace-card);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-sm), var(--shadow-inset);
  overflow: visible;
  transition: all 300ms ease-in-out;
}

.input-wrapper:focus-within {
  box-shadow: 0 0 0 2px var(--lumi-primary-glow), var(--shadow-lg);
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
  transition: all 300ms ease-in-out;
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

.model-dropdown-container,
.skill-dropdown-container {
  position: relative;
}

.model-dropdown,
.skill-dropdown {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 0;
  width: 280px;
  background: var(--workspace-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  z-index: 9999;
  overflow: hidden;
}

.dropdown-header {
  padding: 10px 14px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  position: relative;
  display: flex;
  align-items: center;
  gap: 6px;
}

.dropdown-header::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 14px;
  right: 14px;
  height: 1px;
  background: var(--divider-soft);
}

.dropdown-list {
  max-height: 280px;
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
  transition: all 300ms ease-in-out;
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
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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

.dropdown-section {
  padding: 4px 0;
}

.dropdown-section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px 4px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
}

.skill-icon-badge {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.skill-icon-badge.knowledge {
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
}

.skill-icon-badge.utility {
  background: rgba(245, 158, 11, 0.1);
  color: #f59e0b;
}

.skill-icon-badge.agent {
  background: rgba(139, 92, 246, 0.1);
  color: #8b5cf6;
}

.skill-icon-badge.general {
  background: rgba(13, 148, 136, 0.1);
  color: var(--lumi-primary);
}

.skill-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: var(--radius-full);
  font-weight: 500;
  flex-shrink: 0;
}

.skill-badge.builtin {
  background: rgba(13, 148, 136, 0.1);
  color: var(--lumi-primary);
}

.skill-badge.custom {
  background: rgba(245, 158, 11, 0.1);
  color: #f59e0b;
}

.skill-badge.mcp {
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
}

.mcp-icon {
  color: #3b82f6;
}

.mcp-server-item {
  cursor: default;
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
  transition: all 300ms ease-in-out;
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

.send-btn.stop {
  background: var(--lumi-danger, #ef4444);
}

.send-btn.stop:hover {
  background: var(--lumi-danger-hover, #dc2626);
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
  backdrop-filter: blur(4px);
}

.add-dialog {
  background: var(--workspace-card);
  border-radius: var(--radius-xl);
  padding: 28px;
  width: 440px;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: var(--shadow-xl);
  animation: dialog-enter 0.3s cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes dialog-enter {
  from { opacity: 0; transform: scale(0.95) translateY(10px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
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
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-primary);
  transition: all 300ms ease-in-out;
}

.form-input:focus {
  box-shadow: 0 0 0 2px var(--lumi-primary-glow);
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
  transition: all 300ms ease-in-out;
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
  transition: all 300ms ease-in-out;
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

.markdown-body {
  word-break: break-word;
}

.markdown-body :deep(p) {
  margin: 0 0 12px;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4),
.markdown-body :deep(h5),
.markdown-body :deep(h6) {
  font-weight: 700;
  color: var(--text-primary);
  margin: 20px 0 10px;
  line-height: 1.4;
}

.markdown-body :deep(h1) { font-size: 22px; }
.markdown-body :deep(h2) { font-size: 18px; border-bottom: 1px solid var(--border-light); padding-bottom: 6px; }
.markdown-body :deep(h3) { font-size: 16px; }
.markdown-body :deep(h4) { font-size: 15px; }

.markdown-body :deep(h1:first-child),
.markdown-body :deep(h2:first-child),
.markdown-body :deep(h3:first-child) {
  margin-top: 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 8px 0;
  padding-left: 24px;
}

.markdown-body :deep(li) {
  margin: 4px 0;
  line-height: 1.7;
}

.markdown-body :deep(li::marker) {
  color: var(--lumi-primary);
}

.markdown-body :deep(blockquote) {
  margin: 12px 0;
  padding: 8px 16px;
  border-left: 3px solid var(--lumi-primary);
  background: var(--lumi-primary-light);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  color: var(--text-secondary);
}

.markdown-body :deep(blockquote p) {
  margin: 0;
}

.markdown-body :deep(code) {
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
  background: var(--workspace-panel);
  color: var(--lumi-primary);
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
}

.markdown-body :deep(pre) {
  margin: 12px 0;
  padding: 16px;
  border-radius: var(--radius-md);
  background: #1c1917;
  overflow-x: auto;
  position: relative;
}

.markdown-body :deep(pre code) {
  padding: 0;
  background: none;
  color: #e7e5e4;
  font-size: 13px;
  line-height: 1.6;
}

.markdown-body :deep(table) {
  width: 100%;
  margin: 12px 0;
  border-collapse: collapse;
  font-size: 13px;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  padding: 8px 12px;
  border: 1px solid var(--workspace-border);
  text-align: left;
}

.markdown-body :deep(th) {
  background: var(--workspace-panel);
  font-weight: 600;
}

.markdown-body :deep(tr:nth-child(even)) {
  background: var(--lumi-primary-light);
}

.markdown-body :deep(hr) {
  margin: 16px 0;
  border: none;
  height: 1px;
  background: var(--workspace-border);
}

.markdown-body :deep(a) {
  color: var(--lumi-primary);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.markdown-body :deep(a:hover) {
  color: var(--lumi-primary-hover);
}

.markdown-body :deep(img) {
  max-width: 100%;
  border-radius: var(--radius-md);
  margin: 8px 0;
}

.markdown-body :deep(strong) {
  font-weight: 700;
  color: var(--text-primary);
}

.markdown-body :deep(em) {
  font-style: italic;
  color: var(--text-secondary);
}

.context-usage {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-content: center;
}

.context-bar {
  width: 120px;
  height: 4px;
  border-radius: 2px;
  background: var(--workspace-panel);
  overflow: hidden;
}

.context-bar-fill {
  height: 100%;
  border-radius: 2px;
  background: var(--lumi-primary);
  transition: width 0.4s ease-in-out, background 0.3s ease-in-out;
}

.context-bar-fill.warn {
  background: var(--lumi-warning);
}

.context-bar-fill.danger {
  background: var(--lumi-accent);
}

.context-text {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
}

.msg-appear-enter-active {
  transition: all 0.4s cubic-bezier(0.22, 1, 0.36, 1);
}

.msg-appear-enter-from {
  opacity: 0;
  transform: translateY(16px) scale(0.97);
}
</style>

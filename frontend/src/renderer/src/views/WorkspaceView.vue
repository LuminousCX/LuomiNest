<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick, watch, computed } from 'vue'
import {
  Send,
  Paperclip,
  Mic,
  Wand2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Bot,
  Loader2,
  AlertTriangle,
  RotateCcw,
  Undo2,
  Copy,
  Check,
  Square,
  UploadCloud,
  FileText,
  Image,
  File,
  Download,
  Trash2,
  Quote,
  X,
  Volume2,
  Users,
  User,
  MessageCircle,
  Plus,
  Search,
  MoreVertical,
  Hash,
  ImagePlus,
  UserPlus,
  Zap,
  CheckCircle2,
  AlertCircle,
  Clock,
  Play,
  Layers,
  MessageSquare,
  SquareCheck,
  Pencil,
} from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import { useChatStore } from '../stores/chat'
import { useAgentStore } from '../stores/agent'
import { useModelStore } from '../stores/model'
import { useSocialStore } from '../stores/social'
import { useChatTrashStore } from '../stores/chat-trash'

import { useTTS } from '../composables/useTTS'
import FileUpload from '../components/FileUpload.vue'
import FilePreview from '../components/FilePreview.vue'
import SuggestedQuestions from '../components/SuggestedQuestions.vue'
import { useFileUpload } from '../composables/useFileUpload'
import { useApi } from '../composables/useApi'
import { getProviderLogo } from '../config/provider-logos'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import type { ConversationListItem, ConversationSearchResult, GroupInfo, CollaborationPhase, AgentProfile } from '../types'

marked.setOptions({
  breaks: true,
  gfm: true,
})

const router = useRouter()
const chatStore = useChatStore()
const agentStore = useAgentStore()
const modelStore = useModelStore()
const socialStore = useSocialStore()
const chatTrashStore = useChatTrashStore()
const { isSpeaking: isTTSSpeaking, speakingMessageId: ttsSpeakingMsgId, speak: ttsSpeak, stopSpeaking: ttsStopSpeaking } = useTTS()

const { isUploading, uploadingFile, parsedContent, fileType, fileName, uploadAndForward, clearUploadState } = useFileUpload()
const { truncateMessages, deleteMessage } = useApi()
const fileUploadRef = ref<InstanceType<typeof FileUpload> | null>(null)

const inputText = ref('')
const messagesContainer = ref<HTMLElement | null>(null)
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const showModelDropdown = ref(false)
const copiedId = ref<string | null>(null)
const showReasoning = ref<Record<string, boolean>>({})
const reasoningRefs = ref<Record<string, HTMLElement>>({})
const reasoningScrollRefs = ref<any>(null)
const isNearBottom = ref(true)
const SCROLL_BOTTOM_THRESHOLD = 120
const showScrollToBottomBtn = ref(false)
const isLoadingCurrentConv = computed(() => chatStore.isLoadingCurrentConversation)
let resizeObserver: ResizeObserver | null = null

const showGlobalDropOverlay = ref(false)
let globalDragCounter = 0
let dragLeaveTimer: ReturnType<typeof setTimeout> | null = null

const showFilePreview = ref(false)
const previewFile = ref<{ name: string; type?: string; content?: string } | null>(null)

const showCreateDialog = ref(false)
const newAgentForm = ref({
  name: '',
  description: '',
  systemPrompt: '',
  color: '#147EBC',
})
const createDialogError = ref('')
const agentColors = ['#147EBC', '#6366f1', '#f59e0b', '#f43f5e', '#8b5cf6', '#06b6d4', '#84cc16', '#ec4899']

// 确认对话框状态
const showConfirmDialog = ref(false)
const confirmDialogMessage = ref('')
const confirmDialogCallback = ref<(() => void) | null>(null)
const confirmDialogIsDanger = ref(false)

const openConfirmDialog = (message: string, callback: () => void, isDanger = false) => {
  confirmDialogMessage.value = message
  confirmDialogCallback.value = callback
  confirmDialogIsDanger.value = isDanger
  showConfirmDialog.value = true
}

const handleConfirmDialogConfirm = () => {
  if (confirmDialogCallback.value) {
    confirmDialogCallback.value()
  }
  showConfirmDialog.value = false
  confirmDialogCallback.value = null
}

const handleConfirmDialogCancel = () => {
  showConfirmDialog.value = false
  confirmDialogCallback.value = null
}

const handleCreateAgent = async () => {
  if (!newAgentForm.value.name.trim()) return
  createDialogError.value = ''
  try {
    await agentStore.createAgent({
      name: newAgentForm.value.name.trim(),
      description: newAgentForm.value.description.trim(),
      systemPrompt: newAgentForm.value.systemPrompt.trim(),
      color: newAgentForm.value.color,
    })
    showCreateDialog.value = false
    newAgentForm.value = { name: '', description: '', systemPrompt: '', color: '#147EBC' }
  } catch (e: any) {
    createDialogError.value = e.response?.data?.detail || e.message || '创建 Agent 失败'
  }
}

// 编辑 Agent
const showEditDialog = ref(false)
const editingAgentId = ref<string | null>(null)
const editAgentForm = ref({
  name: '',
  description: '',
  systemPrompt: '',
  color: '#147EBC',
})

const openEditDialog = (agent: any, e?: Event) => {
  if (e) e.stopPropagation()
  editingAgentId.value = agent.id
  editAgentForm.value = {
    name: agent.name || '',
    description: agent.description || '',
    systemPrompt: agent.systemPrompt || '',
    color: agent.color || '#147EBC',
  }
  showEditDialog.value = true
}

const handleUpdateAgent = async () => {
  if (!editingAgentId.value || !editAgentForm.value.name.trim()) return
  try {
    await agentStore.updateAgent(editingAgentId.value, {
      name: editAgentForm.value.name.trim(),
      description: editAgentForm.value.description.trim(),
      systemPrompt: editAgentForm.value.systemPrompt.trim(),
      color: editAgentForm.value.color,
    })
    showEditDialog.value = false
    editingAgentId.value = null
  } catch (e: any) {
    displayToast(e?.message || '更新 Agent 失败')
  }
}

const handleDeleteAgent = async () => {
  if (!editingAgentId.value) return
  const deletedId = editingAgentId.value
  try {
    await agentStore.deleteAgent(deletedId)
    showEditDialog.value = false
    editingAgentId.value = null
    if (localSelectedAgent.value?.id === deletedId) {
      selectedType.value = null
      localSelectedAgent.value = null
      localSelectedConvId.value = null
    }
  } catch (e: any) {
    displayToast(e?.message || '删除 Agent 失败')
  }
}

const toastMessage = ref('')
const showToast = ref(false)
let toastTimer: ReturnType<typeof setTimeout> | null = null

const displayToast = (msg: string) => {
  if (toastTimer) clearTimeout(toastTimer)
  toastMessage.value = msg
  showToast.value = true
  toastTimer = setTimeout(() => {
    showToast.value = false
    toastTimer = null
  }, 3000)
}

// ===== 联系人面板状态 =====
type ContactType = 'agent' | 'group'
const selectedType = ref<ContactType | null>(null)
const contactSearchQuery = ref('')

// ===== 本地状态隔离：WorkspaceView 不依赖 agentStore.activeAgent =====
// 工作台主 Agent 和聊天页面联系人完全分开，互不影响
const localSelectedAgent = ref<AgentProfile | null>(null)
const localSelectedConvId = ref<string | null>(null)

const filteredAgents = computed(() => {
  if (!contactSearchQuery.value) return agentStore.agents
  const q = contactSearchQuery.value.toLowerCase()
  return agentStore.agents.filter(a => a.name.toLowerCase().includes(q) || (a.description || '').toLowerCase().includes(q))
})

const filteredGroups = computed(() => {
  if (!contactSearchQuery.value) return socialStore.groups
  const q = contactSearchQuery.value.toLowerCase()
  return socialStore.groups.filter(g => g.name.toLowerCase().includes(q))
})

const selectAgent = async (agent: AgentProfile) => {
  localSelectedAgent.value = agent
  selectedType.value = 'agent'
  selectedGroupId.value = null
  localSelectedConvId.value = null
  await chatStore.fetchConversations(agent.id)
  chatTrashStore.fetchTrash(agent.id)
}

const selectGroup = (group: GroupInfo) => {
  selectedType.value = 'group'
  selectedGroupId.value = group.id
  socialStore.currentGroup = group
  socialStore.fetchGroupMessages(group.id)
}

// 返回联系人列表：清空选中状态
const backToContacts = () => {
  selectedType.value = null
  localSelectedAgent.value = null
  localSelectedConvId.value = null
  selectedGroupId.value = null
  batchMode.value = false
  selectedIds.value = new Set()
}

// ===== 群聊状态 =====
const selectedGroupId = ref<string | null>(null)
const groupChatInput = ref('')
const sendingGroupMessage = ref(false)
const collaborationMode = ref(false)
const groupMessagesContainer = ref<HTMLElement | null>(null)
const showAddAgentDialog = ref(false)
const showCreateGroupDialog = ref(false)
const addAgentRole = ref('')
const addAgentId = ref('')
const newGroupName = ref('')
const newGroupDesc = ref('')

const selectedGroup = computed(() => {
  if (!selectedGroupId.value) return null
  return socialStore.groups.find(g => g.id === selectedGroupId.value) || null
})

const groupMessages = computed(() => socialStore.groupMessages)

const availableAgentsForGroup = computed(() => {
  if (!selectedGroup.value) return agentStore.agents
  const memberIds = selectedGroup.value.members.map(m => m.agent_id)
  return agentStore.agents.filter(a => !memberIds.includes(a.id))
})

const collaborationPhase = computed(() => socialStore.collaborationPhase)
const collaborationActive = computed(() => socialStore.collaborationActive)
const collaborationTasks = computed(() => socialStore.collaborationTasks)
const agentsResponding = computed(() => socialStore.agentsResponding)
const respondingAgentNames = computed(() => socialStore.respondingAgentNames)

const phaseLabel = computed(() => {
  const labels: Record<CollaborationPhase, string> = {
    analyzing: '分析中',
    dispatching: '分配任务',
    executing: '执行中',
    synthesizing: '综合结果',
    completed: '已完成',
    failed: '失败',
  }
  return collaborationPhase.value ? labels[collaborationPhase.value] : ''
})

const phaseIcon = computed(() => {
  const icons: Record<CollaborationPhase, typeof Loader2> = {
    analyzing: Loader2,
    dispatching: Layers,
    executing: Play,
    synthesizing: Layers,
    completed: CheckCircle2,
    failed: AlertCircle,
  }
  return collaborationPhase.value ? icons[collaborationPhase.value] : null
})

const sendGroupMessage = async () => {
  if (!groupChatInput.value.trim() || !selectedGroupId.value) return
  sendingGroupMessage.value = true
  const userContent = groupChatInput.value
  groupChatInput.value = ''

  try {
    if (collaborationMode.value) {
      socialStore.groupMessages.push({
        id: `user-${Date.now()}`,
        groupId: selectedGroupId.value,
        senderId: 'user',
        senderType: 'user',
        content: userContent,
        timestamp: new Date().toISOString(),
      })

      await socialStore.collaborateStream(
        selectedGroupId.value,
        userContent,
        () => {},
        (err) => { console.error('Collaboration error:', err) },
        () => {},
      )
    } else {
      await socialStore.sendGroupMessage(selectedGroupId.value, userContent)
    }
    await nextTick()
    if (groupMessagesContainer.value) {
      groupMessagesContainer.value.scrollTo({ top: groupMessagesContainer.value.scrollHeight, behavior: 'smooth' })
    }
  } catch (e) {
    console.error('Failed to send message:', e)
  } finally {
    sendingGroupMessage.value = false
  }
}

const createGroup = async () => {
  if (!newGroupName.value.trim()) return
  try {
    const group = await socialStore.createGroup(newGroupName.value.trim(), newGroupDesc.value.trim())
    newGroupName.value = ''
    newGroupDesc.value = ''
    showCreateGroupDialog.value = false
    if (group) {
      selectGroup(group)
    }
  } catch (e) {
    console.error('Failed to create group:', e)
  }
}

const deleteGroup = async (groupId: string) => {
  try {
    await socialStore.deleteGroup(groupId)
    if (selectedGroupId.value === groupId) {
      selectedGroupId.value = null
      selectedType.value = null
    }
  } catch (e) {
    console.error('Failed to delete group:', e)
  }
}

const addAgentToGroup = async () => {
  if (!addAgentId.value || !selectedGroupId.value) return
  try {
    await socialStore.addAgentToGroup(selectedGroupId.value, addAgentId.value, addAgentRole.value || '成员')
    addAgentId.value = ''
    addAgentRole.value = ''
    showAddAgentDialog.value = false
  } catch (e) {
    console.error('Failed to add agent:', e)
  }
}

const removeAgentFromGroup = async (groupId: string, agentId: string) => {
  try {
    await socialStore.removeAgentFromGroup(groupId, agentId)
  } catch (e) {
    console.error('Failed to remove agent:', e)
  }
}

const formatGroupTime = (dateStr: string) => {
  try {
    const d = new Date(dateStr)
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

const getTaskStatusIcon = (status: string) => {
  switch (status) {
    case 'running': return Loader2
    case 'completed': return CheckCircle2
    case 'failed': return AlertCircle
    default: return Clock
  }
}

const getTaskStatusClass = (status: string) => {
  switch (status) {
    case 'running': return 'status-running'
    case 'completed': return 'status-completed'
    case 'failed': return 'status-failed'
    default: return 'status-pending'
  }
}

watch(groupMessages, () => {
  nextTick(() => {
    if (groupMessagesContainer.value) {
      groupMessagesContainer.value.scrollTo({ top: groupMessagesContainer.value.scrollHeight, behavior: 'smooth' })
    }
  })
}, { deep: true })

// ===== 对话历史列表（从 SidebarHistory 迁移） =====
const convSearchQuery = ref('')
const searchResults = ref<ConversationSearchResult[]>([])
const isSearching = ref(false)
let searchTimer: ReturnType<typeof setTimeout> | null = null
let searchSeq = 0

watch(convSearchQuery, (q) => {
  if (searchTimer) clearTimeout(searchTimer)
  if (!q.trim()) {
    searchResults.value = []
    isSearching.value = false
    return
  }
  isSearching.value = true
  searchSeq++
  const currentSeq = searchSeq
  searchTimer = setTimeout(async () => {
    const results = await chatStore.searchConversations(q)
    if (currentSeq === searchSeq) {
      searchResults.value = results
      isSearching.value = false
    }
  }, 300)
})

const isSearchMode = computed(() => convSearchQuery.value.trim().length > 0)

interface TimeGroup {
  label: string
  items: ConversationListItem[]
}

const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

const timeGroups = computed<TimeGroup[]>(() => {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())

  const groups: TimeGroup[] = [
    { label: '今天', items: [] },
    { label: '昨天', items: [] },
    { label: '近7天', items: [] },
    { label: '更早', items: [] }
  ]

  const convs = localSelectedAgent.value
    ? (chatStore.agentConversations[localSelectedAgent.value.id] || [])
    : []
  for (const conv of convs) {
    const d = new Date(conv.updated_at)
    const target = new Date(d.getFullYear(), d.getMonth(), d.getDate())
    const diffDays = Math.floor((today.getTime() - target.getTime()) / 86400000)

    if (diffDays <= 0) groups[0].items.push(conv)
    else if (diffDays === 1) groups[1].items.push(conv)
    else if (diffDays <= 7) groups[2].items.push(conv)
    else groups[3].items.push(conv)
  }

  return groups.filter(g => g.items.length > 0)
})

const formatConvTime = (dateStr: string) => {
  const d = new Date(dateStr)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const target = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const diffDays = Math.floor((today.getTime() - target.getTime()) / 86400000)
  const time = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })

  if (diffDays <= 0) return time
  if (diffDays === 1) return `昨天 ${time}`
  if (diffDays <= 7) return `${WEEKDAYS[d.getDay()]} ${time}`
  if (d.getFullYear() === now.getFullYear()) return `${d.getMonth() + 1}月${d.getDate()}日`
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
}

const highlightSnippet = (snippet: string): string => {
  if (!snippet) return ''
  const escaped = snippet
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
  const q = convSearchQuery.value.trim()
  if (!q) return escaped
  const escapedQ = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const regex = new RegExp(`(${escapedQ})`, 'gi')
  return escaped.replace(regex, '<mark>$1</mark>')
}

const selectConversation = (convId: string, searchKeyword?: string) => {
  if (searchKeyword) {
    chatStore.pendingSearchKeyword = searchKeyword
    chatStore.searchScrollTarget = { convId, keyword: searchKeyword }
  }
  if (localSelectedAgent.value) {
    chatStore.loadConversation(convId, localSelectedAgent.value.id)
    localSelectedConvId.value = convId
  }
}

const handleDeleteConversation = async (convId: string) => {
  try {
    await chatStore.deleteConversation(convId, localSelectedAgent.value?.id)
    if (localSelectedConvId.value === convId) {
      localSelectedConvId.value = null
    }
  } catch (e: unknown) {
    console.error('Failed to delete conversation:', e)
  }
}

const handleNewConversation = () => {
  const prevConvId = localSelectedConvId.value
  if (prevConvId) {
    chatStore.leaveCurrentConversation(prevConvId).catch(() => {})
  }
  if (localSelectedAgent.value) {
    chatStore.clearMessages(localSelectedAgent.value.id)
  }
  localSelectedConvId.value = null
}

const batchMode = ref(false)
const selectedIds = ref<Set<string>>(new Set())

const renamingConvId = ref<string | null>(null)
const renamingTitle = ref('')

const startRename = (convId: string, currentTitle: string) => {
  renamingConvId.value = convId
  renamingTitle.value = currentTitle
  nextTick(() => {
    const input = document.querySelector('.history-item-rename-input') as HTMLInputElement
    if (input) {
      input.focus()
      input.select()
    }
  })
}

const confirmRename = async () => {
  if (!renamingConvId.value) return
  const newTitle = renamingTitle.value.trim()
  if (!newTitle) {
    renamingConvId.value = null
    return
  }
  if (newTitle.length > 200) {
    return
  }
  const success = await chatStore.renameConversation(renamingConvId.value, newTitle, localSelectedAgent.value?.id)
  if (success) {
    renamingConvId.value = null
    renamingTitle.value = ''
  }
}

const cancelRename = () => {
  renamingConvId.value = null
  renamingTitle.value = ''
}

const toggleBatchMode = () => {
  batchMode.value = !batchMode.value
  if (!batchMode.value) {
    selectedIds.value = new Set()
  }
}

const toggleSelect = (convId: string) => {
  const next = new Set(selectedIds.value)
  if (next.has(convId)) {
    next.delete(convId)
  } else {
    next.add(convId)
  }
  selectedIds.value = next
}

const selectAll = () => {
  const convs = localSelectedAgent.value
    ? (chatStore.agentConversations[localSelectedAgent.value.id] || [])
    : []
  const allIds = convs.map((c: ConversationListItem) => c.id)
  if (selectedIds.value.size === allIds.length) {
    selectedIds.value = new Set()
  } else {
    selectedIds.value = new Set(allIds)
  }
}

const handleBatchDelete = async () => {
  if (selectedIds.value.size === 0) return
  try {
    const agentId = localSelectedAgent.value?.id
    await chatTrashStore.batchSoftDelete(Array.from(selectedIds.value), agentId, () => chatStore.fetchConversations(agentId))
    selectedIds.value = new Set()
    batchMode.value = false
  } catch (e: unknown) {
    console.error('Failed to batch delete:', e)
  }
}

const messages = computed(() => {
  if (!localSelectedConvId.value) return []
  return chatStore.convMessages[localSelectedConvId.value] || []
})
const isStreaming = computed(() => {
  if (!localSelectedConvId.value) return false
  return !!chatStore.convStreaming[localSelectedConvId.value]
})
const isBackendReady = computed(() => chatStore.isBackendReady)

// 本地 currentConvId：不依赖 chatStore.currentConvId（后者基于 agentStore.activeAgent）
const currentConvId = computed(() => localSelectedConvId.value || '')

const currentModel = computed(() => {
  const agent = localSelectedAgent.value
  if (agent?.model) return agent.model
  const resolved = modelStore.resolveModel
  return resolved?.model || '未配置模型'
})

const currentProvider = computed(() => {
  const agent = localSelectedAgent.value
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

const selectModel = (providerId: string, modelId: string) => {
  if (localSelectedAgent.value) {
    agentStore.updateAgent(localSelectedAgent.value.id, {
      provider: providerId,
      model: modelId,
    })
  }
  showModelDropdown.value = false
}

const canSend = computed(() => {
  if (!isBackendReady.value) return false
  if (isUploading.value) return false
  return inputText.value.trim().length > 0 || !!parsedContent.value || !!chatStore.quotedMessage
})

const sendMessage = async () => {
  if (!canSend.value) return

  let content = inputText.value.trim()
  const fileContent = parsedContent.value
  const currentFileName = fileName.value
  const currentFileType = fileType.value

  if (!content && fileContent) {
    content = '请帮我分析上传的文件'
  }
  if (!content && chatStore.quotedMessage) {
    content = '请看上面的引用内容'
  }

  inputText.value = ''
  resetTextareaHeight()
  clearUploadState()
  fileUploadRef.value?.clearUploadState()

  const agent = localSelectedAgent.value
  const resolved = modelStore.resolveModel

  const options: any = {
    model: agent?.model || resolved?.model || undefined,
    provider: agent?.provider || resolved?.provider || undefined,
    temperature: modelStore.modelConfig.defaultTemperature,
    maxTokens: modelStore.modelConfig.defaultMaxTokens,
    topP: modelStore.modelConfig.defaultTopP,
  }
  if (agent?.systemPrompt) options.systemPrompt = agent.systemPrompt
  if (agent?.id) options.agentId = agent.id

  if (fileContent) {
    options.fileContent = fileContent
    options.fileType = currentFileType
    options.fileName = currentFileName
  }

  isNearBottom.value = true
  await chatStore.sendMessage(content, options)
  await nextTick()
  scrollToBottom(true)
}

const cancelStreaming = () => {
  chatStore.cancelCurrentRequest()
}

const scrollToBottom = (force = false) => {
  if (!messagesContainer.value) return
  if (!force && !isNearBottom.value) return
  messagesContainer.value.scrollTo({
    top: messagesContainer.value.scrollHeight,
    behavior: force ? 'auto' : 'smooth'
  })
}

const handleMessagesScroll = () => {
  if (!messagesContainer.value) return
  const { scrollTop, scrollHeight, clientHeight } = messagesContainer.value
  const distanceFromBottom = scrollHeight - scrollTop - clientHeight
  isNearBottom.value = distanceFromBottom < SCROLL_BOTTOM_THRESHOLD
  showScrollToBottomBtn.value = !isNearBottom.value && messages.value.length > 0
}

const setupResizeObserver = () => {
  if (!messagesContainer.value) return
  const inner = messagesContainer.value.querySelector('.messages-container') as HTMLElement
  if (!inner) return
  resizeObserver = new ResizeObserver(() => {
    if (isNearBottom.value) {
      scrollToBottom(true)
    }
  })
  resizeObserver.observe(inner)
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
  const raw = marked.parse(text) as string
  return DOMPurify.sanitize(raw)
}

// 智能美化思考过程：将连续文本按语义合并为段落
const beautifyThinking = (text: string): string => {
  if (!text || text.length < 20) return text || ''

  let result = text

  // 如果模型已经输出了【】标题，确保标题前后有空行
  if (/【[^】]+】/.test(result)) {
    result = result.replace(/\s*【/g, '\n\n【')
    result = result.replace(/】\s*/g, '】\n')
    result = result.replace(/\n{3,}/g, '\n\n')
    return result.trim()
  }

  // 如果已经有空行分段，直接返回
  if (/\n\n/.test(result)) return result

  // 兜底：按句号拆分成句子，每2-3句合并为一段落
  const parts = result.split(/([。！？])/)
  const sentences: string[] = []
  let current = ''

  for (const part of parts) {
    current += part
    if (/^[。！？]$/.test(part)) {
      sentences.push(current.trim())
      current = ''
    }
  }
  if (current.trim()) {
    sentences.push(current.trim())
  }

  // 每2-3句合并为一段（根据句子长度动态调整）
  const paragraphs: string[] = []
  let para = ''
  let count = 0

  for (const s of sentences) {
    if (para) para += ' '
    para += s
    count++

    // 短句（<30字）攒3句，长句攒2句，超长段落直接分段
    const threshold = para.length > 150 ? 1 : (s.length < 30 ? 3 : 2)
    if (count >= threshold) {
      paragraphs.push(para)
      para = ''
      count = 0
    }
  }
  if (para) paragraphs.push(para)

  return paragraphs.join('\n\n')
}

// 渲染思考过程的 markdown
const renderReasoningMarkdown = (text: string): string => {
  if (!text) return ''
  const beautified = beautifyThinking(text)
  const raw = marked.parse(beautified) as string
  return DOMPurify.sanitize(raw)
}

const getFileIcon = (fileType?: string) => {
  if (!fileType) return File
  if (fileType === 'image') return Image
  return FileText
}

const openFilePreview = (file: { name: string; type?: string; content?: string }) => {
  previewFile.value = { name: file.name, type: file.type, content: file.content }
  showFilePreview.value = true
}

const closeFilePreview = () => {
  showFilePreview.value = false
  previewFile.value = null
}

const contextUsage = computed(() => {
  // 修复：倒序渲染问题 - 改用正序查找最后一条完成的助手消息
  const lastAssistantMsg = messages.value.findLast(m => m.role === 'assistant' && m.done)
  return lastAssistantMsg?.usage || chatStore.lastUsage || null
})

// 推荐问题：当前显示推荐的消息ID
const currentSuggestionMessageId = computed(() => chatStore.currentSuggestionMessageId)

// 判断当前消息是否是最后一条AI消息（用于重写按钮显示）
const isLastAssistantMessage = (msgId: string) => {
  const msgs = messages.value
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role === 'assistant' && !msgs[i].done) return false
  }
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role === 'assistant') {
      return msgs[i].id === msgId
    }
  }
  return false
}

const getVersionIndex = (msg: any): number => {
  if (!msg.versions || msg.versions.length === 0) return 0
  return msg.currentVersion ?? 0
}

const handleSwitchVersion = (messageId: string, versionIndex: number) => {
  const convId = currentConvId.value
  if (!convId) return
  chatStore.switchVersion(convId, messageId, versionIndex)
}

// 点击推荐问题，填入输入框并发送
const handleSuggestionClick = (question: string) => {
  inputText.value = question
  nextTick(() => sendMessage())
}

// 重新生成：删除当前AI消息及对应的用户消息，重新发送
const handleRegenerate = async (messageId: string) => {
  await chatStore.regenerateMessage(messageId, {
    convId: localSelectedConvId.value || undefined,
    agentId: localSelectedAgent.value?.id,
  })
  await nextTick()
  scrollToBottom(true)
}

// 删除消息：删除用户消息时连同其后的AI回复一起删除
function computeDeleteRange(msgs: any[], messageId: string): { startIndex: number; deleteCount: number } {
  const index = msgs.findIndex((m: any) => m.id === messageId)
  if (index === -1) return { startIndex: -1, deleteCount: 0 }

  let startIndex = index
  if (msgs[startIndex].role === 'assistant') {
    for (let i = startIndex - 1; i >= 0; i--) {
      if (msgs[i].role === 'user') {
        startIndex = i
        break
      }
    }
  }

  let deleteCount = 1
  if (msgs[startIndex].role === 'user') {
    for (let i = startIndex + 1; i < msgs.length; i++) {
      if (msgs[i].role === 'assistant') {
        deleteCount++
      } else {
        break
      }
    }
  }

  return { startIndex, deleteCount }
}

const handleDeleteMessage = (messageId: string) => {
  const convId = currentConvId.value
  if (!convId) return
  const msgs = chatStore.convMessages[convId]
  if (!msgs) return

  const { startIndex } = computeDeleteRange(msgs, messageId)
  if (startIndex === -1) return

  openConfirmDialog(
    '确定删除这条消息及其关联回复？此操作不可撤销。',
    async () => {
      const currentConvIdLocal = currentConvId.value
      if (!currentConvIdLocal) return
      const currentMsgs = chatStore.convMessages[currentConvIdLocal]
      if (!currentMsgs) return

      const { startIndex: reStart, deleteCount: reCount } = computeDeleteRange(currentMsgs, messageId)
      if (reStart === -1) return

      if (reStart + reCount === currentMsgs.length) {
        await truncateMessages(currentConvIdLocal, reStart)
        chatStore.convMessages[currentConvIdLocal] = currentMsgs.slice(0, reStart)
      } else {
        const idsToDelete = currentMsgs.slice(reStart, reStart + reCount).map((m: any) => m.id)
        for (const id of idsToDelete) {
          await deleteMessage(currentConvIdLocal, id)
        }
        chatStore.convMessages[currentConvIdLocal] = currentMsgs.slice(0, reStart).concat(currentMsgs.slice(reStart + reCount))
      }

      if (chatStore.currentSuggestionMessageId === messageId) {
        chatStore.currentSuggestionMessageId = null
      }
    },
    true,
  )
}

// 回退用户消息到输入框：恢复文字，清除附件状态，然后删除该消息及之后所有消息
const handleGoBackToStart = (msg: any) => {
  openConfirmDialog(
    '确定回退这条消息？该消息及之后的所有消息将被删除，内容将恢复到输入框。',
    async () => {
      const convId = currentConvId.value
      if (!convId) return
      const msgs = chatStore.convMessages[convId]
      if (!msgs) return

      inputText.value = msg.content || ''

      if (msg.files && msg.files.length > 0) {
        const file = msg.files[0]
        parsedContent.value = file.content || ''
        fileName.value = file.name || ''
        fileType.value = file.type || 'text'
        uploadingFile.value = {
          name: file.name || 'file',
          status: 'success',
          type: file.type,
          result: file.content,
        }
        isUploading.value = false
      } else {
        clearUploadState()
        fileUploadRef.value?.clearUploadState()
      }

      const index = msgs.findIndex((m: any) => m.id === msg.id)
      if (index !== -1) {
        const keepCount = index
        await truncateMessages(convId, keepCount)
        chatStore.convMessages[convId] = msgs.slice(0, keepCount)
        chatStore.currentSuggestionMessageId = null
      }

      nextTick(() => {
        if (textareaRef.value) textareaRef.value.focus()
        autoResize()
      })
    },
    true,
  )
}

const handleQuoteMessage = (msg: any) => {
  chatStore.quotedMessage = msg
}

const contextPercent = computed(() => {
  if (!contextUsage.value?.totalTokens || !modelStore.modelConfig.defaultMaxTokens) return 0
  return Math.min(100, Math.round((contextUsage.value.totalTokens / modelStore.modelConfig.defaultMaxTokens) * 100))
})

const toggleReasoning = (msgId: string) => {
  showReasoning.value = {
    ...showReasoning.value,
    [msgId]: !showReasoning.value[msgId]
  }
}

watch(() => messages.value, async (msgs) => {
  for (const msg of msgs) {
    if (msg.role !== 'assistant') continue
    if (msg.content && msg.content.length > 0 && showReasoning.value[msg.id] === undefined) {
      showReasoning.value = { ...showReasoning.value, [msg.id]: false }
    }
  }
  await nextTick()
  // 对所有正在推理的消息自动滚动到底部
  const scrollEls = reasoningScrollRefs.value
  if (scrollEls) {
    const els = Array.isArray(scrollEls) ? scrollEls : [scrollEls]
    for (const el of els) {
      if (el && el.scrollHeight > el.clientHeight) {
        el.scrollTop = el.scrollHeight
      }
    }
  }
}, { deep: true, immediate: true })

const copyMessage = async (msgId: string, content: string) => {
  try {
    await navigator.clipboard.writeText(content)
    copiedId.value = msgId
    setTimeout(() => { copiedId.value = null }, 2000)
  } catch {}
}

const handleGlobalDragEnter = (e: DragEvent) => {
  if (e.dataTransfer?.types.includes('Files')) {
    e.preventDefault()
    if (dragLeaveTimer) {
      clearTimeout(dragLeaveTimer)
      dragLeaveTimer = null
    }
    globalDragCounter++
    showGlobalDropOverlay.value = true
  }
}

const handleGlobalDragOver = (e: DragEvent) => {
  if (e.dataTransfer?.types.includes('Files')) {
    e.preventDefault()
    if (dragLeaveTimer) {
      clearTimeout(dragLeaveTimer)
      dragLeaveTimer = null
    }
    showGlobalDropOverlay.value = true
  }
}

const handleGlobalDragLeave = (e: DragEvent) => {
  if (e.dataTransfer?.types.includes('Files')) {
    e.preventDefault()
    globalDragCounter--
    if (globalDragCounter <= 0) {
      dragLeaveTimer = setTimeout(() => {
        showGlobalDropOverlay.value = false
        globalDragCounter = 0
      }, 100)
    }
  }
}

const allowedExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.pdf', '.docx', '.doc', '.txt', '.md', '.csv', '.json', '.xml', '.html', '.css', '.js', '.py', '.java', '.cpp', '.c', '.h', '.go', '.rs', '.ts', '.sql', '.yaml', '.yml']

const isFileAllowed = (fileName: string): boolean => {
  const ext = fileName.toLowerCase().substring(fileName.lastIndexOf('.'))
  return allowedExtensions.includes(ext)
}

const handleGlobalDrop = async (e: DragEvent) => {
  e.preventDefault()
  showGlobalDropOverlay.value = false
  globalDragCounter = 0
  if (dragLeaveTimer) {
    clearTimeout(dragLeaveTimer)
    dragLeaveTimer = null
  }
  const files = e.dataTransfer?.files
  if (files && files.length > 0 && !isUploading.value) {
    const file = files[0]
    if (isFileAllowed(file.name)) {
      await uploadAndForward(file)
    } else {
      displayToast(`不支持的文件类型: ${file.name}`)
    }
  }
}

const handlePaste = async (e: ClipboardEvent) => {
  const items = e.clipboardData?.items
  if (!items) return
  for (let i = 0; i < items.length; i++) {
    if (items[i].kind === 'file') {
      const file = items[i].getAsFile()
      if (file && !isUploading.value) {
        if (isFileAllowed(file.name)) {
          e.preventDefault()
          await uploadAndForward(file)
          return
        } else {
          displayToast(`不支持的文件类型: ${file.name}`)
        }
      }
    }
  }
}

watch(messages, () => {
  if (isStreaming.value && isNearBottom.value) {
    nextTick(() => scrollToBottom())
  }
}, { deep: true })

watch(isLoadingCurrentConv, (loading) => {
  if (loading) {
    isNearBottom.value = true
  } else {
    // 搜索跳转：如果有待搜索的关键词，滚动到匹配的消息
    const keyword = chatStore.pendingSearchKeyword
    if (keyword) {
      chatStore.pendingSearchKeyword = ''
      nextTick(() => {
        scrollToSearchResult(keyword)
      })
    } else {
      nextTick(() => scrollToBottom(true))
    }
  }
})

// 搜索跳转：对话已缓存时，isLoadingCurrentConv 不会触发，直接监听 pendingSearchKeyword
watch(() => chatStore.pendingSearchKeyword, (keyword) => {
  if (keyword && !chatStore.isLoadingCurrentConversation && messages.value.length > 0) {
    chatStore.pendingSearchKeyword = ''
    nextTick(() => {
      scrollToSearchResult(keyword)
    })
  }
})

const scrollToSearchResult = (keyword: string) => {
  if (!messagesContainer.value) return
  const q = keyword.toLowerCase()
  const msgElements = messagesContainer.value.querySelectorAll('.message-row')
  for (const el of msgElements) {
    const text = el.textContent?.toLowerCase() || ''
    if (text.includes(q)) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      // 临时高亮
      el.classList.add('search-highlight')
      setTimeout(() => el.classList.remove('search-highlight'), 2000)
      return
    }
  }
  // 没找到匹配消息，滚动到底部
  scrollToBottom(true)
}

const handleClickOutsideModel = (e: MouseEvent) => {
  const target = e.target as HTMLElement
  if (!target.closest('.model-dropdown-container')) {
    showModelDropdown.value = false
  }
}

function handleChatTrigger(event: CustomEvent) {
  if (event.detail?.message) {
    inputText.value = event.detail.message
  }
}

function handleMemoryChatTrigger(event: CustomEvent) {
  const text = event.detail?.text
  if (text) {
    inputText.value = `关于我之前提到的「${text.slice(0, 80)}」，请帮我进一步分析。`
  }
}

function handleMemoryChatTriggerDirect(text: string) {
  inputText.value = `关于我之前提到的「${text.slice(0, 80)}」，请帮我进一步分析。`
}

(window as any).__memoryChatTrigger = handleMemoryChatTriggerDirect

onMounted(async () => {
  await chatStore.checkBackend()
  if (chatStore.isBackendReady) {
    await Promise.all([
      agentStore.fetchAgents(),
      modelStore.fetchProviders(),
      modelStore.fetchModelConfig(),
      socialStore.fetchGroups(),
      socialStore.fetchAvailableAgents(),
      socialStore.fetchAgentRoles(),
    ])
    // 自动选中第一个真实 agent（不继承工作台的主 Agent，实现状态隔离）
    if (agentStore.agents.length > 0) {
      await selectAgent(agentStore.agents[0])
    }
  }
  document.addEventListener('click', handleClickOutsideModel)
  document.addEventListener('dragenter', handleGlobalDragEnter)
  document.addEventListener('dragover', handleGlobalDragOver)
  document.addEventListener('dragleave', handleGlobalDragLeave)
  document.addEventListener('drop', handleGlobalDrop)
  document.addEventListener('paste', handlePaste)
  window.addEventListener('luominest:chat-trigger', handleChatTrigger as EventListener)
  window.addEventListener('luominest:memory-chat-trigger', handleMemoryChatTrigger as EventListener)
  nextTick(() => setupResizeObserver())
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  document.removeEventListener('click', handleClickOutsideModel)
  document.removeEventListener('dragenter', handleGlobalDragEnter)
  document.removeEventListener('dragover', handleGlobalDragOver)
  document.removeEventListener('dragleave', handleGlobalDragLeave)
  document.removeEventListener('drop', handleGlobalDrop)
  document.removeEventListener('paste', handlePaste)
  window.removeEventListener('luominest:chat-trigger', handleChatTrigger as EventListener)
  window.removeEventListener('luominest:memory-chat-trigger', handleMemoryChatTrigger as EventListener)
  ttsStopSpeaking()
})
</script>

<template>
  <div class="workspace-layout">
    <!-- 左侧：切换式面板（联系人列表 <-> 对话历史/群组信息） -->
    <aside class="left-panel">
      <!-- 联系人列表模式 -->
      <template v-if="!selectedType">
        <div class="contact-header">
          <div class="contact-search">
            <Search :size="14" class="search-icon" />
            <input v-model="contactSearchQuery" type="text" placeholder="搜索联系人..." />
          </div>
          <button class="contact-add-btn" title="新建 Agent" @click="showCreateDialog = true">
            <Plus :size="14" />
          </button>
        </div>

        <div class="contact-list">
          <!-- Agent 分组 -->
          <div class="contact-section" v-if="filteredAgents.length > 0">
            <div class="contact-section-label">
              <User :size="12" />
              <span>Agent</span>
              <span class="section-count">{{ filteredAgents.length }}</span>
            </div>
            <div
              v-for="agent in filteredAgents"
              :key="agent.id"
              :class="['contact-item', { active: selectedType === 'agent' && localSelectedAgent?.id === agent.id }]"
              @click="selectAgent(agent)"
            >
              <div class="contact-avatar" :style="{ background: agent.color + '18', color: agent.color }">
                <Bot :size="16" />
              </div>
              <div class="contact-info">
                <span class="contact-name">{{ agent.name }}</span>
                <span class="contact-desc">{{ agent.description || '智能AI' }}</span>
              </div>
              <button class="contact-edit-btn" title="编辑" @click.stop="openEditDialog(agent, $event)">
                <MoreVertical :size="12" />
              </button>
            </div>
          </div>

          <!-- 群聊分组 -->
          <div class="contact-section">
            <div class="contact-section-label">
              <Hash :size="12" />
              <span>群聊</span>
              <span class="section-count">{{ filteredGroups.length }}</span>
              <button class="section-add-btn" title="新建群组" @click="showCreateGroupDialog = true">
                <Plus :size="12" />
              </button>
            </div>
            <div
              v-for="group in filteredGroups"
              :key="group.id"
              :class="['contact-item', { active: selectedType === 'group' && selectedGroupId === group.id }]"
              @click="selectGroup(group)"
            >
              <div class="contact-avatar group-avatar">
                <Users :size="16" />
              </div>
              <div class="contact-info">
                <div class="contact-top-row">
                  <span class="contact-name">{{ group.name }}</span>
                  <span class="contact-meta">{{ group.aiCount }} AI</span>
                </div>
                <span class="contact-desc">{{ group.description || '暂无描述' }}</span>
              </div>
              <button class="contact-edit-btn" title="删除群组" @click.stop="deleteGroup(group.id)">
                <Trash2 :size="12" />
              </button>
            </div>
            <div v-if="filteredGroups.length === 0 && !contactSearchQuery" class="contact-empty-mini">
              暂无群组
            </div>
          </div>

          <div v-if="filteredAgents.length === 0 && filteredGroups.length === 0" class="contact-empty">
            <Bot :size="28" />
            <p>{{ contactSearchQuery ? '未找到匹配的联系人' : '暂无联系人' }}</p>
          </div>
        </div>
      </template>

      <!-- Agent 模式：对话历史列表 -->
      <template v-else-if="selectedType === 'agent'">
        <div class="left-panel-header">
          <button class="back-btn" title="返回联系人" @click="backToContacts">
            <ChevronLeft :size="16" />
          </button>
          <div class="left-panel-title">
            <div class="left-panel-avatar" :style="{ background: localSelectedAgent?.color + '18', color: localSelectedAgent?.color }">
              <Bot :size="14" />
            </div>
            <span class="left-panel-name">{{ localSelectedAgent?.name }}</span>
          </div>
        </div>

        <div class="sidebar-header">
          <div class="conv-search">
            <Search :size="14" class="search-icon" />
            <input v-model="convSearchQuery" type="text" placeholder="搜索对话..." />
          </div>
          <div class="sidebar-actions">
            <button class="new-conv-btn" title="创建新对话" @click="handleNewConversation">
              <Plus :size="14" />
              <span>新对话</span>
            </button>
            <button
              :class="['batch-toggle-btn', { active: batchMode }]"
              title="批量操作"
              @click="toggleBatchMode"
            >
              <SquareCheck :size="14" />
            </button>
          </div>
        </div>

        <div v-if="batchMode" class="batch-toolbar">
          <button class="batch-action-btn" @click="selectAll">全选</button>
          <span class="batch-count">已选 {{ selectedIds.size }} 项</span>
          <button
            :class="['batch-delete-btn', { disabled: selectedIds.size === 0 }]"
            :disabled="selectedIds.size === 0"
            title="批量删除"
            @click="handleBatchDelete"
          >
            <Trash2 :size="13" />
            删除
          </button>
        </div>

        <div class="conv-list">
          <template v-if="isSearchMode">
            <div v-if="isSearching" class="conv-empty">
              <Loader2 :size="20" class="spin-animation" />
              <span>搜索中...</span>
            </div>
            <template v-else>
              <div
                v-for="result in searchResults"
                :key="result.id"
                :class="['conv-item', { active: currentConvId === result.id }]"
                @click="selectConversation(result.id, convSearchQuery.trim())"
              >
                <MessageSquare :size="14" class="conv-item-icon" />
                <div class="conv-item-content">
                  <span class="conv-item-title">{{ result.title }}</span>
                  <span class="conv-item-snippet" v-html="highlightSnippet(result.snippet)"></span>
                </div>
              </div>
              <div v-if="searchResults.length === 0" class="conv-empty">
                <MessageSquare :size="24" />
                <span>未找到匹配的会话</span>
              </div>
            </template>
          </template>

          <template v-else>
            <template v-for="group in timeGroups" :key="group.label">
              <div class="time-group">
                <div class="time-group-label">
                  <Clock :size="12" />
                  <span>{{ group.label }}</span>
                </div>
                <div
                  v-for="conv in group.items"
                  :key="conv.id"
                  :class="['conv-item', { active: currentConvId === conv.id }]"
                  @click="batchMode ? toggleSelect(conv.id) : selectConversation(conv.id)"
                >
                  <div v-if="batchMode" class="conv-item-checkbox" @click.stop="toggleSelect(conv.id)">
                    <div :class="['checkbox-box', { checked: selectedIds.has(conv.id) }]">
                      <Check v-if="selectedIds.has(conv.id)" :size="10" />
                    </div>
                  </div>
                  <MessageSquare :size="14" class="conv-item-icon" />
                  <div class="conv-item-content">
                    <template v-if="renamingConvId === conv.id">
                      <input
                        v-model="renamingTitle"
                        class="conv-item-rename-input"
                        maxlength="200"
                        @keydown.enter="confirmRename"
                        @keydown.escape="cancelRename"
                        @blur="confirmRename"
                        @click.stop
                      />
                    </template>
                    <template v-else>
                      <span class="conv-item-title">{{ conv.title }}</span>
                      <span class="conv-item-time">{{ formatConvTime(conv.updated_at) }}</span>
                    </template>
                  </div>
                  <template v-if="!batchMode">
                    <button v-if="renamingConvId !== conv.id" class="conv-item-rename" title="重命名" @click.stop="startRename(conv.id, conv.title)">
                      <Pencil :size="13" />
                    </button>
                    <button class="conv-item-delete" title="删除对话" @click.stop="handleDeleteConversation(conv.id)">
                      <Trash2 :size="13" />
                    </button>
                  </template>
                </div>
              </div>
            </template>

            <div v-if="timeGroups.length === 0" class="conv-empty">
              <MessageSquare :size="24" />
              <span>暂无历史记录</span>
            </div>
          </template>
        </div>
      </template>

      <!-- 群组模式：群组信息 + 成员列表 -->
      <template v-else-if="selectedType === 'group' && selectedGroup">
        <div class="left-panel-header">
          <button class="back-btn" title="返回联系人" @click="backToContacts">
            <ChevronLeft :size="16" />
          </button>
          <div class="left-panel-title">
            <div class="left-panel-avatar group-avatar">
              <Users :size="14" />
            </div>
            <div class="left-panel-title-text">
              <span class="left-panel-name">{{ selectedGroup.name }}</span>
              <span class="left-panel-sub">{{ selectedGroup.members.length }} 成员 · {{ selectedGroup.aiCount }} AI</span>
            </div>
          </div>
        </div>

        <div class="group-actions">
          <button
            :class="['group-action-btn', { active: collaborationMode }]"
            title="协作模式"
            @click="collaborationMode = !collaborationMode"
          >
            <Zap :size="14" />
            <span>协作模式</span>
          </button>
          <button class="group-action-btn" title="添加 Agent" @click="showAddAgentDialog = true">
            <UserPlus :size="14" />
            <span>添加成员</span>
          </button>
        </div>

        <div class="group-members">
          <div class="members-label">
            <Bot :size="12" />
            <span>群成员</span>
          </div>
          <div
            v-for="member in selectedGroup.members"
            :key="member.agent_id"
            class="member-item"
          >
            <div class="member-avatar" :style="{ background: member.color + '14', color: member.color }">
              <Bot :size="14" />
            </div>
            <div class="member-info">
              <span class="member-name">{{ member.name }}</span>
              <span class="member-role">{{ member.role }}</span>
            </div>
            <button class="member-remove-btn" title="移除成员" @click="removeAgentFromGroup(selectedGroup!.id, member.agent_id)">
              <X :size="12" />
            </button>
          </div>
          <div v-if="selectedGroup.members.length === 0" class="conv-empty">
            <Bot :size="24" />
            <span>暂无成员，点击上方添加</span>
          </div>
        </div>
      </template>
    </aside>

    <!-- 右侧：聊天面板 -->
    <main class="chat-panel">
      <!-- Agent 模式：原有聊天功能 -->
      <div v-if="selectedType === 'agent'" class="chat-agent-mode">
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

        <div class="chat-area">
          <div ref="messagesContainer" class="messages-scroll" @scroll="handleMessagesScroll">
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
                    <div class="message-sender" v-if="msg.role === 'assistant'">{{ localSelectedAgent?.name || 'LuomiNest' }}</div>
                    <div
                      v-if="msg.role === 'assistant' && (msg.reasoningContent !== undefined || (!msg.done && msg.id === messages[messages.length - 1].id && !msg.content))"
                      class="reasoning-section"
                      :ref="el => { if (el && msg.id) { reasoningRefs[msg.id] = el as any } }"
                    >
                      <div class="reasoning-header" @click="toggleReasoning(msg.id)">
                        <Loader2 v-if="!msg.done && !msg.content && !msg.reasoningContent" :size="12" class="spin-animation" />
                        <Wand2 v-else :size="12" />
                        <span>
                          <template v-if="!msg.done && !msg.content && !msg.reasoningContent">等待模型中...</template>
                          <template v-else-if="!msg.done && !msg.content && msg.reasoningContent">思考中...</template>
                          <template v-else-if="msg.reasoningContent && msg.reasoningContent.length > 0">{{ showReasoning[msg.id] ? '思考过程' : '思考过程（已折叠）' }}</template>
                          <template v-else>思考完成</template>
                        </span>
                        <ChevronDown :size="12" class="reasoning-chevron" :class="{ rotated: !showReasoning[msg.id] }" />
                      </div>
                      <div
                        v-show="showReasoning[msg.id] !== false"
                        class="reasoning-content reasoning-markdown"
                        ref="reasoningScrollRefs"
                      >
                        <div v-html="renderReasoningMarkdown(msg.reasoningContent || '')"></div>
                      </div>
                    </div>

                    <!-- AI消息内容 -->
                    <div v-if="msg.role === 'assistant' && msg.content && msg.content !== '[已中断]'" class="message-content markdown-body">
                      <div v-html="renderMarkdown(msg.content)"></div>
                      <span v-if="msg.interrupted" class="interrupted-inline">
                        <AlertTriangle :size="12" /> 已中断
                      </span>
                    </div>
                    <div v-else-if="(msg.interrupted || msg.content === '[已中断]') && msg.role === 'assistant'" class="interrupted-only">
                      <AlertTriangle :size="12" /> 已中断
                    </div>
                    <div v-if="msg.role === 'assistant' && !msg.done && msg.content" class="streaming-indicator">
                      <span class="streaming-dot"></span>
                    </div>

                    <!-- AI消息操作栏：右下角，始终显示 -->
                    <div v-if="msg.role === 'assistant' && msg.done" class="assistant-msg-actions">
                      <div v-if="msg.versions && msg.versions.length > 1" class="version-nav">
                        <button
                          class="v-btn"
                          :disabled="getVersionIndex(msg) <= 0"
                          @click="handleSwitchVersion(msg.id, getVersionIndex(msg) - 1)"
                          title="上一版本"
                        >
                          <ChevronLeft :size="14" />
                        </button>
                        <span class="v-label">{{ getVersionIndex(msg) + 1 }} / {{ msg.versions.length }}</span>
                        <button
                          class="v-btn"
                          :disabled="getVersionIndex(msg) >= msg.versions.length - 1"
                          @click="handleSwitchVersion(msg.id, getVersionIndex(msg) + 1)"
                          title="下一版本"
                        >
                          <ChevronRight :size="14" />
                        </button>
                      </div>
                      <button class="u-btn" title="复制" @click="copyMessage(msg.id, msg.content)">
                        <Check v-if="copiedId === msg.id" :size="14" />
                        <Copy v-else :size="14" />
                      </button>
                      <button class="u-btn" title="引用" @click="handleQuoteMessage(msg)">
                        <Quote :size="14" />
                      </button>
                      <button
                        class="u-btn"
                        :title="isTTSSpeaking && ttsSpeakingMsgId === msg.id ? '停止朗读' : '朗读'"
                        @click="ttsSpeak(msg.content, msg.id)"
                      >
                        <div v-if="isTTSSpeaking && ttsSpeakingMsgId === msg.id" class="tts-bars">
                          <span class="tts-bar" style="--h: 8px; --d: 0s"></span>
                          <span class="tts-bar" style="--h: 14px; --d: 0.15s"></span>
                          <span class="tts-bar" style="--h: 10px; --d: 0.3s"></span>
                          <span class="tts-bar" style="--h: 6px; --d: 0.45s"></span>
                        </div>
                        <Volume2 v-else :size="14" />
                      </button>
                      <button
                        v-if="isLastAssistantMessage(msg.id)"
                        class="u-btn"
                        title="重新生成"
                        @click="handleRegenerate(msg.id)"
                      >
                        <RotateCcw :size="14" />
                      </button>
                      <button class="u-btn u-btn-danger" title="删除" @click="handleDeleteMessage(msg.id)">
                        <Trash2 :size="14" />
                      </button>
                    </div>

                    <!-- 推荐问题：在操作栏下方 -->
                    <SuggestedQuestions
                      v-if="msg.role === 'assistant' && msg.id === currentSuggestionMessageId && msg.suggestedQuestions && msg.suggestedQuestions.length > 0"
                      :questions="msg.suggestedQuestions"
                      @select="handleSuggestionClick"
                    />

                    <!-- 用户消息：[复制][引用][删除][回退] ← [气泡] -->
                    <div v-if="msg.role === 'user'" class="user-msg-layout">
                      <div class="user-msg-btns">
                        <button class="u-btn u-btn-hover" title="复制" @click="copyMessage(msg.id, msg.content)">
                          <Check v-if="copiedId === msg.id" :size="14" />
                          <Copy v-else :size="14" />
                        </button>
                        <button class="u-btn u-btn-hover" title="引用" @click="handleQuoteMessage(msg)">
                          <Quote :size="14" />
                        </button>
                        <button class="u-btn u-btn-hover u-btn-danger" title="删除" @click="handleDeleteMessage(msg.id)">
                          <Trash2 :size="14" />
                        </button>
                        <button
                          class="u-btn"
                          title="回退到本轮对话发起前"
                          @click="handleGoBackToStart(msg)"
                        >
                          <Undo2 :size="14" />
                        </button>
                      </div>
                      <div class="message-content user-message">
                        <div v-if="msg.quote && (msg.quote.content || (msg.quote.id))" class="message-quote-block" :class="msg.quote.role">
                          <Quote :size="12" class="quote-block-icon" />
                          <div class="quote-block-content">
                            <span class="quote-block-label">{{ msg.quote.role === 'assistant' ? '助手' : '用户' }}</span>
                            <span class="quote-block-text">
                              <span v-if="msg.quote.content">{{ msg.quote.content.slice(0, 150) }}{{ msg.quote.content.length > 150 ? '...' : '' }}</span>
                              <span v-else class="quote-block-empty">（该消息无文字内容）</span>
                            </span>
                          </div>
                        </div>
                        {{ msg.content }}
                        <div v-if="msg.files && msg.files.length > 0" class="message-files">
                          <div
                            v-for="(file, index) in msg.files"
                            :key="index"
                            class="message-file-item"
                            @click="openFilePreview(file)"
                          >
                            <component :is="getFileIcon(file.type)" :size="16" />
                            <span>{{ file.name }}</span>
                            <Download :size="14" class="download-icon" />
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </TransitionGroup>

              <div v-if="messages.length === 0 && !isLoadingCurrentConv" class="empty-state">
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

          <Transition name="conv-loading-fade">
            <div v-if="isLoadingCurrentConv" class="conv-loading-overlay">
              <div class="conv-loading-content">
                <Loader2 :size="20" class="spin-animation" />
                <span>加载对话中...</span>
              </div>
            </div>
          </Transition>

          <Transition name="scroll-btn-fade">
            <button v-if="showScrollToBottomBtn" class="scroll-to-bottom-btn" @click="scrollToBottom(true)">
              <ChevronDown :size="18" />
            </button>
          </Transition>
        </div>

        <div class="input-area">
          <FileUpload ref="fileUploadRef" />
          <div class="input-wrapper">
            <div v-if="chatStore.quotedMessage" class="quote-preview">
              <Quote :size="14" class="quote-preview-icon" />
              <div class="quote-preview-content">
                <span class="quote-preview-label">{{ chatStore.quotedMessage.role === 'assistant' ? '助手' : '用户' }}</span>
                <span class="quote-preview-text">{{ chatStore.quotedMessage.content.slice(0, 80) }}{{ chatStore.quotedMessage.content.length > 80 ? '...' : '' }}</span>
              </div>
              <button class="quote-preview-cancel" @click="chatStore.quotedMessage = null">
                <X :size="14" />
              </button>
            </div>
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
                    <span v-if="currentProviderLogo.svgIcon" class="provider-icon-mini provider-svg-mini" v-html="currentProviderLogo.svgIcon"></span>
                    <span v-else class="provider-icon-mini" :style="{ background: currentProviderLogo.color }">
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
                          <span v-if="opt.providerLogo.svgIcon" class="provider-icon-mini provider-svg-mini" v-html="opt.providerLogo.svgIcon"></span>
                          <span v-else class="provider-icon-mini" :style="{ background: opt.providerLogo.color }">
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
              </div>
              <div class="toolbar-right">
                <button class="tool-btn icon-only" title="附件" @click="fileUploadRef?.triggerFileSelect()">
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
                  :class="['send-btn', { disabled: !canSend }]"
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
            <span v-else></span>
          </div>
        </div>
      </div>

      <!-- 群组模式：群聊消息 -->
      <div v-else-if="selectedType === 'group' && selectedGroup" class="chat-group-mode">
        <div class="group-chat-header">
          <div class="chat-title-area">
            <div class="chat-avatar-mini">
              <Users :size="14" />
            </div>
            <div class="chat-title-text">
              <h3>{{ selectedGroup.name }}</h3>
              <span class="chat-status-line">
                {{ selectedGroup.members.length }} 成员 · {{ selectedGroup.aiCount }} AI
              </span>
            </div>
          </div>
          <div class="chat-actions">
            <button
              :class="['chat-action-btn', { active: collaborationMode }]"
              title="协作模式"
              @click="collaborationMode = !collaborationMode"
            >
              <Zap :size="15" />
            </button>
            <button class="chat-action-btn" title="添加 Agent" @click="showAddAgentDialog = true">
              <UserPlus :size="15" />
            </button>
            <button class="chat-action-btn" title="更多">
              <MoreVertical :size="15" />
            </button>
          </div>
        </div>

        <div class="collaboration-bar" v-if="collaborationMode">
          <div class="collab-mode-indicator">
            <Zap :size="12" />
            <span>多 Agent 协作模式</span>
          </div>
          <div class="collab-phase" v-if="collaborationActive && collaborationPhase">
            <component
              :is="phaseIcon"
              :size="14"
              :class="{ 'spin-animation': collaborationPhase === 'analyzing' || collaborationPhase === 'executing' }"
            />
            <span>{{ phaseLabel }}</span>
          </div>
          <div class="collab-tasks-mini" v-if="collaborationTasks.length > 0">
            <div
              v-for="task in collaborationTasks"
              :key="task.taskId"
              :class="['collab-task-chip', getTaskStatusClass(task.status)]"
            >
              <component
                :is="getTaskStatusIcon(task.status)"
                :size="10"
                :class="{ 'spin-animation': task.status === 'running' }"
              />
              <span>{{ task.description.slice(0, 12) }}{{ task.description.length > 12 ? '...' : '' }}</span>
            </div>
          </div>
        </div>

        <div ref="groupMessagesContainer" class="group-chat-messages">
          <div
            v-for="msg in groupMessages"
            :key="msg.id"
            :class="['msg-row', msg.senderType, { 'collab-synthesis': msg.collaboration?.type === 'synthesis' }]"
          >
            <div v-if="msg.senderType === 'agent'" class="msg-avatar">
              <div
                class="avatar-agent"
                :style="msg.role === '调度员' ? { background: 'rgba(20, 126, 188, 0.15)', color: 'var(--lumi-primary)' } : {}"
              >
                <Bot :size="14" />
              </div>
            </div>
            <div :class="['msg-bubble', msg.senderType, { 'synthesis-bubble': msg.collaboration?.type === 'synthesis' }]">
              <span class="msg-sender" v-if="msg.senderType === 'agent'">
                {{ msg.senderName || 'AI' }}
                <span
                  v-if="msg.role"
                  class="msg-role-tag"
                  :style="msg.collaboration?.type === 'synthesis' ? { background: 'rgba(20, 126, 188, 0.15)', color: 'var(--lumi-primary)' } : {}"
                >
                  {{ msg.role }}
                </span>
                <span v-if="msg.collaboration?.taskId" class="msg-collab-tag">
                  {{ msg.collaboration.taskDescription?.slice(0, 8) }}...
                </span>
              </span>
              <p class="msg-text">{{ msg.content }}</p>
              <span class="msg-time">{{ formatGroupTime(msg.timestamp) }}</span>
            </div>
            <div v-if="msg.senderType === 'user'" class="msg-avatar user-avatar">
              <User :size="16" />
            </div>
          </div>

          <div v-if="collaborationActive && collaborationPhase" class="collab-progress-msg">
            <div class="collab-progress-inner">
              <Loader2 :size="14" class="spin-animation" />
              <span class="collab-progress-text">
                <template v-if="collaborationPhase === 'analyzing'">调度员正在分析任务...</template>
                <template v-else-if="collaborationPhase === 'dispatching'">正在分配子任务...</template>
                <template v-else-if="collaborationPhase === 'executing'">
                  Agent 团队执行中 ({{ collaborationTasks.filter(t => t.status === 'completed').length }}/{{ collaborationTasks.length }})
                </template>
                <template v-else-if="collaborationPhase === 'synthesizing'">调度员正在综合结果...</template>
              </span>
            </div>
          </div>

          <div v-if="agentsResponding && !collaborationActive" class="collab-progress-msg">
            <div class="collab-progress-inner">
              <Loader2 :size="14" class="spin-animation" />
              <span class="collab-progress-text">
                {{ respondingAgentNames.length > 0
                  ? `${respondingAgentNames.join('、')} 正在思考...`
                  : 'Agent 正在响应...' }}
              </span>
            </div>
          </div>

          <div v-if="groupMessages.length === 0 && !collaborationActive" class="chat-empty">
            <MessageCircle :size="32" />
            <p>群聊已创建，添加 Agent 开始协作</p>
          </div>
        </div>

        <div class="group-chat-input-bar">
          <div class="input-tools">
            <button class="input-tool-btn" title="图片">
              <ImagePlus :size="16" />
            </button>
            <button class="input-tool-btn" title="语音">
              <Mic :size="16" />
            </button>
          </div>
          <div class="input-main">
            <input
              v-model="groupChatInput"
              type="text"
              :placeholder="collaborationMode ? '输入消息，Agent 团队将协作处理...' : '发送消息到群聊...'"
              :disabled="sendingGroupMessage || collaborationActive || agentsResponding"
              @keydown.enter="sendGroupMessage"
            />
            <button
              class="input-send-btn"
              @click="sendGroupMessage"
              :disabled="!groupChatInput.trim() || sendingGroupMessage || collaborationActive || agentsResponding"
            >
              <Loader2 v-if="sendingGroupMessage || collaborationActive || agentsResponding" :size="15" class="spin-animation" />
              <Send v-else :size="15" />
            </button>
          </div>
        </div>
      </div>

      <!-- 空状态：未选择联系人 -->
      <div v-else class="chat-empty-state">
        <div class="empty-visual">
          <div class="empty-orb">
            <MessageCircle :size="36" />
          </div>
        </div>
        <h3>选择一个联系人开始对话</h3>
        <p>在左侧选择 Agent 或群聊，开始你的对话</p>
      </div>
    </main>

    <Transition name="global-drop-fade">
      <div v-if="showGlobalDropOverlay" class="global-drop-overlay" @dragover.prevent @drop.prevent>
        <div class="drop-content">
          <div class="drop-icon-wrapper">
            <UploadCloud :size="64" class="drop-main-icon" />
            <div class="drop-particles">
              <span class="particle p1">📄</span>
              <span class="particle p2">📊</span>
              <span class="particle p3"></span>
              <span class="particle p4">📕</span>
              <span class="particle p5">🖼️</span>
            </div>
          </div>
          <h3 class="drop-title">在此处拖放文件</h3>
          <p class="drop-desc">
            支持图片、文档、代码等常见格式
          </p>
          <p class="drop-hint">或按 Ctrl+V 粘贴文件</p>
        </div>
      </div>
    </Transition>

    <Transition name="toast-fade">
      <div v-if="showToast" class="toast-notification">
        <AlertTriangle :size="16" />
        <span>{{ toastMessage }}</span>
      </div>
    </Transition>

    <FilePreview
      :visible="showFilePreview"
      :file-name="previewFile?.name || ''"
      :file-type="previewFile?.type"
      :file-content="previewFile?.content"
      @close="closeFilePreview"
    />

    <Transition name="dialog-fade">
      <div v-if="showCreateDialog" class="create-dialog-overlay" @click.self="showCreateDialog = false">
        <div class="create-dialog">
          <h3>创建自定义 Agent</h3>
          <Transition name="toast-slide">
            <div v-if="createDialogError" class="dialog-error">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <line x1="15" y1="9" x2="9" y2="15"/>
                <line x1="9" y1="9" x2="15" y2="15"/>
              </svg>
              <span>{{ createDialogError }}</span>
              <button class="error-close" @click="createDialogError = ''">
                <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18"/>
                  <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>
          </Transition>
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
              创建
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 编辑 Agent 对话框 -->
    <Transition name="dialog-fade">
      <div v-if="showEditDialog" class="create-dialog-overlay" @click.self="showEditDialog = false">
        <div class="create-dialog">
          <h3>编辑 Agent</h3>
          <div class="form-group">
            <label class="form-label">
              名称
              <span class="required-mark">*</span>
            </label>
            <input v-model="editAgentForm.name" type="text" class="form-input" placeholder="如: 小助手" />
          </div>
          <div class="form-group">
            <label class="form-label">描述</label>
            <input v-model="editAgentForm.description" type="text" class="form-input" placeholder="如: 通用对话助手" />
          </div>
          <div class="form-group">
            <label class="form-label">系统提示词</label>
            <textarea
              v-model="editAgentForm.systemPrompt"
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
                :class="['color-dot', { active: editAgentForm.color === color }]"
                :style="{ background: color }"
                @click="editAgentForm.color = color"
              ></button>
            </div>
          </div>
          <div class="dialog-actions">
            <button class="dialog-btn delete" @click="openConfirmDialog('确定要删除该 Agent 吗？此操作无法撤销。', handleDeleteAgent, true)">
              删除
            </button>
            <div style="flex:1"></div>
            <button class="dialog-btn cancel" @click="showEditDialog = false">取消</button>
            <button
              :class="['dialog-btn confirm', { disabled: !editAgentForm.name.trim() }]"
              :disabled="!editAgentForm.name.trim()"
              @click="handleUpdateAgent"
            >
              保存
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <Transition name="dialog-fade">
      <div v-if="showConfirmDialog" class="confirm-dialog-overlay" @click.self="handleConfirmDialogCancel">
        <div class="confirm-dialog">
          <div class="confirm-dialog-icon">
            <AlertTriangle :size="24" />
          </div>
          <p class="confirm-dialog-message">{{ confirmDialogMessage }}</p>
          <div class="confirm-dialog-actions">
            <button class="dialog-btn confirm" @click="handleConfirmDialogConfirm">
              确定
            </button>
            <button class="dialog-btn cancel" @click="handleConfirmDialogCancel">取消</button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 创建群组对话框 -->
    <Transition name="dialog-fade">
      <div v-if="showCreateGroupDialog" class="create-dialog-overlay" @click.self="showCreateGroupDialog = false">
        <div class="create-dialog">
          <h3>创建群组</h3>
          <div class="form-group">
            <label class="form-label">
              群组名称
              <span class="required-mark">*</span>
            </label>
            <input v-model="newGroupName" type="text" class="form-input" placeholder="如: 项目讨论组" />
          </div>
          <div class="form-group">
            <label class="form-label">描述</label>
            <input v-model="newGroupDesc" type="text" class="form-input" placeholder="群组用途描述" />
          </div>
          <div class="dialog-actions">
            <button class="dialog-btn cancel" @click="showCreateGroupDialog = false">取消</button>
            <button
              :class="['dialog-btn confirm', { disabled: !newGroupName.trim() }]"
              :disabled="!newGroupName.trim()"
              @click="createGroup"
            >
              创建
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 添加 Agent 到群组对话框 -->
    <Transition name="dialog-fade">
      <div v-if="showAddAgentDialog" class="create-dialog-overlay" @click.self="showAddAgentDialog = false">
        <div class="create-dialog">
          <h3>添加 Agent 到群组</h3>
          <div v-if="availableAgentsForGroup.length === 0" class="dialog-empty">
            <Bot :size="24" />
            <p>所有 Agent 都已在群组中，或暂无可用 Agent</p>
          </div>
          <div v-else class="agent-select-list">
            <div
              v-for="agent in availableAgentsForGroup"
              :key="agent.id"
              :class="['agent-select-item', { selected: addAgentId === agent.id }]"
              @click="addAgentId = agent.id"
            >
              <div class="agent-select-avatar" :style="{ background: agent.color + '14', color: agent.color }">
                <Bot :size="18" />
              </div>
              <div class="agent-select-info">
                <span class="agent-select-name">{{ agent.name }}</span>
                <span class="agent-select-desc">{{ agent.description || '暂无描述' }}</span>
              </div>
            </div>
          </div>
          <div v-if="addAgentId" class="form-group">
            <label class="form-label">角色定位</label>
            <input v-model="addAgentRole" type="text" class="form-input" placeholder="如: 调度员、数据专员、计算专员、审核专员" />
            <div class="role-suggestions" v-if="socialStore.agentRoles.length > 0">
              <button
                v-for="role in socialStore.agentRoles"
                :key="role.roleId"
                class="role-suggestion-chip"
                :style="{ background: role.color + '14', color: role.color }"
                @click="addAgentRole = role.name"
              >
                {{ role.name }}
              </button>
            </div>
          </div>
          <div class="dialog-actions">
            <button class="dialog-btn cancel" @click="showAddAgentDialog = false">取消</button>
            <button
              :class="['dialog-btn confirm', { disabled: !addAgentId }]"
              :disabled="!addAgentId"
              @click="addAgentToGroup"
            >
              添加
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

/* ===== 左侧：切换式面板（联系人列表 <-> 对话历史/群组信息） ===== */
.left-panel {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--workspace-sidebar);
  border-right: 1px solid var(--workspace-border);
  overflow: hidden;
}

/* 左栏头部：返回按钮 + 当前选中标题（agent/群组模式） */
.left-panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  flex-shrink: 0;
  border-bottom: 1px solid var(--workspace-border);
}

.back-btn {
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.back-btn:hover {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.left-panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.left-panel-title-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.left-panel-avatar {
  width: 26px;
  height: 26px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.left-panel-avatar.group-avatar {
  background: var(--lumi-primary-glow);
  color: var(--lumi-primary);
}

.left-panel-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.left-panel-sub {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.contact-header {
  padding: 12px 12px 8px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.contact-search {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: var(--workspace-panel);
  border-radius: var(--radius-sm);
  border: 1px solid transparent;
  transition: all var(--transition-fast);
}

.contact-search:focus-within {
  border-color: var(--lumi-primary-border);
  background: var(--surface);
}

.contact-search .search-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.contact-search input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 13px;
  color: var(--text-primary);
  min-width: 0;
}

.contact-search input::placeholder {
  color: var(--text-muted);
}

.contact-add-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.contact-add-btn:hover {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.contact-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 8px 12px;
}

.contact-section {
  margin-bottom: 8px;
}

.contact-section-label {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 8px 6px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.contact-section-label .section-count {
  background: var(--workspace-panel);
  padding: 1px 6px;
  border-radius: 10px;
  font-size: 10px;
  font-weight: 500;
}

.section-add-btn {
  margin-left: auto;
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  color: var(--text-muted);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.section-add-btn:hover {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.contact-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition-fast);
  background: transparent;
  border: none;
  width: 100%;
  text-align: left;
}

.contact-item:hover {
  background: var(--workspace-hover);
}

.contact-item.active {
  background: var(--lumi-primary-light);
}

.contact-avatar {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.contact-avatar.group-avatar {
  background: var(--lumi-primary-glow);
  color: var(--lumi-primary);
}

.contact-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.contact-top-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.contact-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.contact-meta {
  font-size: 10px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.contact-desc {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.contact-edit-btn {
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  color: var(--text-muted);
  background: transparent;
  border: none;
  cursor: pointer;
  opacity: 0;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.contact-item:hover .contact-edit-btn {
  opacity: 1;
}

.contact-edit-btn:hover {
  background: var(--overlay-subtle);
  color: var(--text-secondary);
}

.contact-empty-mini {
  padding: 8px 12px;
  font-size: 11px;
  color: var(--text-muted);
  text-align: center;
}

.contact-empty {
  padding: 32px 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: var(--text-muted);
}

.contact-empty p {
  font-size: 12px;
  margin: 0;
}

/* ===== 对话历史/群组信息区域（在 left-panel 内） ===== */
.sidebar-header {
  padding: 12px 12px 8px;
  flex-shrink: 0;
}

.conv-search {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: var(--surface);
  border-radius: var(--radius-sm);
  border: 1px solid transparent;
  transition: all var(--transition-fast);
  margin-bottom: 8px;
}

.conv-search:focus-within {
  border-color: var(--lumi-primary-border);
}

.conv-search .search-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.conv-search input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 13px;
  color: var(--text-primary);
  min-width: 0;
}

.conv-search input::placeholder {
  color: var(--text-muted);
}

.sidebar-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.new-conv-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 500;
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.new-conv-btn:hover {
  background: var(--lumi-primary-glow);
}

.batch-toggle-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  background: transparent;
  border: 1px solid var(--workspace-border);
  cursor: pointer;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.batch-toggle-btn:hover {
  color: var(--text-secondary);
  background: var(--workspace-hover);
}

.batch-toggle-btn.active {
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
  border-color: var(--lumi-primary-border);
}

.batch-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: var(--lumi-primary-subtle);
  border-bottom: 1px solid var(--workspace-border);
  flex-shrink: 0;
}

.batch-action-btn {
  font-size: 12px;
  color: var(--lumi-primary);
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}

.batch-action-btn:hover {
  background: var(--lumi-primary-light);
}

.batch-count {
  flex: 1;
  font-size: 11px;
  color: var(--text-muted);
  text-align: center;
}

.batch-delete-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--lumi-danger);
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}

.batch-delete-btn:hover:not(.disabled) {
  background: var(--lumi-danger-light);
}

.batch-delete-btn.disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.conv-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 8px 12px;
}

.time-group {
  margin-bottom: 4px;
}

.time-group-label {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 8px 4px;
  font-size: 10px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.conv-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.conv-item:hover {
  background: var(--workspace-hover);
}

.conv-item.active {
  background: var(--lumi-primary-light);
}

.conv-item-checkbox {
  flex-shrink: 0;
  cursor: pointer;
}

.checkbox-box {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  border: 1.5px solid var(--workspace-border);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-fast);
}

.checkbox-box.checked {
  background: var(--lumi-primary);
  border-color: var(--lumi-primary);
  color: var(--text-inverse);
}

.conv-item-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.conv-item-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.conv-item-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conv-item-time {
  font-size: 10px;
  color: var(--text-muted);
}

.conv-item-snippet {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.4;
}

.conv-item-snippet :deep(mark) {
  background: var(--lumi-amber-soft);
  color: var(--lumi-amber-dark);
  padding: 0 2px;
  border-radius: 2px;
}

.conv-item-rename-input {
  width: 100%;
  border: 1px solid var(--lumi-primary-border);
  border-radius: 4px;
  padding: 2px 4px;
  font-size: 13px;
  color: var(--text-primary);
  background: var(--surface);
  outline: none;
}

.conv-item-rename,
.conv-item-delete {
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  color: var(--text-muted);
  background: transparent;
  border: none;
  cursor: pointer;
  opacity: 0;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.conv-item:hover .conv-item-rename,
.conv-item:hover .conv-item-delete {
  opacity: 1;
}

.conv-item-rename:hover {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.conv-item-delete:hover {
  background: var(--lumi-danger-light);
  color: var(--lumi-danger);
}

.conv-empty {
  padding: 32px 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: var(--text-muted);
}

.conv-empty span {
  font-size: 12px;
}

/* ===== 群组操作区 ===== */
.group-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 0 12px 8px;
  flex-shrink: 0;
}

.group-action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--surface);
  border: 1px solid var(--workspace-border);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.group-action-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

.group-action-btn.active {
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
  border-color: var(--lumi-primary-border);
}

.group-members {
  flex: 1;
  overflow-y: auto;
  padding: 4px 12px 12px;
}

.members-label {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 0 6px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.member-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: var(--radius-sm);
  transition: background var(--transition-fast);
}

.member-item:hover {
  background: var(--workspace-hover);
}

.member-avatar {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.member-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.member-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.member-role {
  font-size: 10px;
  color: var(--text-muted);
}

.member-remove-btn {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  color: var(--text-muted);
  background: transparent;
  border: none;
  cursor: pointer;
  opacity: 0;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.member-item:hover .member-remove-btn {
  opacity: 1;
}

.member-remove-btn:hover {
  background: var(--lumi-danger-light);
  color: var(--lumi-danger);
}

/* ===== 右侧：聊天面板 ===== */
.chat-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--workspace-bg);
  overflow: hidden;
  position: relative;
}

.chat-agent-mode {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}

.chat-group-mode {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--text-muted);
}

.chat-empty-state .empty-visual {
  margin-bottom: 8px;
}

.chat-empty-state .empty-orb {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--lumi-primary-gradient-soft);
  color: var(--lumi-primary);
}

.chat-empty-state h3 {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0;
}

.chat-empty-state p {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0;
}

/* ===== 群聊头部 ===== */
.group-chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  border-bottom: 1px solid var(--workspace-border);
  background: var(--workspace-sidebar);
  flex-shrink: 0;
}

.chat-title-area {
  display: flex;
  align-items: center;
  gap: 10px;
}

.chat-avatar-mini {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--lumi-primary-glow);
  color: var(--lumi-primary);
}

.chat-title-text h3 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.chat-status-line {
  font-size: 11px;
  color: var(--text-muted);
}

.chat-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.chat-action-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.chat-action-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-secondary);
}

.chat-action-btn.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

/* ===== 协作模式栏 ===== */
.collaboration-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 20px;
  background: var(--lumi-primary-subtle);
  border-bottom: 1px solid var(--lumi-primary-border);
  flex-shrink: 0;
  flex-wrap: wrap;
}

.collab-mode-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 500;
  color: var(--lumi-primary);
}

.collab-phase {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-secondary);
}

.collab-tasks-mini {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.collab-task-chip {
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 2px 6px;
  border-radius: 10px;
  font-size: 10px;
  background: var(--surface);
  border: 1px solid var(--workspace-border);
}

.collab-task-chip.status-running {
  color: var(--lumi-primary);
  border-color: var(--lumi-primary-border);
}

.collab-task-chip.status-completed {
  color: var(--lumi-success);
  border-color: var(--task-green-border);
}

.collab-task-chip.status-failed {
  color: var(--lumi-danger);
  border-color: var(--task-red-border);
}

.collab-task-chip.status-pending {
  color: var(--text-muted);
}

/* ===== 群聊消息区 ===== */
.group-chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.msg-row {
  display: flex;
  gap: 8px;
  max-width: 80%;
}

.msg-row.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.msg-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: var(--lumi-primary-glow);
  color: var(--lumi-primary);
}

.msg-avatar.user-avatar {
  background: var(--lumi-primary);
  color: var(--text-inverse);
}

.avatar-agent {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.msg-bubble {
  padding: 8px 12px;
  border-radius: var(--radius-md);
  font-size: 13px;
  line-height: 1.5;
  word-break: break-word;
}

.msg-bubble.agent {
  background: var(--surface);
  border: 1px solid var(--workspace-border);
  color: var(--text-primary);
}

.msg-bubble.user {
  background: var(--lumi-primary);
  color: var(--text-inverse);
}

.msg-bubble.synthesis-bubble {
  background: var(--lumi-primary-light);
  border-color: var(--lumi-primary-border);
}

.msg-sender {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 2px;
}

.msg-role-tag {
  padding: 1px 5px;
  border-radius: 8px;
  font-size: 9px;
  font-weight: 500;
  background: var(--workspace-panel);
  color: var(--text-muted);
}

.msg-collab-tag {
  font-size: 9px;
  color: var(--text-muted);
  padding: 1px 4px;
  background: var(--workspace-panel);
  border-radius: 4px;
}

.msg-text {
  margin: 0;
  white-space: pre-wrap;
}

.msg-time {
  font-size: 10px;
  color: var(--text-muted);
  margin-top: 4px;
  display: block;
}

.msg-bubble.user .msg-time {
  color: rgba(255, 255, 255, 0.7);
}

.collab-progress-msg {
  align-self: center;
  padding: 8px 16px;
  background: var(--surface);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-full);
}

.collab-progress-inner {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}

.chat-empty {
  margin: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: var(--text-muted);
  padding: 32px;
}

.chat-empty p {
  font-size: 13px;
  margin: 0;
}

/* ===== 群聊输入栏 ===== */
.group-chat-input-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  border-top: 1px solid var(--workspace-border);
  background: var(--workspace-sidebar);
  flex-shrink: 0;
}

.input-tools {
  display: flex;
  align-items: center;
  gap: 4px;
}

.input-tool-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.input-tool-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-secondary);
}

.input-main {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--surface);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-md);
  padding: 4px 4px 4px 12px;
}

.input-main input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 13px;
  color: var(--text-primary);
  padding: 6px 0;
}

.input-main input::placeholder {
  color: var(--text-muted);
}

.input-send-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--text-inverse);
  background: var(--lumi-primary);
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.input-send-btn:hover:not(:disabled) {
  background: var(--lumi-primary-hover);
}

.input-send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ===== 对话框扩展样式 ===== */
.dialog-empty {
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: var(--text-muted);
}

.dialog-empty p {
  font-size: 12px;
  margin: 0;
  text-align: center;
}

.agent-select-list {
  max-height: 240px;
  overflow-y: auto;
  margin: 0 -4px 8px;
  padding: 0 4px;
}

.agent-select-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.agent-select-item:hover {
  background: var(--workspace-hover);
}

.agent-select-item.selected {
  background: var(--lumi-primary-light);
}

.agent-select-avatar {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.agent-select-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.agent-select-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.agent-select-desc {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.role-suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}

.role-suggestion-chip {
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 10px;
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.role-suggestion-chip:hover {
  transform: translateY(-1px);
}

/* ===== 通用动画 ===== */
.spin-animation {
  animation: luominest-spin 1s linear infinite;
}

@keyframes luominest-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
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
  color: var(--text-inverse);
  flex-shrink: 0;
}

.provider-svg-mini {
  background: transparent !important;
}

.provider-svg-mini :deep(svg) {
  width: 16px;
  height: 16px;
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
  background: var(--lumi-primary-subtle);
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
  background: var(--lumi-accent-light);
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.backend-warning.info .retry-btn {
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
}

.retry-btn:hover {
  background: var(--lumi-accent-border);
}

.backend-warning.info .retry-btn:hover {
  background: var(--lumi-primary-border);
}

.chat-area {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  position: relative;
}

.messages-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
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
  align-items: flex-end;
  gap: 6px;
}

.message-row.user .message-body {
  max-width: 70%;
}

.user-message {
  padding: 12px 18px;
  border-radius: var(--radius-lg);
  border-top-right-radius: 4px;
  background: linear-gradient(135deg, var(--lumi-primary-light), var(--lumi-primary-subtle));
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  transition: all 250ms ease-in-out;
}

.message-row:hover .user-message {
  background: linear-gradient(135deg, var(--lumi-primary-glow), var(--lumi-primary-light));
}

.message-files {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.message-file-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: var(--workspace-card);
  border: 1px solid var(--divider-soft);
  border-radius: var(--radius-sm);
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
}

.message-file-item:hover {
  background: var(--lumi-primary-bg);
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
}

.download-icon {
  opacity: 0.6;
}

.message-file-item:hover .download-icon {
  opacity: 1;
}

/* 消息中的引用块 */
.message-quote-block {
  display: flex;
  gap: 6px;
  padding: 8px 10px;
  margin-bottom: 8px;
  border-left: 3px solid var(--lumi-primary);
  border-radius: 6px;
  background: var(--lumi-primary-light);
}

.message-quote-block.assistant {
  border-left-color: var(--lumi-primary);
}

.message-quote-block.user {
  border-left-color: var(--lumi-emerald);
}

.quote-block-icon {
  color: var(--lumi-primary-border);
  flex-shrink: 0;
  margin-top: 1px;
}

.quote-block-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.quote-block-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--lumi-primary);
}

.quote-block-text {
  font-size: 12px;
  color: var(--text-secondary);
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
}

.quote-block-empty {
  color: var(--overlay-subtle);
  font-style: italic;
}

.quote-preview {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--overlay-subtle);
  background: var(--lumi-primary-subtle);
}

.quote-preview-icon {
  color: var(--overlay-bg);
  flex-shrink: 0;
}

.quote-preview-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.quote-preview-label {
  font-size: 11px;
  color: var(--overlay-bg);
}

.quote-preview-text {
  font-size: 12px;
  color: var(--overlay-bg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.quote-preview-cancel {
  flex-shrink: 0;
  background: none;
  border: none;
  color: var(--overlay-bg);
  cursor: pointer;
  padding: 2px;
  border-radius: 4px;
  display: flex;
  align-items: center;
}

.quote-preview-cancel:hover {
  color: var(--text);
  background: var(--overlay-subtle);
}

.interrupted-inline {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  margin-left: 8px;
  background: var(--lumi-amber-soft);
  border: 1px solid var(--lumi-amber-border);
  border-radius: 4px;
  font-size: 11px;
  color: var(--lumi-amber-dark);
  font-weight: 500;
  vertical-align: middle;
}

.interrupted-only {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 14px;
  background: var(--lumi-amber-soft);
  border: 1px solid var(--lumi-amber-border);
  border-radius: 8px;
  font-size: 12px;
  color: var(--lumi-amber-dark);
  font-weight: 500;
}

/* ====== 用户消息按钮 ====== */
.user-msg-layout {
  display: flex;
  align-items: flex-start;
  gap: 6px;
}

.user-msg-btns {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
  padding-top: 10px;
}

.u-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: var(--radius-sm);
  background: transparent;
  border: 1px solid transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
  padding: 0;
}

.u-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-secondary);
  border-color: var(--workspace-border);
}

.u-btn-danger:hover {
  background: var(--task-red-soft);
  color: var(--lumi-danger);
  border-color: var(--task-red-border);
}

.tts-bars {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
  width: 16px;
  height: 16px;
}

.tts-bar {
  width: 3px;
  border-radius: 1.5px;
  background: var(--lumi-indigo);
  animation: tts-bar-bounce 0.8s ease-in-out infinite alternate;
  animation-delay: var(--d);
}

@keyframes tts-bar-bounce {
  0% { height: 4px; }
  100% { height: var(--h); }
}

/* 复制/删除：默认隐藏，hover该行时显示 */
.u-btn-hover {
  opacity: 0;
  pointer-events: none;
}

.user-msg-layout:hover .u-btn-hover {
  opacity: 1;
  pointer-events: auto;
}

/* AI消息操作栏：右下角，始终显示 */
.assistant-msg-actions {
  display: flex;
  gap: 2px;
  margin-top: 4px;
  align-items: center;
}

.version-nav {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  margin-right: 6px;
  padding: 0 4px;
  border-radius: var(--radius-sm);
  background: var(--workspace-hover);
  border: 1px solid var(--workspace-border);
}

.v-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 3px;
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 0;
  transition: all var(--transition-fast);
}

.v-btn:hover:not(:disabled) {
  background: var(--workspace-border);
  color: var(--text-secondary);
}

.v-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.v-label {
  font-size: 11px;
  color: var(--text-muted);
  min-width: 32px;
  text-align: center;
  user-select: none;
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

.streaming-indicator {
  display: inline-flex;
  align-items: center;
  padding: 4px 0;
}

.streaming-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--lumi-primary);
  animation: streaming-pulse 1.2s ease-in-out infinite;
}

@keyframes streaming-pulse {
  0%, 100% { opacity: 0.4; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1.2); }
}

.conv-loading-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--workspace-bg);
  opacity: 0.85;
  z-index: 10;
}

.conv-loading-content {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 24px;
  border-radius: var(--radius-lg);
  background: var(--workspace-card);
  box-shadow: var(--shadow-md);
  color: var(--text-secondary);
  font-size: 14px;
}

.conv-loading-fade-enter-active {
  animation: conv-loading-in 0.25s ease-out;
}

.conv-loading-fade-leave-active {
  animation: conv-loading-in 0.2s ease-out reverse;
}

@keyframes conv-loading-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

.scroll-to-bottom-btn {
  position: absolute;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  width: 36px;
  height: 36px;
  border-radius: var(--radius-full);
  background: var(--workspace-card);
  box-shadow: var(--shadow-md);
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
  transition: all 300ms ease-in-out;
}

.scroll-to-bottom-btn:hover {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  box-shadow: var(--shadow-lg);
  transform: translateX(-50%) scale(1.08);
}

.scroll-btn-fade-enter-active {
  animation: scroll-btn-in 0.25s ease-out;
}

.scroll-btn-fade-leave-active {
  animation: scroll-btn-in 0.2s ease-out reverse;
}

@keyframes scroll-btn-in {
  from { opacity: 0; transform: translateX(-50%) translateY(8px); }
  to { opacity: 1; transform: translateX(-50%) translateY(0); }
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

.input-area {
  padding: 12px 24px 16px;
  flex-shrink: 0;
  position: relative;
  z-index: 100;
  display: flex;
  flex-direction: column;
  gap: 8px;
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

.model-dropdown-container {
  position: relative;
}

.model-dropdown {
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
  color: var(--text-inverse);
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
  background: var(--lumi-danger);
}

.send-btn.stop:hover {
  background: var(--lumi-danger-hover);
}

.input-footer {
  text-align: center;
  margin-top: 8px;
}

.input-footer span {
  font-size: 11px;
  color: var(--text-muted);
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
  background: var(--text);
  overflow-x: auto;
  position: relative;
}

.markdown-body :deep(pre code) {
  padding: 0;
  background: none;
  color: var(--border-light);
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
  position: relative;
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

.reasoning-section {
  margin-bottom: 10px;
  border: 1px solid var(--task-purple-border);
  border-radius: var(--radius-md);
  background: var(--task-purple-soft);
  overflow: hidden;
}

.reasoning-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  cursor: pointer;
  user-select: none;
  font-size: 12px;
  color: var(--task-purple);
  transition: background var(--transition-fast);
}

.reasoning-header:hover {
  background: var(--task-purple-soft);
}

.reasoning-chevron {
  margin-left: auto;
  transition: transform 0.2s ease;
}

.reasoning-chevron.rotated {
  transform: rotate(-90deg);
}

.reasoning-content {
  padding: 12px 16px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-muted);
  border-top: 1px solid var(--divider-soft);
  border-left: 4px solid var(--task-purple-border);
  border-radius: 0 4px 4px 0;
  background: var(--task-purple-soft);
  word-break: break-word;
  max-height: 400px;
  overflow-y: auto;
}

/* 思考过程 markdown 渲染样式 */
.reasoning-markdown :deep(p) {
  margin: 0 0 10px;
  line-height: 1.8;
  position: relative;
}

.reasoning-markdown :deep(p:last-child) {
  margin-bottom: 0;
}

.reasoning-markdown :deep(strong) {
  color: var(--text-secondary);
  font-weight: 600;
}

.reasoning-markdown :deep(em) {
  color: var(--text-muted);
  font-style: italic;
}

.reasoning-markdown :deep(code) {
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 11px;
  background: var(--task-purple-soft);
  color: var(--task-purple);
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
}

/* 列表样式 */
.reasoning-markdown :deep(ul),
.reasoning-markdown :deep(ol) {
  margin: 4px 0 10px;
  padding-left: 20px;
}

.reasoning-markdown :deep(li) {
  margin: 2px 0;
  line-height: 1.7;
}

.msg-appear-enter-active {
  transition: all 0.4s cubic-bezier(0.22, 1, 0.36, 1);
}

.msg-appear-enter-from {
  opacity: 0;
  transform: translateY(16px) scale(0.97);
}

.global-drop-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 9999;
  background: var(--overlay-bg);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.drop-content {
  text-align: center;
  padding: 60px 80px;
  border-radius: 24px;
  background: var(--surface);
  border: 2px dashed var(--lumi-primary-border);
  box-shadow: 0 20px 60px var(--overlay-subtle), 0 0 80px var(--lumi-primary-light);
  max-width: 560px;
}

.drop-icon-wrapper {
  position: relative;
  display: inline-block;
  margin-bottom: 24px;
}

.drop-main-icon {
  color: var(--lumi-primary);
  animation: drop-bounce 2s ease-in-out infinite;
}

.drop-particles {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 140px;
  height: 140px;
  pointer-events: none;
}

.particle {
  position: absolute;
  font-size: 22px;
  animation: float-particle 3s ease-in-out infinite;
  opacity: 0.7;
}

.p1 { top: -10px; left: 10px; animation-delay: 0s; }
.p2 { top: 0; right: -5px; animation-delay: 0.4s; }
.p3 { bottom: 5px; right: 0; animation-delay: 0.8s; }
.p4 { bottom: -8px; left: 5px; animation-delay: 1.2s; }
.p5 { top: 5px; left: -5px; animation-delay: 1.6s; }

@keyframes drop-bounce {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-12px); }
}

@keyframes float-particle {
  0%, 100% { transform: translate(0, 0) rotate(0deg); }
  25% { transform: translate(6px, -8px) rotate(10deg); }
  50% { transform: translate(-4px, -14px) rotate(-5deg); }
  75% { transform: translate(8px, -4px) rotate(8deg); }
}

.drop-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text);
  margin: 0 0 16px;
  letter-spacing: 0.3px;
}

.drop-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0 0 10px;
  line-height: 1.7;
  word-break: break-all;
}

.drop-hint {
  font-size: 12px;
  color: var(--text-muted);
  margin: 0;
}

.global-drop-fade-enter-active,
.global-drop-fade-leave-active {
  transition: all 0.25s ease;
}

.global-drop-fade-enter-from,
.global-drop-fade-leave-to {
  opacity: 0;
}

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: all 0.3s ease;
}

.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translateY(20px);
}

.toast-notification {
  position: fixed;
  bottom: 100px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  background: var(--workspace-card);
  border: 1px solid var(--divider-soft);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  color: var(--text-primary);
  font-size: 14px;
  z-index: 2000;
}

.toast-notification svg {
  color: var(--lumi-primary);
}

.dialog-fade-enter-active,
.dialog-fade-leave-active {
  transition: all 0.25s ease;
}

.dialog-fade-enter-from,
.dialog-fade-leave-to {
  opacity: 0;
}

.search-highlight {
  animation: search-highlight-pulse 0.6s ease-out;
}

@keyframes search-highlight-pulse {
  0% { background: var(--lumi-primary-border); }
  100% { background: transparent; }
}

.dialog-error {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  background: var(--task-red-soft);
  border: 1px solid var(--task-red-border);
  border-radius: var(--radius-md);
  color: var(--lumi-danger);
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 16px;
  box-shadow: 0 4px 12px var(--overlay-subtle);
}

.dialog-error svg {
  flex-shrink: 0;
}

.error-close {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border: none;
  background: rgba(239, 68, 68, 0.1);
  border-radius: 4px;
  color: var(--lumi-danger);
  cursor: pointer;
  transition: all 0.2s ease;
  margin-left: auto;
}

.error-close:hover {
  background: rgba(239, 68, 68, 0.2);
  transform: rotate(90deg);
}

.toast-slide-enter-active {
  transition: all 0.3s ease-out;
}

.toast-slide-leave-active {
  transition: all 0.2s ease-in;
}

.toast-slide-enter-from {
  opacity: 0;
  transform: translateY(-10px);
}

.toast-slide-leave-to {
  opacity: 0;
  transform: translateY(-10px) scale(0.95);
}

</style>

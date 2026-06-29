<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick, watch, computed } from 'vue'
import { AlertTriangle, MessageCircle } from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import { useChatStore } from '../stores/chat'
import { useAgentStore } from '../stores/agent'
import { useModelStore } from '../stores/model'
import { useSocialStore } from '../stores/social'
import { useChatTrashStore } from '../stores/chat-trash'
import { useTTS } from '../composables/useTTS'
import { useDebouncedSearch } from '../composables/useDebouncedSearch'
import FilePreview from '../components/FilePreview.vue'
import { useFileUpload } from '../composables/useFileUpload'
import { useApi } from '../composables/useApi'
import { useClipboard } from '../composables/useClipboard'
import { useFileDrop } from '../composables/useFileDrop'
import { isUploadAllowed } from '../utils/file'
import { getProviderLogo } from '../config/provider-logos'
import WorkspaceContactPanel from '../components/workspace/WorkspaceContactPanel.vue'
import WorkspaceAgentHistory from '../components/workspace/WorkspaceAgentHistory.vue'
import WorkspaceGroupInfo from '../components/workspace/WorkspaceGroupInfo.vue'
import WorkspaceAgentChat from '../components/workspace/WorkspaceAgentChat.vue'
import WorkspaceGroupChat from '../components/workspace/WorkspaceGroupChat.vue'
import WorkspaceDialogs from '../components/workspace/WorkspaceDialogs.vue'
import WorkspaceDropOverlay from '../components/workspace/WorkspaceDropOverlay.vue'
import type { ConversationListItem, ConversationSearchResult, GroupInfo, AgentProfile } from '../types'
import { generateId } from '../utils/id'

const router = useRouter()
const chatStore = useChatStore()
const agentStore = useAgentStore()
const modelStore = useModelStore()
const socialStore = useSocialStore()
const chatTrashStore = useChatTrashStore()
const { isSpeaking: isTTSSpeaking, speakingMessageId: ttsSpeakingMsgId, speak: ttsSpeak, stopSpeaking: ttsStopSpeaking } = useTTS()

const { isUploading, uploadingFile, parsedContent, fileType, fileName, uploadAndForward, clearUploadState } = useFileUpload()
const { truncateMessages, deleteMessage } = useApi()
const { copiedId, copy: copyMessage } = useClipboard()
const agentChatRef = ref<InstanceType<typeof WorkspaceAgentChat> | null>(null)

const inputText = ref('')
const selectedSkillIds = ref<string[]>([])
const showModelDropdown = ref(false)
const showReasoning = ref<Record<string, boolean>>({})

const { showOverlay: showGlobalDropOverlay } = useFileDrop({
  isUploading,
  isAllowed: isUploadAllowed,
  onUpload: (file: File) => uploadAndForward(file),
  onError: (message: string) => displayToast(message),
})

const showFilePreview = ref(false)
const previewFile = ref<{ name: string; type?: string; content?: string } | null>(null)

const openFilePreview = (file: { name: string; type?: string; content?: string }) => {
  previewFile.value = file
  showFilePreview.value = true
}

const closeFilePreview = () => {
  showFilePreview.value = false
  previewFile.value = null
}

const showCreateDialog = ref(false)
const newAgentForm = ref({
  name: '',
  description: '',
  systemPrompt: '',
  color: 'var(--lumi-brand)',
})
const createDialogError = ref('')
const agentColors = ['var(--lumi-brand)', 'var(--lumi-indigo)', 'var(--lumi-amber)', 'var(--lumi-accent)', 'var(--task-purple)', 'var(--lumi-sky)', 'var(--lumi-success)', 'var(--task-pink)']

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
    newAgentForm.value = { name: '', description: '', systemPrompt: '', color: 'var(--lumi-brand)' }
  } catch (e: any) {
    createDialogError.value = e.response?.data?.detail || e.message || '创建 Agent 失败'
  }
}

const showEditDialog = ref(false)
const editingAgentId = ref<string | null>(null)
const editAgentForm = ref({
  name: '',
  description: '',
  systemPrompt: '',
  color: 'var(--lumi-brand)',
})

const openEditDialog = (agent: AgentProfile, e?: Event) => {
  if (e) e.stopPropagation()
  editingAgentId.value = agent.id
  editAgentForm.value = {
    name: agent.name || '',
    description: agent.description || '',
    systemPrompt: agent.systemPrompt || '',
    color: agent.color || 'var(--lumi-brand)',
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

type ContactType = 'agent' | 'group'
const selectedType = ref<ContactType | null>(null)
const contactSearchQuery = ref('')

const localSelectedAgent = ref<AgentProfile | null>(null)
const localSelectedConvId = ref<string | null>(null)

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

const backToContacts = () => {
  selectedType.value = null
  localSelectedAgent.value = null
  localSelectedConvId.value = null
  selectedGroupId.value = null
  batchMode.value = false
  selectedIds.value = new Set()
}

const selectedGroupId = ref<string | null>(null)
const groupChatInput = ref('')
const sendingGroupMessage = ref(false)
const collaborationMode = ref(false)
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

const sendGroupMessage = async () => {
  if (!groupChatInput.value.trim() || !selectedGroupId.value) return
  sendingGroupMessage.value = true
  const userContent = groupChatInput.value
  groupChatInput.value = ''

  try {
    if (collaborationMode.value) {
      socialStore.groupMessages.push({
        id: generateId('user'),
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
    if (groupChatRef.value) {
      groupChatRef.value.scrollToBottom()
    }
  } catch (e) {
    console.error('Failed to send message:', e)
  } finally {
    sendingGroupMessage.value = false
  }
}

const groupChatRef = ref<InstanceType<typeof WorkspaceGroupChat> | null>(null)

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

const convSearchQuery = ref('')
const { results: searchResults, isSearching } = useDebouncedSearch<ConversationSearchResult[]>(
  convSearchQuery,
  (q) => chatStore.searchConversations(q),
  300,
)

const isSearchMode = computed(() => convSearchQuery.value.trim().length > 0)

interface TimeGroup {
  label: string
  items: ConversationListItem[]
}

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
    const input = document.querySelector('.conv-item-rename-input') as HTMLInputElement
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
const isLoadingCurrentConv = computed(() => chatStore.isLoadingCurrentConversation)
const isBackendReady = computed(() => chatStore.isBackendReady)

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
    const modelIds = provider.selectedModels.length > 0
      ? provider.selectedModels
      : (provider.defaultModel ? [provider.defaultModel] : [])
    for (const modelId of modelIds) {
      options.push({
        providerId: provider.id,
        providerName: provider.name,
        providerLogo: logo,
        modelId,
        modelName: modelId,
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
  agentChatRef.value?.resetTextareaHeight()
  clearUploadState()

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

  await chatStore.sendMessage(content, options)
  await nextTick()
  agentChatRef.value?.scrollToBottom(true)
}

const cancelStreaming = () => {
  chatStore.cancelCurrentRequest()
}

const contextUsage = computed(() => {
  const lastAssistantMsg = messages.value.findLast(m => m.role === 'assistant' && m.done)
  return lastAssistantMsg?.usage || chatStore.lastUsage || null
})

const currentSuggestionMessageId = computed(() => chatStore.currentSuggestionMessageId)

const handleSwitchVersion = (messageId: string, versionIndex: number) => {
  const convId = currentConvId.value
  if (!convId) return
  chatStore.switchVersion(convId, messageId, versionIndex)
}

const handleSuggestionClick = (question: string) => {
  inputText.value = question
  nextTick(() => sendMessage())
}

const handleRegenerate = async (messageId: string) => {
  await chatStore.regenerateMessage(messageId, {
    convId: localSelectedConvId.value || undefined,
    agentId: localSelectedAgent.value?.id,
  })
  await nextTick()
  agentChatRef.value?.scrollToBottom(true)
}

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
      }

      const index = msgs.findIndex((m: any) => m.id === msg.id)
      if (index !== -1) {
        const keepCount = index
        await truncateMessages(convId, keepCount)
        chatStore.convMessages[convId] = msgs.slice(0, keepCount)
        chatStore.currentSuggestionMessageId = null
      }

      nextTick(() => {
        agentChatRef.value?.focusTextarea()
        agentChatRef.value?.autoResize()
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

watch(isLoadingCurrentConv, (loading) => {
  if (!loading) {
    const keyword = chatStore.pendingSearchKeyword
    if (keyword) {
      chatStore.pendingSearchKeyword = ''
      nextTick(() => {
        agentChatRef.value?.scrollToSearchResult(keyword)
      })
    } else {
      nextTick(() => {
        agentChatRef.value?.scrollToBottom(true)
      })
    }
  }
})

watch(() => chatStore.pendingSearchKeyword, (keyword) => {
  if (keyword && !chatStore.isLoadingCurrentConversation && messages.value.length > 0) {
    chatStore.pendingSearchKeyword = ''
    nextTick(() => {
      agentChatRef.value?.scrollToSearchResult(keyword)
    })
  }
})

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
    // 默认显示联系人列表，不自动进入某个 agent 的对话
  }
  document.addEventListener('click', handleClickOutsideModel)
  window.addEventListener('luominest:chat-trigger', handleChatTrigger as EventListener)
  window.addEventListener('luominest:memory-chat-trigger', handleMemoryChatTrigger as EventListener)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutsideModel)
  window.removeEventListener('luominest:chat-trigger', handleChatTrigger as EventListener)
  window.removeEventListener('luominest:memory-chat-trigger', handleMemoryChatTrigger as EventListener)
  ttsStopSpeaking()
})
</script>

<template>
  <div class="workspace-layout">
    <aside class="left-panel">
      <WorkspaceContactPanel
        v-if="!selectedType"
        :agents="agentStore.agents"
        :groups="socialStore.groups"
        :search-query="contactSearchQuery"
        :selected-type="selectedType"
        :selected-agent-id="localSelectedAgent?.id || null"
        :selected-group-id="selectedGroupId"
        @update:search-query="contactSearchQuery = $event"
        @select-agent="selectAgent"
        @select-group="selectGroup"
        @create-agent="showCreateDialog = true"
        @create-group="showCreateGroupDialog = true"
        @delete-group="deleteGroup"
        @edit-agent="openEditDialog"
      />
      <WorkspaceAgentHistory
        v-else-if="selectedType === 'agent'"
        :agent="localSelectedAgent"
        :search-query="convSearchQuery"
        :is-search-mode="isSearchMode"
        :search-results="searchResults"
        :is-searching="isSearching"
        :time-groups="timeGroups"
        :batch-mode="batchMode"
        :selected-ids="selectedIds"
        :current-conv-id="currentConvId"
        :renaming-conv-id="renamingConvId"
        :renaming-title="renamingTitle"
        @back="backToContacts"
        @update:search-query="convSearchQuery = $event"
        @update:renaming-title="renamingTitle = $event"
        @new-conversation="handleNewConversation"
        @toggle-batch-mode="toggleBatchMode"
        @select-all="selectAll"
        @batch-delete="handleBatchDelete"
        @select-conversation="selectConversation"
        @start-rename="startRename"
        @confirm-rename="confirmRename"
        @cancel-rename="cancelRename"
        @delete-conversation="handleDeleteConversation"
        @toggle-select="toggleSelect"
      />
      <WorkspaceGroupInfo
        v-else-if="selectedType === 'group' && selectedGroup"
        :group="selectedGroup"
        :collaboration-mode="collaborationMode"
        @back="backToContacts"
        @toggle-collaboration-mode="collaborationMode = !collaborationMode"
        @add-agent="showAddAgentDialog = true"
        @remove-agent="removeAgentFromGroup(selectedGroup!.id, $event)"
      />
    </aside>

    <main class="chat-panel">
      <WorkspaceAgentChat
        v-if="selectedType === 'agent'"
        ref="agentChatRef"
        :messages="messages"
        :is-loading-current-conv="isLoadingCurrentConv"
        :is-streaming="isStreaming"
        :is-backend-ready="isBackendReady"
        :has-provider="hasProvider"
        :current-model="currentModel"
        :current-provider="currentProvider"
        :current-provider-logo="currentProviderLogo"
        :available-model-options="availableModelOptions"
        :show-model-dropdown="showModelDropdown"
        :input-text="inputText"
        :can-send="canSend"
        :is-uploading="isUploading"
        :quoted-message="chatStore.quotedMessage"
        :context-usage="contextUsage"
        :context-percent="contextPercent"
        :copied-id="copiedId"
        :show-reasoning="showReasoning"
        :current-suggestion-message-id="currentSuggestionMessageId"
        :is-tts-speaking="isTTSSpeaking"
        :tts-speaking-msg-id="ttsSpeakingMsgId"
        :agent="localSelectedAgent"
        :selected-skill-ids="selectedSkillIds"
        @check-backend="chatStore.checkBackend()"
        @go-settings="router.push('/settings/ai-model')"
        @toggle-reasoning="toggleReasoning"
        @copy-message="copyMessage"
        @quote-message="handleQuoteMessage"
        @tts-speak="ttsSpeak"
        @tts-stop="ttsStopSpeaking"
        @regenerate="handleRegenerate"
        @delete-message="handleDeleteMessage"
        @go-back-to-start="handleGoBackToStart"
        @switch-version="handleSwitchVersion"
        @suggestion-click="handleSuggestionClick"
        @update:input-text="inputText = $event"
        @update:selected-skill-ids="selectedSkillIds = $event"
        @send="sendMessage"
        @cancel="cancelStreaming"
        @toggle-model-dropdown="showModelDropdown = !showModelDropdown"
        @select-model="selectModel"
        @clear-quote="chatStore.quotedMessage = null"
        @file-preview="openFilePreview"
      />
      <WorkspaceGroupChat
        v-else-if="selectedType === 'group' && selectedGroup"
        ref="groupChatRef"
        :group="selectedGroup"
        :messages="groupMessages"
        :collaboration-mode="collaborationMode"
        :collaboration-active="collaborationActive"
        :collaboration-phase="collaborationPhase"
        :collaboration-tasks="collaborationTasks"
        :agents-responding="agentsResponding"
        :responding-agent-names="respondingAgentNames"
        :sending-group-message="sendingGroupMessage"
        :group-chat-input="groupChatInput"
        @toggle-collaboration-mode="collaborationMode = !collaborationMode"
        @add-agent="showAddAgentDialog = true"
        @update:group-chat-input="groupChatInput = $event"
        @send-group-message="sendGroupMessage"
      />
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

    <WorkspaceDropOverlay :visible="showGlobalDropOverlay" />

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

    <WorkspaceDialogs
      :show-create-dialog="showCreateDialog"
      :show-edit-dialog="showEditDialog"
      :show-confirm-dialog="showConfirmDialog"
      :show-create-group-dialog="showCreateGroupDialog"
      :show-add-agent-dialog="showAddAgentDialog"
      :create-form="newAgentForm"
      :edit-form="editAgentForm"
      :create-error="createDialogError"
      :confirm-message="confirmDialogMessage"
      :confirm-is-danger="confirmDialogIsDanger"
      :new-group-name="newGroupName"
      :new-group-desc="newGroupDesc"
      :add-agent-id="addAgentId"
      :add-agent-role="addAgentRole"
      :available-agents-for-group="availableAgentsForGroup"
      :agent-colors="agentColors"
      :agent-roles="socialStore.agentRoles"
      @update:show-create-dialog="showCreateDialog = $event"
      @update:create-form="newAgentForm = $event"
      @update:create-error="createDialogError = $event"
      @create-agent="handleCreateAgent"
      @update:show-edit-dialog="showEditDialog = $event"
      @update:edit-form="editAgentForm = $event"
      @update-agent="handleUpdateAgent"
      @delete-agent="openConfirmDialog('确定要删除该 Agent 吗？此操作无法撤销。', handleDeleteAgent, true)"
      @confirm="handleConfirmDialogConfirm"
      @cancel="handleConfirmDialogCancel"
      @update:show-create-group-dialog="showCreateGroupDialog = $event"
      @update:new-group-name="newGroupName = $event"
      @update:new-group-desc="newGroupDesc = $event"
      @create-group="createGroup"
      @update:show-add-agent-dialog="showAddAgentDialog = $event"
      @update:add-agent-id="addAgentId = $event"
      @update:add-agent-role="addAgentRole = $event"
      @add-agent-to-group="addAgentToGroup"
    />
  </div>
</template>

<style scoped>
.workspace-layout {
  display: flex;
  height: 100%;
  overflow: hidden;
  background: var(--workspace-bg);
}

.left-panel {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--workspace-sidebar);
  border-right: 1px solid var(--workspace-border);
  overflow: hidden;
}

.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--workspace-bg);
  position: relative;
}

.chat-empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: var(--text-muted);
  gap: var(--space-4);
}

.chat-empty-state .empty-visual {
  position: relative;
}

.chat-empty-state .empty-orb {
  width: 100px;
  height: 100px;
  border-radius: var(--radius-full);
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 60px var(--lumi-brand-glow);
  animation: lumi-pulse 3s var(--ease-in-out) infinite;
}

.chat-empty-state h3 {
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.chat-empty-state p {
  font-size: var(--text-base);
  color: var(--text-muted);
  margin: 0;
}

@keyframes lumi-pulse {
  0%, 100% { transform: scale(1); opacity: 0.9; }
  50% { transform: scale(1.05); opacity: 1; }
}

.toast-notification {
  position: fixed;
  bottom: 100px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-5);
  background: var(--workspace-card);
  border: 1px solid var(--divider-soft);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  color: var(--text-primary);
  font-size: var(--text-md);
  z-index: 2000;
}

.toast-notification svg {
  color: var(--lumi-brand);
}

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: all var(--duration-normal) var(--ease-default);
}

.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translateY(20px);
}
</style>

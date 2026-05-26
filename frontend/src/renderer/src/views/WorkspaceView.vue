<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick, watch, computed } from 'vue'
import {
  Send,
  Paperclip,
  Mic,
  Wand2,
  ChevronDown,
  ChevronUp,
  ChevronLeft,
  ChevronRight,
  Bot,
  Link2,
  Loader2,
  AlertTriangle,
  RotateCcw,
  Undo2,
  Copy,
  Check,
  Search,
  Zap,
  Server,
  Square,
  UploadCloud,
  FileText,
  Image,
  File,
  Download,
  Plus,
  Sparkles,
  Pencil,
  Trash2,
} from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import { useChatStore } from '../stores/chat'
import { useAgentStore } from '../stores/agent'
import { useModelStore } from '../stores/model'
import { useSkillStore } from '../stores/skill'
import FileUpload from '../components/FileUpload.vue'
import FilePreview from '../components/FilePreview.vue'
import SuggestedQuestions from '../components/SuggestedQuestions.vue'
import { useFileUpload } from '../composables/useFileUpload'
import { useApi } from '../composables/useApi'
import { getProviderLogo } from '../config/provider-logos'
import DOMPurify from 'dompurify'
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

const { isUploading, parsedContent, fileType, fileName, uploadAndForward, clearUploadState } = useFileUpload()
const { truncateMessages } = useApi()
const fileUploadRef = ref<InstanceType<typeof FileUpload> | null>(null)

const inputText = ref('')
const messagesContainer = ref<HTMLElement | null>(null)
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const showModelDropdown = ref(false)
const showSkillDropdown = ref(false)
const agentsCollapsed = ref(false)

const toggleAgents = () => {
  agentsCollapsed.value = !agentsCollapsed.value
}
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
const agentColors = ['#147EBC', '#6366f1', '#f59e0b', '#f43f5e', '#8b5cf6', '#06b6d4', '#84cc16', '#ec4899']

const handleCreateAgent = async () => {
  if (!newAgentForm.value.name.trim()) return
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
    displayToast(e?.message || '创建 Agent 失败')
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
  try {
    await agentStore.deleteAgent(editingAgentId.value)
    showEditDialog.value = false
    editingAgentId.value = null
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

const activeSkills = computed(() => skillStore.skills.filter(s => s.isActive))

const selectModel = (providerId: string, modelId: string) => {
  if (agentStore.activeAgent) {
    agentStore.updateAgent(agentStore.activeAgent.id, {
      provider: providerId,
      model: modelId,
    })
  }
  showModelDropdown.value = false
}

const canSend = computed(() => {
  if (!isBackendReady.value) return false
  if (isUploading.value) return false
  return inputText.value.trim().length > 0 || !!parsedContent.value
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

  inputText.value = ''
  resetTextareaHeight()
  clearUploadState()
  fileUploadRef.value?.clearUploadState()

  const agent = agentStore.activeAgent
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
  // 如果有流式消息，不显示任何重写按钮，避免竞态
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role === 'assistant' && !msgs[i].done) return false
  }
  // 无流式消息时，找最后一条AI消息
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role === 'assistant') {
      return msgs[i].id === msgId
    }
  }
  return false
}

// 点击推荐问题，填入输入框并发送
const handleSuggestionClick = (question: string) => {
  inputText.value = question
  nextTick(() => sendMessage())
}

// 重新生成：删除当前AI消息及对应的用户消息，重新发送
const handleRegenerate = async (messageId: string) => {
  const convId = chatStore.currentConvId
  if (!convId) return
  const msgs = chatStore.convMessages[convId]
  if (!msgs) return

  const aiIndex = msgs.findIndex(m => m.id === messageId)
  if (aiIndex === -1) return

  // 找到这条AI消息之前的最后一条用户消息的位置
  let userIndex = -1
  for (let i = aiIndex - 1; i >= 0; i--) {
    if (msgs[i].role === 'user') {
      userIndex = i
      break
    }
  }
  if (userIndex === -1) return
  const userContent = msgs[userIndex].content

  // 删除从用户消息开始到末尾的所有消息
  const keepCount = userIndex
  chatStore.convMessages[convId] = msgs.slice(0, keepCount)

  // 同步删除后端消息
  await truncateMessages(convId, keepCount)

  // 清除推荐
  chatStore.currentSuggestionMessageId = null

  // 重新发送用户消息
  await chatStore.sendMessage(userContent)
  await nextTick()
  scrollToBottom(true)
}

// 删除消息：删除用户消息时连同其后的AI回复一起删除
const handleDeleteMessage = async (messageId: string) => {
  const convId = chatStore.currentConvId
  if (!convId) return
  const msgs = chatStore.convMessages[convId]
  if (!msgs) return

  const index = msgs.findIndex((m: any) => m.id === messageId)
  if (index !== -1) {
    const targetMsg = msgs[index]
    if (targetMsg.role === 'user') {
      // 找到该用户消息之后连续的AI消息，一并删除
      let deleteCount = 1
      for (let i = index + 1; i < msgs.length; i++) {
        if (msgs[i].role === 'assistant') {
          deleteCount++
        } else {
          break
        }
      }
      const newMsgs = msgs.slice(0, index).concat(msgs.slice(index + deleteCount))
      chatStore.convMessages[convId] = newMsgs
      await truncateMessages(convId, newMsgs.length)
    } else {
      // 仅删除这条AI消息
      const newMsgs = msgs.filter((_: any, i: number) => i !== index)
      chatStore.convMessages[convId] = newMsgs
      await truncateMessages(convId, newMsgs.length)
    }
  }

  // 如果删除的是当前推荐消息，清除推荐
  if (chatStore.currentSuggestionMessageId === messageId) {
    chatStore.currentSuggestionMessageId = null
  }
}

// 回退用户消息到输入框：恢复文字，清除附件状态，然后删除该消息及之后所有消息
const handleGoBackToStart = async (msg: any) => {
  const convId = chatStore.currentConvId
  if (!convId) return
  const msgs = chatStore.convMessages[convId]
  if (!msgs) return

  // 恢复文字内容到输入框
  inputText.value = msg.content || ''

  // 清除附件状态（文件内容无法从前端消息对象中恢复，需要用户重新上传）
  clearUploadState()
  fileUploadRef.value?.clearUploadState()

  // 删除该消息及之后的所有消息
  const index = msgs.findIndex((m: any) => m.id === msg.id)
  if (index !== -1) {
    const keepCount = index
    chatStore.convMessages[convId] = msgs.slice(0, keepCount)
    chatStore.currentSuggestionMessageId = null
    await truncateMessages(convId, keepCount)
  }

  nextTick(() => {
    if (textareaRef.value) textareaRef.value.focus()
    autoResize()
  })
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
}, { deep: false, immediate: true })

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

const insertSkillToInput = (skillName: string) => {
  inputText.value += `<tool_call name="${skillName}">\n{}\n</tool_call >`
  showSkillDropdown.value = false
  if (textareaRef.value) textareaRef.value.focus()
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
  if (!target.closest('.skill-dropdown-container')) {
    showSkillDropdown.value = false
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

// Agent列表横向滚动：鼠标滚轮转横向滚动
function onAgentListWheel(e: WheelEvent) {
  const el = (e.currentTarget as HTMLElement)
  el.scrollLeft += e.deltaY
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
      chatStore.fetchConversations(),
      skillStore.fetchSkills(),
      skillStore.fetchMcpServers(),
    ])
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
})
</script>

<template>
  <div class="workspace-layout">
    <div class="workspace-main">
      <div class="workspace-view">
        <!-- 展开状态：顶栏显示 Agent 列表 -->
        <div v-if="!agentsCollapsed" class="workspace-header">
          <div class="header-left">
            <div class="agent-list" @wheel.prevent.stop="onAgentListWheel">
              <!-- 新建 Agent -->
              <button class="agent-new-btn" @click="showCreateDialog = true">
                <div class="agent-new-icon">
                  <Sparkles :size="22" />
                </div>
                <div class="agent-new-info">
                  <span class="agent-new-title">自定义</span>
                  <span class="agent-new-desc">创建全新 Agent</span>
                </div>
              </button>

              <!-- Agent 列表 -->
              <button
                v-for="agent in agentStore.agents"
                :key="agent.id"
                :class="['agent-card', { active: agentStore.activeAgent?.id === agent.id }]"
                @click="agentStore.setActiveAgent(agent)"
              >
                <span v-if="agentStore.activeAgent?.id === agent.id" class="active-dot"></span>
                <div class="agent-card-icon" :style="{ background: agent.color + '18', color: agent.color }">
                  <Bot :size="22" />
                </div>
                <div class="agent-card-info">
                  <span class="agent-card-name">{{ agent.name }}</span>
                  <span class="agent-card-desc">{{ agent.description || '智能AI' }}</span>
                </div>
                <div class="agent-card-arrow" @click.stop="openEditDialog(agent, $event)">
                  <span class="arrow-icon">›</span>
                </div>
              </button>
            </div>
          </div>
          <div class="header-right">
            <button v-if="!isBackendReady" class="header-icon-btn warning" title="后端未连接" @click="chatStore.checkBackend()">
              <AlertTriangle :size="18" />
            </button>
            <!-- 收起按钮 -->
            <button class="toggle-agent-btn" title="收起Agent列表" @click="toggleAgents">
              <ChevronRight :size="18" />
            </button>
          </div>
        </div>

        <!-- 收起状态：展开按钮（固定在右上角） -->
        <Transition name="agent-list-fade">
          <button v-if="agentsCollapsed" class="toggle-agent-btn floating" title="展开Agent列表" @click="toggleAgents">
            <ChevronLeft :size="18" />
          </button>
        </Transition>

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
                    <div class="message-sender" v-if="msg.role === 'assistant'">{{ agentStore.activeAgent?.name || 'LuomiNest' }}</div>
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
                      <button class="u-btn" title="复制" @click="copyMessage(msg.id, msg.content)">
                        <Check v-if="copiedId === msg.id" :size="14" />
                        <Copy v-else :size="14" />
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

                    <!-- 用户消息：[复制][删除][回退] ← [气泡] -->
                    <div v-if="msg.role === 'user'" class="user-msg-layout">
                      <div class="user-msg-btns">
                        <button class="u-btn u-btn-hover" title="复制" @click="copyMessage(msg.id, msg.content)">
                          <Check v-if="copiedId === msg.id" :size="14" />
                          <Copy v-else :size="14" />
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
    </div>

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
            <button class="dialog-btn delete" @click="handleDeleteAgent">
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
  position: relative;
}

.workspace-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 24px;
  flex-shrink: 0;
  position: relative;
  min-height: 68px;
}

.workspace-header::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 24px;
  right: 64px;
  height: 1px;
  background: var(--divider-soft);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  margin-left: auto;
}

.toggle-agent-btn {
  width: 52px;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  color: var(--text-muted);
  cursor: pointer;
  background: var(--workspace-card);
  border: 1px solid var(--divider-soft);
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.toggle-agent-btn:hover {
  color: var(--text-primary);
  background: var(--workspace-hover);
  border-color: var(--lumi-primary);
}

/* 收起状态：悬浮展开按钮，位置与 header-right 中收起按钮对齐 */
.toggle-agent-btn.floating {
  position: absolute;
  top: calc(8px + (68px / 2));
  transform: translateY(-50%);
  right: 24px;
  z-index: 100;
  box-shadow: var(--shadow-sm);
}

.agent-list-fade-enter-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.agent-list-fade-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.agent-list-fade-enter-from {
  opacity: 0;
  transform: translateX(-12px);
}
.agent-list-fade-leave-to {
  opacity: 0;
  transform: translateX(-12px);
}

.agent-list {
  display: flex;
  flex-direction: row;
  gap: 8px;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 6px 0;
  flex: 1;
  min-width: 0;
}

/* 横向滚动条样式 */
.agent-list::-webkit-scrollbar {
  height: 4px;
}

.agent-list::-webkit-scrollbar-track {
  background: transparent;
}

.agent-list::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.15);
  border-radius: 4px;
}

.agent-list::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.3);
}

.agent-new-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 200ms ease;
  background: transparent;
  border: none;
  flex-shrink: 0;
  white-space: nowrap;
}

.agent-new-btn:hover {
  background: #f3f4f6;
}

.agent-new-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: rgba(236, 72, 153, 0.12);
  color: #ec4899;
}

.agent-new-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.agent-new-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.agent-new-desc {
  font-size: 11px;
  color: var(--text-muted);
  max-width: 100px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.agent-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 200ms ease;
  background: transparent;
  border: none;
  flex-shrink: 0;
  white-space: nowrap;
}

.agent-card:hover {
  background: #f3f4f6;
}

.agent-card.active {
  background: #e8f4fb;
}

.agent-card-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.agent-card-info {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.agent-card-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.agent-card-desc {
  font-size: 11px;
  color: var(--text-muted);
  max-width: 100px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.agent-card-arrow {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.arrow-icon {
  font-size: 18px;
  color: var(--text-muted);
  line-height: 1;
  transition: all 200ms ease;
  cursor: pointer;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
}

.arrow-icon:hover {
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
}

.active-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--lumi-primary);
  flex-shrink: 0;
  margin-right: 2px;
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

.provider-svg-mini {
  background: transparent !important;
}

.provider-svg-mini :deep(svg) {
  width: 16px;
  height: 16px;
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
  background: rgba(20, 126, 188, 0.06);
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
  background: rgba(20, 126, 188, 0.1);
}

.retry-btn:hover {
  background: rgba(244, 63, 94, 0.2);
}

.backend-warning.info .retry-btn:hover {
  background: rgba(20, 126, 188, 0.2);
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
  background: linear-gradient(135deg, rgba(20, 126, 188, 0.08), rgba(20, 126, 188, 0.04));
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  transition: all 250ms ease-in-out;
}

.message-row:hover .user-message {
  background: linear-gradient(135deg, rgba(20, 126, 188, 0.12), rgba(20, 126, 188, 0.06));
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

.interrupted-inline {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  margin-left: 8px;
  background: rgba(251, 191, 36, 0.12);
  border: 1px solid rgba(251, 191, 36, 0.3);
  border-radius: 4px;
  font-size: 11px;
  color: #b45309;
  font-weight: 500;
  vertical-align: middle;
}

.interrupted-only {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 14px;
  background: rgba(251, 191, 36, 0.1);
  border: 1px solid rgba(251, 191, 36, 0.25);
  border-radius: 8px;
  font-size: 12px;
  color: #b45309;
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
  background: rgba(239, 68, 68, 0.08);
  color: #ef4444;
  border-color: rgba(239, 68, 68, 0.2);
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
  background: rgba(20, 126, 188, 0.1);
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
  background: rgba(20, 126, 188, 0.1);
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

.reasoning-section {
  margin-bottom: 10px;
  border: 1px solid rgba(139, 92, 246, 0.2);
  border-radius: var(--radius-md);
  background: rgba(139, 92, 246, 0.04);
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
  color: #8b5cf6;
  transition: background var(--transition-fast);
}

.reasoning-header:hover {
  background: rgba(139, 92, 246, 0.08);
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
  border-left: 4px solid rgba(139, 92, 246, 0.3);
  border-radius: 0 4px 4px 0;
  background: rgba(139, 92, 246, 0.03);
  word-break: break-word;
  max-height: 400px;
  overflow-y: auto;
}

/* 思考过程 markdown 渲染样式 */
.reasoning-markdown :deep(p) {
  margin: 0 0 10px;
  line-height: 1.8;
}

.reasoning-markdown :deep(p:last-child) {
  margin-bottom: 0;
}

/* 【】标题样式 - 关键：让段落标题醒目 */
.reasoning-markdown :deep(p) {
  position: relative;
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
  background: rgba(139, 92, 246, 0.08);
  color: #8b5cf6;
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
  background: rgba(15, 23, 42, 0.75);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.drop-content {
  text-align: center;
  padding: 60px 80px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.95);
  border: 2px dashed rgba(20, 126, 188, 0.4);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15), 0 0 80px rgba(20, 126, 188, 0.1);
  max-width: 560px;
}

.drop-icon-wrapper {
  position: relative;
  display: inline-block;
  margin-bottom: 24px;
}

.drop-main-icon {
  color: var(--lumi-primary, #147ebc);
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
  color: #1e293b;
  margin: 0 0 16px;
  letter-spacing: 0.3px;
}

.drop-desc {
  font-size: 13px;
  color: #64748b;
  margin: 0 0 10px;
  line-height: 1.7;
  word-break: break-all;
}

.drop-hint {
  font-size: 12px;
  color: #94a3b8;
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

/* Create Agent Dialog */
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

.dialog-btn.delete {
  color: var(--lumi-accent, #ef4444);
  background: rgba(239, 68, 68, 0.08);
}

.dialog-btn.delete:hover {
  background: rgba(239, 68, 68, 0.18);
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
  0% { background: rgba(20, 126, 188, 0.2); }
  100% { background: transparent; }
}
</style>

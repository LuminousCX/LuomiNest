<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
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
  Download,
  Trash2,
  Quote,
  X,
  Volume2,
} from 'lucide-vue-next'
import FileUpload from '../../components/FileUpload.vue'
import SuggestedQuestions from '../../components/SuggestedQuestions.vue'
import SkillsPicker from '../common/SkillsPicker.vue'
import LumiEmptyState from '../common/LumiEmptyState.vue'
import { renderMarkdown } from '../../utils/markdown'
import { getFileIcon } from '../../utils/file'
import type { ChatMessage, ProviderLogo, AgentProfile } from '../../types'

const props = defineProps<{
  messages: ChatMessage[]
  isLoadingCurrentConv: boolean
  isStreaming: boolean
  isBackendReady: boolean
  hasProvider: boolean
  currentModel: string
  currentProvider: string
  currentProviderLogo: ProviderLogo
  availableModelOptions: { providerId: string; providerName: string; providerLogo: ProviderLogo; modelId: string; modelName: string }[]
  showModelDropdown: boolean
  inputText: string
  canSend: boolean
  isUploading: boolean
  quotedMessage: ChatMessage | null
  contextUsage: { promptTokens?: number; completionTokens?: number; totalTokens?: number } | null
  contextPercent: number
  copiedId: string | null
  showReasoning: Record<string, boolean>
  currentSuggestionMessageId: string | null
  isTtsSpeaking: boolean
  ttsSpeakingMsgId: string | null
  agent: AgentProfile | null
  selectedSkillIds: string[]
}>()

const emit = defineEmits<{
  'check-backend': []
  'go-settings': []
  'scroll-to-bottom': [force?: boolean]
  'toggle-reasoning': [msgId: string]
  'copy-message': [msgId: string, content: string]
  'quote-message': [msg: ChatMessage]
  'tts-speak': [content: string, msgId: string]
  'tts-stop': []
  regenerate: [messageId: string]
  'delete-message': [messageId: string]
  'go-back-to-start': [msg: ChatMessage]
  'switch-version': [messageId: string, versionIndex: number]
  'suggestion-click': [question: string]
  'update:inputText': [value: string]
  send: []
  cancel: []
  'toggle-model-dropdown': []
  'select-model': [providerId: string, modelId: string]
  'clear-quote': []
  'file-preview': [file: { name: string; type?: string; content?: string }]
  'update:selectedSkillIds': [ids: string[]]
}>()

const messagesContainer = ref<HTMLElement | null>(null)
const textareaRef = ref<HTMLTextAreaElement | null>(null)
const fileUploadRef = ref<InstanceType<typeof FileUpload> | null>(null)
const reasoningScrollRefs = ref<HTMLElement | HTMLElement[] | null>(null)
const isNearBottom = ref(true)
const SCROLL_BOTTOM_THRESHOLD = 120
const showScrollToBottomBtn = ref(false)
let resizeObserver: ResizeObserver | null = null

const inputTextModel = computed<string>({
  get: () => props.inputText,
  set: (value) => emit('update:inputText', value),
})

const scrollToBottom = (force = false) => {
  if (!messagesContainer.value) return
  if (!force && !isNearBottom.value) return
  messagesContainer.value.scrollTo({
    top: messagesContainer.value.scrollHeight,
    behavior: force ? 'auto' : 'smooth'
  })
}

const scrollToSearchResult = (keyword: string) => {
  if (!messagesContainer.value) return
  const q = keyword.toLowerCase()
  const msgElements = messagesContainer.value.querySelectorAll('.message-row')
  for (const el of msgElements) {
    const text = el.textContent?.toLowerCase() || ''
    if (text.includes(q)) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      el.classList.add('search-highlight')
      setTimeout(() => el.classList.remove('search-highlight'), 2000)
      return
    }
  }
  scrollToBottom(true)
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

const handleMessagesScroll = () => {
  if (!messagesContainer.value) return
  const { scrollTop, scrollHeight, clientHeight } = messagesContainer.value
  const distanceFromBottom = scrollHeight - scrollTop - clientHeight
  isNearBottom.value = distanceFromBottom < SCROLL_BOTTOM_THRESHOLD
  showScrollToBottomBtn.value = !isNearBottom.value && props.messages.length > 0
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

const focusTextarea = () => {
  if (textareaRef.value) textareaRef.value.focus()
}

const beautifyThinking = (text: string): string => {
  if (!text || text.length < 20) return text || ''

  let result = text

  if (/【[^】]+】/.test(result)) {
    result = result.replace(/\s*【/g, '\n\n【')
    result = result.replace(/】\s*/g, '】\n')
    result = result.replace(/\n{3,}/g, '\n\n')
    return result.trim()
  }

  if (/\n\n/.test(result)) return result

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

  const paragraphs: string[] = []
  let para = ''
  let count = 0

  for (const s of sentences) {
    if (para) para += ' '
    para += s
    count++

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

const renderReasoningMarkdown = (text: string): string => {
  if (!text) return ''
  return renderMarkdown(beautifyThinking(text))
}

const openFilePreview = (file: { name: string; type?: string; content?: string }) => {
  emit('file-preview', { name: file.name, type: file.type, content: file.content })
}

const getVersionIndex = (msg: ChatMessage): number => {
  if (!msg.versions || msg.versions.length === 0) return 0
  return msg.currentVersion ?? 0
}

const isLastAssistantMessage = (msgId: string) => {
  const msgs = props.messages
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

watch(() => props.messages, async (msgs) => {
  for (const msg of msgs) {
    if (msg.role !== 'assistant') continue
    if (msg.content && msg.content.length > 0 && props.showReasoning[msg.id] === undefined) {
      emit('toggle-reasoning', msg.id)
    }
  }
  await nextTick()
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

watch(() => props.isLoadingCurrentConv, (loading) => {
  if (loading) {
    isNearBottom.value = true
  }
})

onMounted(() => {
  nextTick(() => setupResizeObserver())
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
})

defineExpose({
  scrollToBottom,
  scrollToSearchResult,
  resetTextareaHeight,
  autoResize,
  focusTextarea,
})
</script>

<template>
  <div class="chat-agent-mode">
    <div v-if="!isBackendReady" class="backend-warning">
      <div class="warning-content">
        <AlertTriangle :size="20" />
        <div class="warning-text">
          <p class="warning-title">后端服务未连接</p>
          <p class="warning-desc">请确保 LuomiNest 后端服务已启动 (端口 18000)</p>
        </div>
        <button class="retry-btn" @click="emit('check-backend')">
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
        <button class="retry-btn" @click="emit('go-settings')">
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
                <div class="message-sender" v-if="msg.role === 'assistant'">{{ agent?.name || 'LuomiNest' }}</div>
                <div
                  v-if="msg.role === 'assistant' && (msg.reasoningContent !== undefined || (!msg.done && msg.id === messages[messages.length - 1].id && !msg.content))"
                  class="reasoning-section"
                >
                  <div class="reasoning-header" @click="emit('toggle-reasoning', msg.id)">
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

                <!-- AI消息操作栏 -->
                <div v-if="msg.role === 'assistant' && msg.done" class="assistant-msg-actions">
                  <div v-if="msg.versions && msg.versions.length > 1" class="version-nav">
                    <button
                      class="v-btn"
                      :disabled="getVersionIndex(msg) <= 0"
                      @click="emit('switch-version', msg.id, getVersionIndex(msg) - 1)"
                      title="上一版本"
                    >
                      <ChevronLeft :size="14" />
                    </button>
                    <span class="v-label">{{ getVersionIndex(msg) + 1 }} / {{ msg.versions.length }}</span>
                    <button
                      class="v-btn"
                      :disabled="getVersionIndex(msg) >= msg.versions.length - 1"
                      @click="emit('switch-version', msg.id, getVersionIndex(msg) + 1)"
                      title="下一版本"
                    >
                      <ChevronRight :size="14" />
                    </button>
                  </div>
                  <button class="u-btn" title="复制" @click="emit('copy-message', msg.id, msg.content)">
                    <Check v-if="copiedId === msg.id" :size="14" />
                    <Copy v-else :size="14" />
                  </button>
                  <button class="u-btn" title="引用" @click="emit('quote-message', msg)">
                    <Quote :size="14" />
                  </button>
                  <button
                    class="u-btn"
                    :title="isTtsSpeaking && ttsSpeakingMsgId === msg.id ? '停止朗读' : '朗读'"
                    @click="isTtsSpeaking && ttsSpeakingMsgId === msg.id ? emit('tts-stop') : emit('tts-speak', msg.content, msg.id)"
                  >
                    <div v-if="isTtsSpeaking && ttsSpeakingMsgId === msg.id" class="tts-bars">
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
                    @click="emit('regenerate', msg.id)"
                  >
                    <RotateCcw :size="14" />
                  </button>
                  <button class="u-btn u-btn-danger" title="删除" @click="emit('delete-message', msg.id)">
                    <Trash2 :size="14" />
                  </button>
                </div>

                <!-- 推荐问题 -->
                <SuggestedQuestions
                  v-if="msg.role === 'assistant' && msg.id === currentSuggestionMessageId && msg.suggestedQuestions && msg.suggestedQuestions.length > 0"
                  :questions="msg.suggestedQuestions"
                  @select="emit('suggestion-click', $event)"
                />

                <!-- 用户消息 -->
                <div v-if="msg.role === 'user'" class="user-msg-layout">
                  <div class="user-msg-btns">
                    <button class="u-btn u-btn-hover" title="复制" @click="emit('copy-message', msg.id, msg.content)">
                      <Check v-if="copiedId === msg.id" :size="14" />
                      <Copy v-else :size="14" />
                    </button>
                    <button class="u-btn u-btn-hover" title="引用" @click="emit('quote-message', msg)">
                      <Quote :size="14" />
                    </button>
                    <button class="u-btn u-btn-hover u-btn-danger" title="删除" @click="emit('delete-message', msg.id)">
                      <Trash2 :size="14" />
                    </button>
                    <button
                      class="u-btn"
                      title="回退到本轮对话发起前"
                      @click="emit('go-back-to-start', msg)"
                    >
                      <Undo2 :size="14" />
                    </button>
                  </div>
                  <div class="message-content user-message">
                    <div v-if="msg.quote && (msg.quote.content || (msg.quote.id))" class="message-quote-block" :class="msg.quote.role">
                      <Quote :size="12" class="quote-block-icon" />
                      <div class="quote-block-content">
                        <span class="quote-block-label">{{ msg.quote.role === 'assistant' ? '助手' : '用户' }}</span>
                        <span class="quote-block-text line-clamp-3">
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
                        <component :is="getFileIcon(file.name)" :size="16" />
                        <span>{{ file.name }}</span>
                        <Download :size="14" class="download-icon" />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </TransitionGroup>

          <LumiEmptyState
            v-if="messages.length === 0 && !isLoadingCurrentConv"
            :icon="Bot"
            title="选择一个Agent开始对话"
            description="或直接在下方输入框中提问"
          >
            <template #action>
              <div class="empty-quick-actions">
                <button class="quick-action" @click="inputTextModel = '你好，请介绍一下你自己'">打个招呼</button>
                <button class="quick-action" @click="inputTextModel = '帮我写一段 Python 代码'">写段代码</button>
                <button class="quick-action" @click="inputTextModel = '解释一下什么是大语言模型'">了解 LLM</button>
              </div>
            </template>
          </LumiEmptyState>
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
        <SkillsPicker
          :selected-ids="selectedSkillIds"
          class="input-skills-picker"
          @update:selected-ids="emit('update:selectedSkillIds', $event)"
        />
        <div v-if="quotedMessage" class="quote-preview">
          <Quote :size="14" class="quote-preview-icon" />
          <div class="quote-preview-content">
            <span class="quote-preview-label">{{ quotedMessage.role === 'assistant' ? '助手' : '用户' }}</span>
            <span class="quote-preview-text">{{ quotedMessage.content.slice(0, 80) }}{{ quotedMessage.content.length > 80 ? '...' : '' }}</span>
          </div>
          <button class="quote-preview-cancel" @click="emit('clear-quote')">
            <X :size="14" />
          </button>
        </div>
        <textarea
          ref="textareaRef"
          v-model="inputTextModel"
          placeholder="可以描述任务或提问任何问题"
          rows="1"
          class="chat-input"
          :disabled="!isBackendReady"
          @keydown.enter.exact.prevent="emit('send')"
          @input="autoResize"
        ></textarea>
        <div class="input-toolbar">
          <div class="toolbar-left">
            <div class="model-dropdown-container">
              <button class="tool-btn" title="选择模型" @click.stop="emit('toggle-model-dropdown')">
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
                      @click="emit('select-model', opt.providerId, opt.modelId)"
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
              @click="emit('cancel')"
            >
              <Square :size="16" />
            </button>
            <button
              v-else
              :class="['send-btn', { disabled: !canSend }]"
              title="发送"
              @click="emit('send')"
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
</template>

<style scoped>
.chat-agent-mode {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}

.backend-warning {
  margin: var(--space-2) var(--space-6);
  padding: var(--space-3) var(--space-4);
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
  background: var(--lumi-brand-subtle);
}

.backend-warning.info::before {
  background: var(--lumi-brand);
}

.warning-content {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  color: var(--lumi-accent);
}

.backend-warning.info .warning-content {
  color: var(--lumi-brand);
}

.warning-text {
  flex: 1;
}

.warning-title {
  font-size: var(--text-base);
  font-weight: 600;
}

.warning-desc {
  font-size: var(--text-xs);
  opacity: 0.8;
  margin-top: 2px;
}

.retry-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: 6px var(--space-3);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--lumi-accent);
  background: var(--lumi-accent-light);
  transition: background-color var(--transition-fast), color var(--transition-fast);
  flex-shrink: 0;
}

.backend-warning.info .retry-btn {
  color: var(--lumi-brand);
  background: var(--lumi-brand-light);
}

.retry-btn:hover {
  background: var(--lumi-accent-border);
}

.backend-warning.info .retry-btn:hover {
  background: var(--lumi-brand-border);
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
  padding: var(--space-6);
}

.messages-container {
  max-width: 800px;
  margin: 0 auto;
}

.message-row {
  margin-bottom: var(--space-6);
  animation: msg-slide-in var(--duration-slow) var(--ease-out-expo) both;
  display: flex;
  gap: var(--space-3);
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
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform var(--duration-normal) var(--ease-in-out);
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
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: var(--space-1);
}

.message-content {
  font-size: var(--text-md);
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
  padding: var(--space-3) 18px;
  border-radius: var(--radius-lg);
  border-top-right-radius: 4px;
  background: linear-gradient(135deg, var(--lumi-brand-light), var(--lumi-brand-subtle));
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  transition: background-color var(--duration-normal) var(--ease-in-out), color var(--duration-normal) var(--ease-in-out);
}

.message-row:hover .user-message {
  background: linear-gradient(135deg, var(--lumi-brand-glow), var(--lumi-brand-light));
}

.message-files {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.message-file-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: var(--workspace-card);
  border: 1px solid var(--divider-soft);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  color: var(--text-secondary);
  cursor: pointer;
  transition: background-color var(--duration-leave), color var(--duration-leave), border-color var(--duration-leave);
}

.message-file-item:hover {
  background: var(--lumi-brand-bg);
  border-color: var(--lumi-brand);
  color: var(--lumi-brand);
}

.download-icon {
  opacity: 0.6;
}

.message-file-item:hover .download-icon {
  opacity: 1;
}

.message-quote-block {
  display: flex;
  gap: 6px;
  padding: var(--space-2) 10px;
  margin-bottom: var(--space-2);
  border-left: 3px solid var(--lumi-brand);
  border-radius: var(--radius-xs);
  background: var(--lumi-brand-light);
}

.message-quote-block.assistant {
  border-left-color: var(--lumi-brand);
}

.message-quote-block.user {
  border-left-color: var(--lumi-emerald);
}

.quote-block-icon {
  color: var(--lumi-brand-border);
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
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--lumi-brand);
}

.quote-block-text {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  word-break: break-word;
}

.quote-block-empty {
  color: var(--overlay-subtle);
  font-style: italic;
}

.quote-preview {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--overlay-subtle);
  background: var(--lumi-brand-subtle);
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
  font-size: var(--text-xs);
  color: var(--overlay-bg);
}

.quote-preview-text {
  font-size: var(--text-sm);
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
  gap: var(--space-1);
  padding: 2px var(--space-2);
  margin-left: var(--space-2);
  background: var(--lumi-amber-soft);
  border: 1px solid var(--lumi-amber-border);
  border-radius: 4px;
  font-size: var(--text-xs);
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
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  color: var(--lumi-amber-dark);
  font-weight: 500;
}

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
  width: var(--space-6);
  height: var(--space-6);
  border-radius: var(--radius-sm);
  background: transparent;
  border: 1px solid transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: background-color var(--transition-fast), color var(--transition-fast), border-color var(--transition-fast);
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
  width: var(--space-4);
  height: var(--space-4);
}

.tts-bar {
  width: 3px;
  border-radius: 1.5px;
  background: var(--lumi-indigo);
  animation: tts-bar-bounce var(--duration-enter) var(--ease-in-out) infinite alternate;
  animation-delay: var(--d);
}

@keyframes tts-bar-bounce {
  0% { height: var(--space-1); }
  100% { height: var(--h); }
}

.u-btn-hover {
  opacity: 0;
  pointer-events: none;
}

.user-msg-layout:hover .u-btn-hover {
  opacity: 1;
  pointer-events: auto;
}

.assistant-msg-actions {
  display: flex;
  gap: 2px;
  margin-top: var(--space-1);
  align-items: center;
}

.version-nav {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  margin-right: 6px;
  padding: 0 var(--space-1);
  border-radius: var(--radius-sm);
  background: var(--workspace-hover);
  border: 1px solid var(--workspace-border);
}

.v-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: var(--space-5);
  height: var(--space-5);
  border-radius: 3px;
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 0;
  transition: background-color var(--transition-fast), color var(--transition-fast);
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
  font-size: var(--text-xs);
  color: var(--text-muted);
  min-width: var(--space-7);
  text-align: center;
  user-select: none;
}

.streaming-indicator {
  display: inline-flex;
  align-items: center;
  padding: var(--space-1) 0;
}

.streaming-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  background: var(--lumi-brand);
  animation: streaming-pulse 1.2s var(--ease-in-out) infinite;
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
  z-index: var(--z-sticky);
}

.conv-loading-content {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: var(--space-3) var(--space-6);
  border-radius: var(--radius-lg);
  background: var(--workspace-card);
  box-shadow: var(--shadow-md);
  color: var(--text-secondary);
  font-size: var(--text-md);
}

.conv-loading-fade-enter-active {
  animation: conv-loading-in var(--duration-normal) var(--ease-out-expo);
}

.conv-loading-fade-leave-active {
  animation: conv-loading-in var(--duration-leave) var(--ease-out-expo) reverse;
}

@keyframes conv-loading-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

.scroll-to-bottom-btn {
  position: absolute;
  bottom: var(--space-4);
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
  z-index: var(--z-sticky);
  transition: background-color var(--duration-normal) var(--ease-in-out), color var(--duration-normal) var(--ease-in-out), box-shadow var(--duration-normal) var(--ease-in-out), opacity var(--duration-normal) var(--ease-in-out);
}

.scroll-to-bottom-btn:hover {
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
  box-shadow: var(--shadow-lg);
  transform: translateX(-50%) scale(1.08);
}

.scroll-btn-fade-enter-active {
  animation: scroll-btn-in var(--duration-normal) var(--ease-out-expo);
}

.scroll-btn-fade-leave-active {
  animation: scroll-btn-in var(--duration-leave) var(--ease-out-expo) reverse;
}

@keyframes scroll-btn-in {
  from { opacity: 0; transform: translateX(-50%) translateY(8px); }
  to { opacity: 1; transform: translateX(-50%) translateY(0); }
}

.empty-quick-actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  justify-content: center;
}

.quick-action {
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-full);
  font-size: var(--text-base);
  color: var(--text-secondary);
  background: var(--workspace-card);
  box-shadow: var(--shadow-xs);
  transition: background-color var(--duration-normal) var(--ease-in-out), color var(--duration-normal) var(--ease-in-out), box-shadow var(--duration-normal) var(--ease-in-out);
  cursor: pointer;
}

.quick-action:hover {
  color: var(--lumi-brand);
  background: var(--lumi-brand-light);
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.input-area {
  padding: var(--space-3) var(--space-6) var(--space-4);
  flex-shrink: 0;
  position: relative;
  z-index: var(--z-dropdown);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.input-wrapper {
  background: var(--workspace-card);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-sm), var(--shadow-inset);
  overflow: visible;
  transition: box-shadow var(--duration-normal) var(--ease-in-out), background-color var(--duration-normal) var(--ease-in-out);
}

.input-skills-picker {
  padding: var(--space-2) var(--space-4) 0;
}

.input-wrapper:focus-within {
  box-shadow: 0 0 0 2px var(--lumi-brand-glow), var(--shadow-lg);
}

.chat-input {
  width: 100%;
  padding: 14px var(--space-5);
  font-size: var(--text-md);
  resize: none;
  min-height: var(--space-9);
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
  padding: var(--space-2) var(--space-4) var(--space-3);
  position: relative;
}

.input-toolbar::before {
  content: '';
  position: absolute;
  top: 0;
  left: var(--space-4);
  right: var(--space-4);
  height: 1px;
  background: var(--divider-soft);
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.tool-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  color: var(--text-muted);
  cursor: pointer;
  transition: background-color var(--duration-normal) var(--ease-in-out), color var(--duration-normal) var(--ease-in-out);
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
  bottom: calc(100% + var(--space-2));
  left: 0;
  width: 280px;
  background: var(--workspace-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  z-index: var(--z-modal);
  overflow: hidden;
}

.dropdown-header {
  padding: 10px 14px;
  font-size: var(--text-sm);
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
  padding: var(--space-1);
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: var(--space-2) 10px;
  border-radius: var(--radius-md);
  text-align: left;
  transition: background-color var(--duration-normal) var(--ease-in-out), color var(--duration-normal) var(--ease-in-out);
}

.dropdown-item:hover {
  background: var(--workspace-hover);
}

.dropdown-item.active {
  background: var(--lumi-brand-light);
}

.dropdown-item-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.dropdown-item-model {
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dropdown-item-provider {
  font-size: var(--text-xs);
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dropdown-item.active .dropdown-item-model {
  color: var(--lumi-brand);
}

.dropdown-empty {
  padding: var(--space-5) 14px;
  text-align: center;
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.dropdown-fade-enter-active {
  animation: dropdown-in var(--duration-leave) var(--ease-out-expo);
}

.dropdown-fade-leave-active {
  animation: dropdown-in var(--duration-fast) var(--ease-out-expo) reverse;
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
  background: var(--lumi-brand);
  color: var(--text-inverse);
  cursor: pointer;
  transition: background-color var(--duration-normal) var(--ease-in-out), color var(--duration-normal) var(--ease-in-out), box-shadow var(--duration-normal) var(--ease-in-out);
  margin-left: var(--space-1);
}

.send-btn:hover {
  background: var(--lumi-brand-hover);
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
  margin-top: var(--space-2);
}

.input-footer span {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.markdown-body {
  word-break: break-word;
}

.markdown-body :deep(p) {
  margin: 0 0 var(--space-3);
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
  margin: var(--space-5) 0 10px;
  line-height: 1.4;
}

.markdown-body :deep(h1) { font-size: var(--text-3xl); }
.markdown-body :deep(h2) { font-size: var(--text-2xl); border-bottom: 1px solid var(--border-light); padding-bottom: 6px; }
.markdown-body :deep(h3) { font-size: var(--text-xl); }
.markdown-body :deep(h4) { font-size: var(--text-lg); }

.markdown-body :deep(h1:first-child),
.markdown-body :deep(h2:first-child),
.markdown-body :deep(h3:first-child) {
  margin-top: 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: var(--space-2) 0;
  padding-left: var(--space-6);
}

.markdown-body :deep(li) {
  margin: var(--space-1) 0;
  line-height: 1.7;
}

.markdown-body :deep(li::marker) {
  color: var(--lumi-brand);
}

.markdown-body :deep(blockquote) {
  margin: var(--space-3) 0;
  padding: var(--space-2) var(--space-4);
  border-left: 3px solid var(--lumi-brand);
  background: var(--lumi-brand-light);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  color: var(--text-secondary);
}

.markdown-body :deep(blockquote p) {
  margin: 0;
}

.markdown-body :deep(code) {
  padding: 2px 6px;
  border-radius: 4px;
  font-size: var(--text-base);
  background: var(--workspace-panel);
  color: var(--lumi-brand);
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
}

.markdown-body :deep(pre) {
  margin: var(--space-3) 0;
  padding: var(--space-4);
  border-radius: var(--radius-md);
  background: var(--text);
  overflow-x: auto;
  position: relative;
}

.markdown-body :deep(pre code) {
  padding: 0;
  background: none;
  color: var(--border-light);
  font-size: var(--text-base);
  line-height: 1.6;
}

.markdown-body :deep(table) {
  width: 100%;
  margin: var(--space-3) 0;
  border-collapse: collapse;
  font-size: var(--text-base);
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--workspace-border);
  text-align: left;
}

.markdown-body :deep(th) {
  background: var(--workspace-panel);
  font-weight: 600;
}

.markdown-body :deep(tr:nth-child(even)) {
  background: var(--lumi-brand-light);
}

.markdown-body :deep(hr) {
  margin: var(--space-4) 0;
  border: none;
  height: 1px;
  background: var(--workspace-border);
}

.markdown-body :deep(a) {
  color: var(--lumi-brand);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.markdown-body :deep(a:hover) {
  color: var(--lumi-brand-hover);
}

.markdown-body :deep(img) {
  max-width: 100%;
  border-radius: var(--radius-md);
  margin: var(--space-2) 0;
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
  height: var(--space-1);
  border-radius: 2px;
  background: var(--workspace-panel);
  overflow: hidden;
  position: relative;
}

.context-bar-fill {
  height: 100%;
  border-radius: 2px;
  background: var(--lumi-brand);
  transition: width var(--duration-enter) var(--ease-in-out), background var(--duration-normal) var(--ease-in-out);
}

.context-bar-fill.warn {
  background: var(--lumi-warning);
}

.context-bar-fill.danger {
  background: var(--lumi-accent);
}

.context-text {
  font-size: var(--text-xs);
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
  padding: var(--space-2) var(--space-3);
  cursor: pointer;
  user-select: none;
  font-size: var(--text-sm);
  color: var(--task-purple);
  transition: background var(--transition-fast);
}

.reasoning-header:hover {
  background: var(--task-purple-soft);
}

.reasoning-chevron {
  margin-left: auto;
  transition: transform var(--duration-leave) var(--ease-default);
}

.reasoning-chevron.rotated {
  transform: rotate(-90deg);
}

.reasoning-content {
  padding: var(--space-3) var(--space-4);
  font-size: var(--text-base);
  line-height: 1.6;
  color: var(--text-muted);
  border-top: 1px solid var(--divider-soft);
  border-left: var(--space-1) solid var(--task-purple-border);
  border-radius: 0 4px 4px 0;
  background: var(--task-purple-soft);
  word-break: break-word;
  max-height: 400px;
  overflow-y: auto;
}

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
  padding: 1px var(--space-1);
  border-radius: 3px;
  font-size: var(--text-xs);
  background: var(--task-purple-soft);
  color: var(--task-purple);
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
}

.reasoning-markdown :deep(ul),
.reasoning-markdown :deep(ol) {
  margin: var(--space-1) 0 10px;
  padding-left: var(--space-5);
}

.reasoning-markdown :deep(li) {
  margin: 2px 0;
  line-height: 1.7;
}

.msg-appear-enter-active {
  transition: opacity var(--duration-enter) var(--ease-out-expo), transform var(--duration-enter) var(--ease-out-expo);
}

.msg-appear-enter-from {
  opacity: 0;
  transform: translateY(16px) scale(0.97);
}

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
  width: var(--space-4);
  height: var(--space-4);
}

.search-highlight {
  animation: search-highlight-pulse var(--duration-slow) var(--ease-out-expo);
}

@keyframes search-highlight-pulse {
  0% { background: var(--lumi-brand-border); }
  100% { background: transparent; }
}
</style>

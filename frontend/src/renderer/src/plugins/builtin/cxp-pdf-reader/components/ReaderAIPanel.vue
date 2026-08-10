<script setup lang="ts">
/**
 * ReaderAIPanel — PDF 阅读器 AI 助手面板。
 *
 * 三个 Tab：
 * 1. 总结 — 调用 summarizeDocument 显示摘要 + 关键点
 * 2. 翻译 — 选择目标语言后调用 translateDocument
 * 3. 问答 — 聊天界面，调用 chatWithDocument，支持历史上下文
 *
 * 消息渲染使用主项目 utils/markdown 的 renderMarkdown（marked + DOMPurify）。
 */
import { ref, computed, watch, nextTick } from 'vue'
import {
  Sparkles,
  Languages,
  MessageSquare,
  Send,
  Loader2,
  AlertCircle,
  FileText,
  ListChecks,
  PanelRightClose,
  RotateCcw,
} from 'lucide-vue-next'
import { useToast } from '../../../../composables/useToast'
import { renderMarkdown } from '../../../../utils/markdown'
import { cxPdfApi } from '../services/pdfApi'
import type { CxPdfChatMessage } from '../services/pdfApi'

const props = defineProps<{
  fileId: string
  isOpen: boolean
  currentPage: number
}>()

const emit = defineEmits<{
  toggle: []
}>()

const toast = useToast()

// ---------------------------------------------------------------------------
// Tab 切换
// ---------------------------------------------------------------------------

type TabId = 'summary' | 'translate' | 'chat'
const activeTab = ref<TabId>('summary')

const tabs = [
  { id: 'summary' as const, label: '总结', icon: Sparkles },
  { id: 'translate' as const, label: '翻译', icon: Languages },
  { id: 'chat' as const, label: '问答', icon: MessageSquare },
]

// ---------------------------------------------------------------------------
// 总结 Tab
// ---------------------------------------------------------------------------

interface SummaryState {
  loading: boolean
  error: string | null
  summary: string
  keyPoints: string[]
}

const summaryState = ref<SummaryState>({
  loading: false,
  error: null,
  summary: '',
  keyPoints: [],
})

const handleSummarize = async () => {
  if (!props.fileId) return
  summaryState.value = { loading: true, error: null, summary: '', keyPoints: [] }
  try {
    const result = await cxPdfApi.summarizeDocument(props.fileId)
    summaryState.value = {
      loading: false,
      error: null,
      summary: result.summary ?? '',
      keyPoints: Array.isArray(result.keyPoints) ? result.keyPoints : [],
    }
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    summaryState.value = {
      loading: false,
      error: `总结失败：${msg}`,
      summary: '',
      keyPoints: [],
    }
    toast.error(`AI 总结失败：${msg}`)
  }
}

const handleResetSummary = () => {
  summaryState.value = { loading: false, error: null, summary: '', keyPoints: [] }
}

const summaryHtml = computed(() => renderMarkdown(summaryState.value.summary))

// ---------------------------------------------------------------------------
// 翻译 Tab
// ---------------------------------------------------------------------------

const TRANSLATE_LANGS = [
  { label: '中文', value: 'zh' },
  { label: '英文', value: 'en' },
  { label: '日文', value: 'ja' },
  { label: '韩文', value: 'ko' },
]

interface TranslateState {
  loading: boolean
  error: string | null
  targetLang: string
  pageRange: string
  translation: string
}

const translateState = ref<TranslateState>({
  loading: false,
  error: null,
  targetLang: 'zh',
  pageRange: '',
  translation: '',
})

const handleTranslate = async () => {
  if (!props.fileId) return
  translateState.value = {
    ...translateState.value,
    loading: true,
    error: null,
    translation: '',
  }
  try {
    const result = await cxPdfApi.translateDocument(
      props.fileId,
      translateState.value.targetLang,
      translateState.value.pageRange.trim() || undefined,
    )
    translateState.value = {
      ...translateState.value,
      loading: false,
      error: null,
      translation: result.translation ?? '',
    }
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    translateState.value = {
      ...translateState.value,
      loading: false,
      error: `翻译失败：${msg}`,
      translation: '',
    }
    toast.error(`AI 翻译失败：${msg}`)
  }
}

const handleResetTranslate = () => {
  translateState.value = {
    ...translateState.value,
    loading: false,
    error: null,
    translation: '',
  }
}

const translationHtml = computed(() => renderMarkdown(translateState.value.translation))

// ---------------------------------------------------------------------------
// 问答 Tab
// ---------------------------------------------------------------------------

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  error?: boolean
}

const chatMessages = ref<ChatMessage[]>([])
const chatInput = ref('')
const chatLoading = ref(false)
const chatScrollRef = ref<HTMLDivElement | null>(null)

const scrollToBottom = async () => {
  await nextTick()
  if (chatScrollRef.value) {
    chatScrollRef.value.scrollTop = chatScrollRef.value.scrollHeight
  }
}

const handleSendMessage = async () => {
  const question = chatInput.value.trim()
  if (!question || !props.fileId || chatLoading.value) return

  // 构造历史上下文（仅保留最近 6 条消息）
  const history: CxPdfChatMessage[] = chatMessages.value
    .filter((m) => !m.error)
    .slice(-6)
    .map((m) => ({ role: m.role, content: m.content }))

  // 添加用户消息
  const userMsg: ChatMessage = {
    id: `msg-${Date.now()}-u`,
    role: 'user',
    content: question,
  }
  chatMessages.value.push(userMsg)
  chatInput.value = ''
  chatLoading.value = true
  await scrollToBottom()

  try {
    const result = await cxPdfApi.chatWithDocument(props.fileId, question, history)
    const assistantMsg: ChatMessage = {
      id: `msg-${Date.now()}-a`,
      role: 'assistant',
      content: result.answer ?? '',
    }
    chatMessages.value.push(assistantMsg)
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    const errorMsg: ChatMessage = {
      id: `msg-${Date.now()}-e`,
      role: 'assistant',
      content: `问答失败：${msg}`,
      error: true,
    }
    chatMessages.value.push(errorMsg)
    toast.error(`AI 问答失败：${msg}`)
  } finally {
    chatLoading.value = false
    await scrollToBottom()
  }
}

const handleChatKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    void handleSendMessage()
  }
}

const handleClearChat = () => {
  chatMessages.value = []
}

// 渲染消息 Markdown（仅对非错误消息）
const renderMessage = (msg: ChatMessage): string => {
  if (msg.error) return ''
  return renderMarkdown(msg.content)
}

// ---------------------------------------------------------------------------
// 监听 fileId 变化重置状态
// ---------------------------------------------------------------------------

watch(
  () => props.fileId,
  () => {
    handleResetSummary()
    handleResetTranslate()
    chatMessages.value = []
    chatInput.value = ''
    chatLoading.value = false
  },
)
</script>

<template>
  <Transition name="slide-side-right">
    <aside v-if="isOpen" class="reader-ai-panel">
      <!-- 面板头 -->
      <div class="ai-header">
        <div class="header-title">
          <Sparkles :size="16" />
          <span>AI 助手</span>
        </div>
        <button
          class="header-close"
          title="折叠 AI 面板"
          @click="emit('toggle')"
        >
          <PanelRightClose :size="16" />
        </button>
      </div>

      <!-- Tab 切换 -->
      <div class="ai-tabs">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          class="ai-tab"
          :class="{ active: activeTab === tab.id }"
          @click="activeTab = tab.id"
        >
          <component :is="tab.icon" :size="14" />
          <span>{{ tab.label }}</span>
        </button>
      </div>

      <!-- Tab 内容 -->
      <div class="ai-body">
        <!-- 总结 Tab -->
        <div v-show="activeTab === 'summary'" class="tab-pane">
          <div class="pane-actions">
            <button
              class="action-btn primary"
              :disabled="summaryState.loading"
              @click="handleSummarize"
            >
              <Sparkles :size="14" />
              <span>总结全文</span>
            </button>
            <button
              v-if="summaryState.summary || summaryState.error"
              class="action-btn"
              title="重置"
              @click="handleResetSummary"
            >
              <RotateCcw :size="14" />
            </button>
          </div>

          <div v-if="summaryState.loading" class="pane-loading">
            <Loader2 :size="20" class="loading-spin" />
            <span>AI 正在总结文档...</span>
          </div>

          <div v-else-if="summaryState.error" class="pane-error">
            <AlertCircle :size="20" />
            <p>{{ summaryState.error }}</p>
          </div>

          <div v-else-if="summaryState.summary" class="pane-result">
            <div class="result-section">
              <div class="section-title">
                <FileText :size="14" />
                <span>摘要</span>
              </div>
              <div class="markdown-content" v-html="summaryHtml" />
            </div>

            <div v-if="summaryState.keyPoints.length > 0" class="result-section">
              <div class="section-title">
                <ListChecks :size="14" />
                <span>关键点</span>
              </div>
              <ul class="key-points">
                <li v-for="(point, idx) in summaryState.keyPoints" :key="idx">
                  {{ point }}
                </li>
              </ul>
            </div>
          </div>

          <div v-else class="pane-empty">
            <Sparkles :size="32" class="empty-icon" />
            <p class="empty-text">点击"总结全文"按钮</p>
            <p class="empty-hint">AI 将生成文档摘要与关键点</p>
          </div>
        </div>

        <!-- 翻译 Tab -->
        <div v-show="activeTab === 'translate'" class="tab-pane">
          <div class="pane-form">
            <label class="form-row">
              <span class="form-label">目标语言</span>
              <select v-model="translateState.targetLang" class="form-select">
                <option v-for="lang in TRANSLATE_LANGS" :key="lang.value" :value="lang.value">
                  {{ lang.label }}
                </option>
              </select>
            </label>
            <label class="form-row">
              <span class="form-label">页码范围（可选）</span>
              <input
                v-model="translateState.pageRange"
                type="text"
                class="form-input"
                placeholder="如：1-5 或 1,3,5"
              />
            </label>
            <div class="pane-actions">
              <button
                class="action-btn primary"
                :disabled="translateState.loading"
                @click="handleTranslate"
              >
                <Languages :size="14" />
                <span>翻译</span>
              </button>
              <button
                v-if="translateState.translation || translateState.error"
                class="action-btn"
                title="重置"
                @click="handleResetTranslate"
              >
                <RotateCcw :size="14" />
              </button>
            </div>
          </div>

          <div v-if="translateState.loading" class="pane-loading">
            <Loader2 :size="20" class="loading-spin" />
            <span>AI 正在翻译文档...</span>
          </div>

          <div v-else-if="translateState.error" class="pane-error">
            <AlertCircle :size="20" />
            <p>{{ translateState.error }}</p>
          </div>

          <div v-else-if="translateState.translation" class="pane-result">
            <div class="result-section">
              <div class="section-title">
                <Languages :size="14" />
                <span>翻译结果</span>
              </div>
              <div class="markdown-content" v-html="translationHtml" />
            </div>
          </div>

          <div v-else class="pane-empty">
            <Languages :size="32" class="empty-icon" />
            <p class="empty-text">选择目标语言后点击"翻译"</p>
            <p class="empty-hint">AI 将翻译文档内容</p>
          </div>
        </div>

        <!-- 问答 Tab -->
        <div v-show="activeTab === 'chat'" class="tab-pane chat-pane">
          <div ref="chatScrollRef" class="chat-messages">
            <div v-if="chatMessages.length === 0" class="chat-empty">
              <MessageSquare :size="32" class="empty-icon" />
              <p class="empty-text">向 AI 提问关于文档的问题</p>
              <p class="empty-hint">AI 将基于文档内容回答</p>
            </div>

            <div
              v-for="msg in chatMessages"
              :key="msg.id"
              class="chat-message"
              :class="[`role-${msg.role}`, { error: msg.error }]"
            >
              <div class="msg-avatar">
                <Sparkles v-if="msg.role === 'assistant'" :size="14" />
                <span v-else>我</span>
              </div>
              <div class="msg-content">
                <div v-if="msg.error" class="msg-error">{{ msg.content }}</div>
                <div v-else class="markdown-content" v-html="renderMessage(msg)" />
              </div>
            </div>

            <div v-if="chatLoading" class="chat-message role-assistant">
              <div class="msg-avatar">
                <Sparkles :size="14" />
              </div>
              <div class="msg-content">
                <div class="msg-typing">
                  <Loader2 :size="14" class="loading-spin" />
                  <span>AI 正在思考...</span>
                </div>
              </div>
            </div>
          </div>

          <div class="chat-input-area">
            <div class="chat-input-row">
              <textarea
                v-model="chatInput"
                class="chat-input"
                placeholder="输入你的问题... (Enter 发送, Shift+Enter 换行)"
                rows="2"
                :disabled="chatLoading"
                @keydown="handleChatKeydown"
              />
              <button
                class="send-btn"
                :disabled="!chatInput.trim() || chatLoading"
                title="发送"
                @click="handleSendMessage"
              >
                <Send :size="16" />
              </button>
            </div>
            <div v-if="chatMessages.length > 0" class="chat-actions">
              <button class="link-btn" @click="handleClearChat">
                <RotateCcw :size="12" />
                <span>清空对话</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </aside>
  </Transition>
</template>

<style scoped>
.reader-ai-panel {
  width: 360px;
  flex-shrink: 0;
  background: var(--surface);
  border-left: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.ai-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.header-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--text);
}

.header-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  border-radius: var(--radius-xs);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.header-close:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.ai-tabs {
  display: flex;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.ai-tab {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-1);
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: var(--text-sm);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all var(--transition-fast);
}

.ai-tab:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.ai-tab.active {
  color: var(--lumi-primary);
  border-bottom-color: var(--lumi-primary);
  font-weight: var(--font-medium);
}

.ai-body {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.tab-pane {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: var(--space-3);
  gap: var(--space-3);
}

.pane-actions {
  display: flex;
  gap: var(--space-2);
  flex-shrink: 0;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.action-btn:hover:not(:disabled) {
  background: var(--surface-hover);
  color: var(--text);
  border-color: var(--lumi-primary);
}

.action-btn.primary {
  background: var(--lumi-primary);
  border-color: var(--lumi-primary);
  color: var(--text-inverse);
  font-weight: var(--font-medium);
}

.action-btn.primary:hover:not(:disabled) {
  background: var(--lumi-primary-hover);
  border-color: var(--lumi-primary-hover);
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.pane-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-6);
  color: var(--text-muted);
  font-size: var(--text-sm);
}

.loading-spin {
  animation: cx-pdf-spin 1s linear infinite;
  color: var(--lumi-primary);
}

.pane-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-5);
  color: var(--lumi-danger);
  text-align: center;
  background: var(--lumi-danger-light);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
}

.pane-result {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.result-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.section-title {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-weight: var(--font-semibold);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.markdown-content {
  font-size: var(--text-sm);
  line-height: var(--leading-relaxed);
  color: var(--text);
  word-break: break-word;
}

.markdown-content :deep(p) {
  margin: 0 0 var(--space-2);
}

.markdown-content :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3),
.markdown-content :deep(h4) {
  font-weight: var(--font-semibold);
  margin: var(--space-3) 0 var(--space-2);
  color: var(--text);
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  margin: 0 0 var(--space-2);
  padding-left: var(--space-5);
}

.markdown-content :deep(li) {
  margin-bottom: var(--space-1);
}

.markdown-content :deep(code) {
  padding: 1px 4px;
  border-radius: var(--radius-xs);
  background: var(--surface-hover);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
}

.markdown-content :deep(pre) {
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--bg-secondary);
  overflow-x: auto;
}

.markdown-content :deep(blockquote) {
  margin: 0 0 var(--space-2);
  padding-left: var(--space-3);
  border-left: 3px solid var(--lumi-primary-border);
  color: var(--text-secondary);
}

.key-points {
  margin: 0;
  padding-left: var(--space-5);
  font-size: var(--text-sm);
  color: var(--text);
  line-height: var(--leading-relaxed);
}

.key-points li {
  margin-bottom: var(--space-1);
}

.pane-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  color: var(--text-muted);
  text-align: center;
  padding: var(--space-6);
}

.empty-icon {
  opacity: 0.4;
  color: var(--lumi-primary);
}

.empty-text {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  margin: 0;
}

.empty-hint {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin: 0;
}

/* 翻译表单 */
.pane-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  flex-shrink: 0;
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.form-label {
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-weight: var(--font-medium);
}

.form-select,
.form-input {
  height: 32px;
  padding: 0 var(--space-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text);
  font-size: var(--text-sm);
  outline: none;
  transition: border-color var(--transition-fast);
}

.form-select:focus,
.form-input:focus {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

/* 聊天 Tab */
.chat-pane {
  padding: 0;
  gap: 0;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  gap: var(--space-2);
  color: var(--text-muted);
  text-align: center;
}

.chat-message {
  display: flex;
  gap: var(--space-2);
  align-items: flex-start;
}

.msg-avatar {
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  border-radius: var(--radius-full);
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
}

.role-user .msg-avatar {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.msg-content {
  flex: 1;
  min-width: 0;
  padding-top: 2px;
}

.msg-typing {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-muted);
  font-size: var(--text-sm);
  font-style: italic;
}

.msg-error {
  color: var(--lumi-danger);
  font-size: var(--text-sm);
  background: var(--lumi-danger-light);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
}

.chat-message.error .msg-avatar {
  background: var(--lumi-danger-light);
  color: var(--lumi-danger);
}

.chat-input-area {
  border-top: 1px solid var(--border);
  padding: var(--space-2) var(--space-3);
  flex-shrink: 0;
  background: var(--surface);
}

.chat-input-row {
  display: flex;
  gap: var(--space-2);
  align-items: flex-end;
}

.chat-input {
  flex: 1;
  padding: var(--space-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-secondary);
  color: var(--text);
  font-size: var(--text-sm);
  font-family: var(--font-sans);
  resize: none;
  outline: none;
  transition: border-color var(--transition-fast);
  min-height: 36px;
  max-height: 120px;
}

.chat-input:focus {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

.chat-input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.send-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: var(--radius-sm);
  background: var(--lumi-primary);
  color: var(--text-inverse);
  cursor: pointer;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.send-btn:hover:not(:disabled) {
  background: var(--lumi-primary-hover);
}

.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.chat-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: var(--space-1);
}

.link-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: var(--text-xs);
  cursor: pointer;
  border-radius: var(--radius-xs);
  transition: all var(--transition-fast);
}

.link-btn:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.slide-side-right-enter-active,
.slide-side-right-leave-active {
  transition: width var(--transition-normal), opacity var(--transition-fast);
  overflow: hidden;
}

.slide-side-right-enter-from,
.slide-side-right-leave-to {
  width: 0;
  opacity: 0;
}

@keyframes cx-pdf-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>

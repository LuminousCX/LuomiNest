<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  Loader2,
  AlertTriangle,
  RotateCcw,
  ChevronDown,
  Bot,
  Sparkles,
  Wand2,
  Wrench,
  Terminal,
  CheckCircle2,
  XCircle,
  Brain,
  Cpu,
  ChevronRight,
  ClipboardList,
  Check,
  Copy,
  X,
} from 'lucide-vue-next'
import LumiButton from '../common/LumiButton.vue'
import LumiEmptyState from '../common/LumiEmptyState.vue'
import { renderMarkdown } from '../../utils/markdown'
import { useClipboard } from '../../composables/useClipboard'
import type { ChatMessage } from '../../types'
import type { ToolActivity, SubagentActivity, WorkflowPendingPlan } from './types'

const props = defineProps<{
  messages: ChatMessage[]
  isLoadingCurrentConv: boolean
  isStreaming: boolean
  isBackendReady: boolean
  currentModel: string
  toolActivities: ToolActivity[]
  subagentActivities: SubagentActivity[]
  expandedToolOutputs: Record<string, boolean>
  expandedSubagents: Record<string, boolean>
  expandedSubagentTools: Record<string, boolean>
  showReasoning: Record<string, boolean>
  workflowPendingPlan: WorkflowPendingPlan | null
  confirmationFeedback: string
  isNearBottom: boolean
  showScrollToBottomBtn: boolean
}>()

const emit = defineEmits<{
  'toggle-reasoning': [msgId: string]
  'copy-message': [msgId: string, content: string]
  regenerate: [msgId: string]
  'toggle-tool-output': [id: string]
  'toggle-subagent': [id: string]
  'toggle-subagent-tools': [id: string]
  'confirm-plan': []
  'reject-plan': []
  'update:confirmationFeedback': [value: string]
  scroll: [metrics: { scrollTop: number; scrollHeight: number; clientHeight: number }]
  'scroll-to-bottom': []
  'retry-backend': []
  'set-input-text': [text: string]
}>()

const messagesContainer = ref<HTMLElement | null>(null)
const { copiedId, copy: copyMessage } = useClipboard()

const activeSubagentCount = computed(
  () => props.subagentActivities.filter((a) => a.status === 'running').length
)

const feedbackModel = computed<string>({
  get: () => props.confirmationFeedback,
  set: (value) => emit('update:confirmationFeedback', value),
})

const formatToolArgs = (args: string): string => {
  try {
    const parsed = JSON.parse(args)
    return JSON.stringify(parsed, null, 2)
  } catch {
    return args
  }
}



const handleCopyMessage = async (msgId: string, content: string) => {
  await copyMessage(msgId, content)
  emit('copy-message', msgId, content)
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

const scrollToBottom = (force = false) => {
  if (!messagesContainer.value) return
  if (!force && !props.isNearBottom) return
  messagesContainer.value.scrollTo({
    top: messagesContainer.value.scrollHeight,
    behavior: force ? 'auto' : 'smooth',
  })
}

const getMetrics = () => {
  if (!messagesContainer.value) return null
  const { scrollTop, scrollHeight, clientHeight } = messagesContainer.value
  return { scrollTop, scrollHeight, clientHeight }
}

const handleMessagesScroll = () => {
  if (!messagesContainer.value) return
  const { scrollTop, scrollHeight, clientHeight } = messagesContainer.value
  emit('scroll', { scrollTop, scrollHeight, clientHeight })
}

let resizeObserver: ResizeObserver | null = null

const setupResizeObserver = () => {
  if (!messagesContainer.value) return
  const inner = messagesContainer.value.querySelector('.messages-container') as HTMLElement
  if (!inner) return
  resizeObserver = new ResizeObserver(() => {
    if (props.isNearBottom) {
      scrollToBottom(true)
    }
  })
  resizeObserver.observe(inner)
}

const teardownResizeObserver = () => {
  resizeObserver?.disconnect()
  resizeObserver = null
}

defineExpose({
  scrollToBottom,
  setupResizeObserver,
  teardownResizeObserver,
  getMetrics,
})
</script>

<template>
  <div class="chat-area">
    <div v-if="!isBackendReady" class="backend-warning">
      <div class="warning-content">
        <AlertTriangle :size="20" />
        <div class="warning-text">
          <p class="warning-title">后端服务未连接</p>
          <p class="warning-desc">请确保 LuomiNest 后端服务已启动</p>
        </div>
        <LumiButton variant="danger" size="sm" class="retry-btn shrink-0" @click="emit('retry-backend')">
          <RotateCcw :size="14" />
          <span>重试</span>
        </LumiButton>
      </div>
    </div>

    <div class="main-agent-bar">
      <div class="main-agent-badge">
        <Brain :size="14" />
        <span>主智能体</span>
      </div>
      <span class="main-agent-model">{{ currentModel }}</span>
    </div>

    <div ref="messagesContainer" class="messages-scroll" @scroll="handleMessagesScroll">
      <div class="messages-container">
        <TransitionGroup name="msg-appear" tag="div">
          <div
            v-for="msg in messages"
            :key="msg.id"
            :class="['message-row', msg.role]"
          >
            <div v-if="msg.role === 'assistant'" class="message-avatar shrink-0">
              <div class="avatar-assistant">
                <Bot :size="16" />
              </div>
            </div>
            <div class="message-body">
              <div v-if="msg.role === 'assistant'" class="message-sender">
                主智能体
              </div>
              <div
                v-if="msg.role === 'assistant' && (msg.reasoningContent !== undefined || (!msg.done && msg.id === messages[messages.length - 1].id && !msg.content))"
                class="reasoning-section lumi-card"
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
                >
                  <div v-html="renderMarkdown(msg.reasoningContent || '')"></div>
                </div>
              </div>

              <div
                v-if="msg.role === 'assistant' && msg.id === messages[messages.length - 1].id && toolActivities.length > 0"
                class="tool-activities-section lumi-card"
              >
                <div class="tool-activities-header">
                  <Wrench :size="12" />
                  <span>工具调用 ({{ toolActivities.length }})</span>
                </div>
                <div class="tool-activities-list">
                  <div
                    v-for="activity in toolActivities"
                    :key="activity.id"
                    class="tool-activity-item"
                  >
                    <div class="tool-activity-header" @click="emit('toggle-tool-output', activity.id)">
                      <div class="tool-activity-icon">
                        <Loader2 v-if="activity.status === 'running' || activity.status === 'pending'" :size="13" class="spin-animation" />
                        <CheckCircle2 v-else-if="activity.status === 'completed'" :size="13" />
                        <XCircle v-else-if="activity.status === 'failed'" :size="13" />
                      </div>
                      <Terminal :size="12" />
                      <span class="tool-activity-name">{{ activity.name }}</span>
                      <span v-if="activity.iteration > 0" class="tool-activity-iteration">轮次 {{ activity.iteration + 1 }}</span>
                      <ChevronDown
                        v-if="activity.output"
                        :size="12"
                        class="tool-activity-chevron"
                        :class="{ rotated: !expandedToolOutputs[activity.id] }"
                      />
                    </div>
                    <div v-if="activity.arguments && activity.arguments !== '{}'" class="tool-activity-args">
                      <pre>{{ formatToolArgs(activity.arguments) }}</pre>
                    </div>
                    <div
                      v-if="activity.output && expandedToolOutputs[activity.id]"
                      class="tool-activity-output"
                    >
                      <pre>{{ activity.output }}</pre>
                    </div>
                  </div>
                </div>
              </div>

              <div
                v-if="msg.role === 'assistant' && msg.id === messages[messages.length - 1].id && subagentActivities.length > 0"
                class="subagent-activities-section lumi-card"
              >
                <div class="subagent-activities-header">
                  <Cpu :size="12" />
                  <span>子 Agent 群组 ({{ subagentActivities.length }})</span>
                  <span v-if="activeSubagentCount > 0" class="subagent-active-badge">{{ activeSubagentCount }} 执行中</span>
                </div>
                <div class="subagent-activities-list">
                  <div
                    v-for="agent in subagentActivities"
                    :key="agent.id"
                    :class="['subagent-card', 'lumi-card', { running: agent.status === 'running' }]"
                  >
                    <div class="subagent-card-header" @click="emit('toggle-subagent', agent.id)">
                      <div class="subagent-status-icon">
                        <Loader2 v-if="agent.status === 'running'" :size="13" class="spin-animation" />
                        <CheckCircle2 v-else-if="agent.status === 'completed'" :size="13" />
                        <XCircle v-else-if="agent.status === 'failed'" :size="13" />
                      </div>
                      <div class="subagent-card-info">
                        <div class="subagent-card-title">
                          <span class="subagent-task">{{ agent.task }}</span>
                          <span class="subagent-depth">深度 {{ agent.depth }}</span>
                        </div>
                        <div class="subagent-card-meta">
                          <template v-if="agent.status === 'running' && agent.progress">
                            <span class="subagent-progress">{{ agent.progress }}</span>
                          </template>
                          <template v-else-if="agent.status === 'completed'">
                            <span class="subagent-status-text completed">已完成</span>
                          </template>
                          <template v-else-if="agent.status === 'failed'">
                            <span class="subagent-status-text failed">执行失败</span>
                          </template>
                          <span v-if="agent.toolCalls.length > 0" class="subagent-tools-count">
                            {{ agent.toolCalls.length }} 次工具调用
                          </span>
                        </div>
                      </div>
                      <ChevronRight
                        :size="14"
                        class="subagent-chevron"
                        :class="{ expanded: !expandedSubagents[agent.id] }"
                      />
                    </div>

                    <Transition name="subagent-slide">
                      <div v-show="expandedSubagents[agent.id]" class="subagent-card-body">
                        <div v-if="agent.toolCalls.length > 0" class="subagent-tools-section">
                          <div class="subagent-tools-header" @click="emit('toggle-subagent-tools', agent.id)">
                            <Terminal :size="11" />
                            <span>工具调用历史</span>
                            <ChevronDown
                              :size="11"
                              class="subagent-tools-chevron"
                              :class="{ rotated: !expandedSubagentTools[agent.id] }"
                            />
                          </div>
                          <div v-show="expandedSubagentTools[agent.id]" class="subagent-tools-list">
                            <div
                              v-for="(tc, idx) in agent.toolCalls"
                              :key="idx"
                              class="subagent-tool-item"
                            >
                              <div class="subagent-tool-header">
                                <div class="subagent-tool-icon">
                                  <Loader2 v-if="tc.status === 'running'" :size="11" class="spin-animation" />
                                  <CheckCircle2 v-else :size="11" />
                                </div>
                                <span class="subagent-tool-name">{{ tc.name }}</span>
                              </div>
                              <div v-if="tc.args && tc.args !== '{}'" class="subagent-tool-args">
                                <pre>{{ formatToolArgs(tc.args) }}</pre>
                              </div>
                              <div v-if="tc.output" class="subagent-tool-output">
                                <pre>{{ tc.output }}</pre>
                              </div>
                            </div>
                          </div>
                        </div>

                        <div v-if="agent.result" class="subagent-result">
                          <div class="subagent-result-label">
                            <CheckCircle2 :size="11" />
                            <span>执行结果</span>
                          </div>
                          <div class="subagent-result-content markdown-body">
                            <div v-html="renderMarkdown(agent.result)"></div>
                          </div>
                        </div>

                        <div v-if="agent.error" class="subagent-error">
                          <div class="subagent-error-label">
                            <XCircle :size="11" />
                            <span>错误信息</span>
                          </div>
                          <div class="subagent-error-content">{{ agent.error }}</div>
                        </div>
                      </div>
                    </Transition>
                  </div>
                </div>
              </div>

              <div
                v-if="msg.role === 'assistant' && msg.id === messages[messages.length - 1].id && workflowPendingPlan"
                class="plan-confirmation-section lumi-card"
              >
                <div class="plan-confirmation-header">
                  <ClipboardList :size="14" />
                  <span>执行计划待确认</span>
                  <span class="plan-task-count">{{ workflowPendingPlan.tasks.length }} 个子任务</span>
                </div>
                <div class="plan-confirmation-body">
                  <div v-if="workflowPendingPlan.plan" class="plan-summary">
                    {{ workflowPendingPlan.plan }}
                  </div>
                  <div class="plan-tasks-list">
                    <div
                      v-for="(task, idx) in workflowPendingPlan.tasks"
                      :key="task.task_id || idx"
                      class="plan-task-item"
                    >
                      <div class="plan-task-index">{{ idx + 1 }}</div>
                      <div class="plan-task-info">
                        <div class="plan-task-title">{{ task.title }}</div>
                        <div v-if="task.description" class="plan-task-desc">{{ task.description }}</div>
                        <div class="plan-task-meta">
                          <span v-if="task.tool_name" class="plan-task-tool">
                            <Wrench :size="10" />
                            {{ task.tool_name }}
                          </span>
                          <span v-if="task.priority && task.priority !== 'normal'" class="plan-task-priority" :class="task.priority">
                            {{ task.priority }}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div class="plan-feedback-area">
                    <textarea
                      v-model="feedbackModel"
                      class="lumi-textarea plan-feedback-input"
                      placeholder="反馈（可选）：如需调整计划，请在此说明..."
                      rows="2"
                    ></textarea>
                  </div>
                  <div class="plan-confirmation-actions">
                    <LumiButton variant="secondary" size="sm" class="plan-btn plan-btn-reject" @click="emit('reject-plan')">
                      <X :size="14" />
                      <span>拒绝执行</span>
                    </LumiButton>
                    <LumiButton variant="primary" size="sm" class="plan-btn plan-btn-confirm" @click="emit('confirm-plan')">
                      <Check :size="14" />
                      <span>确认执行</span>
                    </LumiButton>
                  </div>
                </div>
              </div>

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

              <div v-if="msg.role === 'assistant' && msg.done" class="assistant-msg-actions">
                <LumiButton
                  variant="ghost"
                  size="sm"
                  icon-only
                  class="u-btn"
                  :aria-label="copiedId === msg.id ? '已复制' : '复制'"
                  @click="handleCopyMessage(msg.id, msg.content)"
                >
                  <Check v-if="copiedId === msg.id" :size="14" />
                  <Copy v-else :size="14" />
                </LumiButton>
                <LumiButton
                  v-if="isLastAssistantMessage(msg.id)"
                  variant="ghost"
                  size="sm"
                  icon-only
                  aria-label="重新生成"
                  class="u-btn"
                  @click="emit('regenerate', msg.id)"
                >
                  <RotateCcw :size="14" />
                </LumiButton>
              </div>

              <div v-if="msg.role === 'user'" class="user-msg-layout">
                <div class="user-msg-btns">
                  <LumiButton
                    variant="ghost"
                    size="sm"
                    icon-only
                    class="u-btn u-btn-hover"
                    :aria-label="copiedId === msg.id ? '已复制' : '复制'"
                    @click="handleCopyMessage(msg.id, msg.content)"
                  >
                    <Check v-if="copiedId === msg.id" :size="14" />
                    <Copy v-else :size="14" />
                  </LumiButton>
                </div>
                <div class="message-content user-message">
                  {{ msg.content }}
                </div>
              </div>
            </div>
          </div>
        </TransitionGroup>

        <LumiEmptyState
          v-if="messages.length === 0 && !isLoadingCurrentConv"
          :icon="Sparkles"
          title="与陪伴 AI 开始对话"
          description="右侧的 Live2D 将作为主 Agent 陪伴你"
        >
          <template #action>
            <div class="empty-quick-actions">
              <LumiButton variant="outline" size="sm" class="quick-action" @click="emit('set-input-text', '你好，请介绍一下你自己')">
                打个招呼
              </LumiButton>
              <LumiButton variant="outline" size="sm" class="quick-action" @click="emit('set-input-text', '帮我写一段 Python 代码')">
                写段代码
              </LumiButton>
              <LumiButton variant="outline" size="sm" class="quick-action" @click="emit('set-input-text', '解释一下什么是大语言模型')">
                了解 LLM
              </LumiButton>
            </div>
          </template>
        </LumiEmptyState>
      </div>
    </div>

    <Transition name="scroll-btn-fade">
      <LumiButton
        v-if="showScrollToBottomBtn"
        variant="secondary"
        size="md"
        icon-only
        aria-label="滚动到底部"
        class="scroll-to-bottom-btn"
        @click="emit('scroll-to-bottom')"
      >
        <ChevronDown :size="18" />
      </LumiButton>
    </Transition>

    <Transition name="conv-loading-fade">
      <div v-if="isLoadingCurrentConv" class="conv-loading-overlay">
        <div class="conv-loading-content">
          <Loader2 :size="20" class="spin-animation" />
          <span>加载对话中...</span>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
button:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px var(--focus-ring);
}

.chat-area {
  flex: 1;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.backend-warning {
  padding: var(--space-4) var(--space-6);
  background: var(--lumi-danger-light);
  border-bottom: 1px solid var(--lumi-danger);
}

.warning-content {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  color: var(--lumi-danger);
}

.warning-text {
  flex: 1;
}

.warning-title {
  font-size: var(--text-md);
  font-weight: 600;
  margin: 0;
}

.warning-desc {
  font-size: var(--text-sm);
  margin: var(--space-1) 0 0;
  opacity: 0.8;
}

.main-agent-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) var(--space-5);
  border-bottom: 1px solid var(--border-light);
  background: var(--surface);
  flex-shrink: 0;
}

.main-agent-badge {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-3);
  background: var(--lumi-primary-light);
  border-radius: var(--radius-sm);
  color: var(--lumi-primary);
  font-size: var(--text-sm);
  font-weight: 600;
}

.main-agent-model {
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.messages-scroll {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-6);
}

.messages-container {
  max-width: 820px;
  margin: 0 auto;
}

.message-row {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-5);
  animation: msg-in var(--duration-normal) var(--ease-in-out);
}

@keyframes msg-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.message-row.user {
  flex-direction: row-reverse;
}

.avatar-assistant {
  width: var(--space-7);
  height: var(--space-7);
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--lumi-primary), var(--lumi-primary-soft));
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-inverse);
}

.message-body {
  flex: 1;
  min-width: 0;
  max-width: calc(100% - 44px);
}

.message-sender {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: var(--space-1);
}

.reasoning-section {
  margin-bottom: var(--space-2);
  background: var(--surface-hover);
  overflow: hidden;
}

.reasoning-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  cursor: pointer;
  font-size: var(--text-sm);
  color: var(--text-muted);
  transition: background-color var(--transition-fast);
}

.reasoning-header:hover {
  background: var(--surface-active);
}

.reasoning-chevron {
  margin-left: auto;
  transition: transform var(--transition-fast);
}

.reasoning-chevron.rotated {
  transform: rotate(-90deg);
}

.reasoning-content {
  padding: var(--space-2) var(--space-3) var(--space-3);
  font-size: var(--text-sm);
  color: var(--text-muted);
  max-height: 240px;
  overflow-y: auto;
}

.tool-activities-section {
  margin-bottom: var(--space-2);
  background: var(--surface-hover);
  overflow: hidden;
  border: 1px solid var(--border-light);
}

.tool-activities-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-secondary);
  background: var(--surface-active);
}

.tool-activities-list {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.tool-activity-item {
  background: var(--surface);
}

.tool-activity-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  cursor: pointer;
  font-size: var(--text-sm);
  color: var(--text-secondary);
  transition: background-color var(--transition-fast);
}

.tool-activity-header:hover {
  background: var(--surface-hover);
}

.tool-activity-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--space-4);
  height: var(--space-4);
  flex-shrink: 0;
}

.tool-activity-icon :deep(svg) {
  color: var(--text-muted);
}

.tool-activity-icon .spin-animation {
  color: var(--lumi-primary);
}

.tool-activity-item .tool-activity-icon svg[stroke="currentColor"] {
  color: var(--lumi-success);
}

.tool-activity-name {
  font-family: var(--font-mono);
  font-weight: 500;
  color: var(--text-primary);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool-activity-iteration {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  padding: 1px var(--space-2);
  background: var(--surface-hover);
  border-radius: var(--radius-full);
  flex-shrink: 0;
}

.tool-activity-chevron {
  margin-left: auto;
  flex-shrink: 0;
  color: var(--text-muted);
  transition: transform var(--transition-fast);
}

.tool-activity-chevron.rotated {
  transform: rotate(-90deg);
}

.tool-activity-args {
  padding: 0 var(--space-3) var(--space-2) var(--space-9);
}

.tool-activity-args pre,
.tool-activity-output pre {
  font-size: var(--text-xs);
  color: var(--text-muted);
  background: var(--bg-secondary);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-sm);
  margin: 0;
  overflow-x: auto;
  font-family: var(--font-mono);
}

.tool-activity-output {
  padding: 0 var(--space-3) var(--space-2) var(--space-9);
}

.tool-activity-output pre {
  color: var(--text-secondary);
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.subagent-activities-section {
  margin-bottom: var(--space-2);
  background: var(--surface-hover);
  overflow: hidden;
  border: 1px solid var(--border-light);
}

.subagent-activities-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-secondary);
  background: var(--surface-active);
}

.subagent-active-badge {
  margin-left: auto;
  font-size: var(--text-2xs);
  font-weight: 500;
  color: var(--lumi-primary);
  padding: var(--space-1) var(--space-2);
  background: var(--lumi-primary-light);
  border-radius: var(--radius-full);
  animation: pulse var(--duration-slow) var(--ease-in-out) infinite;
}

.subagent-activities-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-1);
}

.subagent-card {
  background: var(--surface);
  border: 1px solid var(--border-light);
  overflow: hidden;
  transition: border-color var(--transition-fast);
}

.subagent-card.running {
  border-color: var(--lumi-primary);
  position: relative;
}

.subagent-card.running::before {
  content: '';
  position: absolute;
  inset: -1px;
  border-radius: var(--card-radius);
  padding: 1px;
  background: linear-gradient(
    90deg,
    var(--lumi-primary),
    var(--lumi-primary-soft),
    var(--lumi-primary)
  );
  background-size: 200% 100%;
  -webkit-mask: linear-gradient(var(--surface) 0 0) content-box, linear-gradient(var(--surface) 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  animation: subagent-shine 2s linear infinite;
  pointer-events: none;
  z-index: 1;
}

@keyframes subagent-shine {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.subagent-card-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3);
  cursor: pointer;
  transition: background-color var(--transition-fast);
}

.subagent-card-header:hover {
  background: var(--surface-hover);
}

.subagent-status-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

.subagent-status-icon :deep(svg) {
  color: var(--text-muted);
}

.subagent-card.running .subagent-status-icon .spin-animation {
  color: var(--lumi-primary);
}

.subagent-card.completed .subagent-status-icon :deep(svg) {
  color: var(--lumi-success);
}

.subagent-card.failed .subagent-status-icon :deep(svg) {
  color: var(--lumi-danger);
}

.subagent-card-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.subagent-card-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.subagent-task {
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-primary);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.subagent-depth {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  padding: 1px var(--space-2);
  background: var(--surface-hover);
  border-radius: var(--radius-full);
  flex-shrink: 0;
}

.subagent-card-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.subagent-progress {
  color: var(--lumi-primary);
  font-style: italic;
}

.subagent-status-text.completed {
  color: var(--lumi-success);
}

.subagent-status-text.failed {
  color: var(--lumi-danger);
}

.subagent-tools-count {
  margin-left: auto;
  font-size: var(--text-2xs);
  padding: 1px var(--space-2);
  background: var(--surface-hover);
  border-radius: var(--radius-full);
}

.subagent-chevron {
  color: var(--text-muted);
  flex-shrink: 0;
  transition: transform var(--transition-fast);
}

.subagent-chevron.expanded {
  transform: rotate(90deg);
}

.subagent-card-body {
  padding: 0 var(--space-3) var(--space-3);
  border-top: 1px solid var(--border-light);
}

.subagent-tools-section {
  margin-top: var(--space-2);
}

.subagent-tools-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-2);
  cursor: pointer;
  font-size: var(--text-xs);
  color: var(--text-muted);
  background: var(--surface-hover);
  border-radius: var(--radius-sm);
  transition: background-color var(--transition-fast);
}

.subagent-tools-header:hover {
  background: var(--surface-active);
}

.subagent-tools-chevron {
  margin-left: auto;
  transition: transform var(--transition-fast);
}

.subagent-tools-chevron.rotated {
  transform: rotate(-90deg);
}

.subagent-tools-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin-top: var(--space-2);
}

.subagent-tool-item {
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
  padding: var(--space-1) var(--space-2);
}

.subagent-tool-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.subagent-tool-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.subagent-tool-icon .spin-animation {
  color: var(--lumi-primary);
}

.subagent-tool-icon :deep(svg) {
  color: var(--lumi-success);
}

.subagent-tool-name {
  font-size: var(--text-xs);
  font-family: var(--font-mono);
  color: var(--text-primary);
  font-weight: 500;
}

.subagent-tool-args pre,
.subagent-tool-output pre {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  background: var(--surface);
  padding: var(--space-1);
  border-radius: var(--radius-sm);
  margin: var(--space-1) 0 0;
  overflow-x: auto;
  max-height: 120px;
  overflow-y: auto;
  font-family: var(--font-mono);
  white-space: pre-wrap;
  word-break: break-word;
}

.subagent-result {
  margin-top: var(--space-3);
  padding: var(--space-2);
  background: var(--lumi-success-light);
  border-radius: var(--radius-sm);
  border-left: 2px solid var(--lumi-success);
}

.subagent-result-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--lumi-success);
  margin-bottom: var(--space-1);
}

.subagent-result-content {
  font-size: var(--text-sm);
  line-height: var(--leading-relaxed);
  color: var(--text-primary);
  max-height: 240px;
  overflow-y: auto;
}

.subagent-result-content :deep(p) {
  margin: var(--space-1) 0;
}

.subagent-result-content :deep(pre) {
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
  padding: var(--space-2);
  overflow-x: auto;
  font-size: var(--text-xs);
  margin: var(--space-1) 0;
}

.subagent-error {
  margin-top: var(--space-3);
  padding: var(--space-2);
  background: var(--lumi-danger-light);
  border-radius: var(--radius-sm);
  border-left: 2px solid var(--lumi-danger);
}

.subagent-error-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--lumi-danger);
  margin-bottom: var(--space-1);
}

.subagent-error-content {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  word-break: break-word;
  line-height: var(--leading-normal);
}

.subagent-slide-enter-active,
.subagent-slide-leave-active {
  transition: opacity var(--transition-fast), max-height var(--transition-normal);
  overflow: hidden;
}

.subagent-slide-enter-from,
.subagent-slide-leave-to {
  opacity: 0;
  max-height: 0;
}

.plan-confirmation-section {
  margin-bottom: var(--space-2);
  background: var(--surface-hover);
  overflow: hidden;
  border: 1px solid var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
  animation: plan-appear var(--duration-normal) var(--ease-in-out);
}

@keyframes plan-appear {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

.plan-confirmation-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
  border-bottom: 1px solid var(--border-light);
}

.plan-task-count {
  margin-left: auto;
  font-size: var(--text-xs);
  font-weight: 500;
  padding: var(--space-1) var(--space-2);
  background: var(--surface);
  border-radius: var(--radius-full);
  color: var(--text-secondary);
}

.plan-confirmation-body {
  padding: var(--space-3) var(--space-4);
}

.plan-summary {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: var(--leading-relaxed);
  margin-bottom: var(--space-3);
  padding: var(--space-2);
  background: var(--surface);
  border-radius: var(--radius-sm);
  border-left: 2px solid var(--lumi-primary);
}

.plan-tasks-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.plan-task-item {
  display: flex;
  gap: var(--space-3);
  padding: var(--space-2);
  background: var(--surface);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-light);
  transition: border-color var(--transition-fast);
}

.plan-task-item:hover {
  border-color: var(--lumi-primary);
}

.plan-task-index {
  width: 22px;
  height: 22px;
  border-radius: var(--radius-full);
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-xs);
  font-weight: 600;
  flex-shrink: 0;
}

.plan-task-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.plan-task-title {
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--text-primary);
  line-height: var(--leading-snug);
}

.plan-task-desc {
  font-size: var(--text-xs);
  color: var(--text-muted);
  line-height: var(--leading-normal);
}

.plan-task-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-1);
}

.plan-task-tool {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-2xs);
  color: var(--text-muted);
  padding: 1px var(--space-2);
  background: var(--surface-hover);
  border-radius: var(--radius-full);
  font-family: var(--font-mono);
}

.plan-task-priority {
  font-size: var(--text-2xs);
  padding: 1px var(--space-2);
  border-radius: var(--radius-full);
  font-weight: 500;
}

.plan-task-priority.urgent {
  background: var(--lumi-danger-light);
  color: var(--lumi-danger);
}

.plan-task-priority.high {
  background: var(--lumi-warning-light);
  color: var(--lumi-warning);
}

.plan-task-priority.low {
  background: var(--surface-hover);
  color: var(--text-muted);
}

.plan-feedback-area {
  margin-bottom: var(--space-3);
}

.plan-feedback-input {
  width: 100%;
  min-height: 60px;
  resize: none;
}

.plan-confirmation-actions {
  display: flex;
  gap: var(--space-2);
  justify-content: flex-end;
}

.message-content {
  font-size: var(--text-md);
  line-height: var(--leading-relaxed);
  color: var(--text-primary);
  word-break: break-word;
}

.message-content.user-message {
  background: var(--lumi-primary);
  color: var(--text-inverse);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-lg) var(--radius-lg) var(--radius-sm) var(--radius-lg);
  display: inline-block;
  max-width: 100%;
}

.user-msg-layout {
  display: flex;
  flex-direction: row-reverse;
  align-items: flex-end;
  gap: var(--space-2);
}

.user-msg-btns {
  display: flex;
  gap: var(--space-1);
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.message-row.user:hover .user-msg-btns {
  opacity: 1;
}

.markdown-body :deep(pre) {
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-4);
  overflow-x: auto;
  font-size: var(--text-base);
  margin: var(--space-2) 0;
}

.markdown-body :deep(code) {
  font-family: var(--font-mono);
}

.markdown-body :deep(p) {
  margin: var(--space-2) 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: var(--space-5);
  margin: var(--space-2) 0;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin: var(--space-3) 0 var(--space-2);
  font-weight: 600;
}

.interrupted-inline {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-sm);
  color: var(--lumi-warning);
  margin-left: var(--space-2);
}

.interrupted-only {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-sm);
  color: var(--lumi-warning);
  padding: var(--space-1) 0;
}

.streaming-indicator {
  display: inline-flex;
  align-items: center;
  margin-top: var(--space-1);
}

.streaming-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  background: var(--lumi-primary);
  animation: pulse 1s var(--ease-in-out) infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.4; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1.2); }
}

.assistant-msg-actions {
  display: flex;
  gap: var(--space-1);
  margin-top: var(--space-2);
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.message-row.assistant:hover .assistant-msg-actions {
  opacity: 1;
}

.u-btn {
  width: 26px;
  height: 26px;
  color: var(--text-muted);
}

.u-btn:hover {
  color: var(--text-primary);
  background: var(--surface-active);
}

.u-btn-hover {
  background: var(--surface);
}

.empty-quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  justify-content: center;
}

.quick-action {
  border-radius: var(--radius-full);
}

.conv-loading-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--overlay-subtle);
  backdrop-filter: blur(4px);
  z-index: 5;
}

.conv-loading-content {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-5);
  background: var(--surface);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  font-size: var(--text-base);
  color: var(--text-secondary);
}

.spin-animation {
  animation: spin 1s linear infinite;
}

.msg-appear-enter-active,
.msg-appear-leave-active {
  transition: opacity var(--transition-fast), transform var(--transition-fast);
}

.msg-appear-enter-from,
.msg-appear-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

.conv-loading-fade-enter-active,
.conv-loading-fade-leave-active {
  transition: opacity var(--transition-fast);
}

.conv-loading-fade-enter-from,
.conv-loading-fade-leave-to {
  opacity: 0;
}

.scroll-to-bottom-btn {
  position: absolute;
  bottom: var(--space-4);
  left: 50%;
  transform: translateX(-50%);
  border-radius: var(--radius-full);
  box-shadow: var(--shadow-sm);
  z-index: 4;
}

.scroll-to-bottom-btn.lumi-btn {
  width: 36px;
  height: 36px;
}

.scroll-to-bottom-btn:hover {
  color: var(--lumi-primary);
  box-shadow: var(--shadow-lg);
}

.scroll-btn-fade-enter-active,
.scroll-btn-fade-leave-active {
  transition: opacity var(--transition-fast), transform var(--transition-fast);
}

.scroll-btn-fade-enter-from,
.scroll-btn-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(10px);
}
</style>

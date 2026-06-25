<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'
import {
  Bot,
  Users,
  User,
  MessageCircle,
  ImagePlus,
  Mic,
  Send,
  Loader2,
  Zap,
  UserPlus,
  MoreVertical,
  CheckCircle2,
  AlertCircle,
  Clock,
  Play,
  Layers,
} from 'lucide-vue-next'
import type { GroupInfo, GroupMessage, CollaborationPhase, CollaborationSubTask } from '../../types'

const props = defineProps<{
  group: GroupInfo | null
  messages: GroupMessage[]
  collaborationMode: boolean
  collaborationActive: boolean
  collaborationPhase: CollaborationPhase | null
  collaborationTasks: CollaborationSubTask[]
  agentsResponding: boolean
  respondingAgentNames: string[]
  sendingGroupMessage: boolean
  groupChatInput: string
}>()

const emit = defineEmits<{
  'toggle-collaboration-mode': []
  'add-agent': []
  'update:groupChatInput': [value: string]
  'send-group-message': []
}>()

const groupMessagesContainer = ref<HTMLElement | null>(null)

const groupChatInputModel = computed<string>({
  get: () => props.groupChatInput,
  set: (value) => emit('update:groupChatInput', value),
})

const phaseLabel = computed(() => {
  if (!props.collaborationPhase) return ''
  const labels: Record<CollaborationPhase, string> = {
    analyzing: '分析中',
    dispatching: '分配任务',
    executing: '执行中',
    synthesizing: '综合结果',
    completed: '已完成',
    failed: '失败',
  }
  return labels[props.collaborationPhase]
})

const phaseIcon = computed(() => {
  if (!props.collaborationPhase) return null
  const icons: Record<CollaborationPhase, typeof Loader2> = {
    analyzing: Loader2,
    dispatching: Layers,
    executing: Play,
    synthesizing: Layers,
    completed: CheckCircle2,
    failed: AlertCircle,
  }
  return icons[props.collaborationPhase]
})

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

const scrollToBottom = () => {
  if (groupMessagesContainer.value) {
    groupMessagesContainer.value.scrollTo({ top: groupMessagesContainer.value.scrollHeight, behavior: 'smooth' })
  }
}

watch(() => props.messages, () => {
  nextTick(() => {
    scrollToBottom()
  })
}, { deep: true })

defineExpose({ scrollToBottom })
</script>

<template>
  <div class="chat-group-mode">
    <div class="group-chat-header">
      <div class="chat-title-area">
        <div class="chat-avatar-mini">
          <Users :size="14" />
        </div>
        <div class="chat-title-text">
          <h3>{{ group?.name }}</h3>
          <span class="chat-status-line">
            {{ group?.members.length }} 成员 · {{ group?.aiCount }} AI
          </span>
        </div>
      </div>
      <div class="chat-actions">
        <button
          :class="['chat-action-btn', { active: collaborationMode }]"
          title="协作模式"
          @click="emit('toggle-collaboration-mode')"
        >
          <Zap :size="15" />
        </button>
        <button class="chat-action-btn" title="添加 Agent" @click="emit('add-agent')">
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
        v-for="msg in messages"
        :key="msg.id"
        :class="['msg-row', msg.senderType, { 'collab-synthesis': msg.collaboration?.type === 'synthesis' }]"
      >
        <div v-if="msg.senderType === 'agent'" class="msg-avatar">
          <div
            class="avatar-agent"
            :style="msg.role === '调度员' ? { background: 'var(--lumi-brand-light)', color: 'var(--lumi-brand)' } : {}"
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
              :style="msg.collaboration?.type === 'synthesis' ? { background: 'var(--lumi-brand-light)', color: 'var(--lumi-brand)' } : {}"
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

      <div v-if="messages.length === 0 && !collaborationActive" class="chat-empty">
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
          v-model="groupChatInputModel"
          type="text"
          :placeholder="collaborationMode ? '输入消息，Agent 团队将协作处理...' : '发送消息到群聊...'"
          :disabled="sendingGroupMessage || collaborationActive || agentsResponding"
          @keydown.enter="emit('send-group-message')"
        />
        <button
          class="input-send-btn"
          @click="emit('send-group-message')"
          :disabled="!groupChatInput.trim() || sendingGroupMessage || collaborationActive || agentsResponding"
        >
          <Loader2 v-if="sendingGroupMessage || collaborationActive || agentsResponding" :size="15" class="spin-animation" />
          <Send v-else :size="15" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-group-mode {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.group-chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-5);
  border-bottom: 1px solid var(--border-light);
  background: var(--surface);
  flex-shrink: 0;
}

.chat-title-area {
  display: flex;
  align-items: center;
  gap: 10px;
}

.chat-avatar-mini {
  width: var(--space-7);
  height: var(--space-7);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--lumi-brand-glow);
  color: var(--lumi-brand);
}

.chat-title-text h3 {
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.chat-status-line {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.chat-actions {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.chat-action-btn {
  width: var(--space-7);
  height: var(--space-7);
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
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
}

.collaboration-bar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-5);
  background: var(--lumi-brand-subtle);
  border-bottom: 1px solid var(--lumi-brand-border);
  flex-shrink: 0;
  flex-wrap: wrap;
}

.collab-mode-indicator {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--lumi-brand);
}

.collab-phase {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.collab-tasks-mini {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  flex-wrap: wrap;
}

.collab-task-chip {
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 2px 6px;
  border-radius: 10px;
  font-size: var(--text-2xs);
  background: var(--surface);
  border: 1px solid var(--border-light);
}

.collab-task-chip.status-running {
  color: var(--lumi-brand);
  border-color: var(--lumi-brand-border);
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

.group-chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4) var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.msg-row {
  display: flex;
  gap: var(--space-2);
  max-width: 80%;
}

.msg-row.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.msg-avatar {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: var(--lumi-brand-glow);
  color: var(--lumi-brand);
}

.msg-avatar.user-avatar {
  background: var(--lumi-brand);
  color: var(--text-inverse);
}

.avatar-agent {
  width: 100%;
  height: 100%;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
}

.msg-bubble {
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  font-size: var(--text-base);
  line-height: 1.5;
  word-break: break-word;
}

.msg-bubble.agent {
  background: var(--surface);
  border: 1px solid var(--border-light);
  color: var(--text-primary);
}

.msg-bubble.user {
  background: var(--lumi-brand);
  color: var(--text-inverse);
}

.msg-bubble.synthesis-bubble {
  background: var(--lumi-brand-light);
  border-color: var(--lumi-brand-border);
}

.msg-sender {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 2px;
}

.msg-role-tag {
  padding: 1px 5px;
  border-radius: var(--radius-sm);
  font-size: var(--text-2xs);
  font-weight: 500;
  background: var(--workspace-panel);
  color: var(--text-muted);
}

.msg-collab-tag {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  padding: 1px var(--space-1);
  background: var(--workspace-panel);
  border-radius: 4px;
}

.msg-text {
  margin: 0;
  white-space: pre-wrap;
}

.msg-time {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  margin-top: var(--space-1);
  display: block;
}

.msg-bubble.user .msg-time {
  color: color-mix(in srgb, var(--text-inverse), transparent 30%);
}

.collab-progress-msg {
  align-self: center;
  padding: var(--space-2) var(--space-4);
  background: var(--surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-full);
}

.collab-progress-inner {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.chat-empty {
  margin: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-muted);
  padding: var(--space-7);
}

.chat-empty p {
  font-size: var(--text-base);
  margin: 0;
}

.group-chat-input-bar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-5);
  border-top: 1px solid var(--workspace-border);
  background: var(--workspace-sidebar);
  flex-shrink: 0;
}

.input-tools {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.input-tool-btn {
  width: var(--space-7);
  height: var(--space-7);
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
  gap: var(--space-2);
  background: var(--surface);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-md);
  padding: var(--space-1) var(--space-1) var(--space-1) var(--space-3);
}

.input-main input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: var(--text-base);
  color: var(--text-primary);
  padding: 6px 0;
}

.input-main input::placeholder {
  color: var(--text-muted);
}

.input-send-btn {
  width: var(--space-7);
  height: var(--space-7);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--text-inverse);
  background: var(--lumi-brand);
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.input-send-btn:hover:not(:disabled) {
  background: var(--lumi-brand-hover);
}

.input-send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.spin-animation {
  animation: luominest-spin 1s linear infinite;
}

@keyframes luominest-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>

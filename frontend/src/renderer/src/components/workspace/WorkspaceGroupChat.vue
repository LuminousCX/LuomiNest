<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Bot,
  Users,
  MessageCircle,
  ImagePlus,
  Mic,
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
import { useAgentStore } from '../../stores/agent'
import type { GroupInfo, GroupMessage, CollaborationPhase, CollaborationSubTask, AgentProfile } from '../../types'
import { useChatScroll } from '../../composables/useChatScroll'
import { useChatWindow } from '../../composables/useChatWindow'
import ThoughtLine from '../common/ThoughtLine.vue'
import ChatThreadHeader from './chat-thread/ChatThreadHeader.vue'
import ChatThreadBubble from './chat-thread/ChatThreadBubble.vue'
import ChatThreadInputBar from './chat-thread/ChatThreadInputBar.vue'

const { t } = useI18n()
const agentStore = useAgentStore()

/** 根据 senderId 查找 agent 的头像 URL */
const getSenderAvatar = (msg: GroupMessage): string | undefined => {
  if (msg.senderType !== 'agent' || !msg.senderId) return undefined
  const agent = agentStore.agents.find((a: AgentProfile) => a.id === msg.senderId)
  return agent?.avatar || undefined
}

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
    analyzing: t('workspace.phaseAnalyzing'),
    dispatching: t('workspace.phaseDispatching'),
    executing: t('workspace.phaseExecuting'),
    synthesizing: t('workspace.phaseSynthesizing'),
    completed: t('workspace.phaseCompleted'),
    failed: t('workspace.phaseFailed'),
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

const isNearBottom = ref(true)
const { scrollToBottom, handleScroll: handleChatScroll } = useChatScroll({
  container: groupMessagesContainer,
  isNearBottom,
  // 深度跟随消息数组；用户翻看历史时不再强拽到底（已批准的行为改进）
  followSource: () => props.messages,
  followDeep: true,
})

// —— 消息窗口化渲染：初始仅挂载最近 N 条，向上滚动分批挂载（保留原生滚动条） ——
const { visibleMessages, maybeLoadOlder } = useChatWindow<GroupMessage>({
  messages: () => props.messages,
  container: groupMessagesContainer,
  rowSelector: '.msg-row',
})

const handleGroupScroll = () => {
  handleChatScroll()
  maybeLoadOlder()
}

defineExpose({ scrollToBottom })
</script>

<template>
  <div class="chat-group-mode">
    <ChatThreadHeader
      :icon="Users"
      :title="group?.name || ''"
      :subtitle="t('workspace.membersSummary', { members: group?.members.length, ai: group?.aiCount })"
    >
      <template #actions>
        <button
          :class="['chat-action-btn lumi-icon-btn', { active: collaborationMode }]"
          :title="t('workspace.collabMode')"
          @click="emit('toggle-collaboration-mode')"
        >
          <Zap :size="15" />
        </button>
        <button class="chat-action-btn lumi-icon-btn" :title="t('workspace.addAgent')" @click="emit('add-agent')">
          <UserPlus :size="15" />
        </button>
        <button class="chat-action-btn lumi-icon-btn" :title="t('workspace.more')">
          <MoreVertical :size="15" />
        </button>
      </template>
    </ChatThreadHeader>

    <div class="collaboration-bar" v-if="collaborationMode">
      <div class="collab-mode-indicator">
        <Zap :size="12" />
        <span>{{ t('workspace.collabModeBanner') }}</span>
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

    <div ref="groupMessagesContainer" class="group-chat-messages" @scroll="handleGroupScroll">
      <ChatThreadBubble
        v-for="msg in visibleMessages"
        :key="msg.id"
        :msg="msg"
        sender-name-fallback="AI"
        agent-only-sender
      >
        <template #avatar="{ msg: m }">
          <div
            class="avatar-agent"
            :style="m.role === '调度员' ? { background: 'var(--lumi-brand-light)', color: 'var(--lumi-brand)' } : {}"
          >
            <img
              v-if="getSenderAvatar(m)"
              :src="getSenderAvatar(m)"
              class="group-msg-avatar-img"
              :alt="m.senderName || ''"
            />
            <Bot v-else :size="14" />
          </div>
        </template>
      </ChatThreadBubble>

      <div v-if="collaborationActive && collaborationPhase" class="collab-progress-msg">
        <div class="collab-progress-inner">
          <Loader2 :size="14" class="spin-animation" />
          <span class="collab-progress-text">
            <template v-if="collaborationPhase === 'analyzing'">{{ t('workspace.collabAnalyzing') }}</template>
            <template v-else-if="collaborationPhase === 'dispatching'">{{ t('workspace.collabDispatching') }}</template>
            <template v-else-if="collaborationPhase === 'executing'">
              {{ t('workspace.collabExecuting', { done: collaborationTasks.filter(tk => tk.status === 'completed').length, total: collaborationTasks.length }) }}
            </template>
            <template v-else-if="collaborationPhase === 'synthesizing'">{{ t('workspace.collabSynthesizing') }}</template>
          </span>
        </div>
      </div>

      <div v-if="agentsResponding && !collaborationActive" class="collab-progress-msg">
        <ThoughtLine
          working
          :label="respondingAgentNames.length > 0
            ? t('workspace.agentsThinking', { names: respondingAgentNames.join('、') })
            : t('workspace.agentResponding')"
          :font-size="13"
        />
      </div>

      <div v-if="messages.length === 0 && !collaborationActive" class="chat-empty">
        <MessageCircle :size="32" />
        <p>{{ t('workspace.groupEmpty') }}</p>
      </div>
    </div>

    <ChatThreadInputBar
      v-model="groupChatInputModel"
      :placeholder="collaborationMode ? t('workspace.phGroupCollab') : t('workspace.phGroupChat')"
      :disabled="collaborationActive || agentsResponding"
      :sending="sendingGroupMessage"
      :send-disabled="!groupChatInput.trim()"
      spinner-on-disabled
      @send="emit('send-group-message')"
    >
      <template #tools>
        <button class="input-tool-btn lumi-icon-btn" :title="t('workspace.image')">
          <ImagePlus :size="16" />
        </button>
        <button class="input-tool-btn lumi-icon-btn" :title="t('workspace.voice')">
          <Mic :size="16" />
        </button>
      </template>
    </ChatThreadInputBar>
  </div>
</template>

<style scoped src="./workspace-shared.css"></style>
<style scoped>
.chat-group-mode {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* transition: all 与全局 .lumi-icon-btn 的 background/color 过滤不同，留本地 */
.chat-action-btn {
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

/* 头像插槽内容：归宿主 scoped 作用域 */
.avatar-agent {
  width: 100%;
  height: 100%;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.group-msg-avatar-img {
  width: 100%;
  height: 100%;
  border-radius: inherit;
  object-fit: cover;
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

/* transition: all 与全局 .lumi-icon-btn 不同，留本地 */
.input-tool-btn {
  transition: all var(--transition-fast);
}

.input-tool-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-secondary);
}
</style>

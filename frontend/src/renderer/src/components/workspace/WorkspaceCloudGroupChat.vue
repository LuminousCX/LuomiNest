<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Cloud, CloudOff, User, Users, Send, Loader2, UserPlus, ChevronUp } from 'lucide-vue-next'
import type { CloudGroupVo } from '@shared/ipc-types'
import type { GroupMessage } from '../../types'
import { useAutoScroll } from '../../composables/useAutoScroll'

/**
 * 云端群聊消息线程（气泡 + 发送框 + 加载更多）。
 * 服务端未上线（state='unavailable'）时整体降级为空态提示，
 * 不自动重试；「重新检测」由用户手动触发。
 */
const { t } = useI18n()

const props = defineProps<{
  group: CloudGroupVo | null
  messages: GroupMessage[]
  /** idle=未登录/未探测 loading=拉取中 ready=可用 unavailable=服务端未开通 */
  state: 'idle' | 'loading' | 'ready' | 'unavailable'
  loading: boolean
  sending: boolean
  canLoadMore: boolean
  input: string
}>()

const emit = defineEmits<{
  invite: []
  'update:input': [value: string]
  send: []
  'load-more': []
  /** 用户手动要求重新探测云端群服务可用性 */
  retry: []
}>()

const container = ref<HTMLElement | null>(null)
const { scrollToBottom } = useAutoScroll(container, () => props.messages, { deep: true, smooth: true })

const inputModel = computed<string>({
  get: () => props.input,
  set: (value) => emit('update:input', value),
})

const unavailable = computed(() => props.state === 'unavailable')
const idle = computed(() => props.state === 'idle')

const roleLabel = computed(() => {
  const role = props.group?.myRole || ''
  if (role === 'owner') return t('workspace.cloud.roleOwner')
  if (role === 'admin') return t('workspace.cloud.roleAdmin')
  return t('workspace.cloud.roleMember')
})

const formatTime = (dateStr: string): string => {
  try {
    return new Date(dateStr).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

const handleKeydown = (event: KeyboardEvent): void => {
  if (!event.isComposing) emit('send')
}

defineExpose({ scrollToBottom })
</script>

<template>
  <div class="cloud-group-chat">
    <div class="cloud-chat-header">
      <div class="chat-title-area">
        <div class="chat-avatar-mini">
          <Cloud :size="14" />
        </div>
        <div class="chat-title-text">
          <h3>{{ group?.name || t('workspace.cloud.sectionLabel') }}</h3>
          <span class="chat-status-line">
            {{ t('workspace.cloud.memberCount', { n: group?.memberCount ?? 0 }) }} · {{ roleLabel }}
          </span>
        </div>
      </div>
      <div class="chat-actions">
        <button class="chat-action-btn" :title="t('workspace.cloud.inviteTitle')" @click="emit('invite')">
          <UserPlus :size="15" />
        </button>
      </div>
    </div>

    <div ref="container" class="cloud-chat-messages">
      <!-- 加载更早历史（契约只有 sinceId 升序，加载更多=加大 limit 重拉） -->
      <div v-if="canLoadMore && !unavailable" class="load-more-row">
        <button class="load-more-btn" :disabled="loading" @click="emit('load-more')">
          <ChevronUp :size="13" />
          <span>{{ t('workspace.cloud.loadMore') }}</span>
        </button>
      </div>

      <div v-if="loading" class="thread-loading">
        <Loader2 :size="15" class="spin-animation" />
        <span>{{ t('workspace.cloud.loading') }}</span>
      </div>

      <template v-else>
        <div
          v-for="msg in messages"
          :key="msg.id"
          :class="['msg-row', msg.senderType]"
        >
          <div v-if="msg.senderType !== 'user'" class="msg-avatar">
            <User :size="15" />
          </div>
          <div :class="['msg-bubble', msg.senderType]">
            <span class="msg-sender" v-if="msg.senderType !== 'user'">{{ msg.senderName }}</span>
            <p class="msg-text">{{ msg.content }}</p>
            <span class="msg-time">{{ formatTime(msg.timestamp) }}</span>
          </div>
          <div v-if="msg.senderType === 'user'" class="msg-avatar user-avatar">
            <User :size="15" />
          </div>
        </div>
      </template>

      <!-- 优雅降级：服务端未开通（404）→ 空态提示，不弹错误、不自动重试 -->
      <div v-if="unavailable" class="cloud-empty">
        <CloudOff :size="32" />
        <p class="cloud-empty-title">{{ t('workspace.cloud.unavailable') }}</p>
        <p class="cloud-empty-hint">{{ t('workspace.cloud.unavailableHint') }}</p>
        <button class="cloud-retry-btn" @click="emit('retry')">{{ t('workspace.cloud.recheck') }}</button>
      </div>

      <!-- 未登录云账号 -->
      <div v-else-if="idle" class="cloud-empty">
        <Cloud :size="32" />
        <p class="cloud-empty-title">{{ t('workspace.cloud.notLoggedIn') }}</p>
      </div>

      <!-- 群内暂无消息 -->
      <div v-else-if="messages.length === 0 && !loading" class="cloud-empty">
        <Users :size="32" />
        <p>{{ t('workspace.cloud.emptyMessages') }}</p>
      </div>
    </div>

    <div class="cloud-chat-input-bar">
      <div class="input-main">
        <input
          v-model="inputModel"
          type="text"
          :placeholder="t('workspace.cloud.phMessage')"
          :disabled="sending || unavailable || idle"
          @keydown.enter="handleKeydown"
        />
        <button
          class="input-send-btn"
          :disabled="!input.trim() || sending || unavailable || idle"
          @click="emit('send')"
        >
          <Loader2 v-if="sending" :size="15" class="spin-animation" />
          <Send v-else :size="15" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.cloud-group-chat {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.cloud-chat-header {
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

.cloud-chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4) var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.load-more-row {
  display: flex;
  justify-content: center;
}

.load-more-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  color: var(--text-muted);
  background: var(--surface);
  border: 1px solid var(--border-light);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.load-more-btn:hover:not(:disabled) {
  color: var(--lumi-brand);
  border-color: var(--lumi-brand-border);
}

.load-more-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.thread-loading {
  align-self: center;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--text-sm);
  color: var(--text-muted);
  padding: var(--space-2) var(--space-4);
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

.msg-bubble {
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  font-size: var(--text-base);
  line-height: 1.5;
  word-break: break-word;
}

.msg-bubble:not(.user) {
  background: var(--surface);
  border: 1px solid var(--border-light);
  color: var(--text-primary);
}

.msg-bubble.user {
  background: var(--lumi-brand);
  color: var(--text-inverse);
}

.msg-sender {
  display: block;
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 2px;
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

.cloud-empty {
  margin: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-muted);
  padding: var(--space-7);
  text-align: center;
}

.cloud-empty p {
  margin: 0;
  font-size: var(--text-base);
}

.cloud-empty-title {
  color: var(--text-secondary);
  font-weight: 600;
}

.cloud-empty-hint {
  font-size: var(--text-sm);
}

.cloud-retry-btn {
  margin-top: var(--space-2);
  padding: 5px 14px;
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  color: var(--lumi-brand);
  background: var(--lumi-brand-light);
  border: 1px solid var(--lumi-brand-border);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.cloud-retry-btn:hover {
  background: var(--lumi-brand-glow);
}

.cloud-chat-input-bar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-5);
  border-top: 1px solid var(--workspace-border);
  background: var(--workspace-sidebar);
  flex-shrink: 0;
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
</style>

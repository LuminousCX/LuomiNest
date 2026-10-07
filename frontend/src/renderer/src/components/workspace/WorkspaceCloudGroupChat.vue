<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Cloud, CloudOff, User, Users, Loader2, UserPlus, ChevronUp } from 'lucide-vue-next'
import type { CloudGroupVo } from '@shared/ipc-types'
import type { GroupMessage } from '../../types'
import { useChatScroll } from '../../composables/useChatScroll'
import ChatThreadHeader from './chat-thread/ChatThreadHeader.vue'
import ChatThreadBubble from './chat-thread/ChatThreadBubble.vue'
import ChatThreadInputBar from './chat-thread/ChatThreadInputBar.vue'

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
const isNearBottom = ref(true)
const { scrollToBottom, handleScroll } = useChatScroll({
  container,
  isNearBottom,
  followSource: () => props.messages,
  followDeep: true,
})

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

defineExpose({ scrollToBottom })
</script>

<template>
  <div class="cloud-group-chat">
    <ChatThreadHeader
      :icon="Cloud"
      :title="group?.name || t('workspace.cloud.sectionLabel')"
      :subtitle="t('workspace.cloud.memberCount', { n: group?.memberCount ?? 0 }) + ' · ' + roleLabel"
    >
      <template #actions>
        <button class="chat-action-btn lumi-icon-btn" :title="t('workspace.cloud.inviteTitle')" @click="emit('invite')">
          <UserPlus :size="15" />
        </button>
      </template>
    </ChatThreadHeader>

    <div ref="container" class="cloud-chat-messages" @scroll="handleScroll()">
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
        <ChatThreadBubble
          v-for="msg in messages"
          :key="msg.id"
          :msg="msg"
          avatar-size="sm"
        >
          <template #avatar>
            <User :size="15" />
          </template>
          <template #avatar-user>
            <User :size="15" />
          </template>
        </ChatThreadBubble>
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

    <ChatThreadInputBar
      v-model="inputModel"
      :placeholder="t('workspace.cloud.phMessage')"
      :disabled="unavailable || idle"
      :sending="sending"
      :send-disabled="!input.trim()"
      @send="emit('send')"
    />
  </div>
</template>

<style scoped src="./workspace-shared.css"></style>
<style scoped>
.cloud-group-chat {
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
</style>

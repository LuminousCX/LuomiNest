<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Bell, CheckCheck, Inbox, Loader2 } from 'lucide-vue-next'
import LumiModal from './LumiModal.vue'
import { formatShortDateTime } from '../../utils/format'
import type { CloudNotificationItem } from '@shared/ipc-types'

/**
 * 站内信弹窗（2026-10-12 生态对接美化批）：
 * - 左上角铃铛的未读红点是唯一入口，列表展示收敛到这里（原左上角弹层只有
 *   300px 宽，标题截断、无正文、贴边，体验局促）；
 * - 数据源 = cloud-account store（60s 轮询主站 /connect/notifications），
 *   打开时立即补拉一次；条目点击标记已读，全部已读一键清零。
 */
const props = defineProps<{
  visible: boolean
  items: CloudNotificationItem[]
  unreadCount: number
  loggedIn: boolean
  loading: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  refresh: []
  markRead: [payload: { id?: number; all?: boolean }]
}>()

const { t } = useI18n()

const formatTime = (ts: string) => (ts ? formatShortDateTime(ts) : '')

const onItemActivate = (item: CloudNotificationItem) => {
  if (!item.isRead) emit('markRead', { id: item.id })
}
</script>

<template>
  <LumiModal
    :visible="visible"
    :title="t('nav.inbox')"
    :width="640"
    @update:visible="emit('update:visible', $event)"
  >
    <div class="inbox-body">
      <div v-if="loggedIn" class="inbox-toolbar">
        <span v-if="unreadCount > 0" class="inbox-unread">{{ t('nav.unreadCount', { n: unreadCount }) }}</span>
        <span v-else class="inbox-unread inbox-unread--zero">{{ t('nav.allRead') }}</span>
        <button
          v-if="unreadCount > 0"
          class="inbox-mark-all"
          :disabled="loading"
          @click="emit('markRead', { all: true })"
        >
          <CheckCheck :size="14" />
          {{ t('nav.markAllRead') }}
        </button>
      </div>

      <div v-if="!loggedIn" class="inbox-state">
        <Inbox :size="28" class="inbox-state-icon" />
        <p>{{ t('nav.loginToView') }}</p>
      </div>

      <div v-else-if="loading && items.length === 0" class="inbox-state">
        <Loader2 :size="22" class="inbox-state-icon spin-animation" />
        <p>{{ t('nav.inboxLoading') }}</p>
      </div>

      <div v-else-if="items.length === 0" class="inbox-state">
        <Bell :size="28" class="inbox-state-icon" />
        <p>{{ t('nav.inboxEmpty') }}</p>
      </div>

      <ul v-else class="inbox-list">
        <li
          v-for="item in items"
          :key="item.id"
          :class="['inbox-item', { 'is-unread': !item.isRead }]"
          @click="onItemActivate(item)"
        >
          <span class="inbox-item-dot" aria-hidden="true"></span>
          <div class="inbox-item-main">
            <span class="inbox-item-title">{{ item.title || item.type }}</span>
            <span v-if="item.content" class="inbox-item-content">{{ item.content }}</span>
          </div>
          <span class="inbox-item-time">{{ formatTime(item.createdAt) }}</span>
        </li>
      </ul>
    </div>
  </LumiModal>
</template>

<style scoped>
.inbox-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.inbox-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 28px;
}

.inbox-unread {
  font-size: var(--text-xs);
  color: var(--lumi-brand);
  padding: 2px var(--space-2);
  background: var(--lumi-brand-light);
  border-radius: var(--radius-full);
}

.inbox-unread--zero {
  color: var(--text-muted);
  background: var(--surface-hover);
}

.inbox-mark-all {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  border: none;
  background: none;
  padding: var(--space-1) var(--space-2);
  font-size: var(--text-xs);
  color: var(--text-secondary);
  cursor: pointer;
  border-radius: var(--radius-sm);
}

.inbox-mark-all:hover:not(:disabled) {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.inbox-mark-all:disabled {
  opacity: 0.5;
  cursor: default;
}

.inbox-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-8) 0;
  color: var(--text-muted);
  font-size: var(--text-sm);
}

.inbox-state-icon {
  color: var(--text-faint);
}

.inbox-list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 420px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.inbox-item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-2);
  border-radius: var(--radius-md);
  cursor: pointer;
}

.inbox-item:hover {
  background: var(--surface-hover);
}

.inbox-item + .inbox-item {
  border-top: 1px solid var(--border-light);
}

.inbox-item-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  background: var(--border-light);
  margin-top: 7px;
  flex-shrink: 0;
}

.inbox-item.is-unread .inbox-item-dot {
  background: var(--lumi-brand);
}

.inbox-item-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.inbox-item-title {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: var(--leading-normal);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.inbox-item.is-unread .inbox-item-title {
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.inbox-item-content {
  font-size: var(--text-xs);
  color: var(--text-muted);
  line-height: var(--leading-normal);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.inbox-item-time {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  flex-shrink: 0;
  margin-top: 2px;
}

.spin-animation {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>

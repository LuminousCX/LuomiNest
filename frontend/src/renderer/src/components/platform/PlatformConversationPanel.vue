<script setup lang="ts">
import { ref } from 'vue'
import {
  MessageSquare, RefreshCw, Bot, User,
  Image as ImageIcon, Cpu,
} from 'lucide-vue-next'
import { usePlatformStore } from '../../stores/platform'
import LumiEmptyState from '../../components/common/LumiEmptyState.vue'
import { formatShortDateTime } from '../../utils/format'
import { useAutoScroll } from '../../composables/useAutoScroll'

const store = usePlatformStore()

const conversationMessagesRef = ref<HTMLElement | null>(null)

const formatMessageTime = (ts: string) => (ts ? formatShortDateTime(ts) : '')

const getRoleIcon = (role: string) => {
  return role === 'assistant' ? Bot : User
}

const getRoleLabel = (role: string) => {
  return role === 'assistant' ? 'LuomiNest' : role === 'system' ? '系统' : '用户'
}

useAutoScroll(conversationMessagesRef, () => store.selectedConversationDetail)
</script>

<template>
  <div class="detail-body conversations-body">
    <div v-if="store.conversationLoading" class="conv-loading">
      <RefreshCw :size="20" class="spin-animation" />
      <span>加载消息中...</span>
    </div>

    <div v-else-if="store.selectedConversationDetail" ref="conversationMessagesRef" class="conv-messages">
      <div
        v-for="msg in store.selectedConversationDetail.messages"
        :key="msg.id"
        :class="['msg-row', msg.role]"
      >
        <div class="msg-avatar">
          <component :is="getRoleIcon(msg.role)" :size="14" />
        </div>
        <div class="msg-content-wrap">
          <div class="msg-meta">
            <span class="msg-sender">{{ msg.senderName || getRoleLabel(msg.role) }}</span>
            <span v-if="msg.model" class="msg-model">
              <Cpu :size="10" />
              {{ msg.model }}
            </span>
            <span class="msg-time">{{ formatMessageTime(msg.timestamp) }}</span>
          </div>
          <div class="msg-bubble">
            <div v-if="msg.content" class="msg-text">{{ msg.content }}</div>
            <div v-if="msg.imageUrls && msg.imageUrls.length > 0" class="msg-images">
              <div v-for="(url, idx) in msg.imageUrls" :key="idx" class="msg-image-item">
                <img :src="url" :alt="`图片 ${idx + 1}`" loading="lazy" />
              </div>
            </div>
            <div v-if="!msg.content && (!msg.imageUrls || msg.imageUrls.length === 0)" class="msg-empty">
              <ImageIcon :size="14" />
              <span>空消息</span>
            </div>
          </div>
        </div>
      </div>
      <LumiEmptyState
        v-if="store.selectedConversationDetail.messages.length === 0"
        :icon="MessageSquare"
        title="对话暂无消息"
        size="md"
      />
    </div>

    <LumiEmptyState
      v-else
      :icon="MessageSquare"
      title="选择对话查看详情"
      size="md"
    />
  </div>
</template>

<style scoped>
.detail-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.conversations-body {
  display: flex;
  flex-direction: row;
  padding: 0;
}

.conv-loading {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  color: var(--text-muted);
  font-size: var(--text-base);
}

.conv-messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.msg-row {
  display: flex;
  gap: var(--space-2);
  max-width: 85%;
  animation: lumi-content-fade-up var(--duration-fast) var(--ease-out-expo) both;
}

.msg-row.user {
  flex-direction: row-reverse;
  align-self: flex-end;
}

.msg-row.assistant,
.msg-row.system {
  align-self: flex-start;
}

.msg-avatar {
  width: calc(var(--space-6) + var(--space-1));
  height: calc(var(--space-6) + var(--space-1));
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
}

.msg-row.user .msg-avatar {
  background: var(--lumi-success-light);
  color: var(--lumi-success);
}

.msg-content-wrap {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.msg-row.user .msg-content-wrap {
  align-items: flex-end;
}

.msg-meta {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

.msg-sender {
  font-weight: var(--font-medium);
  color: var(--text-secondary);
}

.msg-model {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 1px var(--space-1);
  background: var(--bg-secondary);
  border-radius: var(--radius-xs);
  font-size: var(--text-2xs);
}

.msg-time {
  margin-left: auto;
}

.msg-row.user .msg-time {
  margin-left: 0;
  margin-right: auto;
  order: -1;
}

.msg-bubble {
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  font-size: var(--text-base);
  line-height: var(--leading-normal);
  word-break: break-word;
  background: var(--surface-hover);
  color: var(--text-primary);
  border: 1px solid var(--border-light);
}

.msg-row.assistant .msg-bubble {
  border-top-left-radius: var(--radius-xs);
  background: var(--lumi-brand-light);
  border-color: var(--lumi-brand-glow);
}

.msg-row.user .msg-bubble {
  border-top-right-radius: var(--radius-xs);
  background: var(--lumi-success-light);
  border-color: var(--lumi-success);
  color: var(--text-primary);
}

.msg-text {
  white-space: pre-wrap;
}

.msg-images {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
  margin-top: var(--space-2);
}

.msg-image-item {
  width: 160px;
  height: 160px;
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: var(--bg-secondary);
  border: 1px solid var(--border-light);
  cursor: pointer;
  transition: transform var(--transition-fast);
}

.msg-image-item:hover {
  transform: scale(1.02);
}

.msg-image-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.msg-empty {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  color: var(--text-muted);
  font-size: var(--text-xs);
  font-style: italic;
}
</style>

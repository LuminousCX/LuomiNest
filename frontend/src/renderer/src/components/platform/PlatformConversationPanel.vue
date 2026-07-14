<script setup lang="ts">
import { ref, watch } from 'vue'
import {
  Globe, Radio, Cable, Link, MessageCircle, Send, Gamepad2, Home, Smartphone,
  MessageSquare, Eye, ChevronLeft,
  Image as ImageIcon, Cpu, RefreshCw, Bot, User,
} from 'lucide-vue-next'
import { usePlatformStore } from '../../stores/platform'
import LumiButton from '../../components/common/LumiButton.vue'
import LumiEmptyState from '../../components/common/LumiEmptyState.vue'

const store = usePlatformStore()

const conversationMessagesRef = ref<HTMLElement | null>(null)

const iconMap: Record<string, any> = {
  Globe, Radio, Cable, Link, MessageCircle, Send, Gamepad2, Home, Smartphone,
}

const getIcon = (iconName: string) => {
  return iconMap[iconName] || Globe
}

const formatMessageTime = (ts: string) => {
  if (!ts) return ''
  try {
    const d = new Date(ts)
    return d.toLocaleString('zh-CN', {
      month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return ts
  }
}

const getRoleIcon = (role: string) => {
  return role === 'assistant' ? Bot : User
}

const getRoleLabel = (role: string) => {
  return role === 'assistant' ? 'LuomiNest' : role === 'system' ? '系统' : '用户'
}

watch(() => store.selectedConversationDetail, () => {
  if (conversationMessagesRef.value) {
    conversationMessagesRef.value.scrollTop = conversationMessagesRef.value.scrollHeight
  }
}, { flush: 'post' })

const handleSelectConversation = (conversationId: string) => {
  store.selectConversation(conversationId)
}

const handleBackToConversationList = () => {
  store.selectConversation(null)
}
</script>

<template>
  <div class="detail-body conversations-body">
    <div v-if="!store.selectedConversationId" class="conv-list-pane">
      <div v-if="store.selectedInstance" class="detail-badge">
        <component :is="getIcon(store.selectedInstance.icon)" :size="12" />
        <span>{{ store.selectedInstance.name }}</span>
        <span class="badge-count">{{ store.selectedConversations.length }} 个对话</span>
      </div>
      <div class="conv-list">
        <div
          v-for="c in store.selectedConversations"
          :key="c.id"
          class="conv-item clickable"
          @click="handleSelectConversation(c.id)"
        >
          <div class="conv-item-header">
            <span class="conv-item-platform">
              <MessageCircle :size="11" />
              {{ c.platformName }}
            </span>
            <span class="conv-item-time">{{ formatMessageTime(c.time) }}</span>
          </div>
          <span class="conv-item-title">{{ c.title || '未命名对话' }}</span>
          <div class="conv-item-footer">
            <span class="conv-item-preview">{{ c.preview || '暂无消息' }}</span>
            <span class="conv-item-count">{{ c.messageCount }} 条</span>
          </div>
        </div>
        <LumiEmptyState
          :icon="store.selectedInstanceId ? MessageSquare : Eye"
          :title="store.selectedInstanceId ? '暂无对话记录' : '选择平台查看对话记录'"
          size="md"
        />
      </div>
      <div class="detail-notice">
        <Eye :size="14" />
        <span>只读模式 — 对话来自第三方平台推送</span>
      </div>
    </div>

    <div v-else class="conv-detail-pane">
      <div class="conv-detail-header">
        <LumiButton
          size="sm"
          icon-only
          variant="ghost"
          class="back-btn"
          aria-label="返回对话列表"
          @click="handleBackToConversationList"
        >
          <template #icon><ChevronLeft :size="16" /></template>
        </LumiButton>
        <div class="conv-detail-title">
          <span class="title-text">{{ store.selectedConversationDetail?.title || '对话详情' }}</span>
          <span v-if="store.selectedConversationDetail" class="title-meta">
            {{ store.selectedConversationDetail.platformName }}
            <template v-if="store.selectedConversationDetail.senderName">
              · {{ store.selectedConversationDetail.senderName }}
            </template>
            <template v-if="store.selectedConversationDetail.isGroup"> · 群聊</template>
          </span>
        </div>
        <span class="conv-detail-count">
          {{ store.selectedConversationDetail?.messageCount || 0 }} 条消息
        </span>
      </div>

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
        title="无法加载对话内容"
        size="md"
      />
    </div>
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

.conv-list-pane,
.conv-detail-pane {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.conv-list-pane {
  border-right: 1px solid var(--border-light);
}

.conv-list-pane .detail-badge {
  border-bottom: 1px solid var(--border-light);
}

.detail-badge {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-4);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
  border-bottom: 1px solid var(--border-light);
}

.badge-count {
  margin-left: auto;
  font-size: var(--text-2xs);
  padding: 1px var(--space-1);
  border-radius: var(--radius-full);
  background: var(--lumi-brand-glow);
  color: var(--lumi-brand);
  font-weight: var(--font-medium);
}

.conv-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-2);
}

.conv-item {
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  cursor: default;
  transition: background var(--transition-fast);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.conv-item:hover {
  background: var(--surface-hover);
}

.conv-item.clickable {
  cursor: pointer;
}

.conv-item.clickable:hover {
  background: var(--surface-hover);
  border-left: 2px solid var(--lumi-brand);
  padding-left: var(--space-4);
}

.conv-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.conv-item-platform {
  font-size: var(--text-xs);
  color: var(--lumi-brand);
  font-weight: var(--font-medium);
}

.conv-item-time {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.conv-item-title {
  font-size: var(--text-base);
  font-weight: var(--font-medium);
  color: var(--text-primary);
}

.conv-item-preview {
  font-size: var(--text-sm);
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-item-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-2);
}

.conv-item-count {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  padding: 1px var(--space-1);
  background: var(--bg-secondary);
  border-radius: var(--radius-xs);
  flex-shrink: 0;
}

.detail-notice {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  padding: var(--space-2);
  background: var(--bg-secondary);
  color: var(--text-muted);
  font-size: var(--text-xs);
  border-top: 1px solid var(--border-light);
}

.conv-detail-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  border-bottom: 1px solid var(--border-light);
  background: var(--surface);
}

.back-btn {
  color: var(--text-secondary);
}

.back-btn:hover:not(:disabled) {
  background: var(--surface-hover);
  color: var(--lumi-brand);
}

.conv-detail-title {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.title-text {
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.title-meta {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.conv-detail-count {
  font-size: var(--text-xs);
  padding: 3px var(--space-2);
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
  border-radius: var(--radius-xs);
  font-weight: var(--font-medium);
  flex-shrink: 0;
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

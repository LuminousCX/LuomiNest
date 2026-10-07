<script setup lang="ts">
/**
 * 群聊消息气泡（本地群/云群共用）。
 *
 * 完整渲染一条 GroupMessage：头像位 + 气泡（发送者/角色/协作标签、正文、
 * 流式光标、时间）。synthesis/角色/协作标签是 GroupMessage 的固有渲染契约，
 * 云群消息没有这些字段时自然隐藏，因此一并收进本组件。
 * 头像内容因宿主而异（本地群=agent 头像图/机器人图标，云群=用户图标），
 * 通过 avatar / avatar-user 插槽注入，头像容器样式在本组件。
 */
import { User } from 'lucide-vue-next'
import { formatTime } from '@/utils/format'
import type { GroupMessage } from '../../../types'

const props = withDefaults(
  defineProps<{
    msg: GroupMessage
    /** 头像尺寸：md=32px（本地群），sm=28px（云群） */
    avatarSize?: 'md' | 'sm'
    /** 非用户发送者名字为空时的兜底（本地群传 'AI'） */
    senderNameFallback?: string
    /**
     * 仅 agent 显示头像/发送者行（本地群旧语义：system 消息是无头像无发送者的素气泡）。
     * 缺省 false = 云群语义（所有非 user 都显示）。
     */
    agentOnlySender?: boolean
  }>(),
  {
    avatarSize: 'md',
    senderNameFallback: undefined,
    agentOnlySender: false,
  },
)

/** 是否渲染头像位与发送者行（本地群仅 agent；云群所有非 user） */
const showSender = (): boolean =>
  props.agentOnlySender ? props.msg.senderType === 'agent' : props.msg.senderType !== 'user'

/** 气泡底色：agentOnlySender 模式下 system 消息保持素气泡 */
const bubbleClass = (): (string | Record<string, boolean>)[] => {
  const styled = props.msg.senderType === 'agent' || !props.agentOnlySender
  return [
    'msg-bubble',
    props.msg.senderType,
    { 'synthesis-bubble': props.msg.collaboration?.type === 'synthesis', 'bubble-unstyled': !styled },
  ]
}

const senderName = (): string => props.msg.senderName || props.senderNameFallback || ''
</script>

<template>
  <div :class="['msg-row', msg.senderType, { 'collab-synthesis': msg.collaboration?.type === 'synthesis' }]">
    <div
      v-if="showSender()"
      :class="['msg-avatar', { 'msg-avatar--sm': avatarSize === 'sm' }]"
    >
      <slot name="avatar" :msg="msg" />
    </div>

    <div :class="bubbleClass()">
      <span v-if="showSender()" class="msg-sender">
        {{ senderName() }}
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
      <p class="msg-text">
        {{ msg.content }}
        <span v-if="msg.isStreaming" class="streaming-cursor">▋</span>
      </p>
      <span v-if="!msg.isStreaming" class="msg-time">{{ formatTime(msg.timestamp) }}</span>
    </div>

    <div
      v-if="msg.senderType === 'user'"
      :class="['msg-avatar', 'user-avatar', { 'msg-avatar--sm': avatarSize === 'sm' }]"
    >
      <slot name="avatar-user">
        <User :size="16" />
      </slot>
    </div>
  </div>
</template>

<style scoped>
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
  width: 32px;
  height: 32px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: var(--lumi-brand-glow);
  color: var(--lumi-brand);
}

.msg-avatar--sm {
  width: 28px;
  height: 28px;
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

/* 非 user 一律面板底（原本地群 .msg-bubble.agent 与云群 :not(.user) 值全同） */
.msg-bubble:not(.user) {
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

/* agentOnlySender（本地群）模式：system 等非 agent 消息保持无底色素气泡（旧行为） */
.msg-bubble.bubble-unstyled {
  background: transparent;
  border-color: transparent;
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

.streaming-cursor {
  display: inline-block;
  margin-left: 2px;
  color: var(--lumi-brand);
  font-weight: 600;
  animation: luominest-cursor-blink 1s ease-in-out infinite;
}

@keyframes luominest-cursor-blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
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
</style>

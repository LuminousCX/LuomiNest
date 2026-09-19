<script setup lang="ts">
/**
 * 命令执行三档确认弹窗（陪伴式安全）。
 *
 * 后端 PermissionGate 中间件在 agent 执行命令前推送 permission_request，
 * 此处展示命令内容与倒计时，由用户选择：
 * - 允许一次：仅放行本条命令
 * - 允许该对话：本会话内后续命令免确认
 * - 完全访问：持久化放行（黑名单硬防线仍生效）
 * - 拒绝：通知 agent 取消执行
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Terminal, ShieldCheck, MessageCircleHeart, Infinity as InfinityIcon, Ban } from 'lucide-vue-next'
import LumiModal from '../common/LumiModal.vue'
import LumiButton from '../common/LumiButton.vue'
import type { PermissionRequest } from '../../types'

const props = defineProps<{
  request: PermissionRequest | null
  loading?: boolean
}>()

const emit = defineEmits<{
  resolve: [requestId: string, decision: 'once' | 'session' | 'full' | 'deny']
}>()

const { t } = useI18n()

const remaining = ref(0)
let timer: ReturnType<typeof setInterval> | null = null

const stopTimer = (): void => {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

watch(
  () => props.request?.request_id,
  (id) => {
    stopTimer()
    if (!id || !props.request) return
    remaining.value = Math.max(1, Math.ceil(props.request.timeout))
    timer = setInterval(() => {
      remaining.value -= 1
      if (remaining.value <= 0) {
        stopTimer()
        // 倒计时归零即拒绝（后端超时也会兜底拒绝，此处提前收尾）
        emit('resolve', props.request!.request_id, 'deny')
      }
    }, 1000)
  },
  { immediate: true },
)

onBeforeUnmount(stopTimer)

const countdownText = computed(() =>
  props.request ? t('chat.permission.countdown', { seconds: remaining.value }) : '',
)

const emitResolve = (decision: 'once' | 'session' | 'full' | 'deny'): void => {
  if (!props.request) return
  stopTimer()
  emit('resolve', props.request.request_id, decision)
}
</script>

<template>
  <LumiModal
    :visible="!!request"
    :title="t('chat.permission.title')"
    size="md"
    :mask-closable="false"
  >
    <div v-if="request" class="perm-dialog">
      <div class="perm-head">
        <div class="perm-icon"><Terminal :size="18" /></div>
        <div class="perm-meta">
          <div class="perm-tool">{{ t('chat.permission.toolLabel') }}：{{ request.tool }}</div>
          <div class="perm-countdown">{{ countdownText }}</div>
        </div>
      </div>
      <pre class="perm-command">{{ request.command }}</pre>
      <p class="perm-hint">{{ t('chat.permission.hint') }}</p>
      <div class="perm-actions">
        <LumiButton variant="primary" :disabled="loading" @click="emitResolve('once')">
          <MessageCircleHeart :size="15" style="margin-right: 6px" />
          {{ t('chat.permission.once') }}
        </LumiButton>
        <LumiButton variant="secondary" :disabled="loading" @click="emitResolve('session')">
          <ShieldCheck :size="15" style="margin-right: 6px" />
          {{ t('chat.permission.session') }}
        </LumiButton>
        <LumiButton variant="secondary" :disabled="loading" @click="emitResolve('full')">
          <InfinityIcon :size="15" style="margin-right: 6px" />
          {{ t('chat.permission.full') }}
        </LumiButton>
        <LumiButton variant="danger" :disabled="loading" @click="emitResolve('deny')">
          <Ban :size="15" style="margin-right: 6px" />
          {{ t('chat.permission.deny') }}
        </LumiButton>
      </div>
      <p class="perm-footnote">{{ t('chat.permission.fullNote') }}</p>
    </div>
  </LumiModal>
</template>

<style scoped>
.perm-dialog {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.perm-head {
  display: flex;
  align-items: center;
  gap: 10px;
}
.perm-icon {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--lumi-primary-soft, rgba(99, 102, 241, 0.12));
  color: var(--lumi-primary, #6366f1);
  flex-shrink: 0;
}
.perm-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.perm-tool {
  font-size: 13px;
  font-weight: 600;
  color: var(--lumi-text-primary, #1f2937);
}
.perm-countdown {
  font-size: 12px;
  color: var(--lumi-text-secondary, #6b7280);
}
.perm-command {
  margin: 0;
  padding: 12px 14px;
  border-radius: 10px;
  background: var(--lumi-code-bg, #0f172a0d);
  border: 1px solid var(--lumi-border, #e5e7eb);
  font-family: var(--lumi-font-mono, 'JetBrains Mono', Consolas, monospace);
  font-size: 12.5px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 180px;
  overflow: auto;
  color: var(--lumi-text-primary, #1f2937);
}
.perm-hint {
  margin: 0;
  font-size: 12.5px;
  color: var(--lumi-text-secondary, #6b7280);
  line-height: 1.6;
}
.perm-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.perm-footnote {
  margin: 0;
  font-size: 11.5px;
  color: var(--lumi-text-tertiary, #9ca3af);
  line-height: 1.5;
}
</style>

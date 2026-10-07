<script setup lang="ts">
/**
 * 群聊底部输入条（本地群/云群共用）。
 *
 * 整条底栏 = 可选工具位插槽 + 输入框 + 发送钮。
 * Enter 发送内置 isComposing 守卫（修复本地群中文输入法回车误发的问题）；
 * 工具按钮（图片/语音占位）由宿主通过 tools 插槽提供，其样式留在宿主。
 */
import { computed } from 'vue'
import { Loader2, Send } from 'lucide-vue-next'

const props = withDefaults(
  defineProps<{
    modelValue: string
    placeholder?: string
    /** 输入/发送整体禁用（含 sending 时） */
    disabled?: boolean
    /** 发送中（按钮转圈） */
    sending?: boolean
    /** 额外的发送禁用条件（如输入为空） */
    sendDisabled?: boolean
    /** 禁用时按钮是否显示转圈（本地群协作/等待场景为 true；云群降级态保持 Send 图标） */
    spinnerOnDisabled?: boolean
  }>(),
  {
    placeholder: '',
    disabled: false,
    sending: false,
    sendDisabled: false,
    spinnerOnDisabled: false,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
  send: []
}>()

const model = computed<string>({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const sendBlocked = computed(() => props.disabled || props.sending || props.sendDisabled)

const handleEnter = (event: KeyboardEvent): void => {
  // 中文输入法组词期间的回车是选字，不触发发送
  if (event.isComposing) return
  emit('send')
}
</script>

<template>
  <div class="chat-thread-input-bar">
    <div v-if="$slots.tools" class="input-tools">
      <slot name="tools" />
    </div>
    <div class="input-main">
      <input
        v-model="model"
        type="text"
        :placeholder="placeholder"
        :disabled="disabled"
        @keydown.enter="handleEnter"
      />
      <button class="input-send-btn" :disabled="sendBlocked" @click="emit('send')">
        <Loader2 v-if="sending || (spinnerOnDisabled && disabled)" :size="15" class="spin-animation" />
        <Send v-else :size="15" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.chat-thread-input-bar {
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

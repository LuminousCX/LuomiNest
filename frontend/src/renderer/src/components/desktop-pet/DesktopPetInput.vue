<script setup lang="ts">
/**
 * LuomiNest 桌面宠物输入区
 *
 * 桌宠窗口底部的文字输入 + 麦克风按钮。
 * - 文字输入：Enter 发送，Shift+Enter 换行
 * - 麦克风按钮：STT 占位（点击提示功能开发中）
 * - 发送/取消按钮：流式响应中显示取消
 *
 * 通过 window.api.desktopPetChat.sendMessage/cancel 转发到主应用窗口，
 * 由 useDesktopPetChatBridge 调用 chatStore.sendMessage（主 Agent，普通模式）。
 */
import { ref, computed } from 'vue'
import { Send, Square, Mic } from 'lucide-vue-next'

const props = defineProps<{
  isStreaming: boolean
}>()

const emit = defineEmits<{
  'send': [text: string]
  'cancel': []
}>()

const inputText = ref('')
const isMicActive = ref(false)

const canSend = computed(() => inputText.value.trim().length > 0 && !props.isStreaming)

const handleSend = (): void => {
  const text = inputText.value.trim()
  if (!text || props.isStreaming) return
  emit('send', text)
  inputText.value = ''
}

const handleCancel = (): void => {
  emit('cancel')
}

const handleKeydown = (e: KeyboardEvent): void => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

const handleMicClick = (): void => {
  // STT 占位：语音输入功能开发中
  isMicActive.value = !isMicActive.value
}
</script>

<template>
  <div class="pet-input-area">
    <button
      class="pet-mic-btn"
      :class="{ active: isMicActive }"
      :title="isMicActive ? '语音输入（开发中）' : '语音输入'"
      @click="handleMicClick"
    >
      <Mic :size="16" />
    </button>

    <input
      v-model="inputText"
      class="pet-input"
      type="text"
      :placeholder="isStreaming ? '正在回复中...' : '和我说点什么吧'"
      :disabled="isStreaming"
      @keydown="handleKeydown"
    />

    <button
      v-if="!isStreaming"
      class="pet-send-btn"
      :disabled="!canSend"
      title="发送"
      @click="handleSend"
    >
      <Send :size="16" />
    </button>
    <button
      v-else
      class="pet-cancel-btn"
      title="停止生成"
      @click="handleCancel"
    >
      <Square :size="16" />
    </button>
  </div>
</template>

<style scoped>
.pet-input-area {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: color-mix(in srgb, var(--surface) 85%, transparent);
  backdrop-filter: blur(12px);
  border-top: 1px solid var(--border-light);
  z-index: var(--z-sticky);
  -webkit-app-region: no-drag;
}

.pet-mic-btn,
.pet-send-btn,
.pet-cancel-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--space-7);
  height: var(--space-7);
  border-radius: var(--radius-full);
  border: 1px solid var(--border-light);
  background: var(--surface);
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast) var(--ease-in-out);
  flex-shrink: 0;
}

.pet-mic-btn:hover,
.pet-send-btn:hover:not(:disabled) {
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
}

.pet-mic-btn.active {
  border-color: var(--lumi-danger);
  color: var(--lumi-danger);
  background: var(--lumi-danger-light);
  animation: mic-pulse 1.5s var(--ease-in-out) infinite;
}

@keyframes mic-pulse {
  0%, 100% { box-shadow: 0 0 0 0 var(--lumi-danger-glow, transparent); }
  50% { box-shadow: 0 0 0 6px transparent; }
}

.pet-send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.pet-cancel-btn {
  border-color: var(--lumi-danger);
  color: var(--lumi-danger);
  background: var(--lumi-danger-light);
}

.pet-cancel-btn:hover {
  background: var(--lumi-danger);
  color: var(--text-inverse);
}

.pet-input {
  flex: 1;
  min-width: 0;
  height: var(--space-7);
  padding: 0 var(--space-3);
  border-radius: var(--radius-full);
  border: 1px solid var(--border-light);
  background: var(--surface);
  color: var(--text-primary);
  font-size: var(--text-sm);
  outline: none;
  transition: border-color var(--transition-fast) var(--ease-in-out);
}

.pet-input:focus {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 2px var(--focus-ring);
}

.pet-input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.pet-input::placeholder {
  color: var(--text-muted);
}
</style>

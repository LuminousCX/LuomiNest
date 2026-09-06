<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  Send,
  Square,
  Wand2,
} from 'lucide-vue-next'
import LumiButton from '../common/LumiButton.vue'
import SkillsPicker from '../common/SkillsPicker.vue'
import { useAutoResizeTextarea } from '../../composables/useAutoResizeTextarea'
import type { ProviderLogo } from '../../types'
import type { ChatModeLevel, WorkflowModeOption } from './types'

const props = defineProps<{
  inputText: string
  isBackendReady: boolean
  isStreaming: boolean
  canSend: boolean
  currentModel: string
  currentProviderLogo: ProviderLogo
  chatMode: ChatModeLevel
  chatModeOptions: WorkflowModeOption[]
  selectedSkillIds: string[]
}>()

const emit = defineEmits<{
  'update:inputText': [value: string]
  send: []
  cancel: []
  'go-settings': []
  'select-chat-mode': [value: ChatModeLevel]
  'update:selectedSkillIds': [ids: string[]]
}>()

const textareaRef = ref<HTMLTextAreaElement | null>(null)
const { autoResize, resetTextareaHeight } = useAutoResizeTextarea(textareaRef)

const inputTextModel = computed<string>({
  get: () => props.inputText,
  set: (value) => emit('update:inputText', value),
})

const isWorkflowMode = computed(() => props.chatMode !== 'normal')

const selectMode = (value: ChatModeLevel) => {
  emit('select-chat-mode', value)
}

const toggleWorkflowMode = () => {
  if (isWorkflowMode.value) {
    emit('select-chat-mode', 'normal')
  } else {
    emit('select-chat-mode', 'standard')
  }
}

defineExpose({
  resetTextareaHeight,
  autoResize,
})
</script>

<template>
  <div class="input-area">
    <div class="input-wrapper lumi-card">
      <SkillsPicker
        :selected-ids="selectedSkillIds"
        class="input-skills-picker"
        @update:selected-ids="emit('update:selectedSkillIds', $event)"
      />
      <textarea
        ref="textareaRef"
        v-model="inputTextModel"
        placeholder="与陪伴 AI 对话..."
        rows="1"
        class="chat-input"
        :disabled="!isBackendReady"
        @keydown.enter.exact.prevent="emit('send')"
        @input="autoResize"
      ></textarea>
      <div class="input-toolbar">
        <div class="toolbar-left">
          <!-- 2026-08 全局模型统一：工作台不提供模型切换，展示全局主模型；
               点击徽章跳转到 设置 → 模型设置 -->
          <div
            class="model-badge"
            title="当前使用全局主模型，点击前往 设置 → 模型设置 切换"
            @click="emit('go-settings')"
          >
            <span v-if="currentProviderLogo.svgIcon" class="provider-icon-mini provider-svg-mini" v-html="currentProviderLogo.svgIcon"></span>
            <span v-else class="provider-icon-mini" :style="{ background: currentProviderLogo.color }">
              {{ currentProviderLogo.initials }}
            </span>
            <span class="model-btn-text">{{ currentModel }}</span>
          </div>
          <LumiButton
            :class="['workflow-toggle', { active: isWorkflowMode }]"
            variant="secondary"
            size="sm"
            :title="isWorkflowMode ? '专业模式已开启：长任务将自动分解并调度内部模块' : '当前为普通模式：点击切换专业模式'"
            @click="toggleWorkflowMode"
          >
            <template #icon>
              <Wand2 :size="15" />
            </template>
            <span class="workflow-toggle-text">{{ isWorkflowMode ? '专业' : '普通' }}</span>
          </LumiButton>
          <div v-if="isWorkflowMode" class="workflow-mode-selector">
            <LumiButton
              v-for="opt in chatModeOptions"
              :key="opt.value"
              :class="['mode-chip', { active: chatMode === opt.value }]"
              variant="secondary"
              size="sm"
              :title="opt.title"
              @click="selectMode(opt.value)"
            >
              {{ opt.label }}
            </LumiButton>
          </div>
        </div>
        <div class="toolbar-right">
          <LumiButton
            v-if="isStreaming"
            variant="danger"
            size="md"
            icon-only
            aria-label="停止生成"
            class="send-btn stop"
            @click="emit('cancel')"
          >
            <template #icon>
              <Square :size="16" />
            </template>
          </LumiButton>
          <LumiButton
            v-else
            variant="primary"
            size="md"
            icon-only
            aria-label="发送"
            class="send-btn"
            :disabled="!canSend"
            @click="emit('send')"
          >
            <template #icon>
              <Send :size="17" />
            </template>
          </LumiButton>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
button:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px var(--focus-ring);
}

.input-area {
  padding: var(--space-3) var(--space-6) var(--space-4);
  background: var(--bg);
  flex-shrink: 0;
}

.input-wrapper {
  max-width: 820px;
  margin: 0 auto;
  padding: var(--space-3);
  border: 1px solid var(--border-light);
  transition: border-color var(--transition-fast);
}

.input-skills-picker {
  margin-bottom: var(--space-2);
  min-height: 0;
}

.input-skills-picker:empty {
  display: none;
}

.input-wrapper:focus-within {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

.chat-input {
  width: 100%;
  border: none;
  outline: none;
  background: transparent;
  resize: none;
  font-size: var(--text-md);
  line-height: var(--leading-relaxed);
  color: var(--text-primary);
  font-family: inherit;
  min-height: var(--space-6);
  max-height: 120px;
}

.chat-input::placeholder {
  color: var(--text-muted);
}

.chat-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.input-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: var(--space-2);
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.workflow-toggle {
  gap: var(--space-1);
  font-size: var(--text-xs);
  color: var(--text-muted);
  background: var(--surface-hover);
  border-color: transparent;
  border-radius: var(--radius-full);
}

.workflow-toggle:hover {
  color: var(--text-primary);
  background: var(--surface-active);
}

.workflow-toggle.active {
  color: var(--lumi-success);
  background: var(--lumi-success-light);
  border-color: color-mix(in srgb, var(--lumi-success) 30%, transparent);
}

.workflow-toggle-text {
  white-space: nowrap;
}

.workflow-mode-selector {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1);
  background: var(--surface-hover);
  border-radius: var(--radius-full);
}

.mode-chip {
  padding: var(--space-1) var(--space-2);
  font-size: var(--text-xs);
  color: var(--text-muted);
  background: transparent;
  border-color: transparent;
  border-radius: var(--radius-full);
  white-space: nowrap;
}

.mode-chip:hover {
  color: var(--text-primary);
  background: var(--surface-active);
}

.mode-chip.active {
  color: var(--lumi-success);
  background: var(--lumi-success-light);
}

.model-btn-text {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 2026-08 全局模型统一：工作台只读徽章展示全局主模型，点击跳转设置页 */
.model-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-full);
  background: var(--surface-hover);
  color: var(--text-muted);
  font-size: var(--text-xs);
  cursor: pointer;
  user-select: none;
  max-width: 220px;
  transition: background var(--transition-fast) ease-in-out, color var(--transition-fast) ease-in-out;
}

.model-badge:hover {
  background: var(--surface-active);
  color: var(--text-primary);
}

.provider-icon-mini {
  width: 18px;
  height: 18px;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-2xs);
  font-weight: 700;
  color: var(--text-inverse);
  flex-shrink: 0;
}

.provider-svg-mini {
  background: transparent !important;
}

.provider-svg-mini :deep(svg) {
  width: var(--space-4);
  height: var(--space-4);
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.send-btn.lumi-btn {
  width: 34px;
  height: 34px;
}
</style>

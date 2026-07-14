<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  Send,
  Square,
  ChevronDown,
  Wand2,
} from 'lucide-vue-next'
import LumiButton from '../common/LumiButton.vue'
import SkillsPicker from '../common/SkillsPicker.vue'
import type { ProviderLogo } from '../../types'
import type { ChatModeLevel, WorkflowModeOption } from './types'

const props = defineProps<{
  inputText: string
  isBackendReady: boolean
  isStreaming: boolean
  canSend: boolean
  currentModel: string
  currentProvider: string
  currentProviderLogo: ProviderLogo
  availableModelOptions: {
    providerId: string
    providerName: string
    providerLogo: ProviderLogo
    modelId: string
    modelName: string
  }[]
  showModelDropdown: boolean
  chatMode: ChatModeLevel
  chatModeOptions: WorkflowModeOption[]
  selectedSkillIds: string[]
}>()

const emit = defineEmits<{
  'update:inputText': [value: string]
  send: []
  cancel: []
  'toggle-model-dropdown': []
  'select-model': [providerId: string, modelId: string]
  'update:chatMode': [value: ChatModeLevel]
  'select-chat-mode': [value: ChatModeLevel]
  'update:selectedSkillIds': [ids: string[]]
}>()

const textareaRef = ref<HTMLTextAreaElement | null>(null)

const inputTextModel = computed<string>({
  get: () => props.inputText,
  set: (value) => emit('update:inputText', value),
})

const isWorkflowMode = computed(() => props.chatMode !== 'normal')

const selectMode = (value: ChatModeLevel) => {
  emit('update:chatMode', value)
  emit('select-chat-mode', value)
}

const resetTextareaHeight = () => {
  if (textareaRef.value) {
    textareaRef.value.style.height = 'auto'
  }
}

const autoResize = () => {
  if (textareaRef.value) {
    textareaRef.value.style.height = 'auto'
    textareaRef.value.style.height = `${Math.min(textareaRef.value.scrollHeight, 120)}px`
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
          <div class="model-dropdown-container">
            <LumiButton
              variant="secondary"
              size="sm"
              class="tool-btn"
              @click.stop="emit('toggle-model-dropdown')"
            >
              <template #icon>
                <span v-if="currentProviderLogo.svgIcon" class="provider-icon-mini provider-svg-mini" v-html="currentProviderLogo.svgIcon"></span>
                <span v-else class="provider-icon-mini" :style="{ background: currentProviderLogo.color }">
                  {{ currentProviderLogo.initials }}
                </span>
              </template>
              <span class="model-btn-text">{{ currentModel }}</span>
              <ChevronDown :size="14" />
            </LumiButton>
            <Transition name="dropdown-fade">
              <div v-if="showModelDropdown" class="model-dropdown">
                <div class="dropdown-header">选择模型</div>
                <div class="dropdown-list">
                  <LumiButton
                    v-for="opt in availableModelOptions"
                    :key="`${opt.providerId}-${opt.modelId}`"
                    variant="ghost"
                    size="sm"
                    block
                    :class="['dropdown-item', { active: currentProvider === opt.providerId && currentModel === opt.modelId }]"
                    @click="emit('select-model', opt.providerId, opt.modelId)"
                  >
                    <template #icon>
                      <span v-if="opt.providerLogo.svgIcon" class="provider-icon-mini provider-svg-mini" v-html="opt.providerLogo.svgIcon"></span>
                      <span v-else class="provider-icon-mini" :style="{ background: opt.providerLogo.color }">
                        {{ opt.providerLogo.initials }}
                      </span>
                    </template>
                    <div class="dropdown-item-info">
                      <span class="dropdown-item-model">{{ opt.modelName }}</span>
                      <span class="dropdown-item-provider">{{ opt.providerName }}</span>
                    </div>
                  </LumiButton>
                  <div v-if="availableModelOptions.length === 0" class="dropdown-empty">
                    暂无可用模型，请先到设置多选模型
                  </div>
                </div>
              </div>
            </Transition>
          </div>
          <LumiButton
            :class="['workflow-toggle', { active: isWorkflowMode }]"
            variant="secondary"
            size="sm"
            :title="isWorkflowMode ? '专业模式已开启：长任务将自动分解并调度内部模块' : '当前为普通模式：点击标准/超长开启专业模式'"
          >
            <template #icon>
              <Wand2 :size="15" />
            </template>
            <span class="workflow-toggle-text">{{ isWorkflowMode ? '专业' : '普通' }}</span>
          </LumiButton>
          <div class="workflow-mode-selector">
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
            <Square :size="16" />
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
            <Send :size="17" />
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

.model-dropdown-container {
  position: relative;
}

.model-dropdown {
  position: absolute;
  bottom: calc(100% + var(--space-2));
  left: 0;
  width: 280px;
  background: var(--surface);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  border: 1px solid var(--border-light);
  z-index: 9999;
  overflow: hidden;
}

.dropdown-header {
  padding: var(--space-3) var(--space-4);
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.dropdown-header::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: var(--space-4);
  right: var(--space-4);
  height: 1px;
  background: var(--divider-soft);
}

.dropdown-list {
  max-height: 280px;
  overflow-y: auto;
  padding: var(--space-1);
}

.dropdown-item.lumi-btn {
  justify-content: flex-start;
  text-align: left;
  gap: var(--space-3);
  padding: var(--space-2) 10px;
  width: 100%;
}

.dropdown-item:hover {
  background: var(--workspace-hover);
}

.dropdown-item.active {
  background: var(--lumi-primary-light);
}

.dropdown-item.active .dropdown-item-model {
  color: var(--lumi-primary);
}

.dropdown-item-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.dropdown-item-model {
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dropdown-item-provider {
  font-size: var(--text-xs);
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dropdown-empty {
  padding: var(--space-5) var(--space-4);
  text-align: center;
  font-size: var(--text-sm);
  color: var(--text-muted);
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

.dropdown-fade-enter-active,
.dropdown-fade-leave-active {
  transition: opacity var(--transition-fast), transform var(--transition-fast);
}

.dropdown-fade-enter-from,
.dropdown-fade-leave-to {
  opacity: 0;
  transform: translateY(4px);
}
</style>

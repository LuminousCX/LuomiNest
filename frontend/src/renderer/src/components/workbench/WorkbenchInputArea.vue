<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { computed, ref } from 'vue'
import { Wand2, Globe } from 'lucide-vue-next'
import LumiButton from '../common/LumiButton.vue'
import PromptBar from '../common/PromptBar.vue'
import type { PromptBarMenuItem } from '../common/prompt-bar'
import SkillsPicker from '../common/SkillsPicker.vue'
import { useChatPromptPrefs } from '../../composables/useChatPromptPrefs'
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

const { t } = useI18n()

const emit = defineEmits<{
  'update:inputText': [value: string]
  send: []
  cancel: []
  'go-settings': []
  'select-chat-mode': [value: ChatModeLevel]
  'update:selectedSkillIds': [ids: string[]]
}>()

// PromptBar 自管 textarea 高度；保留旧接口供 useWorkbenchMessages 的 resetTextareaHeight 调用
const promptBarRef = ref<InstanceType<typeof PromptBar> | null>(null)

const inputTextModel = computed<string>({
  get: () => props.inputText,
  set: (value) => emit('update:inputText', value),
})

const isWorkflowMode = computed(() => props.chatMode !== 'normal')

// 模型菜单 + 响应档位（共享偏好：localStorage 落地，见 useChatPromptPrefs 的交接说明）
const { modelOptions, selectedModelKey, effortKey } = useChatPromptPrefs()

// 加号附件菜单：工作台无上传链路（canSend/发送均不含附件），两项目前均为占位
const attachMenuItems = computed<PromptBarMenuItem[]>(() => [
  { key: 'upload', name: t('chat.attach.upload'), description: t('chat.attach.uploadDesc'), disabled: true },
  { key: 'web-search', icon: Globe, name: t('chat.attach.webSearch'), description: t('chat.attach.webSearchDesc'), disabled: true },
])

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
  resetTextareaHeight: () => {},
  autoResize: () => {},
  focus: () => promptBarRef.value?.focus(),
})
</script>

<template>
  <div class="input-area">
    <div class="input-wrapper">
      <PromptBar
        ref="promptBarRef"
        v-model="inputTextModel"
        :placeholder="t('workbench.input.placeholder')"
        :disabled="!isBackendReady"
        :busy="isStreaming"
        :can-send="canSend"
        :models="modelOptions"
        :model-key="selectedModelKey"
        v-model:effort="effortKey"
        :menu-items="attachMenuItems"
        show-model-settings
        @update:model="selectedModelKey = $event"
        @send="emit('send')"
        @stop="emit('cancel')"
        @model-settings="emit('go-settings')"
      >
        <template #top>
          <SkillsPicker
            :selected-ids="selectedSkillIds"
            class="input-skills-picker"
            @update:selected-ids="emit('update:selectedSkillIds', $event)"
          />
        </template>
        <template #tools>
          <LumiButton
            :class="['workflow-toggle', { active: isWorkflowMode }]"
            variant="secondary"
            size="sm"
            :title="isWorkflowMode ? t('workbench.input.proOn') : t('workbench.input.proOff')"
            @click="toggleWorkflowMode"
          >
            <template #icon>
              <Wand2 :size="15" />
            </template>
            <span class="workflow-toggle-text">{{ isWorkflowMode ? t('workbench.input.proLabel') : t('workbench.input.normalLabel') }}</span>
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
        </template>
      </PromptBar>
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
}

.input-skills-picker {
  min-height: 0;
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
</style>

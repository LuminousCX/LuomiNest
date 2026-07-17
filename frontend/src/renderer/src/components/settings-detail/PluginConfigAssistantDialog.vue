<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import {
  Sparkles,
  Send,
  RotateCcw,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Lightbulb,
} from 'lucide-vue-next'
import LumiModal from '../common/LumiModal.vue'
import LumiButton from '../common/LumiButton.vue'
import LumiInput from '../common/LumiInput.vue'
import { usePluginsStore } from '../../stores/plugins'
import type {
  CxConfigSuggestion,
  CxSettingPatch,
  CxPluginConfigResult,
  CxPluginConfigExplain,
} from '../../plugins/types'

const props = defineProps<{
  visible: boolean
  pluginId: string | null
  pluginName?: string
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

const store = usePluginsStore()

const userRequest = ref('')
const loadingConfig = ref(false)
const generating = ref(false)
const applying = ref(false)
const explaining = ref(false)
const resetting = ref(false)
const errorMessage = ref('')

const currentConfig = ref<CxPluginConfigResult | null>(null)
const suggestion = ref<CxConfigSuggestion | null>(null)
const explanation = ref<CxPluginConfigExplain | null>(null)

const pluginDisplayName = computed(() => props.pluginName ?? props.pluginId ?? '插件')

const loadConfig = async () => {
  if (!props.pluginId) return
  loadingConfig.value = true
  errorMessage.value = ''
  try {
    currentConfig.value = await store.getPluginConfig(props.pluginId)
  } finally {
    loadingConfig.value = false
  }
}

const handleSuggest = async () => {
  if (!props.pluginId) return
  if (!userRequest.value.trim()) {
    errorMessage.value = '请描述希望对插件配置进行的修改'
    return
  }
  generating.value = true
  errorMessage.value = ''
  suggestion.value = null
  try {
    const result = await store.suggestPluginConfig(props.pluginId, userRequest.value.trim())
    suggestion.value = result
    if (!result) {
      errorMessage.value = '生成配置建议失败，请查看错误提示'
    }
  } finally {
    generating.value = false
  }
}

const handleApply = async () => {
  if (!props.pluginId || !suggestion.value) return
  applying.value = true
  errorMessage.value = ''
  try {
    const patches: CxSettingPatch[] = suggestion.value.patches.map((p) => ({
      op: p.op,
      key: p.key,
      value: p.value,
      reason: p.reason,
      validation_error: p.validation_error,
    }))
    const result = await store.applyPluginConfigPatches(props.pluginId, patches, true)
    if (result) {
      suggestion.value = null
      userRequest.value = ''
      await loadConfig()
    }
  } finally {
    applying.value = false
  }
}

const handleExplain = async () => {
  if (!props.pluginId) return
  explaining.value = true
  errorMessage.value = ''
  explanation.value = null
  try {
    explanation.value = await store.explainPluginConfig(props.pluginId)
  } finally {
    explaining.value = false
  }
}

const handleReset = async () => {
  if (!props.pluginId) return
  if (!window.confirm(`确认将插件「${pluginDisplayName.value}」的配置重置为默认值？`)) return
  resetting.value = true
  errorMessage.value = ''
  try {
    await store.resetPluginConfig(props.pluginId)
    await loadConfig()
  } finally {
    resetting.value = false
  }
}

const handleClose = () => {
  emit('update:visible', false)
}

const formatValue = (v: unknown): string => {
  if (v === null || v === undefined) return '（空）'
  if (typeof v === 'boolean') return v ? 'true' : 'false'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

const patchOpLabel = (op: string): string => {
  switch (op) {
    case 'set':
      return '设置'
    case 'remove':
      return '删除'
    case 'reset':
      return '重置'
    default:
      return op
  }
}

watch(
  () => props.visible,
  (visible) => {
    if (!visible) return
    userRequest.value = ''
    suggestion.value = null
    explanation.value = null
    errorMessage.value = ''
    currentConfig.value = null
    if (props.pluginId) {
      loadConfig()
    }
  },
)
</script>

<template>
  <LumiModal
    :visible="visible"
    :title="`AI 配置助手：${pluginDisplayName}`"
    size="lg"
    @close="handleClose"
    @update:visible="emit('update:visible', $event)"
  >
    <div class="assistant-dialog">
      <!-- 当前配置预览 -->
      <section class="section">
        <header class="section-header">
          <Sparkles :size="14" />
          <span>当前配置</span>
          <LumiButton
            variant="ghost"
            size="sm"
            :disabled="explaining || !pluginId"
            :loading="explaining"
            @click="handleExplain"
          >
            <Lightbulb :size="13" />
            <span>AI 解释</span>
          </LumiButton>
          <LumiButton
            variant="ghost"
            size="sm"
            :disabled="resetting || !pluginId"
            :loading="resetting"
            @click="handleReset"
          >
            <RotateCcw :size="13" />
            <span>重置默认</span>
          </LumiButton>
        </header>

        <div v-if="loadingConfig" class="loading-state">
          <Loader2 :size="14" class="spinning" />
          <span>加载配置中...</span>
        </div>
        <div v-else-if="currentConfig && Object.keys(currentConfig.settings).length" class="config-grid">
          <div v-for="(val, key) in currentConfig.settings" :key="String(key)" class="config-item">
            <span class="config-key">{{ key }}</span>
            <span class="config-value">{{ formatValue(val) }}</span>
          </div>
        </div>
        <p v-else class="empty-text">插件暂无可配置项</p>
      </section>

      <!-- AI 解释结果 -->
      <section v-if="explanation" class="section explain-section">
        <header class="section-header">
          <Lightbulb :size="14" />
          <span>AI 配置解释</span>
        </header>
        <p class="explain-text">{{ explanation.explanation }}</p>
      </section>

      <!-- 自然语言配置请求 -->
      <section class="section">
        <header class="section-header">
          <Sparkles :size="14" />
          <span>用自然语言描述配置需求</span>
        </header>
        <div class="request-row">
          <LumiInput
            v-model="userRequest"
            placeholder="例如：把超时时间改为 30 秒；启用调试日志"
            :error="errorMessage ? errorMessage : false"
            :disabled="generating || applying"
            @enter="handleSuggest"
          />
          <LumiButton
            variant="primary"
            size="md"
            :disabled="generating || applying || !userRequest.trim()"
            :loading="generating"
            @click="handleSuggest"
          >
            <Send :size="13" />
            <span>生成建议</span>
          </LumiButton>
        </div>
        <p class="form-hint">AI 会读取插件配置声明并生成可应用的 patch</p>
      </section>

      <!-- 建议结果 -->
      <section v-if="suggestion" class="section suggestion-section">
        <header class="section-header">
          <Sparkles :size="14" />
          <span>AI 建议</span>
          <span v-if="suggestion.confidence" class="confidence-badge">
            置信度 {{ Math.round(suggestion.confidence * 100) }}%
          </span>
        </header>

        <p class="suggestion-summary">{{ suggestion.summary }}</p>

        <div v-if="suggestion.patches.length" class="patch-list">
          <div
            v-for="(patch, idx) in suggestion.patches"
            :key="idx"
            :class="['patch-item', { invalid: patch.validation_error }]"
          >
            <div class="patch-head">
              <span :class="['patch-op', `op-${patch.op}`]">{{ patchOpLabel(patch.op) }}</span>
              <span class="patch-key">{{ patch.key }}</span>
              <span v-if="patch.op === 'set'" class="patch-value">→ {{ formatValue(patch.value) }}</span>
            </div>
            <p v-if="patch.reason" class="patch-reason">{{ patch.reason }}</p>
            <p v-if="patch.validation_error" class="patch-error">
              <AlertCircle :size="12" />
              <span>{{ patch.validation_error }}</span>
            </p>
          </div>
        </div>

        <div class="suggestion-actions">
          <LumiButton
            variant="ghost"
            size="sm"
            :disabled="applying"
            @click="suggestion = null"
          >
            取消
          </LumiButton>
          <LumiButton
            variant="primary"
            size="sm"
            :disabled="applying"
            :loading="applying"
            @click="handleApply"
          >
            <CheckCircle2 :size="13" />
            <span>应用配置</span>
          </LumiButton>
        </div>
      </section>

      <!-- 错误提示 -->
      <div v-if="errorMessage && !suggestion" class="error-message">
        <AlertCircle :size="13" />
        <span>{{ errorMessage }}</span>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <LumiButton variant="ghost" size="sm" @click="handleClose">关闭</LumiButton>
      </div>
    </template>
  </LumiModal>
</template>

<style scoped>
.assistant-dialog {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.section {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.section-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.section-header > :first-child {
  color: var(--lumi-primary);
}

.section-header .lumi-btn {
  margin-left: auto;
}

.section-header .lumi-btn:first-of-type {
  margin-left: auto;
}

.section-header .lumi-btn + .lumi-btn {
  margin-left: 0;
}

.loading-state {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3);
  color: var(--text-muted);
  font-size: var(--text-sm);
  background: var(--surface-hover);
  border-radius: var(--radius-sm);
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: var(--space-2);
}

.config-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-2) var(--space-3);
  background: var(--surface-hover);
  border-radius: var(--radius-sm);
}

.config-key {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  font-family: var(--font-mono, monospace);
}

.config-value {
  font-size: var(--text-sm);
  color: var(--text-primary);
  word-break: break-all;
}

.empty-text {
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin: 0;
  padding: var(--space-3);
  text-align: center;
}

.explain-section {
  padding: var(--space-3);
  background: var(--surface-hover);
  border-radius: var(--radius-sm);
}

.explain-text {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: 1.6;
  white-space: pre-wrap;
}

.request-row {
  display: flex;
  gap: var(--space-2);
  align-items: stretch;
}

.form-hint {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  margin: 0;
}

.suggestion-section {
  padding: var(--space-3);
  background: var(--surface-hover);
  border-radius: var(--radius-sm);
  border: 1px solid var(--lumi-primary-light, rgba(99, 102, 241, 0.2));
}

.confidence-badge {
  margin-left: auto;
  padding: 2px 8px;
  font-size: var(--text-2xs);
  font-weight: var(--font-semibold);
  color: var(--lumi-primary);
  background: var(--lumi-primary-light, rgba(99, 102, 241, 0.1));
  border-radius: var(--radius-full);
}

.suggestion-summary {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: 1.6;
}

.patch-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.patch-item {
  padding: var(--space-2) var(--space-3);
  background: var(--workspace-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.patch-item.invalid {
  border-color: rgba(239, 68, 68, 0.4);
  background: rgba(239, 68, 68, 0.05);
}

.patch-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-xs);
  flex-wrap: wrap;
}

.patch-op {
  padding: 1px 6px;
  font-size: var(--text-2xs);
  font-weight: var(--font-semibold);
  border-radius: var(--radius-xs);
}

.patch-op.op-set {
  color: rgb(22, 163, 74);
  background: rgba(34, 197, 94, 0.12);
}

.patch-op.op-remove {
  color: rgb(220, 38, 38);
  background: rgba(239, 68, 68, 0.12);
}

.patch-op.op-reset {
  color: rgb(37, 99, 235);
  background: rgba(59, 130, 246, 0.12);
}

.patch-key {
  font-family: var(--font-mono, monospace);
  color: var(--text-primary);
  font-weight: var(--font-semibold);
}

.patch-value {
  color: var(--text-secondary);
  font-family: var(--font-mono, monospace);
}

.patch-reason {
  margin: 4px 0 0;
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

.patch-error {
  display: flex;
  align-items: center;
  gap: 4px;
  margin: 4px 0 0;
  font-size: var(--text-2xs);
  color: rgb(220, 38, 38);
}

.suggestion-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-3);
}

.error-message {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  background: rgba(239, 68, 68, 0.08);
  color: rgb(220, 38, 38);
  font-size: var(--text-xs);
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
}

.spinning {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>

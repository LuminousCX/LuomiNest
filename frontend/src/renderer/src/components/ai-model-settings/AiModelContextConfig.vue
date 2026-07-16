<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  Info,
  Check,
  AlertCircle,
  Loader2,
} from 'lucide-vue-next'
import { useModelStore } from '../../stores/model'
import { useToast } from '../../composables/useToast'

const modelStore = useModelStore()
const toast = useToast()

const providers = computed(() => modelStore.providers)

const contextWindowSize = ref(0)
const compressionThreshold = ref(0.82)
const llmCompressEnabled = ref(false)
const summaryModel = ref('')
const summaryProvider = ref('')

const showInfo = ref(false)
const saveStatus = ref<'idle' | 'saving' | 'saved' | 'error'>('idle')
const saveValidationError = ref('')

const summaryAvailableModels = computed(() => {
  const provider = providers.value.find(p => p.id === summaryProvider.value)
  if (!provider) return []
  if (provider.selectedModels.length > 0) {
    return provider.selectedModels.map(id => ({ id, name: id }))
  }
  return provider.models
})

const isContextWindowValid = computed(() => {
  const val = contextWindowSize.value
  if (val === 0) return { valid: true, error: '' }
  if (val < 4096) return { valid: false, error: '上下文窗口大小不能至少为 4096 tokens' }
  if (val > 1000000) return { valid: false, error: '上下文窗口大小不能超过 1,000,000 tokens' }
  return { valid: true, error: '' }
})

const onSummaryProviderChange = () => {
  summaryModel.value = ''
}

const handleSave = async () => {
  saveValidationError.value = ''
  if (!isContextWindowValid.value.valid) {
    saveValidationError.value = isContextWindowValid.value.error
    saveStatus.value = 'error'
    toast.warning(isContextWindowValid.value.error)
    setTimeout(() => { saveStatus.value = 'idle' }, 3000)
    return
  }
  saveStatus.value = 'saving'
  try {
    await modelStore.updateModelConfig({
      contextWindowSize: contextWindowSize.value,
      compressionThreshold: compressionThreshold.value,
      llmCompressEnabled: llmCompressEnabled.value,
      summaryModel: summaryModel.value,
      summaryProvider: summaryProvider.value,
    })
    saveStatus.value = 'saved'
    toast.success('上下文配置已保存')
    setTimeout(() => { saveStatus.value = 'idle' }, 2000)
  } catch {
    saveStatus.value = 'error'
    toast.error('上下文配置保存失败')
    setTimeout(() => { saveStatus.value = 'idle' }, 3000)
  }
}

onMounted(() => {
  const cfg = modelStore.modelConfig
  contextWindowSize.value = cfg.contextWindowSize ?? 0
  compressionThreshold.value = cfg.compressionThreshold ?? 0.82
  llmCompressEnabled.value = cfg.llmCompressEnabled ?? false
  summaryModel.value = cfg.summaryModel || ''
  summaryProvider.value = cfg.summaryProvider || ''
})
</script>

<template>
  <div class="content-section">
    <div class="section-header">
      <div class="section-header-left">
        <div class="section-header-text">
          <h3 class="section-title">上下文与压缩</h3>
          <span class="section-tag">高级</span>
        </div>
      </div>
      <button
        :class="['info-btn', { active: showInfo }]"
        @click="showInfo = !showInfo"
      >
        <Info :size="16" />
      </button>
    </div>
    <Transition name="info-expand">
      <div v-if="showInfo" class="section-info-panel">
        <p>配置 LLM 上下文窗口大小和对话压缩策略，优化长对话场景下的性能与成本。</p>
        <p class="info-tip">上下文窗口为 0 时自动从 Provider 获取模型的最大上下文长度，推荐保持自动检测。</p>
      </div>
    </Transition>

    <div class="config-form">
      <!-- 上下文窗口大小 -->
      <div class="form-group">
        <div class="form-label-row">
          <label class="form-label">上下文窗口大小 (tokens)</label>
          <span class="form-value">{{ contextWindowSize === 0 ? '自动' : contextWindowSize.toLocaleString() }}</span>
        </div>
        <input
          type="number"
          v-model.number="contextWindowSize"
          min="0"
          max="1000000"
          step="1024"
          class="form-number-input"
          placeholder="0 表示自动检测，或输入自定义值（如 128000）"
        />
        <span v-if="saveValidationError && !isContextWindowValid.valid" class="form-hint hint-error">
          {{ saveValidationError }}
        </span>
        <span v-else class="form-hint">
          设为 0 自动从 Provider 获取，或输入 4096 ~ 1000000 之间的自定义值
        </span>
      </div>

      <!-- 压缩阈值 -->
      <div class="form-group">
        <div class="form-label-row">
          <label class="form-label">压缩阈值</label>
          <span class="form-value">{{ compressionThreshold.toFixed(2) }}</span>
        </div>
        <input type="range" v-model.number="compressionThreshold" min="0.5" max="0.95" step="0.05" class="form-slider" />
        <div class="slider-labels"><span>早压缩</span><span>晚压缩</span></div>
        <span class="form-hint">当上下文使用率超过此阈值时触发压缩，值越高压缩越晚触发</span>
      </div>

      <!-- 启用 LLM 摘要压缩 -->
      <div class="form-group">
        <div class="toggle-row">
          <label class="form-label">启用 LLM 摘要压缩</label>
          <button
            :class="['toggle-switch', { active: llmCompressEnabled }]"
            @click="llmCompressEnabled = !llmCompressEnabled"
          >
            <span class="toggle-knob" />
          </button>
        </div>
        <span class="form-hint">开启后，超长对话将使用 LLM 生成摘要以压缩上下文</span>
      </div>

      <!-- 摘要模型（仅启用压缩时显示） -->
      <Transition name="fade-slide">
        <div v-if="llmCompressEnabled" class="summary-config-area">
          <div class="form-group">
            <label class="form-label">摘要供应商</label>
            <div class="form-select-wrap">
              <select v-model="summaryProvider" class="form-select" @change="onSummaryProviderChange">
                <option value="">使用主模型供应商</option>
                <option v-for="p in providers" :key="p.id" :value="p.id">{{ p.name }}</option>
              </select>
              <svg class="select-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">摘要模型</label>
            <div class="form-select-wrap">
              <select v-model="summaryModel" class="form-select">
                <option value="">使用主模型</option>
                <option v-for="m in summaryAvailableModels" :key="m.id" :value="m.id">{{ m.name }}</option>
              </select>
              <svg class="select-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
            </div>
            <span v-if="summaryProvider && summaryAvailableModels.length === 0" class="form-hint hint-warn">
              该供应商暂无模型列表
            </span>
          </div>
        </div>
      </Transition>

      <button
        :class="['save-btn', { saving: saveStatus === 'saving', saved: saveStatus === 'saved', error: saveStatus === 'error' }]"
        :disabled="saveStatus === 'saving'"
        @click="handleSave"
      >
        <Loader2 v-if="saveStatus === 'saving'" :size="16" class="spin-animation" />
        <Check v-else-if="saveStatus === 'saved'" :size="16" />
        <AlertCircle v-else-if="saveStatus === 'error'" :size="16" />
        <Check v-else :size="16" />
        {{ saveStatus === 'saving' ? '保存中...' : saveStatus === 'saved' ? '已保存' : saveStatus === 'error' ? (saveValidationError || '保存失败') : '保存配置' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.content-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-5);
  background: var(--workspace-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--workspace-border);
  transition: all var(--transition-normal);
}

.section-header-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.section-header-text {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
}

.section-title {
  font-size: var(--text-lg);
  font-weight: 700;
  color: var(--text-primary);
}

.section-tag {
  font-size: var(--text-xs);
  font-weight: 500;
  color: var(--text-muted);
  letter-spacing: 0.5px;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-full);
  background: var(--workspace-panel);
}

.info-btn {
  width: var(--space-7);
  height: var(--space-7);
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all var(--transition-normal);
  flex-shrink: 0;
}

.info-btn:hover {
  background: var(--workspace-hover);
  color: var(--lumi-primary);
}

.info-btn.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.section-info-panel {
  padding: var(--space-3) var(--space-5);
  background: var(--workspace-panel);
  border-radius: var(--radius-md);
  border: 1px solid var(--workspace-border);
  font-size: var(--text-base);
  color: var(--text-secondary);
  line-height: 1.7;
}

.section-info-panel p {
  margin-bottom: var(--space-2);
}

.section-info-panel p:last-child {
  margin-bottom: 0;
}

.info-tip {
  color: var(--lumi-primary) !important;
  font-weight: 500;
  font-size: var(--text-sm) !important;
}

.info-expand-enter-active {
  animation: info-expand-in var(--duration-slow) var(--ease-in-out);
}

.info-expand-leave-active {
  animation: info-expand-in var(--duration-fast) var(--ease-in-out) reverse;
}

@keyframes info-expand-in {
  from {
    opacity: 0;
    max-height: 0;
    margin-top: calc(var(--space-2) * -1);
  }
  to {
    opacity: 1;
    max-height: 200px;
    margin-top: 0;
  }
}

.config-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  max-width: 560px;
}

.form-hint {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-top: calc(var(--space-1) * -1);
}

.hint-warn {
  color: var(--lumi-amber);
}

.hint-error {
  color: var(--lumi-accent);
  font-weight: 500;
}

.form-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.form-value {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--lumi-primary);
  font-variant-numeric: tabular-nums;
}

.form-number-input {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-md);
  font-size: var(--text-base);
  color: var(--text-primary);
  transition: all var(--transition-normal);
}

.form-number-input:focus {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 var(--space-1) var(--lumi-primary-glow);
  outline: none;
}

.form-number-input::placeholder {
  color: var(--text-muted);
  font-size: var(--text-sm);
}

.form-slider {
  width: 100%;
  height: var(--space-2);
  appearance: none;
  background: var(--workspace-border);
  border-radius: var(--space-1);
  outline: none;
  cursor: pointer;
}

.form-slider::-webkit-slider-thumb {
  appearance: none;
  width: var(--space-4);
  height: var(--space-4);
  border-radius: var(--radius-full);
  background: var(--lumi-primary);
  cursor: pointer;
  box-shadow: 0 var(--space-1) var(--space-2) var(--lumi-primary-border);
  transition: transform var(--transition-normal);
}

.form-slider::-webkit-slider-thumb:hover {
  transform: scale(1.15);
}

.slider-labels {
  display: flex;
  justify-content: space-between;
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-top: var(--space-1);
}

.toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.toggle-switch {
  position: relative;
  width: 44px;
  height: 24px;
  border-radius: var(--radius-full);
  background: var(--workspace-border);
  border: none;
  cursor: pointer;
  transition: background var(--transition-normal);
  padding: 0;
}

.toggle-switch.active {
  background: var(--lumi-primary);
}

.toggle-knob {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 20px;
  height: 20px;
  border-radius: var(--radius-full);
  background: white;
  transition: transform var(--transition-normal);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

.toggle-switch.active .toggle-knob {
  transform: translateX(20px);
}

.summary-config-area {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-4);
  background: var(--workspace-panel);
  border-radius: var(--radius-md);
  border: 1px solid var(--workspace-border);
}

.fade-slide-enter-active {
  animation: fade-slide-in var(--duration-normal) var(--ease-in-out);
}

.fade-slide-leave-active {
  animation: fade-slide-in var(--duration-fast) var(--ease-in-out) reverse;
}

@keyframes fade-slide-in {
  from {
    opacity: 0;
    transform: translateY(-8px);
    max-height: 0;
  }
  to {
    opacity: 1;
    transform: translateY(0);
    max-height: 300px;
  }
}

.form-select-wrap {
  position: relative;
  display: flex;
  align-items: center;
}

.form-select {
  width: 100%;
  padding: var(--space-2) var(--space-8) var(--space-2) var(--space-3);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-md);
  font-size: var(--text-base);
  color: var(--text-primary);
  cursor: pointer;
  appearance: none;
  transition: all var(--transition-normal);
}

.form-select:focus {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 var(--space-1) var(--lumi-primary-glow);
}

.select-icon {
  position: absolute;
  right: var(--space-3);
  color: var(--text-muted);
  pointer-events: none;
}

.save-btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-6);
  border-radius: var(--radius-md);
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--text-inverse);
  background: var(--lumi-primary);
  cursor: pointer;
  transition: all var(--transition-normal);
  align-self: flex-start;
}

.save-btn:hover {
  background: var(--lumi-primary-hover);
}

.save-btn.saving {
  opacity: 0.8;
  cursor: wait;
}

.save-btn.saved {
  background: var(--lumi-emerald);
}

.save-btn.error {
  background: var(--lumi-accent);
}

.spin-animation {
  animation: spin 1s linear infinite;
}
</style>

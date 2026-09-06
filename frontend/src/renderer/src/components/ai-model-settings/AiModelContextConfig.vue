<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import {
  Info,
  Check,
  AlertCircle,
  Loader2,
  SlidersHorizontal,
  MessageSquareText,
  Bot,
  ChevronDown,
  ChevronUp,
} from 'lucide-vue-next'
import { useModelStore } from '../../stores/model'
import { useToast } from '../../composables/useToast'

const modelStore = useModelStore()
const toast = useToast()

const providers = computed(() => modelStore.providers)
const contextOverrides = computed(() => modelStore.contextOverrides)

const contextWindowSize = ref(0)
const compressionThreshold = ref(0.82)
const compressionRatio = ref(45)
const llmCompressEnabled = ref(false)
const summaryModel = ref('')
const summaryProvider = ref('')

const showInfo = ref(false)
const saveStatus = ref<'idle' | 'saving' | 'saved' | 'error'>('idle')
const saveValidationError = ref('')
const expandedModels = ref<Set<string>>(new Set())

const summaryAvailableModels = computed(() => {
  const provider = providers.value.find(p => p.id === summaryProvider.value)
  if (!provider) return []
  if (provider.selectedModels.length > 0) {
    return provider.selectedModels.map(id => ({ id, name: id }))
  }
  return provider.models
})

const groupedOverrides = computed(() => {
  const groups: Record<string, typeof contextOverrides.value> = {}
  for (const item of contextOverrides.value) {
    const pid = item.providerId || 'unknown'
    if (!groups[pid]) groups[pid] = []
    groups[pid].push(item)
  }
  return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b))
})

const providerNameMap = computed(() => {
  const map: Record<string, string> = {}
  for (const p of providers.value) {
    map[p.id] = p.name || p.id
  }
  return map
})

const isContextWindowValid = computed(() => {
  const val = contextWindowSize.value
  if (val === 0) return { valid: true, error: '' }
  if (val < 4096) return { valid: false, error: '上下文窗口大小不能小于 4096 tokens' }
  if (val > 2000000) return { valid: false, error: '上下文窗口大小不能超过 2,000,000 tokens' }
  return { valid: true, error: '' }
})

const onSummaryProviderChange = () => {
  summaryModel.value = ''
}

const handleSaveGlobal = async () => {
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
      compressionRatio: compressionRatio.value,
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

const formatTokens = (n: number) => {
  if (n === 0) return '自动'
  if (n >= 1000000) return `${(n / 1000000).toFixed(2)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`
  return `${n}`
}

const sliderMaxForModel = (item: typeof contextOverrides.value[0]) => {
  const base = item.maxContextTokens || 128_000
  const max = Math.max(base, 131_072)
  return Math.min(max, 2_000_000)
}

const sliderStepForModel = (max: number) => {
  if (max >= 1_000_000) return 4096
  if (max >= 128_000) return 1024
  return 256
}

const updatingModels = ref<Set<string>>(new Set())
const updateModelTimer = ref<Record<string, number>>({})

const scheduleUpdateModel = (item: typeof contextOverrides.value[0]) => {
  const key = `${item.providerId}/${item.modelId}`
  if (updateModelTimer.value[key]) {
    window.clearTimeout(updateModelTimer.value[key])
  }
  updatingModels.value.add(key)
  updateModelTimer.value[key] = window.setTimeout(async () => {
    try {
      await modelStore.updateContextOverride(item.providerId, item.modelId, {
        enabled: item.enabled,
        maxContextTokens: item.maxContextTokens,
      })
    } catch {
      toast.error(`模型 ${item.name || item.modelId} 保存失败`)
    } finally {
      updatingModels.value.delete(key)
    }
  }, 400)
}

const toggleModelExpanded = (key: string) => {
  if (expandedModels.value.has(key)) {
    expandedModels.value.delete(key)
  } else {
    expandedModels.value.add(key)
  }
}

const isExpanded = (key: string) => expandedModels.value.has(key)

onMounted(() => {
  const cfg = modelStore.modelConfig
  contextWindowSize.value = cfg.contextWindowSize ?? 0
  compressionThreshold.value = cfg.compressionThreshold ?? 0.82
  compressionRatio.value = cfg.compressionRatio ?? 45
  llmCompressEnabled.value = cfg.llmCompressEnabled ?? false
  summaryModel.value = cfg.summaryModel || ''
  summaryProvider.value = cfg.summaryProvider || ''
})

watch(() => modelStore.modelConfig, (cfg) => {
  contextWindowSize.value = cfg.contextWindowSize ?? 0
  compressionThreshold.value = cfg.compressionThreshold ?? 0.82
  compressionRatio.value = cfg.compressionRatio ?? 45
  llmCompressEnabled.value = cfg.llmCompressEnabled ?? false
  summaryModel.value = cfg.summaryModel || ''
  summaryProvider.value = cfg.summaryProvider || ''
}, { deep: true })
</script>

<template>
  <div class="context-config">
    <!-- 全局上下文与压缩 -->
    <div class="content-section">
      <div class="section-header">
        <div class="section-header-left">
          <div class="section-icon">
            <SlidersHorizontal :size="18" />
          </div>
          <div class="section-header-text">
            <h3 class="section-title">上下文与压缩</h3>
            <span class="section-tag">全局</span>
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
          <p class="info-tip">上下文窗口为 0 时自动从模型配置的最大上下文长度推断；LM 摘要压缩比例推荐 40% - 50%。</p>
        </div>
      </Transition>

      <div class="config-form">
        <!-- 上下文窗口大小 -->
        <div class="form-group">
          <div class="form-label-row">
            <label class="form-label">全局上下文窗口大小</label>
            <span class="form-value">{{ contextWindowSize === 0 ? '自动' : formatTokens(contextWindowSize) }}</span>
          </div>
          <input
            type="range"
            v-model.number="contextWindowSize"
            min="0"
            max="2000000"
            step="1024"
            class="form-slider"
          />
          <div class="slider-meta">
            <span class="slider-meta-label">自动</span>
            <input
              type="number"
              v-model.number="contextWindowSize"
              min="0"
              max="2000000"
              step="1024"
              class="form-number-input inline"
              placeholder="0"
            />
            <span class="slider-meta-label">2M</span>
          </div>
          <span v-if="saveValidationError && !isContextWindowValid.valid" class="form-hint hint-error">
            {{ saveValidationError }}
          </span>
          <span v-else class="form-hint">设为 0 自动按各模型最大上下文推断；手动设置将覆盖所有模型</span>
        </div>

        <!-- 压缩阈值 -->
        <div class="form-group">
          <div class="form-label-row">
            <label class="form-label">压缩阈值</label>
            <span class="form-value">{{ (compressionThreshold * 100).toFixed(0) }}%</span>
          </div>
          <input type="range" v-model.number="compressionThreshold" min="0.5" max="0.95" step="0.05" class="form-slider" />
          <div class="slider-labels"><span>早压缩</span><span>晚压缩</span></div>
          <span class="form-hint">当上下文使用率超过此阈值时触发压缩，值越高压缩越晚触发</span>
        </div>

        <!-- LM 摘要压缩比例 -->
        <div class="form-group">
          <div class="form-label-row">
            <label class="form-label">LM 摘要压缩保留比例</label>
            <span class="form-value" :class="{ 'value-recommended': compressionRatio >= 40 && compressionRatio <= 50 }">{{ compressionRatio }}%</span>
          </div>
          <input type="range" v-model.number="compressionRatio" min="1" max="100" step="1" class="form-slider" />
          <div class="slider-labels"><span>1% 激进</span><span class="recommended-badge">推荐 40% - 50%</span><span>100% 不压缩</span></div>
          <span class="form-hint">摘要后保留的历史上下文占比，数值越低压缩越激进；100% 表示不压缩</span>
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
          @click="handleSaveGlobal"
        >
          <Loader2 v-if="saveStatus === 'saving'" :size="16" class="spin-animation" />
          <Check v-else-if="saveStatus === 'saved'" :size="16" />
          <AlertCircle v-else-if="saveStatus === 'error'" :size="16" />
          <Check v-else :size="16" />
          {{ saveStatus === 'saving' ? '保存中...' : saveStatus === 'saved' ? '已保存' : saveStatus === 'error' ? (saveValidationError || '保存失败') : '保存全局配置' }}
        </button>
      </div>
    </div>

    <!-- 按模型上下文覆盖 -->
    <div class="content-section">
      <div class="section-header">
        <div class="section-header-left">
          <div class="section-icon section-icon--model">
            <Bot :size="18" />
          </div>
          <div class="section-header-text">
            <h3 class="section-title">模型上下文覆盖</h3>
            <span class="section-tag">按模型</span>
          </div>
        </div>
        <span class="section-count">{{ contextOverrides.length }} 个模型</span>
      </div>

      <div class="section-info-panel section-info-panel--inline">
        <p><MessageSquareText :size="14" /> 此处按模型维度单独设置最大上下文长度与启用状态；未覆盖的模型将使用上方全局设置或自动推断。</p>
      </div>

      <div v-if="contextOverrides.length === 0" class="empty-state">
        <Bot :size="32" />
        <p>暂无模型数据</p>
        <span class="empty-hint">请先添加供应商，系统会自动拉取并存储模型列表</span>
      </div>

      <div v-else class="model-groups">
        <div v-for="[providerId, items] in groupedOverrides" :key="providerId" class="model-group">
          <div class="group-title">{{ providerNameMap[providerId] || providerId }}</div>
          <div class="model-list">
            <div
              v-for="item in items"
              :key="item.id"
              :class="['model-card', { disabled: !item.enabled }]"
            >
              <div class="model-card-header">
                <div class="model-info">
                  <span class="model-name">{{ item.name || item.modelId }}</span>
                  <span class="model-id">{{ item.modelId }}</span>
                </div>
                <div class="model-actions">
                  <button
                    :class="['toggle-switch', 'toggle-switch--sm', { active: item.enabled }]"
                    @click="item.enabled = !item.enabled; scheduleUpdateModel(item)"
                  >
                    <span class="toggle-knob" />
                  </button>
                  <button class="expand-btn" @click="toggleModelExpanded(`${providerId}/${item.modelId}`)">
                    <ChevronUp v-if="isExpanded(`${providerId}/${item.modelId}`)" :size="16" />
                    <ChevronDown v-else :size="16" />
                  </button>
                </div>
              </div>

              <div class="model-card-summary">
                <span class="token-badge">
                  {{ item.enabled ? (item.maxContextTokens === 0 ? '自动推断' : `最大 ${formatTokens(item.maxContextTokens)}`) : '已禁用' }}
                </span>
                <Loader2 v-if="updatingModels.has(`${item.providerId}/${item.modelId}`)" :size="14" class="spin-animation" />
              </div>

              <Transition name="expand-vertical">
                <div v-if="isExpanded(`${providerId}/${item.modelId}`)" class="model-card-body">
                  <div class="form-group form-group--compact">
                    <div class="form-label-row">
                      <label class="form-label">最大上下文长度</label>
                      <span class="form-value">{{ item.maxContextTokens === 0 ? '自动' : formatTokens(item.maxContextTokens) }}</span>
                    </div>
                    <input
                      type="range"
                      v-model.number="item.maxContextTokens"
                      min="0"
                      :max="sliderMaxForModel(item)"
                      :step="sliderStepForModel(sliderMaxForModel(item))"
                      class="form-slider"
                      @change="scheduleUpdateModel(item)"
                    />
                    <div class="slider-meta">
                      <span class="slider-meta-label">自动</span>
                      <input
                        type="number"
                        v-model.number="item.maxContextTokens"
                        min="0"
                        max="2000000"
                        step="1024"
                        class="form-number-input inline"
                        placeholder="0"
                        @input="scheduleUpdateModel(item)"
                      />
                      <span class="slider-meta-label">{{ formatTokens(sliderMaxForModel(item)) }}</span>
                    </div>
                    <span class="form-hint">0 表示按模型 ID 自动推断；自定义值将覆盖全局设置</span>
                  </div>
                </div>
              </Transition>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.context-config {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

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

.section-icon {
  width: var(--space-8);
  height: var(--space-8);
  border-radius: var(--radius-md);
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.section-icon--model {
  background: var(--lumi-emerald-light, rgba(16, 185, 129, 0.12));
  color: var(--lumi-emerald, #10b981);
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

.section-count {
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-weight: 500;
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

.section-info-panel--inline {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  font-size: var(--text-sm);
}

.section-info-panel--inline svg {
  flex-shrink: 0;
  color: var(--lumi-primary);
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
  gap: var(--space-5);
  max-width: 600px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.form-group--compact {
  gap: var(--space-1);
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

.form-label {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--text-primary);
}

.form-value {
  font-size: var(--text-base);
  font-weight: 700;
  color: var(--lumi-primary);
  font-variant-numeric: tabular-nums;
}

.value-recommended {
  color: var(--lumi-emerald, #10b981);
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

.form-number-input.inline {
  width: 120px;
  text-align: center;
  padding: var(--space-1) var(--space-2);
  font-size: var(--text-sm);
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

.recommended-badge {
  color: var(--lumi-emerald, #10b981);
  font-weight: 600;
}

.slider-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.slider-meta-label {
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
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
  flex-shrink: 0;
}

.toggle-switch.active {
  background: var(--lumi-primary);
}

.toggle-switch--sm {
  width: 36px;
  height: 20px;
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

.toggle-switch--sm .toggle-knob {
  width: 16px;
  height: 16px;
}

.toggle-switch.active .toggle-knob {
  transform: translateX(20px);
}

.toggle-switch--sm.active .toggle-knob {
  transform: translateX(16px);
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




.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-10) var(--space-4);
  color: var(--text-muted);
  background: var(--workspace-panel);
  border-radius: var(--radius-lg);
  border: 1px dashed var(--workspace-border);
}

.empty-state p {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--text-secondary);
}

.empty-hint {
  font-size: var(--text-sm);
  color: var(--text-muted);
  text-align: center;
}

.model-groups {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.model-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.group-title {
  font-size: var(--text-sm);
  font-weight: 700;
  color: var(--text-secondary);
  padding-left: var(--space-2);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.group-title::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  background: var(--lumi-primary);
}

.model-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--space-3);
}

.model-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--workspace-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--workspace-border);
  transition: all var(--transition-normal);
}

.model-card:hover {
  border-color: var(--workspace-border-hover, var(--lumi-primary-border));
  box-shadow: 0 2px 8px var(--workspace-shadow, rgba(0, 0, 0, 0.04));
}

.model-card.disabled {
  opacity: 0.65;
  background: var(--workspace-panel);
}

.model-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
}

.model-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.model-name {
  font-size: var(--text-base);
  font-weight: 700;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-id {
  font-size: var(--text-xs);
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}

.expand-btn {
  width: var(--space-7);
  height: var(--space-7);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all var(--transition-normal);
}

.expand-btn:hover {
  background: var(--workspace-hover);
  color: var(--lumi-primary);
}

.model-card-summary {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.token-badge {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-full);
}

.model-card.disabled .token-badge {
  color: var(--text-muted);
  background: var(--workspace-hover);
}

.model-card-body {
  padding-top: var(--space-2);
  border-top: 1px solid var(--workspace-border);
}

.expand-vertical-enter-active {
  animation: expand-vertical-in var(--duration-normal) var(--ease-in-out);
  overflow: hidden;
}

.expand-vertical-leave-active {
  animation: expand-vertical-in var(--duration-fast) var(--ease-in-out) reverse;
  overflow: hidden;
}

@keyframes expand-vertical-in {
  from {
    opacity: 0;
    max-height: 0;
    padding-top: 0;
  }
  to {
    opacity: 1;
    max-height: 240px;
    padding-top: var(--space-2);
  }
}
</style>
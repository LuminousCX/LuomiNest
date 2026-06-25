<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  Settings2,
  ChevronRight,
  Server,
  CheckSquare,
  Search,
  Edit3,
  Trash2,
  Plus,
  Check,
  Loader2,
} from 'lucide-vue-next'
import { useModelStore } from '../../stores/model'
import { useToast } from '../../composables/useToast'

const emit = defineEmits<{
  (e: 'add-provider'): void
  (e: 'edit-provider', providerId: string): void
}>()

const modelStore = useModelStore()
const toast = useToast()

const providers = computed(() => modelStore.providers)
const showProviderList = ref(true)
const expandedModelPicker = ref('')
const savingSelectedModels = ref('')
const localSelectedModels = ref<Record<string, string[]>>({})

const getProviderIcon = (providerId: string): string => {
  const tmpl = modelStore.allTemplates.find(t => t.id === providerId)
  return tmpl?.svgIcon || ''
}

const toggleModelPicker = (providerId: string) => {
  if (expandedModelPicker.value === providerId) {
    expandedModelPicker.value = ''
  } else {
    const provider = providers.value.find(p => p.id === providerId)
    localSelectedModels.value[providerId] = provider ? [...provider.selectedModels] : []
    expandedModelPicker.value = providerId
  }
}

const toggleModelSelection = (providerId: string, modelId: string) => {
  const list = localSelectedModels.value[providerId] || []
  const idx = list.indexOf(modelId)
  if (idx >= 0) {
    list.splice(idx, 1)
  } else {
    list.push(modelId)
  }
  localSelectedModels.value[providerId] = [...list]
}

const saveSelectedModels = async (providerId: string) => {
  savingSelectedModels.value = providerId
  try {
    const selected = localSelectedModels.value[providerId] || []
    await modelStore.updateProvider(providerId, { selectedModels: selected })
    toast.success(`已保存 ${selected.length} 个模型`)
    expandedModelPicker.value = ''
  } catch (e: any) {
    toast.error(`保存失败：${e.message || '未知错误'}`)
  } finally {
    savingSelectedModels.value = ''
  }
}

const handleFetchModels = async (providerId: string) => {
  try {
    await modelStore.fetchProviderModels(providerId)
    toast.info('模型列表已刷新')
  } catch (e: any) {
    console.error('Failed to fetch models:', e)
    toast.error(`获取模型列表失败：${e.message || '未知错误'}`)
  }
}

const handleRemoveProvider = async (providerId: string) => {
  try {
    const p = providers.value.find(pr => pr.id === providerId)
    await modelStore.removeProvider(providerId)
    toast.success(`供应商「${p?.name || providerId}」已删除`)
  } catch (e: any) {
    console.error('Failed to remove provider:', e)
    toast.error(`删除供应商失败：${e.message || '未知错误'}`)
  }
}
</script>

<template>
  <div class="provider-section">
    <div class="provider-section-header" @click="showProviderList = !showProviderList">
      <div class="provider-section-title">
        <Settings2 :size="14" />
        <span>供应商管理</span>
        <span class="provider-count">{{ providers.length }}</span>
      </div>
      <ChevronRight :size="14" :class="['chevron-toggle', { expanded: showProviderList }]" />
    </div>
    <Transition name="expand">
      <div v-if="showProviderList" class="provider-list">
        <div v-for="provider in providers" :key="provider.id" class="provider-item">
          <div class="provider-item-info">
            <div class="provider-item-header">
              <div v-if="getProviderIcon(provider.id)" class="provider-svg-icon" v-html="getProviderIcon(provider.id)"></div>
              <Server v-else :size="14" class="provider-item-icon" />
              <span class="provider-item-name">{{ provider.name }}</span>
              <span v-if="provider.isDefault" class="default-badge">默认</span>
              <span v-if="provider.selectedModels.length > 0" class="selected-count-badge">{{ provider.selectedModels.length }} 模型</span>
            </div>
            <div class="provider-item-detail">
              <span class="detail-text">{{ provider.baseUrl }}</span>
              <span class="detail-sep">|</span>
              <span class="detail-text">{{ provider.defaultModel || '未设置' }}</span>
            </div>
          </div>
          <div class="provider-item-actions">
            <button class="action-btn" title="多选模型" @click="toggleModelPicker(provider.id)">
              <CheckSquare :size="13" />
            </button>
            <button class="action-btn" title="获取模型" @click="handleFetchModels(provider.id)">
              <Search :size="13" />
            </button>
            <button class="action-btn" title="编辑" @click="emit('edit-provider', provider.id)">
              <Edit3 :size="13" />
            </button>
            <button class="action-btn danger" title="删除" @click="handleRemoveProvider(provider.id)">
              <Trash2 :size="13" />
            </button>
          </div>
          <Transition name="expand">
            <div v-if="expandedModelPicker === provider.id" class="model-picker-panel">
              <div class="model-picker-header">
                <span class="model-picker-title">多选可用模型（显示到工作台/对话页）</span>
                <span v-if="provider.models.length === 0" class="model-picker-hint">暂无模型列表，请先点击搜索图标获取</span>
              </div>
              <div v-if="provider.models.length > 0" class="model-picker-list">
                <label
                  v-for="m in provider.models"
                  :key="m.id"
                  class="model-picker-item"
                >
                  <input
                    type="checkbox"
                    :checked="(localSelectedModels[provider.id] || []).includes(m.id)"
                    @change="toggleModelSelection(provider.id, m.id)"
                  />
                  <span class="model-picker-name">{{ m.name }}</span>
                </label>
              </div>
              <div v-if="provider.models.length > 0" class="model-picker-footer">
                <span class="model-picker-count">已选 {{ (localSelectedModels[provider.id] || []).length }} 个</span>
                <button
                  class="model-picker-save"
                  :disabled="savingSelectedModels === provider.id"
                  @click="saveSelectedModels(provider.id)"
                >
                  <Loader2 v-if="savingSelectedModels === provider.id" :size="12" class="spin-animation" />
                  <Check v-else :size="12" />
                  保存
                </button>
              </div>
            </div>
          </Transition>
        </div>
        <div v-if="providers.length === 0" class="empty-provider">
          <p>暂无供应商</p>
          <button class="add-inline-btn" @click="emit('add-provider')">
            <Plus :size="14" />
            添加供应商
          </button>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.provider-section {
  margin-top: var(--space-2);
  border-top: 1px solid var(--workspace-border);
  padding-top: var(--space-4);
}

.provider-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-normal);
}

.provider-section-header:hover {
  background: var(--workspace-hover);
}

.provider-section-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--text-secondary);
}

.provider-count {
  font-size: var(--text-xs);
  padding: 1px var(--space-2);
  border-radius: var(--radius-full);
  background: var(--workspace-panel);
  color: var(--text-muted);
  font-weight: 500;
}

.chevron-toggle {
  color: var(--text-muted);
  transition: transform var(--transition-normal);
}

.chevron-toggle.expanded {
  transform: rotate(90deg);
}

.provider-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding-top: var(--space-2);
}

.provider-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  transition: all var(--transition-normal);
}

.provider-item:hover {
  border-color: var(--lumi-primary);
  box-shadow: 0 1px var(--space-1) var(--lumi-primary-glow);
}

.provider-item-info {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
  flex: 1;
}

.provider-item-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.provider-item-icon {
  color: var(--lumi-primary);
  flex-shrink: 0;
}

.provider-item-name {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--text-primary);
}

.default-badge {
  font-size: var(--text-2xs);
  padding: 1px var(--space-2);
  border-radius: var(--radius-full);
  background: var(--lumi-primary);
  color: var(--text-inverse);
  font-weight: 500;
}

.selected-count-badge {
  font-size: var(--text-2xs);
  padding: 1px var(--space-2);
  border-radius: var(--radius-full);
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  font-weight: 500;
}

.model-picker-panel {
  flex-basis: 100%;
  margin-top: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--surface-hover);
  border: 1px solid var(--border-light);
}

.model-picker-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-2);
}

.model-picker-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-primary);
}

.model-picker-hint {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.model-picker-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  max-height: 180px;
  overflow-y: auto;
}

.model-picker-item {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-sm);
  background: var(--surface-active);
  cursor: pointer;
  font-size: var(--text-xs);
  color: var(--text-secondary);
  transition: all var(--transition-fast);
}

.model-picker-item:hover {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.model-picker-item input {
  margin: 0;
  cursor: pointer;
}

.model-picker-name {
  white-space: nowrap;
}

.model-picker-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px solid var(--border-light);
}

.model-picker-count {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.model-picker-save {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  border: none;
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  font-weight: 500;
  color: var(--text-inverse);
  background: var(--lumi-primary);
  cursor: pointer;
  transition: opacity var(--duration-leave) var(--ease-in-out);
}

.model-picker-save:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.provider-item-detail {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-xs);
  color: var(--text-muted);
  padding-left: var(--space-5);
}

.detail-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-sep {
  opacity: 0.3;
}

.provider-item-actions {
  display: flex;
  gap: var(--space-1);
  flex-shrink: 0;
}

.action-btn {
  width: var(--space-7);
  height: var(--space-7);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all var(--transition-normal);
}

.action-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-secondary);
}

.action-btn.danger:hover {
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
}

.empty-provider {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-5);
  color: var(--text-muted);
  font-size: var(--text-base);
}

.add-inline-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
  transition: all var(--transition-normal);
}

.add-inline-btn:hover {
  background: var(--lumi-primary);
  color: var(--text-inverse);
}

.provider-svg-icon {
  width: var(--space-4);
  height: var(--space-4);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.provider-svg-icon :deep(svg) {
  width: var(--space-4);
  height: var(--space-4);
}

.spin-animation {
  animation: spin 1s linear infinite;
}

.expand-enter-active {
  animation: expand-in var(--duration-slow) var(--ease-in-out);
}

.expand-leave-active {
  animation: expand-in var(--duration-fast) var(--ease-in-out) reverse;
}

@keyframes expand-in {
  from {
    opacity: 0;
    max-height: 0;
  }
  to {
    opacity: 1;
    max-height: 600px;
  }
}
</style>

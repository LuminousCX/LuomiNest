<script setup lang="ts">
import { ref, watch } from 'vue'
import {
  Globe, Radio, Cable, Link, MessageCircle, Send, Gamepad2, Home, Smartphone,
} from 'lucide-vue-next'
import { usePlatformStore } from '../../stores/platform'
import type { PlatformAdapterType } from '../../types'
import LumiModal from '../../components/common/LumiModal.vue'
import LumiButton from '../../components/common/LumiButton.vue'
import LumiInput from '../../components/common/LumiInput.vue'
import { createLuomiNestRendererLogger } from '../../utils/logger'

const logger = createLuomiNestRendererLogger('Platform')

const store = usePlatformStore()

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  created: []
}>()

const selectedAdapterType = ref<PlatformAdapterType | null>(null)
const newPlatformName = ref('')
const newPlatformConfig = ref<Record<string, any>>({})

const iconMap: Record<string, any> = {
  Globe, Radio, Cable, Link, MessageCircle, Send, Gamepad2, Home, Smartphone,
}

const getIcon = (iconName: string) => {
  return iconMap[iconName] || Globe
}

const openAddDialog = (adapterType: PlatformAdapterType) => {
  selectedAdapterType.value = adapterType
  newPlatformName.value = adapterType.displayName
  newPlatformConfig.value = { ...adapterType.configTemplate }
}

const closeAddDialog = () => {
  emit('update:visible', false)
}

const handleCreate = async () => {
  if (!selectedAdapterType.value || !newPlatformName.value.trim()) return
  try {
    await store.createInstance({
      adapterType: selectedAdapterType.value.name,
      name: newPlatformName.value.trim(),
      config: newPlatformConfig.value,
      enable: true,
    })
    closeAddDialog()
    emit('created')
  } catch (e: unknown) {
    logger.error('Failed to create platform instance:', e)
  }
}

watch(() => props.visible, (visible) => {
  if (visible) {
    selectedAdapterType.value = null
    newPlatformName.value = ''
    newPlatformConfig.value = {}
  }
})
</script>

<template>
  <LumiModal :visible="visible" title="添加平台" size="lg" @close="closeAddDialog" @update:visible="emit('update:visible', $event)">
    <div v-if="!selectedAdapterType" class="dialog-body">
      <p class="dialog-desc">选择要接入的平台类型：</p>
      <div class="adapter-type-grid">
        <button
          v-for="at in store.adapterTypes"
          :key="at.name"
          class="adapter-type-card"
          @click="openAddDialog(at)"
        >
          <div class="atc-icon" :class="at.category">
            <component :is="getIcon(at.icon)" :size="20" />
          </div>
          <div class="atc-info">
            <span class="atc-name">{{ at.displayName }}</span>
            <span class="atc-desc">{{ at.description }}</span>
          </div>
          <span class="atc-category" :class="at.category">{{ at.category === 'social' ? '社交' : at.category === 'iot' ? 'IoT' : '通用' }}</span>
        </button>
      </div>
    </div>

    <div v-else class="dialog-body">
      <div class="form-group">
        <label class="form-label">平台名称</label>
        <LumiInput v-model="newPlatformName" type="text" placeholder="输入平台实例名称" />
      </div>
      <div class="form-group">
        <label class="form-label">平台类型</label>
        <div class="form-type-badge">
          <component :is="getIcon(selectedAdapterType.icon)" :size="14" />
          <span>{{ selectedAdapterType.displayName }}</span>
        </div>
      </div>
      <div v-if="Object.keys(selectedAdapterType.configMetadata).length > 0" class="form-group">
        <label class="form-label">连接配置</label>
        <div class="config-fields">
          <div v-for="(meta, key) in selectedAdapterType.configMetadata" :key="key" class="config-field">
            <label class="config-field-label">{{ meta.label || key }}</label>
            <LumiInput
              v-model="newPlatformConfig[key]"
              :type="meta.type === 'password' ? 'password' : meta.type === 'number' ? 'number' : 'text'"
              :placeholder="meta.label || key"
            />
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <LumiButton variant="secondary" size="sm" @click="closeAddDialog">取消</LumiButton>
      <LumiButton
        v-if="selectedAdapterType"
        variant="primary"
        size="sm"
        :disabled="!newPlatformName.trim()"
        @click="handleCreate"
      >确认添加</LumiButton>
      <LumiButton v-else variant="primary" size="sm" @click="closeAddDialog">关闭</LumiButton>
    </template>
  </LumiModal>
</template>

<style scoped>
.dialog-desc {
  font-size: var(--text-base);
  color: var(--text-muted);
  margin-bottom: var(--space-4);
}

.adapter-type-grid {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.adapter-type-card {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--surface);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
  cursor: pointer;
  transition: all var(--transition-fast);
  text-align: left;
}

.adapter-type-card:hover {
  border-color: var(--lumi-brand);
  box-shadow: var(--shadow-glow-sm);
}

.atc-icon {
  width: var(--space-8);
  height: var(--space-8);
  border-radius: var(--radius-sm);
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.atc-icon.social {
  background: var(--task-purple-soft);
  color: var(--task-purple);
}

.atc-icon.iot {
  background: var(--task-green-soft);
  color: var(--lumi-success);
}

.atc-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.atc-name {
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.atc-desc {
  font-size: var(--text-xs);
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.atc-category {
  padding: 3px var(--space-2);
  border-radius: var(--radius-xs);
  font-size: var(--text-2xs);
  font-weight: var(--font-medium);
  flex-shrink: 0;
}

.atc-category.social {
  background: var(--task-purple-soft);
  color: var(--task-purple);
}

.atc-category.iot {
  background: var(--task-green-soft);
  color: var(--lumi-success);
}

.atc-category.general {
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
}

.form-group {
  margin-bottom: var(--space-4);
}

.form-label {
  display: block;
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--text-secondary);
  margin-bottom: var(--space-1);
}

.form-type-badge {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  background: var(--lumi-brand-light);
  border-radius: var(--radius-sm);
  font-size: var(--text-base);
  font-weight: var(--font-medium);
  color: var(--lumi-brand);
}

.config-fields {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.config-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.config-field-label {
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: var(--text-muted);
}
</style>

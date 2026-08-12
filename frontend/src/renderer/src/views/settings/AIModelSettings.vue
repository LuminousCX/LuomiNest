<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  ArrowLeft,
  Cpu,
  Zap,
  Atom,
  Plus,
  Settings2,
  Volume2,
  Mic,
} from 'lucide-vue-next'
import { useModelStore } from '../../stores/model'
import AiModelMainConfig from '../../components/ai-model-settings/AiModelMainConfig.vue'
import AiModelReasonerConfig from '../../components/ai-model-settings/AiModelReasonerConfig.vue'
import AiModelAddProviderDialog from '../../components/ai-model-settings/AiModelAddProviderDialog.vue'
import AiModelEditProviderDialog from '../../components/ai-model-settings/AiModelEditProviderDialog.vue'
import AiModelContextConfig from '../../components/ai-model-settings/AiModelContextConfig.vue'
import SettingsTtsSection from '../../components/settings-detail/SettingsTtsSection.vue'
import SettingsSttSection from '../../components/settings-detail/SettingsSttSection.vue'

const router = useRouter()
const modelStore = useModelStore()
const route = useRoute()

const props = defineProps<{
  initialTile?: string
}>()

const activeTile = ref(props.initialTile || (route.meta?.initialTile as string) || 'main')

const modelTiles = [
  { id: 'main', label: '主模型', icon: Zap, tag: '快速响应' },
  { id: 'reasoner', label: '推理模型', icon: Atom, tag: 'Agent' },
  { id: 'context', label: '高级设置', icon: Settings2, tag: '上下文' },
  { id: 'tts', label: '语音合成', icon: Volume2, tag: 'TTS' },
  { id: 'stt', label: '语音识别', icon: Mic, tag: 'STT' },
]

const showAddDialog = ref(false)
const showEditDialog = ref(false)
const editingProviderId = ref('')

const showProviderActions = computed(() => {
  return ['main', 'reasoner', 'context'].includes(activeTile.value)
})

const openAddDialog = () => {
  showAddDialog.value = true
}

const openEditDialog = (providerId: string) => {
  editingProviderId.value = providerId
  showEditDialog.value = true
}

onMounted(async () => {
  await Promise.all([
    modelStore.fetchProviders(),
    modelStore.fetchTemplates(),
    modelStore.fetchModelConfig(),
    modelStore.fetchContextOverrides(),
  ])
})
</script>

<template>
  <div class="ai-model-settings">
    <div class="settings-detail-header animate-fade-in">
      <button class="back-btn" @click="router.push('/settings')">
        <ArrowLeft :size="18" />
      </button>
      <div class="header-icon">
        <Cpu :size="24" />
      </div>
      <div>
        <h1 class="page-title">模型设置</h1>
        <p class="page-subtitle">配置大语言模型、语音合成与语音识别引擎</p>
      </div>
    </div>

    <div class="settings-detail-body">
      <div class="detail-sidebar animate-slide-up">
        <nav class="tile-nav">
          <button
            v-for="tile in modelTiles"
            :key="tile.id"
            :class="['tile-item', { active: activeTile === tile.id }]"
            @click="activeTile = tile.id"
          >
            <component :is="tile.icon" :size="18" />
            <div class="tile-text">
              <span class="tile-label">{{ tile.label }}</span>
              <span class="tile-tag">{{ tile.tag }}</span>
            </div>
          </button>
        </nav>

        <div v-if="showProviderActions" class="sidebar-footer">
          <button class="add-provider-btn" @click="openAddDialog">
            <Plus :size="16" />
            <span>添加供应商</span>
          </button>
        </div>
      </div>

      <div :class="['detail-content', 'animate-slide-up', { 'detail-content--panel': activeTile === 'tts' || activeTile === 'stt' }]" :style="{ animationDelay: '100ms' }">
        <AiModelMainConfig
          v-if="activeTile === 'main'"
          @add-provider="openAddDialog"
          @edit-provider="openEditDialog"
        />
        <AiModelReasonerConfig
          v-if="activeTile === 'reasoner'"
        />
        <AiModelContextConfig
          v-if="activeTile === 'context'"
        />
        <SettingsTtsSection
          v-if="activeTile === 'tts'"
          :embedded="true"
        />
        <SettingsSttSection
          v-if="activeTile === 'stt'"
          :embedded="true"
        />
      </div>
    </div>

    <AiModelAddProviderDialog v-model:visible="showAddDialog" />
    <AiModelEditProviderDialog v-model:visible="showEditDialog" :provider-id="editingProviderId" />
  </div>
</template>

<script lang="ts">
export default { name: 'AIModelSettings' }
</script>

<style scoped>
.ai-model-settings {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--workspace-bg);
  overflow: hidden;
}

.settings-detail-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-5) var(--space-7);
  border-bottom: 1px solid var(--workspace-border);
  flex-shrink: 0;
}

.back-btn {
  width: var(--space-8);
  height: var(--space-8);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all var(--transition-normal);
}

.back-btn:hover {
  background: var(--workspace-hover);
  color: var(--lumi-primary);
}

.header-icon {
  width: var(--space-9);
  height: var(--space-9);
  border-radius: var(--radius-lg);
  background: var(--lumi-primary-gradient-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--lumi-primary);
}

.page-title {
  font-size: var(--text-2xl);
  font-weight: 700;
  color: var(--text-primary);
}

.page-subtitle {
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin-top: 1px;
}

.settings-detail-body {
  display: flex;
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

.detail-sidebar {
  width: 200px;
  flex-shrink: 0;
  border-right: 1px solid var(--workspace-border);
  padding: var(--space-4) var(--space-3);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.tile-nav {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.tile-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--text-secondary);
  text-align: left;
  transition: all var(--transition-normal);
}

.tile-item:hover {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

.tile-item.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.tile-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.tile-label {
  font-weight: 600;
  font-size: var(--text-base);
}

.tile-tag {
  font-size: var(--text-2xs);
  font-weight: 500;
  opacity: 0.6;
  letter-spacing: 0.5px;
}

.sidebar-footer {
  margin-top: auto;
  padding-top: var(--space-4);
  border-top: 1px solid var(--workspace-border);
}

.add-provider-btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--lumi-primary);
  transition: all var(--transition-normal);
}

.add-provider-btn:hover {
  background: var(--lumi-primary-light);
}

.detail-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-6) var(--space-7);
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.detail-content--panel {
  padding: 0;
  overflow-y: auto;
  overflow-x: hidden;
}

/* ── 统一加大内容区 section 间距 ── */
.detail-content :deep(.content-section) {
  gap: var(--space-7);
}
</style>

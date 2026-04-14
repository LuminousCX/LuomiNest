<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import {
  Settings2, Play, Pause, RotateCcw, Save, Plus, Trash2,
  ChevronDown, ChevronRight, Sliders, Layers, MousePointer, Sparkles
} from 'lucide-vue-next'
import type { ModelAsset, ModelConfiguration, ModelAnimation, ModelInteraction } from '../../types'
import { modelApi } from '../../services/modelApi'

const props = defineProps<{
  model: ModelAsset
}>()

const emit = defineEmits<{
  (e: 'update:model', model: ModelAsset): void
}>()

const activeTab = ref<'properties' | 'animations' | 'interactions'>('properties')
const configurations = ref<ModelConfiguration[]>([])
const animations = ref<ModelAnimation[]>([])
const interactions = ref<ModelInteraction[]>([])
const selectedConfigId = ref<string | null>(null)
const isLoading = ref(false)
const isSaving = ref(false)
const expandedSections = ref<Record<string, boolean>>({
  position: true,
  render: true,
  animation: true,
  physics: true
})

const currentConfig = computed(() => {
  return configurations.value.find(c => c.id === selectedConfigId.value) || configurations.value[0] || null
})

const editableProperties = computed(() => {
  if (!currentConfig.value?.properties) return { scale: 1, position: { x: 0, y: 0, z: 0 } }
  return { 
    ...currentConfig.value.properties,
    position: { ...(currentConfig.value.properties.position || { x: 0, y: 0, z: 0 }) }
  }
})

const editableAnimParams = computed(() => {
  if (!currentConfig.value?.animation_params) return {}
  return { ...currentConfig.value.animation_params }
})

const editableRenderSettings = computed(() => {
  if (!currentConfig.value?.render_settings) return {}
  return { ...currentConfig.value.render_settings }
})

const editablePhysicsSettings = computed(() => {
  if (!currentConfig.value?.physics_settings) return {}
  return { ...currentConfig.value.physics_settings }
})

watch(() => props.model.id, async (newId) => {
  if (newId) await loadData()
}, { immediate: true })

async function loadData() {
  isLoading.value = true
  try {
    const [configs, anims, inters] = await Promise.all([
      modelApi.getConfigurations(props.model.id),
      modelApi.getAnimations(props.model.id),
      modelApi.getInteractions(props.model.id)
    ])
    configurations.value = configs
    animations.value = anims
    interactions.value = inters
    if (configs.length > 0 && !selectedConfigId.value) {
      selectedConfigId.value = configs.find(c => c.is_default)?.id || configs[0].id
    }
  } catch (err) {
    console.error('Failed to load model data:', err)
  } finally {
    isLoading.value = false
  }
}

function toggleSection(key: string) {
  expandedSections.value[key] = !expandedSections.value[key]
}

async function saveConfiguration() {
  if (!currentConfig.value) return
  isSaving.value = true
  try {
    await modelApi.updateConfiguration(currentConfig.value.id, {
      properties: editableProperties.value,
      animation_params: editableAnimParams.value,
      render_settings: editableRenderSettings.value,
      physics_settings: editablePhysicsSettings.value,
    } as any)
  } catch (err) {
    console.error('Failed to save configuration:', err)
  } finally {
    isSaving.value = false
  }
}

async function toggleAnimation(anim: ModelAnimation) {
  try {
    await modelApi.updateAnimation(anim.id, { is_enabled: !anim.is_enabled })
    anim.is_enabled = !anim.is_enabled
  } catch (err) {
    console.error('Failed to toggle animation:', err)
  }
}

async function toggleInteraction(inter: ModelInteraction) {
  try {
    await modelApi.updateInteraction(inter.id, { is_enabled: !inter.is_enabled })
    inter.is_enabled = !inter.is_enabled
  } catch (err) {
    console.error('Failed to toggle interaction:', err)
  }
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

const modelTypeLabel: Record<string, string> = {
  live2d: 'Live2D',
  blender: 'Blender/glTF',
  vam: 'VAM',
  vrm: 'VRM'
}
</script>

<template>
  <div class="config-panel">
    <div class="panel-header">
      <div class="model-info">
        <h3>{{ model.name }}</h3>
        <div class="model-meta">
          <span class="meta-badge">{{ modelTypeLabel[model.model_type] || model.model_type }}</span>
          <span class="meta-text">v{{ model.version }}</span>
          <span class="meta-text">{{ formatSize(model.file_size) }}</span>
        </div>
      </div>
      <button class="save-btn" :disabled="isSaving" @click="saveConfiguration">
        <Save :size="14" />
        <span>{{ isSaving ? '保存中...' : '保存配置' }}</span>
      </button>
    </div>

    <div class="config-tabs">
      <button
        :class="['tab-btn', { active: activeTab === 'properties' }]"
        @click="activeTab = 'properties'"
      >
        <Sliders :size="14" /> 属性
      </button>
      <button
        :class="['tab-btn', { active: activeTab === 'animations' }]"
        @click="activeTab = 'animations'"
      >
        <Layers :size="14" /> 动画
        <span v-if="animations.length" class="tab-count">{{ animations.length }}</span>
      </button>
      <button
        :class="['tab-btn', { active: activeTab === 'interactions' }]"
        @click="activeTab = 'interactions'"
      >
        <MousePointer :size="14" /> 交互
        <span v-if="interactions.length" class="tab-count">{{ interactions.length }}</span>
      </button>
    </div>

    <div class="config-select" v-if="configurations.length > 1">
      <select v-model="selectedConfigId" class="config-dropdown">
        <option v-for="cfg in configurations" :key="cfg.id" :value="cfg.id">
          {{ cfg.display_name || cfg.config_name }}{{ cfg.is_default ? ' (默认)' : '' }}
        </option>
      </select>
    </div>

    <div class="panel-body" v-if="!isLoading">
      <!-- Properties Tab -->
      <div v-if="activeTab === 'properties'" class="tab-content">
        <div class="section" v-if="currentConfig">
          <button class="section-header" @click="toggleSection('position')">
            <component :is="expandedSections.position ? ChevronDown : ChevronRight" :size="14" />
            <span>位置与变换</span>
          </button>
          <div v-if="expandedSections.position" class="section-body">
            <div class="prop-grid">
              <div class="prop-item">
                <label>缩放</label>
                <input type="number" step="0.1" v-model.number="editableProperties.scale" class="prop-input" />
              </div>
              <div class="prop-item">
                <label>X 位置</label>
                <input type="number" step="0.1" v-model.number="editableProperties.position.x" class="prop-input" />
              </div>
              <div class="prop-item">
                <label>Y 位置</label>
                <input type="number" step="0.1" v-model.number="editableProperties.position.y" class="prop-input" />
              </div>
              <div class="prop-item">
                <label>Z 位置</label>
                <input type="number" step="0.1" v-model.number="editableProperties.position.z" class="prop-input" />
              </div>
            </div>
          </div>
        </div>

        <div class="section" v-if="currentConfig">
          <button class="section-header" @click="toggleSection('render')">
            <component :is="expandedSections.render ? ChevronDown : ChevronRight" :size="14" />
            <span>渲染设置</span>
          </button>
          <div v-if="expandedSections.render" class="section-body">
            <div class="prop-grid">
              <div class="prop-item">
                <label>抗锯齿</label>
                <select v-model="editableRenderSettings.antialiasing" class="prop-input">
                  <option value="none">关闭</option>
                  <option value="msaa_2x">MSAA 2x</option>
                  <option value="msaa_4x">MSAA 4x</option>
                  <option value="msaa_8x">MSAA 8x</option>
                </select>
              </div>
              <div class="prop-item">
                <label>目标帧率</label>
                <input type="number" v-model.number="editableRenderSettings.target_fps" class="prop-input" />
              </div>
              <div class="prop-item" v-if="editableRenderSettings.tone_mapping !== undefined">
                <label>色调映射</label>
                <select v-model="editableRenderSettings.tone_mapping" class="prop-input">
                  <option value="none">关闭</option>
                  <option value="aces">ACES</option>
                  <option value="reinhard">Reinhard</option>
                </select>
              </div>
              <div class="prop-item" v-if="editableRenderSettings.exposure !== undefined">
                <label>曝光度</label>
                <input type="number" step="0.1" v-model.number="editableRenderSettings.exposure" class="prop-input" />
              </div>
            </div>
          </div>
        </div>

        <div class="section" v-if="currentConfig">
          <button class="section-header" @click="toggleSection('animation')">
            <component :is="expandedSections.animation ? ChevronDown : ChevronRight" :size="14" />
            <span>动画参数</span>
          </button>
          <div v-if="expandedSections.animation" class="section-body">
            <div class="prop-grid">
              <div class="prop-item">
                <label>闲置动画</label>
                <button
                  :class="['toggle-sm', { on: editableAnimParams.idle_enabled }]"
                  @click="editableAnimParams.idle_enabled = !editableAnimParams.idle_enabled"
                >
                  {{ editableAnimParams.idle_enabled ? '开启' : '关闭' }}
                </button>
              </div>
              <div class="prop-item">
                <label>闲置间隔 (ms)</label>
                <input type="number" v-model.number="editableAnimParams.idle_interval_ms" class="prop-input" />
              </div>
              <div class="prop-item">
                <label>眨眼</label>
                <button
                  :class="['toggle-sm', { on: editableAnimParams.blink_enabled }]"
                  @click="editableAnimParams.blink_enabled = !editableAnimParams.blink_enabled"
                >
                  {{ editableAnimParams.blink_enabled ? '开启' : '关闭' }}
                </button>
              </div>
              <div class="prop-item">
                <label>呼吸幅度</label>
                <input type="number" step="0.01" v-model.number="editableAnimParams.breath_amplitude" class="prop-input" />
              </div>
            </div>
          </div>
        </div>

        <div class="section" v-if="currentConfig">
          <button class="section-header" @click="toggleSection('physics')">
            <component :is="expandedSections.physics ? ChevronDown : ChevronRight" :size="14" />
            <span>物理设置</span>
          </button>
          <div v-if="expandedSections.physics" class="section-body">
            <div class="prop-grid">
              <div class="prop-item">
                <label>物理模拟</label>
                <button
                  :class="['toggle-sm', { on: editablePhysicsSettings.enabled }]"
                  @click="editablePhysicsSettings.enabled = !editablePhysicsSettings.enabled"
                >
                  {{ editablePhysicsSettings.enabled ? '开启' : '关闭' }}
                </button>
              </div>
              <div class="prop-item" v-if="editablePhysicsSettings.gravity !== undefined">
                <label>重力</label>
                <input type="number" step="0.1" v-model.number="editablePhysicsSettings.gravity" class="prop-input" />
              </div>
              <div class="prop-item" v-if="editablePhysicsSettings.damping !== undefined">
                <label>阻尼</label>
                <input type="number" step="0.01" v-model.number="editablePhysicsSettings.damping" class="prop-input" />
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Animations Tab -->
      <div v-if="activeTab === 'animations'" class="tab-content">
        <div v-if="animations.length === 0" class="empty-state">
          <Layers :size="32" />
          <span>暂无动画数据</span>
        </div>
        <div v-else class="anim-list">
          <div
            v-for="anim in animations"
            :key="anim.id"
            :class="['anim-card', { disabled: !anim.is_enabled }]"
          >
            <div class="anim-left">
              <button class="anim-toggle" @click="toggleAnimation(anim)">
                <component :is="anim.is_enabled ? Pause : Play" :size="14" />
              </button>
              <div class="anim-info">
                <span class="anim-name">{{ anim.name }}</span>
                <span class="anim-meta">
                  {{ anim.group || '默认' }} · {{ anim.duration.toFixed(1) }}s · {{ anim.fps }}fps
                  <span v-if="anim.loop" class="loop-tag">循环</span>
                </span>
              </div>
            </div>
            <div class="anim-right">
              <span class="anim-trigger">{{ anim.trigger_type }}</span>
              <span class="anim-blend">{{ anim.blend_mode }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Interactions Tab -->
      <div v-if="activeTab === 'interactions'" class="tab-content">
        <div v-if="interactions.length === 0" class="empty-state">
          <MousePointer :size="32" />
          <span>暂无交互配置</span>
        </div>
        <div v-else class="inter-list">
          <div
            v-for="inter in interactions"
            :key="inter.id"
            :class="['inter-card', { disabled: !inter.is_enabled }]"
          >
            <div class="inter-left">
              <button class="inter-toggle" @click="toggleInteraction(inter)">
                <Sparkles :size="14" :class="{ active: inter.is_enabled }" />
              </button>
              <div class="inter-info">
                <span class="inter-name">{{ inter.name }}</span>
                <span class="inter-meta">
                  {{ inter.interaction_type }} · {{ inter.trigger_event }} → {{ inter.target_parameter }}
                </span>
              </div>
            </div>
            <div class="inter-right">
              <span class="inter-range">{{ inter.min_value }} ~ {{ inter.max_value }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="loading-state">
      <RotateCcw :size="20" class="spin" />
      <span>加载中...</span>
    </div>
  </div>
</template>

<style scoped>
.config-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--surface);
  border-left: 1px solid var(--border);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 18px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.model-info h3 {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
}

.model-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}

.meta-badge {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  font-weight: 500;
}

.meta-text {
  font-size: 11px;
  color: var(--text-muted);
}

.save-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: var(--radius-md);
  background: var(--lumi-primary);
  color: #fff;
  font-size: 12px;
  font-weight: 500;
  transition: all var(--transition-fast);
}

.save-btn:hover:not(:disabled) {
  background: var(--lumi-primary-hover);
}

.save-btn:disabled {
  opacity: 0.5;
}

.config-tabs {
  display: flex;
  gap: 2px;
  padding: 8px 18px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 8px 14px;
  border-radius: var(--radius-md);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.tab-btn:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.tab-btn.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.tab-count {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 8px;
  background: var(--surface-hover);
  color: var(--text-muted);
}

.config-select {
  padding: 10px 18px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.config-dropdown {
  width: 100%;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-secondary);
  color: var(--text);
  font-size: 13px;
}

.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 0;
}

.tab-content {
  padding: 12px 0;
}

.section {
  border-bottom: 1px solid var(--border-light);
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 12px 18px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.section-header:hover {
  background: var(--surface-hover);
}

.section-body {
  padding: 0 18px 14px;
}

.prop-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.prop-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.prop-item label {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 500;
}

.prop-input {
  padding: 7px 10px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--bg-secondary);
  color: var(--text);
  font-size: 12px;
  transition: all var(--transition-fast);
}

.prop-input:focus {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 2px var(--lumi-primary-glow);
}

.toggle-sm {
  padding: 7px 10px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--bg-secondary);
  color: var(--text-muted);
  font-size: 12px;
  cursor: pointer;
  transition: all var(--transition-fast);
  text-align: center;
}

.toggle-sm.on {
  background: var(--lumi-primary-light);
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
}

.anim-list,
.inter-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.anim-card,
.inter-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 18px;
  transition: background var(--transition-fast);
}

.anim-card:hover,
.inter-card:hover {
  background: var(--surface-hover);
}

.anim-card.disabled,
.inter-card.disabled {
  opacity: 0.5;
}

.anim-left,
.inter-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.anim-toggle,
.inter-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.anim-toggle:hover,
.inter-toggle:hover {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.inter-toggle .active {
  color: var(--lumi-primary);
}

.anim-info,
.inter-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.anim-name,
.inter-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
}

.anim-meta,
.inter-meta {
  font-size: 11px;
  color: var(--text-muted);
}

.loop-tag {
  display: inline-block;
  padding: 0 5px;
  border-radius: 4px;
  background: rgba(34, 197, 94, 0.1);
  color: #22c55e;
  font-size: 10px;
  margin-left: 4px;
}

.anim-right,
.inter-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.anim-trigger,
.anim-blend {
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 6px;
  background: var(--surface-hover);
  color: var(--text-muted);
}

.inter-range {
  font-size: 11px;
  color: var(--text-muted);
  font-family: monospace;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 48px 24px;
  color: var(--text-muted);
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 48px;
  color: var(--text-muted);
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
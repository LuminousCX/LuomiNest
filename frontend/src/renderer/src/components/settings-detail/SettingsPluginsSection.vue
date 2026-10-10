<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Puzzle,
  Package,
  Brain,
  RefreshCw,
  Power,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Loader2,
  Tag,
  Lock,
  Plus,
  Pencil,
  Trash2,
  Sparkles,
} from 'lucide-vue-next'

const PackageIcon = Package
const BrainIcon = Brain
import LumiCard from '../common/LumiCard.vue'
import LumiButton from '../common/LumiButton.vue'
import LumiEmptyState from '../common/LumiEmptyState.vue'
import SegmentTabs from '../common/SegmentTabs.vue'
import type { SegmentTabOption } from '../common/SegmentTabs.vue'
import { usePluginsStore } from '../../stores/plugins'
import { resolvePluginIcon } from '../../plugins/plugin-icons'
import type {
  CxFrontendPluginInstance,
  CxBackendPlugin,
  CxBackendSkill,
} from '../../plugins/types'
import SkillEditDialog from './SkillEditDialog.vue'
import ConfirmDialog from '../common/ConfirmDialog.vue'
import PluginConfigAssistantDialog from './PluginConfigAssistantDialog.vue'

const store = usePluginsStore()
const { t } = useI18n()

const activeTab = ref<'frontend' | 'backend' | 'skills'>('frontend')

onMounted(() => {
  store.initAll()
})

// ---------------- 前端插件状态徽章 ----------------
const frontendStatusBadge = (status: CxFrontendPluginInstance['status']) => {
  switch (status) {
    case 'active': return { text: t('settingsEx.plugins.statusActive'), cls: 'active', icon: CheckCircle2 }
    case 'inactive': return { text: t('settingsEx.plugins.statusInactive'), cls: 'inactive', icon: XCircle }
    case 'error': return { text: t('settingsEx.plugins.statusError'), cls: 'error', icon: AlertCircle }
    default: return { text: t('settingsEx.plugins.statusDiscovered'), cls: 'discovered', icon: Tag }
  }
}

// ---------------- 后端插件状态徽章 ----------------
const backendStatusBadge = (plugin: CxBackendPlugin) => {
  if (plugin.is_active) return { text: t('settingsEx.plugins.statusRunning'), cls: 'active', icon: CheckCircle2 }
  if (plugin.status === 'error') return { text: t('settingsEx.plugins.statusError'), cls: 'error', icon: AlertCircle }
  if (plugin.status === 'disabled') return { text: t('settingsEx.plugins.statusDisabled'), cls: 'inactive', icon: XCircle }
  return { text: plugin.status, cls: 'discovered', icon: Tag }
}

// ---------------- 技能状态徽章 ----------------
const skillStatusBadge = (skill: CxBackendSkill) => {
  if (skill.is_active) return { text: t('settingsEx.plugins.statusEnabled'), cls: 'active', icon: CheckCircle2 }
  if (skill.status === 'error') return { text: t('settingsEx.plugins.statusError'), cls: 'error', icon: AlertCircle }
  return { text: t('settingsEx.plugins.statusDisabled'), cls: 'inactive', icon: XCircle }
}

// ---------------- 操作处理 ----------------
const handleFrontendToggle = (plugin: CxFrontendPluginInstance) => {
  if (plugin.status === 'active') {
    store.disableFrontendPlugin(plugin.manifest.id)
  } else {
    store.enableFrontendPlugin(plugin.manifest.id)
  }
}

const handleBackendToggle = (plugin: CxBackendPlugin) => {
  if (plugin.is_active) {
    store.disableBackendPlugin(plugin.id)
  } else {
    store.enableBackendPlugin(plugin.id)
  }
}

const handleSkillToggle = (skill: CxBackendSkill) => {
  if (skill.is_active) {
    store.disableSkill(skill.id)
  } else {
    store.enableSkill(skill.id)
  }
}

// ---------------- 技能编辑对话框 ----------------
const skillEditVisible = ref(false)
const editingSkillId = ref<string | null>(null)

const openCreateSkill = () => {
  editingSkillId.value = null
  skillEditVisible.value = true
}

const openEditSkill = (skillId: string) => {
  editingSkillId.value = skillId
  skillEditVisible.value = true
}

const handleSkillSaved = () => {
  // store.writeSkill 内部已刷新技能列表
}

const deleteSkillTarget = ref<CxBackendSkill | null>(null)

const handleDeleteSkill = (skill: CxBackendSkill): void => {
  deleteSkillTarget.value = skill
}

const confirmDeleteSkill = async (): Promise<void> => {
  const skill = deleteSkillTarget.value
  if (!skill) return
  await store.deleteSkill(skill.id)
  deleteSkillTarget.value = null
}

// ---------------- 插件 AI 配置助手对话框 ----------------
const pluginAssistantVisible = ref(false)
const assistantPluginId = ref<string | null>(null)
const assistantPluginName = ref<string>('')

const openPluginAssistant = (plugin: CxBackendPlugin) => {
  assistantPluginId.value = plugin.id
  assistantPluginName.value = plugin.name
  pluginAssistantVisible.value = true
}

// ---------------- 统计摘要 ----------------
const summary = computed(() => ({
  frontend: t('settingsEx.plugins.summaryFrontend', { active: store.frontendStats.active, total: store.frontendStats.total }),
  backend: t('settingsEx.plugins.summaryBackend', { active: store.backendStats.active, total: store.backendStats.total }),
  skills: t('settingsEx.plugins.summarySkills', { active: store.skillStats.active, total: store.skillStats.total }),
}))

/** 插件页主 tab（SegmentTabs lg 档，badge 为各类统计摘要） */
const tabOptions = computed<SegmentTabOption<'frontend' | 'backend' | 'skills'>[]>(() => [
  { value: 'frontend', label: t('settingsEx.plugins.tabFrontend'), icon: Puzzle, badge: summary.value.frontend },
  { value: 'backend', label: t('settingsEx.plugins.tabBackend'), icon: Package, badge: summary.value.backend },
  { value: 'skills', label: t('settingsEx.plugins.tabSkills'), icon: Brain, badge: summary.value.skills },
])
</script>

<template>
  <div class="settings-panel plugins-section">
    <!-- 标签栏：SegmentTabs（lg） -->
    <SegmentTabs v-model="activeTab" :options="tabOptions" size="lg" />

    <!-- 操作栏 -->
    <div class="action-bar">
      <LumiButton
        variant="ghost"
        size="sm"
        :disabled="store.loadingBackend"
        @click="store.initAll()"
      >
        <RefreshCw :size="14" :class="['refresh-icon', { spinning: store.loadingBackend }]" />
        <span>{{ t('settingsEx.plugins.refresh') }}</span>
      </LumiButton>
      <LumiButton
        v-if="activeTab === 'backend'"
        variant="ghost"
        size="sm"
        :disabled="store.operating"
        @click="store.reloadAllBackendPlugins()"
      >
        <RefreshCw :size="14" />
        <span>{{ t('settingsEx.plugins.reloadAll') }}</span>
      </LumiButton>
      <LumiButton
        v-if="activeTab === 'skills'"
        variant="ghost"
        size="sm"
        :disabled="store.operating"
        @click="store.reloadAllSkills()"
      >
        <RefreshCw :size="14" />
        <span>{{ t('settingsEx.plugins.reloadAll') }}</span>
      </LumiButton>
      <LumiButton
        v-if="activeTab === 'skills'"
        variant="primary"
        size="sm"
        :disabled="store.operating"
        @click="openCreateSkill"
      >
        <Plus :size="14" />
        <span>{{ t('settingsEx.plugins.createSkill') }}</span>
      </LumiButton>
    </div>

    <!-- 前端插件列表 -->
    <div v-if="activeTab === 'frontend'" class="plugin-list">
      <LumiEmptyState
        v-if="!store.frontendPlugins.length"
        :icon="PackageIcon"
        :title="t('settingsEx.plugins.frontendEmptyTitle')"
        :description="t('settingsEx.plugins.frontendEmptyDesc')"
      />
      <LumiCard
        v-for="plugin in store.frontendPlugins"
        :key="plugin.manifest.id"
        class="plugin-card"
        padding="md"
      >
        <div class="plugin-header">
          <div class="plugin-icon-box">
            <component :is="resolvePluginIcon(plugin.manifest.icon)" :size="20" />
          </div>
          <div class="plugin-info">
            <div class="plugin-title-row">
              <span class="plugin-name">{{ plugin.manifest.name }}</span>
              <span class="plugin-version">v{{ plugin.manifest.version }}</span>
              <span v-if="plugin.manifest.builtin" class="builtin-badge">
                <Lock :size="11" /> {{ t('settingsEx.plugins.builtin') }}
              </span>
            </div>
            <span class="plugin-id">{{ plugin.manifest.id }}</span>
            <p class="plugin-desc">{{ plugin.manifest.description }}</p>
          </div>
          <div :class="['status-badge', frontendStatusBadge(plugin.status).cls]">
            <component :is="frontendStatusBadge(plugin.status).icon" :size="12" />
            <span>{{ frontendStatusBadge(plugin.status).text }}</span>
          </div>
        </div>

        <div v-if="plugin.errorMessage" class="error-message">
          <AlertCircle :size="13" />
          <span>{{ plugin.errorMessage }}</span>
        </div>

        <div class="plugin-meta">
          <span v-if="plugin.manifest.author" class="meta-item">{{ t('settingsEx.plugins.author', { name: plugin.manifest.author }) }}</span>
          <span class="meta-item">{{ t('settingsEx.plugins.contributions', { views: plugin.registeredViewIds.length, commands: plugin.registeredCommandIds.length, themes: plugin.registeredThemeIds.length }) }}</span>
        </div>

        <div class="plugin-actions">
          <LumiButton
            :variant="plugin.status === 'active' ? 'danger-ghost' : 'primary'"
            size="sm"
            :disabled="store.operating || plugin.manifest.builtin === false && plugin.status === 'error'"
            :loading="store.operating"
            @click="handleFrontendToggle(plugin)"
          >
            <Power :size="13" />
            <span>{{ plugin.status === 'active' ? t('settingsEx.plugins.disable') : t('settingsEx.plugins.enable') }}</span>
          </LumiButton>
        </div>
      </LumiCard>
    </div>

    <!-- 后端插件列表 -->
    <div v-else-if="activeTab === 'backend'" class="plugin-list">
      <div v-if="store.loadingBackend && !store.backendPlugins.length" class="loading-state">
        <Loader2 :size="22" class="spinning" />
        <span>{{ t('settingsEx.plugins.loadingBackend') }}</span>
      </div>
      <LumiEmptyState
        v-else-if="!store.backendPlugins.length"
        :icon="PackageIcon"
        :title="t('settingsEx.plugins.backendEmptyTitle')"
        :description="t('settingsEx.plugins.backendEmptyDesc')"
      />
      <LumiCard
        v-for="plugin in store.backendPlugins"
        :key="plugin.id"
        class="plugin-card"
        padding="md"
      >
        <div class="plugin-header">
          <div class="plugin-icon-box">
            <component :is="resolvePluginIcon(plugin.icon)" :size="20" />
          </div>
          <div class="plugin-info">
            <div class="plugin-title-row">
              <span class="plugin-name">{{ plugin.name }}</span>
              <span class="plugin-version">v{{ plugin.version }}</span>
              <span v-if="plugin.reserved" class="builtin-badge">
                <Lock :size="11" /> {{ t('settingsEx.plugins.reserved') }}
              </span>
            </div>
            <span class="plugin-id">{{ plugin.id }}</span>
            <p class="plugin-desc">{{ plugin.description }}</p>
          </div>
          <div :class="['status-badge', backendStatusBadge(plugin).cls]">
            <component :is="backendStatusBadge(plugin).icon" :size="12" />
            <span>{{ backendStatusBadge(plugin).text }}</span>
          </div>
        </div>

        <div v-if="plugin.error_message" class="error-message">
          <AlertCircle :size="13" />
          <span>{{ plugin.error_message }}</span>
        </div>

        <div class="plugin-meta">
          <span v-if="plugin.author" class="meta-item">{{ t('settingsEx.plugins.author', { name: plugin.author }) }}</span>
          <span class="meta-item">{{ t('settingsEx.plugins.platform', { value: plugin.platform }) }}</span>
          <span v-if="plugin.permissions?.length" class="meta-item">{{ t('settingsEx.plugins.permissions', { value: plugin.permissions.join(', ') }) }}</span>
        </div>

        <div class="plugin-actions">
          <LumiButton
            :variant="plugin.is_active ? 'danger-ghost' : 'primary'"
            size="sm"
            :disabled="store.operating || plugin.reserved"
            :loading="store.operating"
            @click="handleBackendToggle(plugin)"
          >
            <Power :size="13" />
            <span>{{ plugin.is_active ? t('settingsEx.plugins.disableAlt') : t('settingsEx.plugins.enable') }}</span>
          </LumiButton>
          <LumiButton
            variant="ghost"
            size="sm"
            :disabled="store.operating"
            @click="store.reloadBackendPlugin(plugin.id)"
          >
            <RefreshCw :size="13" />
            <span>{{ t('settingsEx.plugins.reload') }}</span>
          </LumiButton>
          <LumiButton
            v-if="plugin.settings && Object.keys(plugin.settings).length > 0"
            variant="outline"
            size="sm"
            :disabled="store.operating"
            @click="openPluginAssistant(plugin)"
          >
            <Sparkles :size="13" />
            <span>{{ t('settingsEx.plugins.aiConfig') }}</span>
          </LumiButton>
        </div>
      </LumiCard>
    </div>

    <!-- 技能列表 -->
    <div v-else class="plugin-list">
      <div v-if="store.loadingBackend && !store.skills.length" class="loading-state">
        <Loader2 :size="22" class="spinning" />
        <span>{{ t('settingsEx.plugins.loadingSkills') }}</span>
      </div>
      <LumiEmptyState
        v-else-if="!store.skills.length"
        :icon="BrainIcon"
        :title="t('settingsEx.plugins.skillsEmptyTitle')"
        :description="t('settingsEx.plugins.skillsEmptyDesc')"
      />
      <LumiCard
        v-for="skill in store.skills"
        :key="skill.id"
        class="plugin-card"
        padding="md"
      >
        <div class="plugin-header">
          <div class="plugin-icon-box">
            <Brain :size="20" />
          </div>
          <div class="plugin-info">
            <div class="plugin-title-row">
              <span class="plugin-name">{{ skill.name || skill.id }}</span>
              <span class="plugin-version">v{{ skill.version }}</span>
            </div>
            <span class="plugin-id">{{ skill.id }}</span>
            <p class="plugin-desc">{{ skill.description }}</p>
            <div v-if="skill.trigger_keywords?.length" class="skill-keywords">
              <span v-for="kw in skill.trigger_keywords" :key="kw" class="keyword-chip">{{ kw }}</span>
            </div>
          </div>
          <div :class="['status-badge', skillStatusBadge(skill).cls]">
            <component :is="skillStatusBadge(skill).icon" :size="12" />
            <span>{{ skillStatusBadge(skill).text }}</span>
          </div>
        </div>

        <div class="plugin-meta">
          <span v-if="skill.author" class="meta-item">{{ t('settingsEx.plugins.author', { name: skill.author }) }}</span>
          <span class="meta-item">{{ t('settingsEx.plugins.category', { value: skill.category || t('settingsEx.plugins.uncategorized') }) }}</span>
          <span v-if="skill.source_format" class="meta-item">{{ t('settingsEx.plugins.format', { value: skill.source_format }) }}</span>
        </div>

        <div class="plugin-actions">
          <LumiButton
            :variant="skill.is_active ? 'danger-ghost' : 'primary'"
            size="sm"
            :disabled="store.operating"
            :loading="store.operating"
            @click="handleSkillToggle(skill)"
          >
            <Power :size="13" />
            <span>{{ skill.is_active ? t('settingsEx.plugins.disableAlt') : t('settingsEx.plugins.enable') }}</span>
          </LumiButton>
          <LumiButton
            variant="ghost"
            size="sm"
            :disabled="store.operating"
            @click="store.reloadSkill(skill.id)"
          >
            <RefreshCw :size="13" />
            <span>{{ t('settingsEx.plugins.reload') }}</span>
          </LumiButton>
          <LumiButton
            variant="outline"
            size="sm"
            :disabled="store.operating"
            @click="openEditSkill(skill.id)"
          >
            <Pencil :size="13" />
            <span>{{ t('settingsEx.plugins.edit') }}</span>
          </LumiButton>
          <LumiButton
            variant="danger-ghost"
            size="sm"
            :disabled="store.operating"
            @click="handleDeleteSkill(skill)"
          >
            <Trash2 :size="13" />
            <span>{{ t('settingsEx.plugins.delete') }}</span>
          </LumiButton>
        </div>
      </LumiCard>
    </div>

    <!-- 技能编辑对话框（在所有 tab 之外，确保都能渲染） -->
    <SkillEditDialog
      v-model:visible="skillEditVisible"
      :skill-id="editingSkillId"
      @saved="handleSkillSaved"
    />

    <!-- 插件 AI 配置助手对话框 -->
    <PluginConfigAssistantDialog
      v-model:visible="pluginAssistantVisible"
      :plugin-id="assistantPluginId"
      :plugin-name="assistantPluginName"
    />

    <ConfirmDialog
      :visible="deleteSkillTarget !== null"
      :message="deleteSkillTarget ? t('settingsEx.plugins.confirmDeleteSkill', { name: deleteSkillTarget.name }) : ''"
      :danger="true"
      :confirm-text="t('common.delete')"
      @confirm="confirmDeleteSkill"
      @cancel="deleteSkillTarget = null"
    />
  </div>
</template>

<style scoped>
.plugins-section {
  /* layout handled by settings-panel shared class */
}

/* 标签栏 → SegmentTabs（lg），样式由全局组件承担 */

.action-bar {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}

.refresh-icon.spinning {
  animation: spin 0.8s linear infinite;
}



.plugin-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-8);
  color: var(--text-muted);
  font-size: var(--text-sm);
}

.spinning {
  animation: spin 0.8s linear infinite;
}

.plugin-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.plugin-header {
  display: flex;
  gap: var(--space-3);
  align-items: flex-start;
}

.plugin-icon-box {
  width: var(--space-10);
  height: var(--space-10);
  border-radius: var(--radius-md);
  background: var(--lumi-brand-gradient-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--lumi-primary);
  flex-shrink: 0;
}

.plugin-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.plugin-title-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.plugin-name {
  font-size: var(--text-md);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.plugin-version {
  font-size: var(--text-xs);
  color: var(--text-muted);
  padding: 1px 6px;
  border-radius: var(--radius-xs);
  background: var(--surface-hover);
}

.builtin-badge {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: var(--text-2xs);
  color: var(--text-muted);
  padding: 1px 6px;
  border-radius: var(--radius-xs);
  background: var(--surface-hover);
  border: 1px solid var(--border);
}

.plugin-id {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.plugin-desc {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  margin-top: 2px;
  line-height: 1.5;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: var(--radius-full);
  font-size: var(--text-2xs);
  font-weight: var(--font-semibold);
  flex-shrink: 0;
}

.status-badge.active {
  background: var(--lumi-success-light);
  color: var(--lumi-success-hover);
}

.status-badge.inactive {
  background: var(--surface-hover);
  color: var(--text-muted);
}

.status-badge.error {
  background: var(--lumi-danger-light);
  color: var(--lumi-danger-hover);
}

.status-badge.discovered {
  background: var(--lumi-info-light);
  color: var(--lumi-info-hover);
}

.error-message {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--lumi-danger-light);
  color: var(--lumi-danger-hover);
  font-size: var(--text-xs);
}

.plugin-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  padding-top: var(--space-2);
  border-top: 1px solid var(--divider-soft);
}

.meta-item {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.skill-keywords {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}

.keyword-chip {
  font-size: var(--text-2xs);
  padding: 1px 6px;
  border-radius: var(--radius-xs);
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.plugin-actions {
  display: flex;
  gap: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px solid var(--divider-soft);
}
</style>

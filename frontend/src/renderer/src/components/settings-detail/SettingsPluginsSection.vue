<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
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
import { usePluginsStore } from '../../stores/plugins'
import { resolvePluginIcon } from '../../plugins/plugin-icons'
import type {
  CxFrontendPluginInstance,
  CxBackendPlugin,
  CxBackendSkill,
} from '../../plugins/types'
import SkillEditDialog from './SkillEditDialog.vue'
import PluginConfigAssistantDialog from './PluginConfigAssistantDialog.vue'

const store = usePluginsStore()

const activeTab = ref<'frontend' | 'backend' | 'skills'>('frontend')

const tabs = [
  { id: 'frontend' as const, label: '前端插件', icon: Puzzle },
  { id: 'backend' as const, label: '后端插件', icon: Package },
  { id: 'skills' as const, label: '技能', icon: Brain },
]

onMounted(() => {
  store.initAll()
})

// ---------------- 前端插件状态徽章 ----------------
const frontendStatusBadge = (status: CxFrontendPluginInstance['status']) => {
  switch (status) {
    case 'active': return { text: '已激活', cls: 'active', icon: CheckCircle2 }
    case 'inactive': return { text: '已停用', cls: 'inactive', icon: XCircle }
    case 'error': return { text: '错误', cls: 'error', icon: AlertCircle }
    default: return { text: '已发现', cls: 'discovered', icon: Tag }
  }
}

// ---------------- 后端插件状态徽章 ----------------
const backendStatusBadge = (plugin: CxBackendPlugin) => {
  if (plugin.is_active) return { text: '运行中', cls: 'active', icon: CheckCircle2 }
  if (plugin.status === 'error') return { text: '错误', cls: 'error', icon: AlertCircle }
  if (plugin.status === 'disabled') return { text: '已禁用', cls: 'inactive', icon: XCircle }
  return { text: plugin.status, cls: 'discovered', icon: Tag }
}

// ---------------- 技能状态徽章 ----------------
const skillStatusBadge = (skill: CxBackendSkill) => {
  if (skill.is_active) return { text: '已启用', cls: 'active', icon: CheckCircle2 }
  if (skill.status === 'error') return { text: '错误', cls: 'error', icon: AlertCircle }
  return { text: '已禁用', cls: 'inactive', icon: XCircle }
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

const handleDeleteSkill = async (skill: CxBackendSkill) => {
  if (!window.confirm(`确认删除技能「${skill.name}」？此操作不可恢复。`)) return
  await store.deleteSkill(skill.id)
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
  frontend: `${store.frontendStats.active}/${store.frontendStats.total} 已激活`,
  backend: `${store.backendStats.active}/${store.backendStats.total} 运行中`,
  skills: `${store.skillStats.active}/${store.skillStats.total} 已启用`,
}))
</script>

<template>
  <div class="plugins-section">
    <!-- 标签栏 -->
    <div class="tabs-bar">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        :class="['tab-btn', { active: activeTab === tab.id }]"
        @click="activeTab = tab.id"
      >
        <component :is="tab.icon" :size="15" />
        <span>{{ tab.label }}</span>
        <span class="tab-summary">{{ summary[tab.id] }}</span>
      </button>
    </div>

    <!-- 操作栏 -->
    <div class="action-bar">
      <LumiButton
        variant="ghost"
        size="sm"
        :disabled="store.loadingBackend"
        @click="store.initAll()"
      >
        <RefreshCw :size="14" :class="['refresh-icon', { spinning: store.loadingBackend }]" />
        <span>刷新</span>
      </LumiButton>
      <LumiButton
        v-if="activeTab === 'backend'"
        variant="ghost"
        size="sm"
        :disabled="store.operating"
        @click="store.reloadAllBackendPlugins()"
      >
        <RefreshCw :size="14" />
        <span>重载全部</span>
      </LumiButton>
      <LumiButton
        v-if="activeTab === 'skills'"
        variant="ghost"
        size="sm"
        :disabled="store.operating"
        @click="store.reloadAllSkills()"
      >
        <RefreshCw :size="14" />
        <span>重载全部</span>
      </LumiButton>
      <LumiButton
        v-if="activeTab === 'skills'"
        variant="primary"
        size="sm"
        :disabled="store.operating"
        @click="openCreateSkill"
      >
        <Plus :size="14" />
        <span>新建技能</span>
      </LumiButton>
    </div>

    <!-- 前端插件列表 -->
    <div v-if="activeTab === 'frontend'" class="plugin-list">
      <LumiEmptyState
        v-if="!store.frontendPlugins.length"
        :icon="PackageIcon"
        title="暂无前端插件"
        description="将插件放入 frontend/src/renderer/src/plugins/builtin/ 目录即可被自动发现"
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
                <Lock :size="11" /> 内置
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
          <span v-if="plugin.manifest.author" class="meta-item">作者：{{ plugin.manifest.author }}</span>
          <span class="meta-item">贡献：{{ plugin.registeredViewIds.length }} 视图 / {{ plugin.registeredCommandIds.length }} 命令 / {{ plugin.registeredThemeIds.length }} 主题</span>
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
            <span>{{ plugin.status === 'active' ? '停用' : '启用' }}</span>
          </LumiButton>
        </div>
      </LumiCard>
    </div>

    <!-- 后端插件列表 -->
    <div v-else-if="activeTab === 'backend'" class="plugin-list">
      <div v-if="store.loadingBackend && !store.backendPlugins.length" class="loading-state">
        <Loader2 :size="22" class="spinning" />
        <span>加载后端插件中...</span>
      </div>
      <LumiEmptyState
        v-else-if="!store.backendPlugins.length"
        :icon="PackageIcon"
        title="暂无后端插件"
        description="将插件放入 backend/plugins/ 目录并重启后端即可被发现"
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
                <Lock :size="11" /> 保留
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
          <span v-if="plugin.author" class="meta-item">作者：{{ plugin.author }}</span>
          <span class="meta-item">平台：{{ plugin.platform }}</span>
          <span v-if="plugin.permissions?.length" class="meta-item">权限：{{ plugin.permissions.join(', ') }}</span>
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
            <span>{{ plugin.is_active ? '禁用' : '启用' }}</span>
          </LumiButton>
          <LumiButton
            variant="ghost"
            size="sm"
            :disabled="store.operating"
            @click="store.reloadBackendPlugin(plugin.id)"
          >
            <RefreshCw :size="13" />
            <span>重载</span>
          </LumiButton>
          <LumiButton
            v-if="plugin.settings && Object.keys(plugin.settings).length > 0"
            variant="outline"
            size="sm"
            :disabled="store.operating"
            @click="openPluginAssistant(plugin)"
          >
            <Sparkles :size="13" />
            <span>AI 配置</span>
          </LumiButton>
        </div>
      </LumiCard>
    </div>

    <!-- 技能列表 -->
    <div v-else class="plugin-list">
      <div v-if="store.loadingBackend && !store.skills.length" class="loading-state">
        <Loader2 :size="22" class="spinning" />
        <span>加载技能中...</span>
      </div>
      <LumiEmptyState
        v-else-if="!store.skills.length"
        :icon="BrainIcon"
        title="暂无技能"
        description="将 SKILL.md 放入 backend/skills/ 目录即可被自动发现"
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
              <span class="plugin-name">{{ skill.name }}</span>
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
          <span v-if="skill.author" class="meta-item">作者：{{ skill.author }}</span>
          <span v-if="skill.category" class="meta-item">分类：{{ skill.category }}</span>
          <span v-if="skill.source_format" class="meta-item">格式：{{ skill.source_format }}</span>
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
            <span>{{ skill.is_active ? '禁用' : '启用' }}</span>
          </LumiButton>
          <LumiButton
            variant="ghost"
            size="sm"
            :disabled="store.operating"
            @click="store.reloadSkill(skill.id)"
          >
            <RefreshCw :size="13" />
            <span>重载</span>
          </LumiButton>
          <LumiButton
            variant="outline"
            size="sm"
            :disabled="store.operating"
            @click="openEditSkill(skill.id)"
          >
            <Pencil :size="13" />
            <span>编辑</span>
          </LumiButton>
          <LumiButton
            variant="danger-ghost"
            size="sm"
            :disabled="store.operating"
            @click="handleDeleteSkill(skill)"
          >
            <Trash2 :size="13" />
            <span>删除</span>
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
  </div>
</template>

<style scoped>
.plugins-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  max-width: 760px;
}

.tabs-bar {
  display: flex;
  gap: var(--space-1);
  padding: var(--space-1);
  border-radius: var(--radius-md);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
}

.tab-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border: none;
  background: transparent;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.tab-btn:hover {
  color: var(--text-primary);
  background: var(--workspace-hover);
}

.tab-btn.active {
  background: var(--workspace-card);
  color: var(--lumi-primary);
  box-shadow: var(--shadow-xs);
}

.tab-summary {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  padding: 1px 6px;
  border-radius: var(--radius-full);
  background: var(--surface-hover);
}

.tab-btn.active .tab-summary {
  color: var(--lumi-primary);
  background: var(--lumi-primary-light, rgba(99, 102, 241, 0.1));
}

.action-bar {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}

.refresh-icon.spinning {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
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
  font-family: var(--font-mono, monospace);
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
  background: var(--lumi-success-light, rgba(34, 197, 94, 0.12));
  color: var(--lumi-success-hover, rgb(22, 163, 74));
}

.status-badge.inactive {
  background: var(--surface-hover);
  color: var(--text-muted);
}

.status-badge.error {
  background: var(--lumi-danger-light, rgba(239, 68, 68, 0.12));
  color: var(--lumi-danger-hover, rgb(220, 38, 38));
}

.status-badge.discovered {
  background: var(--lumi-info-light, rgba(59, 130, 246, 0.12));
  color: var(--lumi-info-hover, rgb(37, 99, 235));
}

.error-message {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--lumi-danger-light, rgba(239, 68, 68, 0.08));
  color: var(--lumi-danger-hover, rgb(220, 38, 38));
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
  background: var(--lumi-primary-light, rgba(99, 102, 241, 0.1));
  color: var(--lumi-primary);
}

.plugin-actions {
  display: flex;
  gap: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px solid var(--divider-soft);
}
</style>

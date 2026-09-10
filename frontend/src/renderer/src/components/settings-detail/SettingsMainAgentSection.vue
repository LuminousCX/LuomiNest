<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Brain, Check, AlertCircle, Save, Loader2 } from 'lucide-vue-next'
import { usePlatformStore } from '../../stores/platform'
import { PRESET_AGENT_AVATARS, type PresetAvatar } from '../../composables/useWorkspaceAgentDialogs'
import LumiButton from '../common/LumiButton.vue'
import { createLuomiNestRendererLogger } from '../../utils/logger'

const logger = createLuomiNestRendererLogger('Settings')

const platformStore = usePlatformStore()
const { t } = useI18n()

const presetAvatars: PresetAvatar[] = PRESET_AGENT_AVATARS
const agentColors: string[] = [
  'var(--lumi-brand)',
  'var(--lumi-indigo)',
  'var(--lumi-amber)',
  'var(--lumi-accent)',
  'var(--task-sky)',
  'var(--lumi-sky)',
  'var(--lumi-success)',
  'var(--task-pink)',
]

// 2026-08 全局模型统一：主智能体面板仅管理"人设"（系统提示词 / 头像 / 颜色）。
// 模型与生成参数（provider/model/temperature/maxTokens）统一在"模型设置"页配置，
// 此处不再读写，避免把陈旧值写回全局配置。
const mainAgentEdit = ref({
  systemPrompt: '',
  color: '',
  avatar: null as string | null,
  avatarMode: 'color' as 'color' | 'preset',
})
const mainAgentLoading = ref(false)
const mainAgentSaving = ref(false)
const mainAgentSaveMsg = ref<{ type: 'success' | 'error'; text: string } | null>(null)

const loadMainAgentConfig = async () => {
  mainAgentLoading.value = true
  try {
    await platformStore.fetchMainAgent()
    if (platformStore.mainAgent) {
      mainAgentEdit.value = {
        systemPrompt: platformStore.mainAgent.systemPrompt,
        color: platformStore.mainAgent.color || 'var(--lumi-brand)',
        avatar: platformStore.mainAgent.avatar || null,
        avatarMode: platformStore.mainAgent.avatar ? 'preset' : 'color',
      }
    }
  } catch (e) {
    logger.error('Failed to load main agent config:', e)
  } finally {
    mainAgentLoading.value = false
  }
}

const handleSaveMainAgentConfig = async () => {
  mainAgentSaving.value = true
  mainAgentSaveMsg.value = null
  try {
    await platformStore.updateMainAgent({
      systemPrompt: mainAgentEdit.value.systemPrompt,
      color: mainAgentEdit.value.avatarMode === 'color' ? mainAgentEdit.value.color : '',
      avatar: mainAgentEdit.value.avatarMode === 'preset' ? (mainAgentEdit.value.avatar || '') : '',
    })
    mainAgentSaveMsg.value = { type: 'success', text: t('settingsEx.mainAgent.savedToast') }
    setTimeout(() => { mainAgentSaveMsg.value = null }, 3000)
  } catch (e) {
    mainAgentSaveMsg.value = { type: 'error', text: t('settingsEx.mainAgent.saveFailed', { message: e instanceof Error ? e.message : String(e) }) }
  } finally {
    mainAgentSaving.value = false
  }
}

onMounted(() => {
  loadMainAgentConfig()
})
</script>

<template>
  <div class="settings-panel animate-slide-up">
    <div v-if="mainAgentLoading" class="settings-card">
      <div class="settings-card__body settings-card__body--compact main-agent-loading">
        <Loader2 :size="20" class="spin-animation" />
        <span>{{ t('settingsEx.mainAgent.loading') }}</span>
      </div>
    </div>

    <template v-else>
      <section class="settings-card">
        <div class="settings-card__header">
          <Brain :size="18" />
          <span class="settings-card__title">{{ t('settingsEx.mainAgent.personaTitle') }}</span>
        </div>
        <div class="settings-card__body">
          <div class="settings-form-row">
            <label class="settings-form-label">{{ t('settingsEx.mainAgent.systemPrompt') }}</label>
            <textarea
              v-model="mainAgentEdit.systemPrompt"
              class="settings-form-textarea main-agent-prompt"
              rows="10"
              :placeholder="t('settingsEx.mainAgent.promptPlaceholder')"
            />
            <span class="settings-form-hint">{{ t('settingsEx.mainAgent.promptHint') }}</span>
          </div>
        </div>
      </section>

      <section class="settings-card">
        <div class="settings-card__header">
          <Brain :size="18" />
          <span class="settings-card__title">{{ t('settingsEx.mainAgent.avatarTitle') }}</span>
        </div>
        <div class="settings-card__body">
          <div class="settings-mode-selector">
            <button
              :class="['settings-mode-btn', { active: mainAgentEdit.avatarMode === 'color' }]"
              @click="mainAgentEdit.avatarMode = 'color'"
            >{{ t('settingsEx.mainAgent.modeColor') }}</button>
            <button
              :class="['settings-mode-btn', { active: mainAgentEdit.avatarMode === 'preset' }]"
              @click="mainAgentEdit.avatarMode = 'preset'"
            >{{ t('settingsEx.mainAgent.modePreset') }}</button>
          </div>

          <div v-if="mainAgentEdit.avatarMode === 'color'" class="color-picker">
            <button
              v-for="color in agentColors"
              :key="color"
              :class="['color-dot', { active: mainAgentEdit.color === color }]"
              :style="{ background: color }"
              @click="mainAgentEdit.color = color"
            ></button>
          </div>

          <div v-else class="preset-avatar-grid">
            <button
              v-for="avatar in presetAvatars"
              :key="avatar.id"
              :class="['preset-avatar-item', { selected: mainAgentEdit.avatar === avatar.url }]"
              :title="avatar.name"
              @click="mainAgentEdit.avatar = avatar.url"
            >
              <img :src="avatar.url" :alt="avatar.name" class="preset-avatar-img" />
            </button>
          </div>
        </div>
      </section>

      <div class="settings-btn-row">
        <div
          v-if="mainAgentSaveMsg"
          :class="['settings-message', mainAgentSaveMsg.type === 'success' ? 'settings-message--success' : 'settings-message--error']"
        >
          <component :is="mainAgentSaveMsg.type === 'success' ? Check : AlertCircle" :size="14" />
          <span>{{ mainAgentSaveMsg.text }}</span>
        </div>
        <LumiButton
          variant="primary"
          size="sm"
          :loading="mainAgentSaving"
          :disabled="mainAgentSaving"
          @click="handleSaveMainAgentConfig"
        >
          <Save :size="14" />
          <span>{{ mainAgentSaving ? t('settingsEx.mainAgent.saving') : t('settingsEx.mainAgent.saveConfig') }}</span>
        </LumiButton>
      </div>
    </template>
  </div>
</template>

<style scoped>
.main-agent-loading {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  justify-content: center;
  color: var(--text-muted);
  font-size: var(--text-base);
  padding: var(--space-6) 0;
}

.main-agent-prompt {
  min-height: 160px;
  line-height: 1.6;
  font-size: var(--text-base);
}

.color-picker {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.color-dot {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-full);
  border: 2px solid var(--workspace-border);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.color-dot.active {
  border-color: var(--text-primary);
  transform: scale(1.15);
}

.preset-avatar-grid {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.preset-avatar-item {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-full);
  border: 2px solid transparent;
  padding: 0;
  cursor: pointer;
  transition: all var(--transition-normal);
  background: var(--bg-secondary);
  overflow: hidden;
}

.preset-avatar-item:hover {
  transform: scale(1.08);
}

.preset-avatar-item.selected {
  border-color: var(--lumi-brand);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--lumi-brand) 20%, transparent);
}

.preset-avatar-img {
  width: 100%;
  height: 100%;
  border-radius: inherit;
  object-fit: cover;
}

</style>

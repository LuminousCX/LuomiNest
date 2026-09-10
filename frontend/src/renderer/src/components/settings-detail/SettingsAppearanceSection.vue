<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Palette,
  Sparkles
} from 'lucide-vue-next'
import { useThemeStore } from '../../stores/theme'
import type { Skin } from '../../stores/theme-types'
import { PRESET_THEME_IDS } from '../../stores/theme-types'
import { presetThemeNames, presetThemeColors } from '../../stores/theme-presets'
import ThemeSkinSelector from '../theme/ThemeSkinSelector.vue'
import ThemeSkinEditor from '../theme/ThemeSkinEditor.vue'
import { useToast } from '../../composables/useToast'
import '../../styles/views/theme-settings.css'
import '../../styles/views/settings-shared.css'

const themeStore = useThemeStore()
const toast = useToast()
const { t } = useI18n()

// ─── Skin Editor ─────────────────────────────
const editorVisible = ref(false)
const editingSkin = ref<Skin | null>(null)
const editorMode = ref<'edit' | 'create'>('create')

function openSkinEditor(id: string) {
  const skin = themeStore.allSkins.find((s) => s.id === id)
  if (!skin) return

  if (skin.type === 'preset') {
    // 编辑预设皮肤：以此为基础创建自定义皮肤副本
    editingSkin.value = {
      ...skin,
      id: `custom-skin-${Date.now()}`,
      type: 'custom',
      name: t('settingsEx.appearance.skinCopyName', { name: skin.name })
    }
    editorMode.value = 'create'
  } else {
    editingSkin.value = skin
    editorMode.value = 'edit'
  }
  editorVisible.value = true
}

function openNewSkinEditor() {
  editingSkin.value = null
  editorMode.value = 'create'
  editorVisible.value = true
}

function handleApplySkin(id: string) {
  themeStore.setSkin(id)
  toast.success(t('settingsEx.appearance.skinApplied'))
}

function closeEditor() {
  editorVisible.value = false
  editingSkin.value = null
}

function handleSaveSkin(skin: Skin) {
  if (editorMode.value === 'edit' && skin.type === 'custom') {
    themeStore.updateCustomSkin(skin.id, skin)
    toast.success(t('settingsEx.appearance.skinSaved'))
  } else {
    themeStore.addCustomSkin(skin)
    toast.success(t('settingsEx.appearance.skinCreated'))
  }
  closeEditor()
}

function handleDeleteSkin(id: string) {
  themeStore.deleteCustomSkin(id)
  toast.info(t('settingsEx.appearance.skinDeleted'))
}

// ─── Color Theme ─────────────────────────────
function handleColorThemeSelect(id: string) {
  const activeSkin = themeStore.activeSkin
  if (activeSkin?.type === 'custom') {
    themeStore.updateCustomSkin(activeSkin.id, { colorThemeId: id })
    toast.success(t('settingsEx.appearance.colorThemeUpdated'))
  } else {
    themeStore.setColorTheme(id)
  }
}

function getSkinPreviewStyle(skin?: Skin): Record<string, string> {
  if (!skin) return { background: 'var(--surface-hover)' }
  const image = skin.background.image
  if (!image) return { background: 'var(--surface-hover)' }
  if (/^(?:linear|radial|conic)-gradient\(/.test(image)) {
    return { background: image }
  }
  return {
    backgroundImage: `url('${image}')`,
    backgroundSize: skin.background.fit === 'contain' ? 'contain' : 'cover',
    backgroundPosition: skin.background.fit === 'right' ? 'right center' : 'center',
    backgroundRepeat: 'no-repeat'
  }
}

const activeColorThemeName = computed(() => {
  const theme = themeStore.activeTheme
  return theme?.name ?? t('settingsEx.appearance.defaultSkinName')
})
</script>

<template>
  <div class="settings-panel appearance-panel">
    <!-- Hero -->
    <div class="appearance-hero">
      <div
        class="appearance-hero__preview"
        :style="getSkinPreviewStyle(themeStore.activeSkin)"
      >
        <div v-if="themeStore.activeSkin?.background.image" class="appearance-hero__overlay" />
        <div class="appearance-hero__glass">
          <h2 class="appearance-hero__title">{{ themeStore.activeSkin?.name ?? t('settingsEx.appearance.defaultSkinName') }}</h2>
          <p class="appearance-hero__desc">
            {{ themeStore.activeSkin?.type === 'preset' ? t('settingsEx.appearance.presetSkin') : t('settingsEx.appearance.customSkin') }} ·
            {{ t('settingsEx.appearance.modeLabel', { mode: themeStore.isDark ? t('settingsEx.appearance.modeDark') : t('settingsEx.appearance.modeLight') }) }} ·
            {{ t('settingsEx.appearance.colorScheme', { name: activeColorThemeName }) }}
          </p>
        </div>
      </div>
    </div>

    <!-- 皮肤包 -->
    <section class="settings-card">
      <div class="settings-card__header">
        <Sparkles :size="18" />
        <span class="settings-card__title">{{ t('settingsEx.appearance.skinSection') }}</span>
      </div>
      <div class="settings-card__body">
        <p class="settings-card__hint">{{ t('settingsEx.appearance.skinHint') }}</p>
        <ThemeSkinSelector
          :active-id="themeStore.activeSkinId"
          @apply="handleApplySkin"
          @edit="openSkinEditor"
          @create="openNewSkinEditor"
        />
      </div>
    </section>

    <!-- 色彩主题 -->
    <section class="settings-card">
      <div class="settings-card__header">
        <Palette :size="18" />
        <span class="settings-card__title">{{ t('settingsEx.appearance.colorSection') }}</span>
      </div>
      <div class="settings-card__body">
        <p class="settings-card__hint">{{ t('settingsEx.appearance.colorHint') }}</p>
        <div class="theme-preset-grid">
          <button
            v-for="id in PRESET_THEME_IDS"
            :key="id"
            :class="[
              'theme-preset-card',
              { 'theme-preset-card--active': themeStore.activeColorThemeId === id }
            ]"
            :aria-label="t('settingsEx.appearance.selectTheme', { name: presetThemeNames[id] })"
            @click="handleColorThemeSelect(id)"
          >
            <div class="theme-preset-card__preview">
              <span
                v-for="(color, idx) in presetThemeColors[id]"
                :key="idx"
                class="theme-preset-card__dot"
                :style="{ background: color }"
              />
            </div>
            <span class="theme-preset-card__name">{{ presetThemeNames[id] }}</span>
          </button>
        </div>
      </div>
    </section>

    <!-- 皮肤编辑器 -->
    <ThemeSkinEditor
      v-if="editorVisible"
      :skin="editingSkin"
      :mode="editorMode"
      @save="handleSaveSkin"
      @delete="handleDeleteSkin"
      @cancel="closeEditor"
    />
  </div>
</template>

<style scoped>
.appearance-panel {
  /* centering handled by settings-panel shared class */
}

/* ── 顶栏摘要 ── */
.appearance-hero {
  position: relative;
  background: var(--workspace-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-2xl);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.appearance-hero__preview {
  position: relative;
  width: 100%;
  height: 160px;
  background-size: cover;
  background-position: center;
  display: flex;
  align-items: flex-end;
  padding: var(--space-4);
}

.appearance-hero__overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, transparent 30%, rgba(0, 0, 0, 0.35) 100%);
}

.appearance-hero__glass {
  position: relative;
  z-index: 1;
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-lg);
  background: color-mix(in srgb, var(--surface) 80%, transparent);
  -webkit-backdrop-filter: blur(12px);
  backdrop-filter: blur(12px);
  border: 1px solid color-mix(in srgb, var(--surface) 60%, var(--border-light));
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
}

.appearance-hero__title {
  font-size: var(--text-xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  letter-spacing: -0.3px;
}

.appearance-hero__desc {
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin-top: 2px;
}
</style>

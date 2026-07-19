<script setup lang="ts">
import { ref, computed } from 'vue'
import { Sun, Moon, Monitor, Plus, Pencil, Trash2, Upload, Check, X, Palette, Image, Type, Sparkles } from 'lucide-vue-next'
import { useThemeStore } from '../../stores/theme'
import { MAX_CUSTOM_THEMES } from '../../stores/theme-types'
import type { ColorTheme } from '../../stores/theme-types'
import ThemePresetSelector from '../theme/ThemePresetSelector.vue'
import ThemeCustomEditor from '../theme/ThemeCustomEditor.vue'
import '../../styles/views/theme-settings.css'

const themeStore = useThemeStore()

// ─── Theme Mode ────────────────────────────────
type ThemeMode = 'light' | 'dark' | 'system'

const themeMode = computed<ThemeMode>(() => {
  // We only have isDark boolean; 'system' is not tracked separately yet
  return themeStore.isDark ? 'dark' : 'light'
})

function setMode(mode: ThemeMode) {
  if (mode === 'system') {
    // Follow system preference
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    themeStore.setTheme(prefersDark)
  } else {
    themeStore.setTheme(mode === 'dark')
  }
}

// ─── Custom Theme Editor ───────────────────────
const editorVisible = ref(false)
const editingTheme = ref<ColorTheme | null>(null)

function openNewEditor() {
  editingTheme.value = null
  editorVisible.value = true
}

function openEditEditor(theme: ColorTheme) {
  editingTheme.value = theme
  editorVisible.value = true
}

function closeEditor() {
  editorVisible.value = false
  editingTheme.value = null
}

function handleSaveTheme(theme: ColorTheme) {
  if (editingTheme.value) {
    // Update existing
    themeStore.updateCustomTheme(theme.id, {
      name: theme.name,
      light: theme.light,
      dark: theme.dark
    })
  } else {
    // Add new
    themeStore.addCustomTheme(theme)
  }
  themeStore.setColorTheme(theme.id)
  closeEditor()
}

function handleDeleteTheme(id: string) {
  themeStore.deleteCustomTheme(id)
}

// ─── Background ────────────────────────────────
const presetBackgrounds = [
  { id: 'none', label: '无', class: '' },
  { id: 'blue', label: '蓝', class: 'theme-bg-blue' },
  { id: 'purple', label: '紫', class: 'theme-bg-purple' },
  { id: 'red', label: '红', class: 'theme-bg-red' },
  { id: 'green', label: '绿', class: 'theme-bg-green' },
  { id: 'orange', label: '橙', class: 'theme-bg-orange' }
]

const activeBgId = computed(() => {
  if (!themeStore.background.image) return 'none'
  // Check if it matches a known gradient class
  for (const bg of presetBackgrounds) {
    if (bg.class && themeStore.background.image.includes(bg.class)) return bg.id
  }
  return 'custom'
})

function selectBackground(id: string) {
  if (id === 'none') {
    themeStore.setBackgroundImage(null)
  } else {
    // Use a CSS gradient as background image
    const gradients: Record<string, string> = {
      blue: 'linear-gradient(135deg, #147EBC 0%, #5BA4D4 50%, #0d5f8a 100%)',
      purple: 'linear-gradient(135deg, #7C3AED 0%, #A78BFA 50%, #5B21B6 100%)',
      red: 'linear-gradient(135deg, #C0392B 0%, #E74C3C 50%, #922B21 100%)',
      green: 'linear-gradient(135deg, #059669 0%, #34D399 50%, #047857 100%)',
      orange: 'linear-gradient(135deg, #EA580C 0%, #FB923C 50%, #C2410C 100%)'
    }
    themeStore.setBackgroundImage(gradients[id] ?? null)
  }
}

async function triggerFileUpload() {
  const imagePath = await window.api.dialog.selectBackgroundImage()
  if (imagePath) {
    themeStore.setBackgroundImage(imagePath)
  }
}

const canAddCustom = computed(() => themeStore.customThemes.length < MAX_CUSTOM_THEMES)
</script>

<template>
  <div class="main-agent-panel animate-slide-up">
    <!-- ── 主题模式 ─────────────────────────── -->
    <div class="main-agent-card">
      <div class="main-agent-card-header">
        <Sun :size="18" />
        <span class="main-agent-card-title">主题模式</span>
      </div>
      <div class="main-agent-card-body">
        <span class="platform-form-hint" style="margin-bottom: var(--space-3); margin-top: 0; display: block;">选择浅色或深色外观，或跟随系统自动切换</span>
        <div class="theme-mode-selector" role="radiogroup" aria-label="主题模式">
          <button
            :class="['mode-btn', { active: themeMode === 'light' }]"
            @click="setMode('light')"
            role="radio"
            :aria-checked="themeMode === 'light'"
            aria-label="浅色模式"
          >
            <Sun :size="16" />
            <span>浅色</span>
          </button>
          <button
            :class="['mode-btn', { active: themeMode === 'dark' }]"
            @click="setMode('dark')"
            role="radio"
            :aria-checked="themeMode === 'dark'"
            aria-label="深色模式"
          >
            <Moon :size="16" />
            <span>深色</span>
          </button>
          <button
            :class="['mode-btn', { active: themeMode === 'system' }]"
            @click="setMode('system')"
            role="radio"
            :aria-checked="themeMode === 'system'"
            aria-label="跟随系统"
          >
            <Monitor :size="16" />
            <span>跟随系统</span>
          </button>
        </div>
      </div>
    </div>

    <!-- ── 色彩主题 ─────────────────────────── -->
    <div class="main-agent-card">
      <div class="main-agent-card-header">
        <Palette :size="18" />
        <span class="main-agent-card-title">色彩主题</span>
      </div>
      <div class="main-agent-card-body">
        <span class="platform-form-hint" style="margin-bottom: var(--space-3); margin-top: 0; display: block;">选择界面的配色方案</span>

        <!-- 预设主题 -->
        <ThemePresetSelector v-model="themeStore.activeColorThemeId" />

        <!-- 自定义主题列表 -->
        <div v-if="themeStore.customThemes.length > 0" class="theme-custom-list">
          <div
            v-for="ct in themeStore.customThemes"
            :key="ct.id"
            :class="['theme-custom-card', { 'theme-custom-card--active': themeStore.activeColorThemeId === ct.id }]"
            @click="themeStore.setColorTheme(ct.id)"
          >
            <div class="theme-custom-card__colors">
              <span class="theme-custom-card__dot" :style="{ background: ct.light.primary }" />
              <span class="theme-custom-card__dot" :style="{ background: ct.light.secondary }" />
              <span class="theme-custom-card__dot" :style="{ background: ct.light.accent }" />
            </div>
            <span class="theme-custom-card__name">{{ ct.name }}</span>
            <div class="theme-custom-card__actions">
              <button class="theme-custom-card__btn" @click.stop="openEditEditor(ct)">
                <Pencil :size="14" />
              </button>
              <button class="theme-custom-card__btn theme-custom-card__btn--danger" @click.stop="handleDeleteTheme(ct.id)">
                <Trash2 :size="14" />
              </button>
            </div>
          </div>
        </div>

        <!-- 新建自定义主题 -->
        <button v-if="canAddCustom" class="theme-add-btn" @click="openNewEditor">
          <Plus :size="14" />
          <span>新建自定义主题</span>
        </button>
      </div>
    </div>

    <!-- ── 背景图片 ─────────────────────────── -->
    <div class="main-agent-card">
      <div class="main-agent-card-header">
        <Image :size="18" />
        <span class="main-agent-card-title">背景图片</span>
      </div>
      <div class="main-agent-card-body">
        <span class="platform-form-hint" style="margin-bottom: var(--space-3); margin-top: 0; display: block;">设置工作台背景</span>

        <!-- 预设背景选项 -->
        <div class="background-grid">
          <button
            v-for="bg in presetBackgrounds"
            :key="bg.id"
            :class="['background-option', { 'background-option--active': activeBgId === bg.id }]"
            @click="selectBackground(bg.id)"
          >
            <div v-if="bg.class" :class="['background-option__thumb', bg.class]" />
            <div v-else class="background-option__none">
              <X :size="16" />
            </div>
            <div v-if="activeBgId === bg.id" class="background-option__check">
              <Check :size="10" />
            </div>
          </button>
        </div>

        <!-- 自定义上传 -->
        <button class="background-upload-btn" @click="triggerFileUpload">
          <Upload :size="14" />
          <span>上传自定义背景</span>
        </button>

        <!-- 模糊度滑块 -->
        <div class="theme-slider-row">
          <span class="theme-slider-row__label">模糊度</span>
          <input
            type="range"
            class="theme-slider-row__input"
            min="0"
            max="20"
            :value="themeStore.background.blur"
            @input="themeStore.setBackgroundBlur(Number(($event.target as HTMLInputElement).value))"
          />
          <span class="theme-slider-row__value">{{ themeStore.background.blur }}px</span>
        </div>

        <!-- 透明度滑块 -->
        <div class="theme-slider-row">
          <span class="theme-slider-row__label">透明度</span>
          <input
            type="range"
            class="theme-slider-row__input"
            min="0"
            max="100"
            :value="themeStore.background.opacity"
            @input="themeStore.setBackgroundOpacity(Number(($event.target as HTMLInputElement).value))"
          />
          <span class="theme-slider-row__value">{{ themeStore.background.opacity }}%</span>
        </div>
      </div>
    </div>

    <!-- ── 字体大小（占位符） ──────────────── -->
    <div class="main-agent-card">
      <div class="main-agent-card-header">
        <Type :size="18" />
        <span class="main-agent-card-title">字体大小</span>
      </div>
      <div class="main-agent-card-body">
        <div class="theme-placeholder-row">
          <div>
            <div class="theme-placeholder-row__label">调整界面文字大小</div>
          </div>
          <span class="theme-placeholder-row__control">即将推出</span>
        </div>
      </div>
    </div>

    <!-- ── 动画效果（占位符） ──────────────── -->
    <div class="main-agent-card">
      <div class="main-agent-card-header">
        <Sparkles :size="18" />
        <span class="main-agent-card-title">动画效果</span>
      </div>
      <div class="main-agent-card-body">
        <div class="theme-placeholder-row">
          <div>
            <div class="theme-placeholder-row__label">开启或关闭界面动画</div>
          </div>
          <span class="theme-placeholder-row__control">即将推出</span>
        </div>
      </div>
    </div>

    <!-- ── 自定义主题编辑器弹窗 ────────────── -->
    <ThemeCustomEditor
      v-if="editorVisible"
      :theme="editingTheme"
      @save="handleSaveTheme"
      @cancel="closeEditor"
    />
  </div>
</template>

<style scoped>
/* ── 复用主智能体页面的卡片布局模式 ── */
.main-agent-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  padding: var(--space-6) var(--space-7);
  overflow-y: auto;
  flex: 1;
}

.main-agent-card {
  background: var(--workspace-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  overflow: hidden;
  box-shadow: var(--shadow-xs);
}

.main-agent-card-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--divider-soft);
  color: var(--lumi-primary);
}

.main-agent-card-title {
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--text-primary);
}

.main-agent-card-body {
  padding: var(--space-4);
}

.platform-form-hint {
  display: block;
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-top: var(--space-2);
  line-height: 1.4;
}

/* ── 主题模式选择器 — 复用 avatar-mode-toggle 模式 ── */
.theme-mode-selector {
  display: flex;
  gap: var(--space-1);
  margin-bottom: var(--space-3);
  background: var(--workspace-panel);
  border-radius: var(--radius-md);
  padding: 3px;
}

.mode-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: 7px var(--space-3);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-secondary);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.mode-btn.active {
  background: var(--surface);
  color: var(--text-primary);
  box-shadow: var(--shadow-xs);
}

/* ── 占位符行 ── */
.theme-placeholder-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  background: var(--workspace-panel);
  border-radius: var(--radius-md);
  border: 1px solid var(--workspace-border);
}

.theme-placeholder-row__label {
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-primary);
}

.theme-placeholder-row__control {
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-full);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-weight: 500;
}
</style>

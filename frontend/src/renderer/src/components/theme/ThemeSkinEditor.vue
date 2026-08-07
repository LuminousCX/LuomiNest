<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import {
  X,
  Upload,
  Trash2,
  Sun,
  Moon,
  Monitor,
  Check,
  Image,
  Palette,
  Sparkles,
  Radius,
  SlidersHorizontal,
  Plus,
  Pencil
} from 'lucide-vue-next'
import { useThemeStore } from '../../stores/theme'
import type { BackgroundFit, ColorTheme, Skin } from '../../stores/theme-types'
import { PRESET_THEME_IDS } from '../../stores/theme-types'
import { presetThemeNames, getThemePreviewColors } from '../../stores/theme-presets'
import { BACKGROUND_PRESETS, findPresetById } from '../../stores/background-presets'
import LumiButton from '../common/LumiButton.vue'
import ThemeCustomEditor from './ThemeCustomEditor.vue'
import { useToast } from '../../composables/useToast'

const props = defineProps<{
  skin: Skin | null
  mode: 'edit' | 'create'
}>()

const emit = defineEmits<{
  save: [skin: Skin]
  delete: [id: string]
  cancel: []
}>()

const themeStore = useThemeStore()
const toast = useToast()

const isEdit = computed(() => props.mode === 'edit')
const canDelete = computed(() => isEdit.value && props.skin?.type === 'custom')

function handleDelete() {
  const id = props.skin?.id
  if (!id) return
  emit('delete', id)
}

// ─── Form State ──────────────────────────────
const name = ref(props.skin?.name ?? '我的皮肤')
const colorThemeId = ref(props.skin?.colorThemeId ?? 'blue')
const mode = ref<'light' | 'dark' | 'system'>(props.skin?.mode ?? 'system')
const backgroundImage = ref<string | null>(props.skin?.background.image ?? null)
const backgroundBlur = ref(props.skin?.background.blur ?? 0)
const backgroundOpacity = ref(props.skin?.background.opacity ?? 100)
const backgroundFit = ref<BackgroundFit>(props.skin?.background.fit ?? 'cover')
const glassIntensity = ref(props.skin?.glassIntensity ?? 35)
const ambientIntensity = ref(props.skin?.ambientIntensity ?? 30)
const radiusTendency = ref(props.skin?.radiusTendency ?? 50)

const uploadingBackground = ref(false)

// ─── Custom Color Theme Editor ───────────────
const customEditorVisible = ref(false)
const editingCustomTheme = ref<ColorTheme | null>(null)
const isCreatingCustomColorTheme = ref(false)

function resetFormFromSkin(skin: Skin | null) {
  if (skin) {
    name.value = skin.name
    colorThemeId.value = skin.colorThemeId
    mode.value = skin.mode
    backgroundImage.value = skin.background.image
    backgroundBlur.value = skin.background.blur
    backgroundOpacity.value = skin.background.opacity
    backgroundFit.value = skin.background.fit ?? 'cover'
    glassIntensity.value = skin.glassIntensity
    ambientIntensity.value = skin.ambientIntensity
    radiusTendency.value = skin.radiusTendency ?? 50
  } else {
    name.value = '我的皮肤'
    colorThemeId.value = 'blue'
    mode.value = 'system'
    backgroundImage.value = null
    backgroundBlur.value = 0
    backgroundOpacity.value = 100
    backgroundFit.value = 'cover'
    glassIntensity.value = 35
    ambientIntensity.value = 30
    radiusTendency.value = 50
  }
  customEditorVisible.value = false
  editingCustomTheme.value = null
  isCreatingCustomColorTheme.value = false
}

watch(() => props.skin, (newSkin) => {
  resetFormFromSkin(newSkin)
}, { immediate: true })

// ─── Background Helpers ──────────────────────
const activeBgPresetId = computed(() => {
  if (!backgroundImage.value) return 'none'
  return BACKGROUND_PRESETS.find((p) => p.value === backgroundImage.value)?.id ?? 'custom'
})

function isGradient(value: string | null): boolean {
  return !!value && (/^linear-gradient\(/.test(value) || /^radial-gradient\(/.test(value) || /^conic-gradient\(/.test(value))
}

function selectBackgroundPreset(id: string) {
  if (id === 'none') {
    backgroundImage.value = null
  } else {
    backgroundImage.value = findPresetById(id)?.value ?? null
  }
}

async function triggerFileUpload() {
  try {
    uploadingBackground.value = true
    const result = await window.api.dialog.selectBackgroundImage()
    console.log('[ThemeSkinEditor] selectBackgroundImage result:', result)
    if (!result.success) {
      if (result.error !== '用户取消选择') {
        toast.error(`选择背景图片失败：${result.error}`)
      }
      return
    }
    if (typeof result.url !== 'string' || !result.url.startsWith('luominest-bg:')) {
      toast.error('背景图片地址格式异常')
      console.error('[ThemeSkinEditor] invalid background url:', result.url)
      return
    }
    backgroundImage.value = result.url
    if (result.warning) {
      toast.warning(result.warning)
    } else {
      toast.success(`背景图片已上传 (${result.width}×${result.height})`)
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    console.error('[ThemeSkinEditor] upload error:', err)
    toast.error(`选择背景图片失败：${message}`)
  } finally {
    uploadingBackground.value = false
  }
}

function removeCustomBackground() {
  backgroundImage.value = null
}

const previewBackgroundStyle = computed<Record<string, string>>(() => {
  const image = backgroundImage.value
  const theme = themeStore.activeTheme
  const primary = theme?.light.primary ?? '#147EBC'
  const secondary = theme?.light.secondary ?? '#5BA4D4'

  const base: Record<string, string> = {
    filter: `blur(${backgroundBlur.value}px)`,
    opacity: String(backgroundOpacity.value / 100)
  }

  if (!image) {
    base.background = `linear-gradient(135deg, color-mix(in srgb, ${primary} 12%, var(--bg)) 0%, color-mix(in srgb, ${secondary} 12%, var(--bg)) 100%)`
    return base
  }
  if (isGradient(image)) {
    base.background = image
    return base
  }
  base.backgroundImage = `url('${image}')`
  base.backgroundSize = backgroundFit.value === 'contain' ? 'contain' : 'cover'
  base.backgroundPosition = backgroundFit.value === 'right' ? 'right center' : 'center'
  base.backgroundRepeat = 'no-repeat'
  return base
})

const previewGlassStyle = computed<Record<string, string>>(() => {
  const minRadius = 8
  const maxRadius = 28
  const radius = minRadius + (radiusTendency.value / 100) * (maxRadius - minRadius)
  const blur = Math.max(0, glassIntensity.value * 0.3)
  return {
    borderRadius: `${radius}px`,
    backdropFilter: `blur(${blur}px) saturate(1.2)`,
    WebkitBackdropFilter: `blur(${blur}px) saturate(1.2)`
  }
})

function selectPresetColorTheme(id: string) {
  colorThemeId.value = id
  customEditorVisible.value = false
}

function openCreateCustomColorTheme() {
  isCreatingCustomColorTheme.value = true
  editingCustomTheme.value = null
  customEditorVisible.value = true
}

function openEditCustomColorTheme(theme: ColorTheme) {
  isCreatingCustomColorTheme.value = false
  editingCustomTheme.value = theme
  customEditorVisible.value = true
}

function handleCustomColorThemeSave(theme: ColorTheme) {
  if (isCreatingCustomColorTheme.value) {
    themeStore.addCustomTheme(theme)
    colorThemeId.value = theme.id
    toast.success('自定义颜色已创建')
  } else {
    themeStore.updateCustomTheme(theme.id, theme)
    toast.success('自定义颜色已更新')
  }
  customEditorVisible.value = false
  editingCustomTheme.value = null
  isCreatingCustomColorTheme.value = false
}

function handleCustomColorThemeCancel() {
  customEditorVisible.value = false
  editingCustomTheme.value = null
  isCreatingCustomColorTheme.value = false
}

// ─── Save ────────────────────────────────────
function handleSave() {
  if (!name.value.trim()) {
    toast.error('请输入皮肤名称')
    return
  }

  // 如果自定义颜色编辑器还开着，提示先处理
  if (customEditorVisible.value) {
    toast.info('请先保存或取消自定义颜色编辑')
    return
  }

  const id = props.skin?.id ?? `custom-skin-${Date.now()}`
  const skin: Skin = {
    id,
    name: name.value.trim(),
    type: 'custom',
    colorThemeId: colorThemeId.value,
    mode: mode.value,
    background: {
      image: backgroundImage.value,
      blur: backgroundBlur.value,
      opacity: backgroundOpacity.value,
      fit: backgroundFit.value
    },
    glassIntensity: glassIntensity.value,
    ambientIntensity: ambientIntensity.value,
    radiusTendency: radiusTendency.value
  }
  emit('save', skin)
}

function getCustomThemePreviewColors(theme: ColorTheme): string[] {
  return [theme.light.primary, theme.light.secondary, theme.light.accent]
}
</script>

<template>
  <div class="skin-editor-overlay" @click.self="emit('cancel')">
    <div class="skin-editor">
      <div class="skin-editor__header">
        <h3 class="skin-editor__title">
          {{ isEdit ? '编辑皮肤' : '新建皮肤' }}
        </h3>
        <button class="skin-editor__close" aria-label="关闭" @click="emit('cancel')">
          <X :size="18" />
        </button>
      </div>

      <div class="skin-editor__body custom-scrollbar">
        <!-- Preview -->
        <div class="editor-section">
          <label class="editor-section__label">
            <Sparkles :size="14" />
            实时预览
          </label>
          <div class="skin-editor__preview" :style="previewBackgroundStyle">
            <div class="preview-glass" :style="previewGlassStyle">
              <div class="preview-title">{{ name || '我的皮肤' }}</div>
              <div class="preview-subtitle">这是一段示例文字</div>
              <div class="preview-btn">主按钮</div>
            </div>
          </div>
        </div>

        <!-- Name -->
        <div class="editor-section">
          <label class="editor-section__label">
            <Palette :size="14" />
            皮肤名称
          </label>
          <input
            v-model="name"
            type="text"
            class="editor-input"
            placeholder="输入皮肤名称"
            maxlength="20"
          />
        </div>

        <!-- Color Theme -->
        <div class="editor-section">
          <label class="editor-section__label">色彩主题</label>

          <!-- 预设主题 -->
          <div class="color-theme-grid">
            <button
              v-for="id in PRESET_THEME_IDS"
              :key="id"
              :class="['color-theme-card', { active: colorThemeId === id }]"
              @click="selectPresetColorTheme(id)"
            >
              <div class="color-theme-card__dots">
                <span
                  v-for="(color, idx) in getThemePreviewColors(id)"
                  :key="idx"
                  class="color-theme-card__dot"
                  :style="{ background: color }"
                />
              </div>
              <span class="color-theme-card__name">{{ presetThemeNames[id] }}</span>
              <Check v-if="colorThemeId === id" :size="12" class="color-theme-card__check" />
            </button>
          </div>

          <!-- 自定义颜色主题 -->
          <div v-if="themeStore.customThemes.length > 0" class="custom-theme-list">
            <div class="custom-theme-list__label">自定义颜色</div>
            <div class="custom-theme-grid">
              <button
                v-for="theme in themeStore.customThemes"
                :key="theme.id"
                :class="['custom-theme-card', { active: colorThemeId === theme.id }]"
                @click="colorThemeId = theme.id"
              >
                <div class="custom-theme-card__dots">
                  <span
                    v-for="(color, idx) in getCustomThemePreviewColors(theme)"
                    :key="idx"
                    class="color-theme-card__dot"
                    :style="{ background: color }"
                  />
                </div>
                <span class="custom-theme-card__name">{{ theme.name }}</span>
                <span
                  class="custom-theme-card__edit"
                  role="button"
                  tabindex="0"
                  :aria-label="`编辑${theme.name}颜色主题`"
                  @click.stop="openEditCustomColorTheme(theme)"
                  @keydown.enter.stop="openEditCustomColorTheme(theme)"
                  @keydown.space.stop.prevent="openEditCustomColorTheme(theme)"
                >
                  <Pencil :size="12" />
                </span>
                <Check v-if="colorThemeId === theme.id" :size="12" class="color-theme-card__check" />
              </button>
            </div>
          </div>

          <!-- 新建自定义颜色 -->
          <LumiButton
            variant="outline"
            size="sm"
            class="create-color-btn"
            @click="openCreateCustomColorTheme"
          >
            <Plus :size="14" />
            <span>新建自定义颜色</span>
          </LumiButton>

          <!-- 自定义颜色编辑器 -->
          <ThemeCustomEditor
            v-if="customEditorVisible"
            :theme="editingCustomTheme"
            @save="handleCustomColorThemeSave"
            @cancel="handleCustomColorThemeCancel"
          />
        </div>

        <!-- Mode -->
        <div class="editor-section">
          <label class="editor-section__label">主题模式</label>
          <div class="mode-selector">
            <button
              v-for="m in [
                { id: 'light', label: '浅色', icon: Sun },
                { id: 'dark', label: '深色', icon: Moon },
                { id: 'system', label: '跟随系统', icon: Monitor }
              ]"
              :key="m.id"
              :class="['mode-btn', { active: mode === m.id }]"
              @click="mode = m.id as 'light' | 'dark' | 'system'"
            >
              <component :is="m.icon" :size="14" />
              <span>{{ m.label }}</span>
            </button>
          </div>
        </div>

        <!-- Background -->
        <div class="editor-section">
          <label class="editor-section__label">
            <Image :size="14" />
            背景
          </label>
          <div class="background-grid">
            <button
              v-for="bg in BACKGROUND_PRESETS"
              :key="bg.id"
              :class="['background-option', { active: activeBgPresetId === bg.id }]"
              :title="bg.name"
              @click="selectBackgroundPreset(bg.id)"
            >
              <div
                v-if="bg.id !== 'none'"
                class="background-option__thumb"
                :style="{
                  background: bg.type === 'pattern' ? (bg.thumb || bg.value) : bg.value,
                  backgroundSize: bg.type === 'pattern' ? '16px 16px' : 'cover'
                }"
              />
              <div v-else class="background-option__none">
                <span>无</span>
              </div>
              <span class="background-option__name">{{ bg.name }}</span>
            </button>

            <!-- 已上传的自定义背景 -->
            <div
              v-if="activeBgPresetId === 'custom' && backgroundImage"
              :key="'custom-bg'"
              class="background-option background-option--custom background-option--active"
              title="当前自定义背景"
            >
              <div
                class="background-option__thumb"
                :style="previewBackgroundStyle"
              />
              <span class="background-option__name">自定义</span>
            </div>
          </div>

          <div class="upload-row">
            <LumiButton
              variant="outline"
              size="sm"
              :loading="uploadingBackground"
              :disabled="uploadingBackground"
              @click="triggerFileUpload"
            >
              <Upload :size="14" />
              <span>上传自定义背景</span>
            </LumiButton>
            <LumiButton
              v-if="activeBgPresetId === 'custom'"
              variant="danger-ghost"
              size="sm"
              @click="removeCustomBackground"
            >
              <Trash2 :size="14" />
              <span>移除</span>
            </LumiButton>
          </div>
        </div>

        <!-- Background Fit -->
        <div class="editor-section">
          <label class="editor-section__label">背景适配</label>
          <div class="fit-selector">
            <button
              v-for="fit in [
                { id: 'cover', label: '覆盖' },
                { id: 'contain', label: '适应' },
                { id: 'center', label: '居中' },
                { id: 'right', label: '居右' }
              ]"
              :key="fit.id"
              :class="['fit-btn', { active: backgroundFit === fit.id }]"
              @click="backgroundFit = fit.id as BackgroundFit"
            >
              {{ fit.label }}
            </button>
          </div>
        </div>

        <!-- Sliders -->
        <div class="editor-section">
          <label class="editor-section__label">
            <SlidersHorizontal :size="14" />
            效果调节
          </label>

          <div class="slider-row">
            <span class="slider-row__label">模糊度</span>
            <input
              v-model.number="backgroundBlur"
              type="range"
              min="0"
              max="20"
              class="slider-row__input"
            />
            <span class="slider-row__value">{{ backgroundBlur }}px</span>
          </div>

          <div class="slider-row">
            <span class="slider-row__label">透明度</span>
            <input
              v-model.number="backgroundOpacity"
              type="range"
              min="0"
              max="100"
              class="slider-row__input"
            />
            <span class="slider-row__value">{{ backgroundOpacity }}%</span>
          </div>

          <div class="slider-row">
            <span class="slider-row__label">毛玻璃强度</span>
            <input
              v-model.number="glassIntensity"
              type="range"
              min="0"
              max="100"
              class="slider-row__input"
            />
            <span class="slider-row__value">{{ glassIntensity }}</span>
          </div>

          <div class="slider-row">
            <span class="slider-row__label">氛围光强度</span>
            <input
              v-model.number="ambientIntensity"
              type="range"
              min="0"
              max="100"
              class="slider-row__input"
            />
            <span class="slider-row__value">{{ ambientIntensity }}</span>
          </div>

          <div class="slider-row">
            <span class="slider-row__label">
              <Radius :size="12" />
              圆角倾向
            </span>
            <input
              v-model.number="radiusTendency"
              type="range"
              min="0"
              max="100"
              class="slider-row__input"
            />
            <span class="slider-row__value">{{ radiusTendency }}</span>
          </div>
        </div>
      </div>

      <div class="skin-editor__footer">
        <LumiButton
          v-if="canDelete"
          variant="danger-ghost"
          @click="handleDelete"
        >
          <Trash2 :size="16" />
          <span>删除</span>
        </LumiButton>
        <div class="skin-editor__footer-spacer" />
        <LumiButton variant="ghost" @click="emit('cancel')">取消</LumiButton>
        <LumiButton variant="primary" @click="handleSave">
          {{ isEdit ? '保存' : '创建' }}
        </LumiButton>
      </div>
    </div>
  </div>
</template>

<style scoped>
.skin-editor-overlay {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--modal-overlay);
  -webkit-backdrop-filter: blur(4px);
  backdrop-filter: blur(4px);
}

.skin-editor {
  display: flex;
  flex-direction: column;
  width: 760px;
  max-width: calc(100vw - var(--space-8));
  max-height: min(760px, calc(100vh - var(--space-8)));
  background: var(--surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-xl);
  box-shadow: var(--modal-shadow);
  overflow: hidden;
}

.skin-editor__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-light);
  flex-shrink: 0;
}

.skin-editor__title {
  font-size: var(--text-lg);
  font-weight: var(--font-bold);
  color: var(--text-primary);
}

.skin-editor__close {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.skin-editor__close:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.skin-editor__body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.skin-editor__footer {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5);
  border-top: 1px solid var(--border-light);
  flex-shrink: 0;
}

.skin-editor__footer-spacer {
  flex: 1;
}

.editor-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.editor-section__label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--text-secondary);
}

.editor-input {
  height: var(--input-height);
  padding: var(--input-padding);
  border: var(--input-border);
  border-radius: var(--input-radius);
  background: var(--input-bg);
  color: var(--text-primary);
  font-size: var(--text-base);
  outline: none;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.editor-input:focus {
  border-color: var(--input-focus-border);
  box-shadow: var(--input-focus-ring);
}

.skin-editor__preview {
  height: 140px;
  border-radius: var(--radius-xl);
  background-size: cover;
  background-position: center;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border: 1px solid var(--border-light);
  position: relative;
}

.skin-editor__preview::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 50% 50%, transparent 0%, rgba(0, 0, 0, 0.08) 100%);
  pointer-events: none;
}

.preview-glass {
  position: relative;
  z-index: 1;
  padding: var(--space-4) var(--space-6);
  border-radius: var(--radius-xl);
  background: color-mix(in srgb, var(--surface) 78%, transparent);
  -webkit-backdrop-filter: blur(16px) saturate(1.2);
  backdrop-filter: blur(16px) saturate(1.2);
  border: 1px solid color-mix(in srgb, var(--surface) 60%, var(--border-light));
  box-shadow:
    0 8px 24px rgba(0, 0, 0, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.25);
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  min-width: 180px;
}

.preview-title {
  font-size: var(--text-lg);
  font-weight: var(--font-bold);
  color: var(--text-primary);
}

.preview-subtitle {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.preview-btn {
  align-self: center;
  padding: var(--space-2) var(--space-5);
  border-radius: var(--radius-md);
  background: var(--lumi-brand);
  color: var(--text-inverse);
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  box-shadow: 0 4px 12px color-mix(in srgb, var(--lumi-brand) 30%, transparent);
}

.color-theme-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: var(--space-2);
}

.color-theme-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--surface);
  cursor: pointer;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
  position: relative;
}

.color-theme-card:hover {
  border-color: var(--lumi-brand-border);
}

.color-theme-card.active {
  border-color: var(--lumi-brand);
  box-shadow: 0 0 0 2px var(--lumi-brand-light);
}

.color-theme-card__dots {
  display: flex;
  gap: var(--space-1);
}

.color-theme-card__dot {
  width: 16px;
  height: 16px;
  border-radius: var(--radius-full);
  border: 1px solid rgba(0, 0, 0, 0.08);
}

.color-theme-card__name {
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

.color-theme-card__check {
  position: absolute;
  top: var(--space-1);
  right: var(--space-1);
  color: var(--lumi-brand);
}

.custom-theme-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.custom-theme-list__label {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.custom-theme-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: var(--space-2);
}

.custom-theme-card {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--surface);
  cursor: pointer;
  transition: all var(--transition-fast);
  position: relative;
}

.custom-theme-card:hover {
  border-color: var(--lumi-brand-border);
}

.custom-theme-card.active {
  border-color: var(--lumi-brand);
  box-shadow: 0 0 0 2px var(--lumi-brand-light);
}

.custom-theme-card__dots {
  display: flex;
  gap: 4px;
}

.custom-theme-card__name {
  flex: 1;
  font-size: var(--text-xs);
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.custom-theme-card__edit {
  width: 22px;
  height: 22px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity var(--transition-fast), background var(--transition-fast);
}

.custom-theme-card:hover .custom-theme-card__edit {
  opacity: 1;
}

.custom-theme-card__edit:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.create-color-btn {
  margin-top: var(--space-2);
  align-self: flex-start;
}

.mode-selector {
  display: flex;
  gap: var(--space-2);
}

.mode-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--surface);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: var(--text-sm);
  transition: all var(--transition-fast);
}

.mode-btn:hover {
  border-color: var(--lumi-brand-border);
  color: var(--text-primary);
}

.mode-btn.active {
  border-color: var(--lumi-brand);
  background: var(--lumi-brand-subtle);
  color: var(--lumi-brand);
}

.background-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(72px, 1fr));
  gap: var(--space-2);
}

.background-option {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--surface);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.background-option:hover {
  border-color: var(--lumi-brand-border);
}

.background-option.active {
  border-color: var(--lumi-brand);
  box-shadow: 0 0 0 2px var(--lumi-brand-light);
}

.background-option__thumb {
  width: 100%;
  aspect-ratio: 1;
  border-radius: var(--radius-sm);
  background-size: cover;
  background-position: center;
}

.background-option__none {
  width: 100%;
  aspect-ratio: 1;
  border-radius: var(--radius-sm);
  background: var(--surface-hover);
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-xs);
}

.background-option__name {
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
  line-height: 1.2;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.background-option:hover .background-option__name,
.background-option--active .background-option__name {
  color: var(--lumi-brand);
}

.upload-row {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.fit-selector {
  display: flex;
  gap: var(--space-2);
}

.fit-btn {
  flex: 1;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--surface);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: var(--text-sm);
  transition: all var(--transition-fast);
}

.fit-btn:hover {
  border-color: var(--lumi-brand-border);
}

.fit-btn.active {
  border-color: var(--lumi-brand);
  background: var(--lumi-brand-subtle);
  color: var(--lumi-brand);
}

.slider-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) 0;
}

.slider-row__label {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  width: 90px;
  flex-shrink: 0;
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.slider-row__input {
  flex: 1;
  accent-color: var(--lumi-brand);
}

.slider-row__value {
  min-width: 48px;
  padding: 2px var(--space-2);
  text-align: center;
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  color: var(--lumi-brand);
  background: var(--lumi-brand-subtle);
  border-radius: var(--radius-sm);
  font-variant-numeric: tabular-nums;
}
</style>

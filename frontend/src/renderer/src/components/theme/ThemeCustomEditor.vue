<script setup lang="ts">
import { ref, computed } from 'vue'
import type { ColorTheme, ThemeColorSet } from '../../stores/theme-types'
import ColorPickerInput from './ColorPickerInput.vue'

const props = defineProps<{
  theme: ColorTheme | null
}>()

const emit = defineEmits<{
  save: [theme: ColorTheme]
  cancel: []
}>()

// Local state for editing
const name = ref(props.theme?.name ?? '')
const primary = ref(props.theme?.light.primary ?? '#147EBC')
const secondary = ref(props.theme?.light.secondary ?? '#5BA4D4')
const accent = ref(props.theme?.light.accent ?? '#f43f5e')

const isEdit = computed(() => props.theme !== null)

/** Darken a hex color by a percentage (0-1) */
function darken(hex: string, amount: number): string {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  const clamp = (v: number) => Math.max(0, Math.min(255, Math.round(v * (1 - amount))))
  return `#${clamp(r).toString(16).padStart(2, '0')}${clamp(g).toString(16).padStart(2, '0')}${clamp(b).toString(16).padStart(2, '0')}`
}

/** Lighten a hex color by mixing toward white */
function lighten(hex: string, amount: number): string {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  const clamp = (v: number) => Math.max(0, Math.min(255, Math.round(v + (255 - v) * amount)))
  return `#${clamp(r).toString(16).padStart(2, '0')}${clamp(g).toString(16).padStart(2, '0')}${clamp(b).toString(16).padStart(2, '0')}`
}

/** Build a full ThemeColorSet from the 3 base colors */
function buildColorSet(p: string, s: string, a: string): ThemeColorSet {
  return {
    primary: p,
    secondary: s,
    accent: a,
    primaryHover: darken(p, 0.12),
    primaryLight: `rgba(${parseInt(p.slice(1, 3), 16)}, ${parseInt(p.slice(3, 5), 16)}, ${parseInt(p.slice(5, 7), 16)}, 0.1)`,
    secondaryHover: darken(s, 0.1),
    secondaryLight: `rgba(${parseInt(s.slice(1, 3), 16)}, ${parseInt(s.slice(3, 5), 16)}, ${parseInt(s.slice(5, 7), 16)}, 0.1)`,
    accentHover: darken(a, 0.12),
    accentLight: `rgba(${parseInt(a.slice(1, 3), 16)}, ${parseInt(a.slice(3, 5), 16)}, ${parseInt(a.slice(5, 7), 16)}, 0.1)`,
    shadowBrand: `rgba(${parseInt(p.slice(1, 3), 16)}, ${parseInt(p.slice(3, 5), 16)}, ${parseInt(p.slice(5, 7), 16)}, 0.15)`,
    gradientBrand: `linear-gradient(135deg, ${p}, ${s})`
  }
}

/** Build dark variant: lighten base colors for dark bg */
function buildDarkColorSet(p: string, s: string, a: string): ThemeColorSet {
  const lp = lighten(p, 0.25)
  const ls = lighten(s, 0.25)
  const la = lighten(a, 0.25)
  return {
    primary: lp,
    secondary: ls,
    accent: la,
    primaryHover: lighten(lp, 0.12),
    primaryLight: `rgba(${parseInt(lp.slice(1, 3), 16)}, ${parseInt(lp.slice(3, 5), 16)}, ${parseInt(lp.slice(5, 7), 16)}, 0.15)`,
    secondaryHover: lighten(ls, 0.1),
    secondaryLight: `rgba(${parseInt(ls.slice(1, 3), 16)}, ${parseInt(ls.slice(3, 5), 16)}, ${parseInt(ls.slice(5, 7), 16)}, 0.12)`,
    accentHover: lighten(la, 0.12),
    accentLight: `rgba(${parseInt(la.slice(1, 3), 16)}, ${parseInt(la.slice(3, 5), 16)}, ${parseInt(la.slice(5, 7), 16)}, 0.15)`,
    shadowBrand: `rgba(${parseInt(lp.slice(1, 3), 16)}, ${parseInt(lp.slice(3, 5), 16)}, ${parseInt(lp.slice(5, 7), 16)}, 0.2)`,
    gradientBrand: `linear-gradient(135deg, ${lp}, ${ls})`
  }
}

function handleSave() {
  if (!name.value.trim()) return
  const id = props.theme?.id ?? `custom-${Date.now()}`
  const theme: ColorTheme = {
    id,
    name: name.value.trim(),
    type: 'custom',
    light: buildColorSet(primary.value, secondary.value, accent.value),
    dark: buildDarkColorSet(primary.value, secondary.value, accent.value)
  }
  emit('save', theme)
}
</script>

<template>
  <div class="theme-editor-overlay" @click.self="emit('cancel')">
    <div class="theme-editor">
      <h3 class="theme-editor__title">{{ isEdit ? '编辑自定义主题' : '新建自定义主题' }}</h3>

      <!-- Name -->
      <div class="theme-editor__field">
        <label class="theme-editor__field-label">主题名称</label>
        <input
          v-model="name"
          type="text"
          class="theme-editor__name-input"
          placeholder="输入主题名称"
          maxlength="20"
        />
      </div>

      <!-- Colors -->
      <div class="theme-editor__field">
        <label class="theme-editor__field-label">三色配色</label>
        <div class="theme-editor__colors">
          <ColorPickerInput v-model="primary" label="主色" />
          <ColorPickerInput v-model="secondary" label="辅色" />
          <ColorPickerInput v-model="accent" label="强调色" />
        </div>
      </div>

      <!-- Preview -->
      <div class="theme-editor__field">
        <label class="theme-editor__field-label">实时预览</label>
        <div class="theme-editor__preview">
          <span class="theme-editor__preview-title">UI 元素预览</span>
          <div class="theme-editor__preview-row">
            <button
              class="theme-editor__preview-btn"
              :style="{ background: primary }"
            >主色按钮</button>
            <button
              class="theme-editor__preview-btn"
              :style="{ background: secondary }"
            >辅色按钮</button>
            <button
              class="theme-editor__preview-btn"
              :style="{ background: accent }"
            >强调按钮</button>
          </div>
          <div
            class="theme-editor__preview-card"
            :style="{ borderColor: secondary }"
          >
            这是一个卡片元素，边框使用辅色。
          </div>
          <span
            class="theme-editor__preview-link"
            :style="{ color: accent }"
          >这是一个强调色链接</span>
        </div>
      </div>

      <!-- Actions -->
      <div class="theme-editor__actions">
        <button class="theme-editor__btn" @click="emit('cancel')">取消</button>
        <button class="theme-editor__btn theme-editor__btn--primary" @click="handleSave">
          {{ isEdit ? '保存' : '创建' }}
        </button>
      </div>
    </div>
  </div>
</template>

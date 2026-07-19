<script setup lang="ts">
import { useThemeStore } from '../../stores/theme'
import { PRESET_THEME_IDS } from '../../stores/theme-types'
import { presetThemeNames, presetThemeColors } from '../../stores/theme-presets'

defineProps<{
  modelValue: string
}>()

const themeStore = useThemeStore()

function selectTheme(id: string) {
  themeStore.setColorTheme(id)
}
</script>

<template>
  <div class="theme-preset-grid">
    <button
      v-for="id in PRESET_THEME_IDS"
      :key="id"
      :class="['theme-preset-card', { 'theme-preset-card--active': modelValue === id }]"
      :aria-label="`选择${presetThemeNames[id]}主题`"
      @click="selectTheme(id)"
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
</template>

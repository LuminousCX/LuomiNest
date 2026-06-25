<script setup lang="ts">
import SettingsGenericSection from './SettingsGenericSection.vue'
import type { SectionItem } from './types'

const items: SectionItem[] = [
  { label: '主题模式', desc: '浅色 / 深色 / 跟随系统', type: 'select' },
  { label: '主色调', desc: '选择界面主色调', type: 'color' },
  { label: '字体大小', desc: '调整界面文字大小', type: 'slider' },
  { label: '动画效果', desc: '开启或关闭界面动画', type: 'toggle' }
]
</script>

<template>
  <SettingsGenericSection section="appearance" :items="items" />
</template>

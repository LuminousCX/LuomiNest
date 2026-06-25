<script setup lang="ts">
import SettingsGenericSection from './SettingsGenericSection.vue'
import type { SectionItem } from './types'

const items: SectionItem[] = [
  { label: '桌面通知', desc: '接收桌面推送通知', type: 'toggle' },
  { label: '声音提醒', desc: '收到消息时播放提示音', type: 'toggle' },
  { label: '免打扰模式', desc: '设定免打扰时段', type: 'time' },
  { label: '消息预览', desc: '在通知中显示消息内容', type: 'toggle' }
]
</script>

<template>
  <SettingsGenericSection section="notifications" :items="items" />
</template>

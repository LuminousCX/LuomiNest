<script setup lang="ts">
import { computed } from 'vue'
import SettingsGenericSection from './SettingsGenericSection.vue'
import { useSectionSettings } from '../../composables/useSectionSettings'
import type { SectionItem, SectionValue } from './types'

const state = useSectionSettings('notifications', {
  desktopNotify: true,
  soundAlert: true,
  dndRange: '22:00-08:00',
  messagePreview: true
})

const items = computed<SectionItem[]>(() => [
  { key: 'desktopNotify', label: '桌面通知', desc: '接收桌面推送通知', type: 'toggle', value: state.desktopNotify },
  { key: 'soundAlert', label: '声音提醒', desc: '收到消息时播放提示音', type: 'toggle', value: state.soundAlert },
  { key: 'dndRange', label: '免打扰模式', desc: '设定免打扰时段，期间通知静音', type: 'time', value: state.dndRange },
  { key: 'messagePreview', label: '消息预览', desc: '在通知中显示消息内容', type: 'toggle', value: state.messagePreview }
])

function handleChange(key: string, value: SectionValue) {
  const target = state as Record<string, SectionValue>
  target[key] = value
}
</script>

<template>
  <SettingsGenericSection section="notifications" :items="items" @change="handleChange" />
</template>

<script setup lang="ts">
import SettingsGenericSection from './SettingsGenericSection.vue'
import type { SectionItem } from './types'

const items: SectionItem[] = [
  { label: '端到端加密', desc: '所有对话数据加密存储', type: 'toggle' },
  { label: '本地存储', desc: '数据仅保存在本地设备', type: 'toggle' },
  { label: '自动清除', desc: '定期清除过期对话记录', type: 'select' },
  { label: '访问控制', desc: '设置应用启动密码', type: 'password' }
]
</script>

<template>
  <SettingsGenericSection section="privacy" :items="items" />
</template>

<script setup lang="ts">
import SettingsGenericSection from './SettingsGenericSection.vue'
import type { SectionItem } from './types'

const items: SectionItem[] = [
  { label: '已安装工具', desc: '查看和管理已安装的 MCP 工具', type: 'list' },
  { label: '添加工具', desc: '从市场或自定义安装工具', type: 'button' },
  { label: '工具权限', desc: '管理工具的访问权限', type: 'select' },
  { label: '运行日志', desc: '查看工具运行日志', type: 'button' }
]
</script>

<template>
  <SettingsGenericSection section="mcp" :items="items" />
</template>

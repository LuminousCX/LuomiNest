<script setup lang="ts">
import SettingsGenericSection from './SettingsGenericSection.vue'
import { useToast } from '../../composables/useToast'
import type { SectionItem } from './types'

const toast = useToast()

const items: SectionItem[] = [
  { key: 'installed', label: '已安装工具', desc: '查看和管理已安装的 MCP 工具', type: 'list', actionText: '查看' },
  { key: 'add', label: '添加工具', desc: '从市场或自定义安装工具', type: 'button', actionText: '添加' },
  { key: 'permissions', label: '工具权限', desc: '管理工具的访问权限', type: 'action', actionText: '配置' },
  { key: 'logs', label: '运行日志', desc: '查看工具运行日志', type: 'button', actionText: '查看' }
]

// MCP 工具管理功能开发中：动作行统一提示入口未开放
function handleSelect() {
  toast.info('MCP 工具管理功能正在开发中，敬请期待')
}
</script>

<template>
  <SettingsGenericSection section="mcp" :items="items" @select="handleSelect" />
</template>

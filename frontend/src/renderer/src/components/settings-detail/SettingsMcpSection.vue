<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import SettingsGenericSection from './SettingsGenericSection.vue'
import { useToast } from '../../composables/useToast'
import type { SectionItem } from './types'

const { t } = useI18n()
const toast = useToast()

// computed：保证切换语言时条目文案随之更新
const items = computed<SectionItem[]>(() => [
  { key: 'installed', label: t('settingsEx.mcp.installed.label'), desc: t('settingsEx.mcp.installed.desc'), type: 'list', actionText: t('settingsEx.mcp.installed.action') },
  { key: 'add', label: t('settingsEx.mcp.add.label'), desc: t('settingsEx.mcp.add.desc'), type: 'button', actionText: t('settingsEx.mcp.add.action') },
  { key: 'permissions', label: t('settingsEx.mcp.permissions.label'), desc: t('settingsEx.mcp.permissions.desc'), type: 'action', actionText: t('settingsEx.mcp.permissions.action') },
  { key: 'logs', label: t('settingsEx.mcp.logs.label'), desc: t('settingsEx.mcp.logs.desc'), type: 'button', actionText: t('settingsEx.mcp.logs.action') }
])

// MCP 工具管理功能开发中：动作行统一提示入口未开放
function handleSelect() {
  toast.info(t('settingsEx.mcp.devToast'))
}
</script>

<template>
  <SettingsGenericSection section="mcp" :items="items" @select="handleSelect" />
</template>

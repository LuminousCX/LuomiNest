<script setup lang="ts">
import { computed } from 'vue'
import SettingsGenericSection from './SettingsGenericSection.vue'
import SettingsCommandSecuritySection from './SettingsCommandSecuritySection.vue'
import { useSectionSettings } from '../../composables/useSectionSettings'
import { useToast } from '../../composables/useToast'
import type { SectionItem, SectionValue } from './types'

const toast = useToast()

// accessPassword 为敏感信息：仅会话内保留在内存，不进入持久化通道
const state = useSectionSettings(
  'privacy',
  {
    e2eEncryption: true,
    localStorageOnly: true,
    autoClean: 'never',
    accessPassword: ''
  },
  ['accessPassword']
)

const items = computed<SectionItem[]>(() => [
  { key: 'e2eEncryption', label: '端到端加密', desc: '所有对话数据加密存储', type: 'toggle', value: state.e2eEncryption },
  { key: 'localStorageOnly', label: '本地存储', desc: '数据仅保存在本地设备', type: 'toggle', value: state.localStorageOnly },
  {
    key: 'autoClean',
    label: '自动清除',
    desc: '定期清除过期对话记录',
    type: 'select',
    value: state.autoClean,
    options: [
      { label: '从不', value: 'never' },
      { label: '7 天后', value: '7d' },
      { label: '30 天后', value: '30d' },
      { label: '90 天后', value: '90d' }
    ]
  },
  {
    key: 'accessPassword',
    label: '访问控制',
    desc: '设置应用启动密码',
    type: 'password',
    value: state.accessPassword,
    placeholder: '输入启动密码'
  }
])

function handleChange(key: string, value: SectionValue) {
  const target = state as Record<string, SectionValue>
  target[key] = value
  if (key === 'accessPassword' && value) {
    toast.info('访问控制功能开发中，密码仅在当前会话保留，暂不保存')
  }
}
</script>

<template>
  <div class="settings-panel animate-slide-up settings-security-wrap">
    <SettingsGenericSection section="privacy" :items="items" class="settings-panel--nested" @change="handleChange" />
    <SettingsCommandSecuritySection class="settings-panel--nested" />
  </div>
</template>

<style scoped>
.settings-security-wrap {
  gap: var(--space-4);
}
</style>

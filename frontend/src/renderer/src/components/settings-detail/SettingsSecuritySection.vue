<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import SettingsGenericSection from './SettingsGenericSection.vue'
import SettingsCommandSecuritySection from './SettingsCommandSecuritySection.vue'
import { useSectionSettings } from '../../composables/useSectionSettings'
import { useToast } from '../../composables/useToast'
import type { SectionItem, SectionValue } from './types'

const toast = useToast()
const { t } = useI18n()

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
  { key: 'e2eEncryption', label: t('settingsEx.security.e2eEncryption'), desc: t('settingsEx.security.e2eDesc'), type: 'toggle', value: state.e2eEncryption },
  { key: 'localStorageOnly', label: t('settingsEx.security.localStorageOnly'), desc: t('settingsEx.security.localStorageDesc'), type: 'toggle', value: state.localStorageOnly },
  {
    key: 'autoClean',
    label: t('settingsEx.security.autoClean'),
    desc: t('settingsEx.security.autoCleanDesc'),
    type: 'select',
    value: state.autoClean,
    options: [
      { label: t('settingsEx.security.never'), value: 'never' },
      { label: t('settingsEx.security.after7d'), value: '7d' },
      { label: t('settingsEx.security.after30d'), value: '30d' },
      { label: t('settingsEx.security.after90d'), value: '90d' }
    ]
  },
  {
    key: 'accessPassword',
    label: t('settingsEx.security.accessControl'),
    desc: t('settingsEx.security.accessControlDesc'),
    type: 'password',
    value: state.accessPassword,
    placeholder: t('settingsEx.security.accessPasswordPlaceholder')
  }
])

function handleChange(key: string, value: SectionValue) {
  const target = state as Record<string, SectionValue>
  target[key] = value
  if (key === 'accessPassword' && value) {
    toast.info(t('settingsEx.security.accessPasswordDevToast'))
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

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import SettingsGenericSection from './SettingsGenericSection.vue'
import { useSectionSettings } from '../../composables/useSectionSettings'
import type { SectionItem, SectionValue } from './types'

/**
 * 通知设置子页面（纯前端 demo）：
 * - 控件仅为本地占位交互，状态经 useSectionSettings 只持久化在
 *   localStorage（luominest-settings:notifications），不调用任何后端接口；
 * - 布局复用 SettingsGenericSection 的既有行样式（toggle / 双时间选择）。
 *
 * TODO(云端站内信): 后期对接云端 Java 站内信服务时，将 desktopNotify /
 * soundAlert / dndRange / messagePreview 同步为云端用户偏好，
 * 并在 desktopNotify（总开关）关闭时同步抑制站内信推送。
 */
const state = useSectionSettings('notifications', {
  desktopNotify: true,
  soundAlert: true,
  dndRange: '22:00-08:00',
  messagePreview: true
})

const { t } = useI18n()

const items = computed<SectionItem[]>(() => [
  {
    key: 'desktopNotify',
    label: t('settingsEx.notifications.desktopNotify'),
    desc: t('settingsEx.notifications.desktopNotifyDesc'),
    type: 'toggle',
    value: state.desktopNotify
  },
  {
    key: 'dndRange',
    label: t('settingsEx.notifications.dndRange'),
    desc: t('settingsEx.notifications.dndRangeDesc'),
    type: 'time',
    value: state.dndRange
  },
  {
    key: 'soundAlert',
    label: t('settingsEx.notifications.soundAlert'),
    desc: t('settingsEx.notifications.soundAlertDesc'),
    type: 'toggle',
    value: state.soundAlert
  },
  {
    key: 'messagePreview',
    label: t('settingsEx.notifications.messagePreview'),
    desc: t('settingsEx.notifications.messagePreviewDesc'),
    type: 'toggle',
    value: state.messagePreview
  }
])

function handleChange(key: string, value: SectionValue) {
  const target = state as Record<string, SectionValue>
  target[key] = value
}
</script>

<template>
  <SettingsGenericSection section="notifications" :items="items" @change="handleChange" />
</template>

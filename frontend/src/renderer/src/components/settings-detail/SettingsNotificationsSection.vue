<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import SettingsGenericSection from './SettingsGenericSection.vue'
import type { SectionItem, SectionValue } from './types'
import type { NotificationPrefs } from '@shared/ipc-types'

/**
 * 通知设置子页面（2026-10-12 云端站内信对接）：
 * - 持久化在 main 进程 configStore（config:getNotifications / setNotifications），
 *   并经从站偏好云同步（prefs-sync 的 notifications 键）多端一致，替代原 localStorage demo；
 * - 远端应用（他端修改/换机登录）经 app:remote-prefs-applied 推送即时回显；
 * - desktopNotify 为总开关：关闭时云端站内信不触发桌面通知（提醒链路读取此偏好）。
 */
const { t } = useI18n()

const DEFAULT_PREFS: NotificationPrefs = {
  desktopNotify: true,
  soundAlert: true,
  dndRange: '22:00-08:00',
  messagePreview: true,
}

const prefs = ref<NotificationPrefs>({ ...DEFAULT_PREFS })
let unsubscribe: (() => void) | null = null

onMounted(async () => {
  try {
    const stored = await window.api.config.getNotifications()
    if (stored) prefs.value = { ...DEFAULT_PREFS, ...stored }
  } catch {
    // main 不可达时保持默认值（界面仍可交互）
  }
  unsubscribe = window.api.app.onRemotePrefsApplied((data) => {
    if (data.notifications) prefs.value = { ...prefs.value, ...data.notifications }
  })
})

onUnmounted(() => {
  unsubscribe?.()
  unsubscribe = null
})

const items = computed<SectionItem[]>(() => [
  {
    key: 'desktopNotify',
    label: t('settingsEx.notifications.desktopNotify'),
    desc: t('settingsEx.notifications.desktopNotifyDesc'),
    type: 'toggle',
    value: prefs.value.desktopNotify
  },
  {
    key: 'dndRange',
    label: t('settingsEx.notifications.dndRange'),
    desc: t('settingsEx.notifications.dndRangeDesc'),
    type: 'time',
    value: prefs.value.dndRange
  },
  {
    key: 'soundAlert',
    label: t('settingsEx.notifications.soundAlert'),
    desc: t('settingsEx.notifications.soundAlertDesc'),
    type: 'toggle',
    value: prefs.value.soundAlert
  },
  {
    key: 'messagePreview',
    label: t('settingsEx.notifications.messagePreview'),
    desc: t('settingsEx.notifications.messagePreviewDesc'),
    type: 'toggle',
    value: prefs.value.messagePreview
  }
])

function handleChange(key: string, value: SectionValue) {
  if (key === 'dndRange') {
    if (typeof value !== 'string') return
    prefs.value = { ...prefs.value, dndRange: value }
  } else if (typeof value === 'boolean') {
    prefs.value = { ...prefs.value, [key]: value }
  } else {
    return
  }
  // 增量写入 main（configStore 合并持久化 + 节流云同步上传）
  void window.api.config.setNotifications({ [key]: value } as Partial<NotificationPrefs>)
}
</script>

<template>
  <SettingsGenericSection section="notifications" :items="items" @change="handleChange" />
</template>

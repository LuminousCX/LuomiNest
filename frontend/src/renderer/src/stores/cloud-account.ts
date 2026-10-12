/**
 * 云端通行证账号共享状态（2026-10-12 生态对接：左上角头像/铃铛/设置页共用）。
 *
 * 登录态由 main 进程状态机持有：renderer 首次 start() 时拉一次 status()，
 * 之后通过 onStatus 推送保持同步（登录/登出/授权码变化都会推）。
 * account 即生态站（luminouschenxi）账号摘要，avatar 为生态站头像
 * （主站 /userinfo 权威来源），未登录或拉取失败时为空，UI 回退占位图标。
 *
 * 站内信（主站 /connect/notifications）：登录态下每 60s 轮询一次最近列表与
 * 未读数，供左上角铃铛展示；未登录轮询静默停摆，登录推送触发立即补拉。
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { CloudAuthStatus, CloudNotificationItem } from '@shared/ipc-types'

/** 站内信轮询间隔（铃铛未读对实时性要求不高，1 分钟足够） */
const NOTIFICATIONS_POLL_INTERVAL_MS = 60_000

export const useCloudAccountStore = defineStore('cloudAccount', () => {
  const status = ref<CloudAuthStatus>({ state: 'loggedOut' })
  const loaded = ref(false)

  /** authorized 时的账号摘要；未登录/账户信息拉取失败时为 undefined */
  const account = computed(() =>
    status.value.state === 'authorized' ? (status.value.account ?? undefined) : undefined
  )
  /** 生态站头像 URL（可能为空串，调用方回退占位图标） */
  const avatar = computed(() => account.value?.avatar || '')
  const nickname = computed(() => account.value?.nickname || '')

  // ── 站内信（主站 /connect/notifications）──
  const notificationsLoading = ref(false)
  const notifications = ref<CloudNotificationItem[]>([])
  const unreadCount = ref(0)

  const applyStatus = (next: CloudAuthStatus) => {
    const wasAuthorized = status.value.state === 'authorized'
    status.value = next
    loaded.value = true
    // 登录态变化立即对齐站内信轮询（登录补拉一次，登出清空并停摆）
    if (next.state === 'authorized' && !wasAuthorized) void refreshNotifications()
    if (next.state !== 'authorized') {
      notifications.value = []
      unreadCount.value = 0
    }
  }

  const refreshNotifications = async (): Promise<void> => {
    if (status.value.state !== 'authorized' || notificationsLoading.value) return
    notificationsLoading.value = true
    try {
      const result = await window.api.cloud.notifications()
      if (result.ok) {
        notifications.value = result.items ?? []
        unreadCount.value = result.unread ?? 0
      }
      // 失败静默：保留上次数据，等下个轮询周期
    } catch {
      // main 不可达：静默
    } finally {
      notificationsLoading.value = false
    }
  }

  const markNotificationRead = async (payload: { id?: number; all?: boolean }): Promise<void> => {
    try {
      const { updated } = await window.api.cloud.notificationsRead(payload)
      if (updated > 0) {
        if (payload.all) {
          notifications.value = notifications.value.map((n) => ({ ...n, isRead: true }))
          unreadCount.value = 0
        } else if (payload.id !== undefined) {
          const target = notifications.value.find((n) => n.id === payload.id)
          if (target && !target.isRead) {
            target.isRead = true
            unreadCount.value = Math.max(0, unreadCount.value - 1)
          }
        }
      }
    } catch {
      // 失败静默：下次轮询以服务端为准
    }
  }

  let unsubscribe: (() => void) | null = null
  let pollTimer: ReturnType<typeof setInterval> | null = null
  let started = false

  const refresh = async () => {
    try {
      applyStatus(await window.api.cloud.status())
    } catch {
      loaded.value = true
    }
  }

  /** 订阅 main 推送并拉取一次当前状态；幂等，App 内多个使用方共享一次订阅 */
  const start = () => {
    if (started) return
    started = true
    try {
      unsubscribe = window.api.cloud.onStatus(applyStatus)
    } catch {
      // main 不可达时仅保留主动拉取路径
    }
    void refresh()
    pollTimer = setInterval(() => void refreshNotifications(), NOTIFICATIONS_POLL_INTERVAL_MS)
  }

  const stop = () => {
    unsubscribe?.()
    unsubscribe = null
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
    started = false
  }

  return {
    status,
    loaded,
    account,
    avatar,
    nickname,
    notifications,
    notificationsLoading,
    unreadCount,
    refresh,
    refreshNotifications,
    markNotificationRead,
    start,
    stop,
  }
})

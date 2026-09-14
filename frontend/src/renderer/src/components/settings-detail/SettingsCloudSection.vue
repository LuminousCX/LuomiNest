<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Cloud,
  LogIn,
  LogOut,
  ExternalLink,
  Loader2,
  User,
  Coins,
  Gauge,
  KeyRound,
  AlertCircle,
  ShieldCheck,
  Cable,
  Cpu,
  X,
  Copy,
  Check
} from 'lucide-vue-next'
import LumiButton from '../common/LumiButton.vue'
import type {
  CloudAuthStatus,
  CloudRoutingMode,
  CloudModelInfo,
  CloudBackendStatus
} from '@shared/ipc-types'

const { t, te } = useI18n()

// ── 登录状态（main 进程状态机推送，renderer 只见摘要）──
const loaded = ref(false)
const status = ref<CloudAuthStatus>({ state: 'loggedOut' })
const routingMode = ref<CloudRoutingMode>('off')
const loginLoading = ref(false)
const modeToggling = ref(false)

// ── 云端可用模型 / 本地后端注入状态（拉取失败均静默降级，不阻塞页面）──
const cloudModels = ref<CloudModelInfo[]>([])
const backendStatus = ref<CloudBackendStatus | null>(null)

let unsubscribe: (() => void) | null = null

const loadCloudModels = async () => {
  if (cloudModels.value.length > 0) return
  try {
    cloudModels.value = await window.api.cloud.fetchModels()
  } catch {
    cloudModels.value = []
  }
}

const loadBackendStatus = async () => {
  try {
    backendStatus.value = await window.api.cloud.getBackendStatus()
  } catch {
    backendStatus.value = null
  }
}

const applyStatus = (next: CloudAuthStatus) => {
  status.value = next
  loaded.value = true
  // authorized 态按需加载模型目录（仅首次）与后端注入状态（便宜，随推送刷新）
  if (next.state === 'authorized') {
    void loadCloudModels()
    void loadBackendStatus()
  }
}

const refreshStatus = async () => {
  try {
    applyStatus(await window.api.cloud.status())
  } catch {
    loaded.value = true
  }
  try {
    routingMode.value = await window.api.cloud.getRoutingMode()
  } catch {
    // main 不可达时保持默认值
  }
}

// ── 登录 / 授权页 / 退出 ──
const handleLogin = async () => {
  if (loginLoading.value) return
  loginLoading.value = true
  try {
    applyStatus(await window.api.cloud.login())
  } catch {
    applyStatus({ state: 'error', error: 'unknown' })
  } finally {
    loginLoading.value = false
  }
}

const openVerification = async () => {
  try {
    await window.api.cloud.openVerification()
  } catch {
    // 打开失败保持等待态，用户可重试
  }
}

// ── 等待授权态：复制用户码 / 取消本次授权 ──
const copied = ref(false)
let copyTimer: ReturnType<typeof setTimeout> | undefined

const copyUserCode = async () => {
  const code = status.value.userCode
  if (!code) return
  try {
    await navigator.clipboard.writeText(code)
    copied.value = true
    if (copyTimer) clearTimeout(copyTimer)
    copyTimer = setTimeout(() => (copied.value = false), 1500)
  } catch {
    // 剪贴板不可用时用户码仍可手动选中复制（user-select: all）
  }
}

const handleLogout = async () => {
  try {
    applyStatus(await window.api.cloud.logout())
  } catch {
    // 失败时等待状态推送兜底
  }
}

// ── 云端模式开关（off / all，写入 main config-store）──
const toggleRoutingMode = async () => {
  if (modeToggling.value) return
  modeToggling.value = true
  const next: CloudRoutingMode = routingMode.value === 'all' ? 'off' : 'all'
  try {
    await window.api.cloud.setRoutingMode(next)
    routingMode.value = next
  } catch {
    // 失败保持原模式
  } finally {
    modeToggling.value = false
  }
}

const routingModeLabel = computed(() =>
  routingMode.value === 'all' ? t('settingsEx.cloud.routingModeOn') : t('settingsEx.cloud.routingModeOff')
)

// ── 错误文案：已知错误码映射 i18n，未知码原样展示 ──
const errorText = computed(() => {
  const code = status.value.error || 'unknown'
  const key = `settingsEx.cloud.errors.${code}`
  return te(key) ? t(key) : code
})

const formatNumber = (value: number): string => value.toLocaleString()

// ── 余额展示：拉取失败（null）显示"无法获取余额"，不用假 0 ──
const coinBalanceText = computed(() => {
  const balance = status.value.account?.coinBalance
  return typeof balance === 'number' ? formatNumber(balance) : null
})

// ── 今日额度明细行（总额/已用/重置时间/加成包；数据缺失时整行不展示）──
const quotaLine = computed(() => {
  const quota = status.value.account?.quota
  if (!quota || !quota.freeTotal) return null
  let reset = '—'
  if (quota.resetAt) {
    const at = new Date(quota.resetAt)
    if (!Number.isNaN(at.getTime()))
      reset = at.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }
  const parts = [
    t('settingsEx.cloud.quotaDetail', {
      total: formatNumber(quota.freeTotal),
      used: formatNumber(quota.freeUsed),
      time: reset
    })
  ]
  if (quota.bonusRemaining > 0)
    parts.push(t('settingsEx.cloud.quotaBonus', { amount: formatNumber(quota.bonusRemaining) }))
  return parts.join(' · ')
})

// ── 账户详情行（称号/荣誉/邮箱/注册/到期；缺失的字段不展示对应行）──
const accountDetails = computed(() => {
  const account = status.value.account
  if (!account) return []
  const rows: Array<{ label: string; value: string }> = []
  if (account.title) rows.push({ label: t('settingsEx.cloud.honorTitle'), value: account.title })
  if (typeof account.honorLevel === 'number')
    rows.push({ label: t('settingsEx.cloud.honorLevel'), value: `Lv.${account.honorLevel}` })
  if (account.email) rows.push({ label: t('settingsEx.cloud.email'), value: account.email })
  if (account.registeredAt)
    rows.push({ label: t('settingsEx.cloud.registeredAt'), value: account.registeredAt })
  if (account.tierExpiresAt)
    rows.push({ label: t('settingsEx.cloud.tierExpires'), value: account.tierExpiresAt.slice(0, 10) })
  return rows
})

// ── 本地后端注入状态文案（含令牌尾号，便于与后端日志比对）──
const backendStatusLabel = computed(() => {
  const backend = backendStatus.value
  if (!backend?.configured) return t('settingsEx.cloud.backendNotInjected')
  return t('settingsEx.cloud.backendInjected', { tail: backend.tokenTail4 || '----' })
})

onMounted(() => {
  unsubscribe = window.api.cloud.onStatus(applyStatus)
  void refreshStatus()
})

onUnmounted(() => {
  unsubscribe?.()
  unsubscribe = null
  if (copyTimer) clearTimeout(copyTimer)
})
</script>

<template>
  <div class="settings-panel animate-slide-up">
    <!-- 加载中 -->
    <section v-if="!loaded" class="settings-card">
      <div class="settings-card__body settings-card__body--compact cloud-loading">
        <Loader2 :size="20" class="cloud-loading__spinner" />
        <span>{{ t('settingsEx.cloud.loading') }}</span>
      </div>
    </section>

    <!-- 等待授权确认 -->
    <template v-else-if="status.state === 'pendingAuth'">
      <section class="settings-card">
        <div class="settings-card__header">
          <KeyRound :size="16" />
          <span class="settings-card__title">{{ t('settingsEx.cloud.pendingTitle') }}</span>
        </div>
        <div class="settings-card__body">
          <p class="cloud-pending__hint">{{ t('settingsEx.cloud.pendingHint') }}</p>
          <div class="cloud-user-code">{{ status.userCode || '—' }}</div>
          <div class="cloud-code-tools">
            <button type="button" class="cloud-copy-btn" @click="copyUserCode">
              <Check v-if="copied" :size="13" />
              <Copy v-else :size="13" />
              <span>{{ t(copied ? 'settingsEx.cloud.copied' : 'settingsEx.cloud.copyUserCode') }}</span>
            </button>
          </div>
          <div class="cloud-actions">
            <LumiButton variant="primary" size="md" @click="openVerification">
              <template #icon>
                <ExternalLink :size="16" />
              </template>
              {{ t('settingsEx.cloud.openVerification') }}
            </LumiButton>
            <LumiButton variant="ghost" size="md" @click="handleLogout">
              <template #icon>
                <X :size="16" />
              </template>
              {{ t('settingsEx.cloud.cancel') }}
            </LumiButton>
          </div>
          <div class="cloud-waiting">
            <Loader2 :size="14" class="cloud-waiting__spinner" />
            <span>{{ t('settingsEx.cloud.waiting') }}</span>
          </div>
        </div>
      </section>
    </template>

    <!-- 已登录：账户信息 + 云端模式 -->
    <template v-else-if="status.state === 'authorized'">
      <section class="settings-card">
        <div class="settings-card__header">
          <Cloud :size="16" />
          <span class="settings-card__title">{{ t('settingsEx.cloud.authorizedTitle') }}</span>
        </div>
        <div class="settings-card__body">
          <div class="cloud-profile">
            <div class="cloud-profile__avatar">
              <img
                v-if="status.account?.avatar"
                :src="status.account.avatar"
                alt=""
                class="cloud-profile__avatar-img"
                referrerpolicy="no-referrer"
              />
              <User v-else :size="32" />
            </div>
            <div class="cloud-profile__info">
              <div class="cloud-profile__name">{{ status.account?.nickname || '—' }}</div>
              <div class="cloud-profile__meta">
                <span v-if="status.account?.title" class="cloud-profile__title">{{ status.account.title }}</span>
                <span>{{ t('settingsEx.cloud.passportName') }}</span>
              </div>
            </div>
          </div>

          <div class="cloud-meta-grid">
            <div class="cloud-meta-item">
              <span class="cloud-meta-item__label">{{ t('settingsEx.cloud.tier') }}</span>
              <span class="cloud-meta-item__value">{{ status.account?.tier || '—' }}</span>
            </div>
            <div class="cloud-meta-item">
              <span class="cloud-meta-item__label">{{ t('settingsEx.cloud.coinBalance') }}</span>
              <span class="cloud-meta-item__value cloud-meta-item__value--coin">
                <Coins :size="14" />
                <span v-if="coinBalanceText">{{ coinBalanceText }}</span>
                <span v-else class="cloud-meta-item__unavailable">
                  {{ t('settingsEx.cloud.balanceUnavailable') }}
                </span>
              </span>
            </div>
            <div class="cloud-meta-item">
              <span class="cloud-meta-item__label">{{ t('settingsEx.cloud.quotaRemaining') }}</span>
              <span class="cloud-meta-item__value cloud-meta-item__value--quota">
                <Gauge :size="14" />
                {{ formatNumber(status.account?.quotaRemaining ?? 0) }}
              </span>
            </div>
          </div>

          <!-- 今日额度明细（总额/已用/重置/加成包，数据缺失自动隐藏） -->
          <div v-if="quotaLine" class="cloud-quota-line">{{ quotaLine }}</div>

          <!-- 账户详情（称号/荣誉/邮箱/注册/到期，缺失字段自动隐藏） -->
          <ul v-if="accountDetails.length > 0" class="cloud-detail-list">
            <li v-for="row in accountDetails" :key="row.label" class="cloud-detail-list__item">
              <span class="cloud-detail-list__label">{{ row.label }}</span>
              <span class="cloud-detail-list__value">{{ row.value }}</span>
            </li>
          </ul>

          <div class="cloud-actions cloud-actions--end">
            <LumiButton variant="danger-ghost" size="md" @click="handleLogout">
              <template #icon>
                <LogOut :size="16" />
              </template>
              {{ t('settingsEx.cloud.logout') }}
            </LumiButton>
          </div>
        </div>
      </section>

      <section class="settings-card">
        <div class="settings-card__body">
          <div class="cloud-routing-row">
            <div class="cloud-routing-row__info">
              <label class="cloud-routing-row__label">
                <Cloud :size="14" />
                <span>{{ t('settingsEx.cloud.routingMode') }}</span>
              </label>
              <span class="cloud-routing-row__hint">{{ t('settingsEx.cloud.routingModeHint') }}</span>
            </div>
            <span class="cloud-routing-row__state">{{ routingModeLabel }}</span>
            <button
              type="button"
              class="cloud-toggle"
              role="switch"
              :aria-checked="routingMode === 'all'"
              :disabled="modeToggling"
              @click="toggleRoutingMode"
            >
              <span class="cloud-toggle__thumb" />
            </button>
          </div>
        </div>
      </section>

      <!-- 本地后端注入状态（拉取失败时展示未注入，不阻塞页面） -->
      <section class="settings-card">
        <div class="settings-card__body settings-card__body--compact">
          <div class="cloud-backend-row">
            <Cable :size="14" />
            <span>{{ backendStatusLabel }}</span>
          </div>
        </div>
      </section>

      <!-- 云端可用模型（拉取失败静默降级为不显示） -->
      <section v-if="cloudModels.length > 0" class="settings-card">
        <div class="settings-card__header">
          <Cpu :size="16" />
          <span class="settings-card__title">{{ t('settingsEx.cloud.modelsTitle') }}</span>
          <span class="cloud-models__count">{{ cloudModels.length }}</span>
        </div>
        <div class="settings-card__body">
          <ul class="cloud-models">
            <li v-for="model in cloudModels" :key="model.modelId" class="cloud-models__item">
              <span class="cloud-models__name">{{ model.displayName }}</span>
              <span class="cloud-models__id">{{ model.modelId }}</span>
            </li>
          </ul>
        </div>
      </section>

      <section class="settings-card settings-card--dimmed">
        <div class="settings-card__body settings-card__body--compact">
          <div class="cloud-tip">
            <ShieldCheck :size="14" />
            <span>{{ t('settingsEx.cloud.logoutTip') }}</span>
          </div>
        </div>
      </section>
    </template>

    <!-- 错误 + 重试 -->
    <template v-else-if="status.state === 'error'">
      <section class="settings-card">
        <div class="settings-card__header">
          <AlertCircle :size="16" />
          <span class="settings-card__title">{{ t('settingsEx.cloud.errorTitle') }}</span>
        </div>
        <div class="settings-card__body">
          <div class="cloud-banner cloud-banner--error" role="status">
            <AlertCircle :size="14" />
            <span>{{ errorText }}</span>
          </div>
          <div class="cloud-actions">
            <LumiButton variant="primary" size="md" :loading="loginLoading" @click="handleLogin">
              <template #icon>
                <LogIn v-if="!loginLoading" :size="16" />
              </template>
              {{ t('settingsEx.cloud.retry') }}
            </LumiButton>
          </div>
        </div>
      </section>
    </template>

    <!-- 未登录 -->
    <template v-else>
      <section class="settings-card">
        <div class="settings-card__header">
          <Cloud :size="16" />
          <span class="settings-card__title">{{ t('settingsEx.cloud.loggedOutTitle') }}</span>
        </div>
        <div class="settings-card__body">
          <p class="cloud-pending__hint">{{ t('settingsEx.cloud.loggedOutDesc') }}</p>
          <div class="cloud-actions">
            <LumiButton variant="primary" size="lg" :loading="loginLoading" @click="handleLogin">
              <template #icon>
                <LogIn v-if="!loginLoading" :size="16" />
              </template>
              {{ loginLoading ? t('settingsEx.cloud.loggingIn') : t('settingsEx.cloud.login') }}
            </LumiButton>
          </div>
        </div>
      </section>

      <section class="settings-card settings-card--dimmed">
        <div class="settings-card__body settings-card__body--compact">
          <div class="cloud-tip">
            <ShieldCheck :size="14" />
            <span>{{ t('settingsEx.cloud.storageTip') }}</span>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.cloud-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-6);
  color: var(--text-muted);
  font-size: var(--text-sm);
}

.cloud-loading__spinner,
.cloud-waiting__spinner {
  color: var(--lumi-primary);
  animation: spin 1s linear infinite;
}

/* ── 说明文字 ── */
.cloud-pending__hint {
  margin: 0 0 var(--space-3);
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: 1.6;
}

/* ── 授权码展示 ── */
.cloud-user-code {
  padding: var(--space-4);
  border: 1px dashed var(--border-light);
  border-radius: var(--radius-md);
  background: var(--surface-hover);
  font-family: var(--font-mono, monospace);
  font-size: var(--text-2xl);
  font-weight: var(--font-semibold);
  letter-spacing: 0.35em;
  text-align: center;
  color: var(--lumi-primary);
  user-select: all;
}

/* ── 用户码工具行（复制） ── */
.cloud-code-tools {
  display: flex;
  justify-content: center;
  margin-top: var(--space-2);
}

.cloud-copy-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 2px 8px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  font-size: var(--text-xs);
  color: var(--text-muted);
  cursor: pointer;
  transition: color var(--duration-fast, 0.15s) ease-in-out,
    background var(--duration-fast, 0.15s) ease-in-out;
}

.cloud-copy-btn:hover {
  color: var(--lumi-primary);
  background: var(--surface-hover);
}

.cloud-waiting {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-3);
  font-size: var(--text-xs);
  color: var(--text-muted);
}

/* ── 账户资料卡 ── */
.cloud-profile {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-2) 0;
}

.cloud-profile__avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border-radius: var(--radius-full);
  background: color-mix(in srgb, var(--lumi-primary) 12%, transparent);
  color: var(--lumi-primary);
  flex-shrink: 0;
  overflow: hidden;
}

.cloud-profile__avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.cloud-profile__info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.cloud-profile__name {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cloud-profile__meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.cloud-profile__title {
  color: var(--lumi-warning);
  font-weight: 500;
}

/* ── 今日额度明细行 ── */
.cloud-quota-line {
  margin-top: var(--space-2);
  font-size: var(--text-xs);
  color: var(--text-muted);
  letter-spacing: 0.2px;
}

/* ── 账户详情列表 ── */
.cloud-detail-list {
  margin: var(--space-3) 0 0;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background: var(--surface-hover);
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.cloud-detail-list__item {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-3);
  font-size: var(--text-xs);
}

.cloud-detail-list__label {
  color: var(--text-muted);
  flex-shrink: 0;
}

.cloud-detail-list__value {
  color: var(--text-secondary);
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── 元信息网格 ── */
.cloud-meta-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-3);
  padding: var(--space-3) 0;
  border-top: 1px solid var(--divider-soft);
  border-bottom: 1px solid var(--divider-soft);
}

.cloud-meta-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.cloud-meta-item__label {
  font-size: var(--text-xs);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.cloud-meta-item__value {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-sm);
  color: var(--text-primary);
  font-weight: 500;
}

.cloud-meta-item__value--coin {
  color: var(--lumi-warning);
}

.cloud-meta-item__value--quota {
  color: var(--lumi-success);
}

.cloud-meta-item__unavailable {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

/* ── 本地后端注入状态行 ── */
.cloud-backend-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.cloud-backend-row svg {
  color: var(--lumi-primary);
  opacity: 0.7;
}

/* ── 云端可用模型列表（滚动区）── */
.cloud-models__count {
  margin-left: auto;
  padding: 1px 8px;
  border-radius: var(--radius-full);
  background: var(--surface-hover);
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.cloud-models {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  max-height: 240px;
  overflow-y: auto;
}

.cloud-models__item {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background: var(--surface-hover);
}

.cloud-models__name {
  font-size: var(--text-sm);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cloud-models__id {
  font-family: var(--font-mono, monospace);
  font-size: var(--text-xs);
  color: var(--text-muted);
  flex-shrink: 0;
}

.cloud-actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-4);
}

.cloud-actions--end {
  justify-content: flex-end;
  margin-top: var(--space-3);
}

/* ── 云端模式开关行 ── */
.cloud-routing-row {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.cloud-routing-row__info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.cloud-routing-row__label {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-secondary);
}

.cloud-routing-row__label svg {
  color: var(--text-muted);
}

.cloud-routing-row__hint {
  font-size: var(--text-xs);
  color: var(--text-muted);
  line-height: 1.5;
}

.cloud-routing-row__state {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  white-space: nowrap;
}

.cloud-toggle {
  position: relative;
  width: 36px;
  height: 20px;
  flex: none;
  border-radius: 999px;
  border: 1px solid var(--border-color);
  background: var(--bg-tertiary);
  cursor: pointer;
  transition: background var(--duration-fast, 0.15s) ease-in-out,
    border-color var(--duration-fast, 0.15s) ease-in-out;
  padding: 0;
}

.cloud-toggle:disabled {
  opacity: 0.6;
  cursor: default;
}

.cloud-toggle__thumb {
  position: absolute;
  top: 1px;
  left: 1px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--text-primary);
  transition: transform var(--duration-fast, 0.15s) ease-in-out,
    background var(--duration-fast, 0.15s) ease-in-out;
}

.cloud-toggle[aria-checked='true'] {
  background: var(--lumi-primary);
  border-color: var(--lumi-primary);
}

.cloud-toggle[aria-checked='true'] .cloud-toggle__thumb {
  transform: translateX(16px);
  background: var(--text-inverse);
}

.cloud-toggle:hover {
  border-color: var(--lumi-primary);
}

/* ── 错误横幅 ── */
.cloud-banner {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
}

.cloud-banner--error {
  background: color-mix(in srgb, var(--lumi-danger) 12%, transparent);
  color: var(--lumi-danger);
}

/* ── 提示 ── */
.cloud-tip {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  font-size: var(--text-xs);
  color: var(--text-muted);
  line-height: 1.5;
}

.cloud-tip svg {
  flex-shrink: 0;
  margin-top: 2px;
  color: var(--lumi-primary);
  opacity: 0.7;
}

/* ── 响应式 ── */
@media (max-width: 640px) {
  .cloud-meta-grid {
    grid-template-columns: 1fr;
    gap: var(--space-2);
  }

  .cloud-routing-row {
    flex-wrap: wrap;
  }
}
</style>

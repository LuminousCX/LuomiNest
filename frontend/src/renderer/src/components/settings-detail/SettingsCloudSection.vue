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
  ShieldCheck
} from 'lucide-vue-next'
import LumiButton from '../common/LumiButton.vue'
import type { CloudAuthStatus, CloudRoutingMode } from '@shared/ipc-types'

const { t, te } = useI18n()

// ── 登录状态（main 进程状态机推送，renderer 只见摘要）──
const loaded = ref(false)
const status = ref<CloudAuthStatus>({ state: 'loggedOut' })
const routingMode = ref<CloudRoutingMode>('off')
const loginLoading = ref(false)
const modeToggling = ref(false)

let unsubscribe: (() => void) | null = null

const applyStatus = (next: CloudAuthStatus) => {
  status.value = next
  loaded.value = true
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

onMounted(() => {
  unsubscribe = window.api.cloud.onStatus(applyStatus)
  void refreshStatus()
})

onUnmounted(() => {
  unsubscribe?.()
  unsubscribe = null
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
          <div class="cloud-actions">
            <LumiButton variant="primary" size="md" @click="openVerification">
              <template #icon>
                <ExternalLink :size="16" />
              </template>
              {{ t('settingsEx.cloud.openVerification') }}
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
              <User :size="32" />
            </div>
            <div class="cloud-profile__info">
              <div class="cloud-profile__name">{{ status.account?.nickname || '—' }}</div>
              <div class="cloud-profile__meta">{{ t('settingsEx.cloud.passportName') }}</div>
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
                {{ formatNumber(status.account?.coinBalance ?? 0) }}
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
  font-size: var(--text-sm);
  color: var(--text-muted);
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

<script setup lang="ts">
/**
 * 用量与配额面板（设置 → 辰汐云）
 *
 * 纯展示组件：今日免费额度进度 + 权益总览 + 最近用量。
 * 数据缺失时静默降级为"暂无数据"，不发请求、不持有登录状态。
 * 自 SettingsCloudSection 拆出（2026-10 样式重构）。
 */
import { computed } from 'vue'
import { formatTime, formatShortDateTime } from '@/utils/format'
import { useI18n } from 'vue-i18n'
import type { CloudAccountInfo, CloudUsageEntry } from '@shared/ipc-types'

const { t } = useI18n()

const props = defineProps<{
  /** 云端账户信息（quota/权益来源；未登录或缺失时整体降级） */
  account?: CloudAccountInfo | null
  /** 最近用量条目（拉取失败/为空时展示空态） */
  usage: CloudUsageEntry[]
}>()

const formatNumber = (value: number): string => value.toLocaleString()

// ── 余额展示：拉取失败（null）显示"无法获取余额"，不用假 0 ──
const coinBalanceText = computed(() => {
  const balance = props.account?.coinBalance
  return typeof balance === 'number' ? formatNumber(balance) : null
})

// ── 今日额度进度（quota 缺失时整体降级为"暂无数据"）──
const quotaDetail = computed(() => props.account?.quota ?? null)

const quotaPercent = computed(() => {
  const quota = quotaDetail.value
  if (!quota || quota.freeTotal <= 0) return null
  return Math.min(100, Math.round((quota.freeUsed / quota.freeTotal) * 100))
})

const quotaResetText = computed(() => {
  const resetAt = quotaDetail.value?.resetAt
  if (!resetAt) return ''
  const at = new Date(resetAt)
  return Number.isNaN(at.getTime()) ? '' : formatTime(resetAt)
})

// 最近用量条目的时间列：可解析则本地化短格式，否则原样透传；缺失为空串
const usageTimeText = (iso: string | null): string => {
  if (!iso) return ''
  const at = new Date(iso)
  if (Number.isNaN(at.getTime())) return iso
  return formatShortDateTime(iso)
}
</script>

<template>
  <div class="cloud-usage-panel">
    <!-- 今日免费额度进度（quota 缺失时降级提示） -->
    <template v-if="quotaDetail">
      <div class="cloud-usage-progress">
        <div class="cloud-usage-progress__labels">
          <span>{{ t('settingsEx.cloud.quotaTodayUsed') }}</span>
          <span class="cloud-usage-progress__figures">
            {{ formatNumber(quotaDetail.freeUsed) }} / {{ formatNumber(quotaDetail.freeTotal) }}
            <template v-if="quotaPercent !== null">&nbsp;· {{ quotaPercent }}%</template>
          </span>
        </div>
        <div
          class="cloud-usage-progress__track"
          role="progressbar"
          :aria-valuenow="quotaPercent ?? 0"
          aria-valuemin="0"
          aria-valuemax="100"
        >
          <div
            class="cloud-usage-progress__fill"
            :class="{ 'cloud-usage-progress__fill--hot': (quotaPercent ?? 0) >= 90 }"
            :style="{ width: `${quotaPercent ?? 0}%` }"
          />
        </div>
      </div>
      <ul class="cloud-detail-list">
        <li class="cloud-detail-list__item">
          <span class="cloud-detail-list__label">{{ t('settingsEx.cloud.quotaDailyFree') }}</span>
          <span class="cloud-detail-list__value">{{ formatNumber(quotaDetail.freeTotal) }}</span>
        </li>
        <li class="cloud-detail-list__item">
          <span class="cloud-detail-list__label">{{ t('settingsEx.cloud.quotaRemaining') }}</span>
          <span class="cloud-detail-list__value">{{ formatNumber(quotaDetail.freeRemaining) }}</span>
        </li>
        <li v-if="quotaDetail.bonusRemaining > 0" class="cloud-detail-list__item">
          <span class="cloud-detail-list__label">{{ t('settingsEx.cloud.bonusPack') }}</span>
          <span class="cloud-detail-list__value">+{{ formatNumber(quotaDetail.bonusRemaining) }}</span>
        </li>
        <li v-if="quotaResetText" class="cloud-detail-list__item">
          <span class="cloud-detail-list__label">{{ t('settingsEx.cloud.quotaResetAt') }}</span>
          <span class="cloud-detail-list__value">{{ quotaResetText }}</span>
        </li>
      </ul>
    </template>
    <p v-else class="cloud-usage-empty">{{ t('settingsEx.cloud.quotaNoData') }}</p>

    <!-- 权益总览（档位/芙贝币余额/荣誉等级，缺失行自动隐藏） -->
    <div class="cloud-usage-subtitle">{{ t('settingsEx.cloud.benefitsTitle') }}</div>
    <ul class="cloud-detail-list">
      <li class="cloud-detail-list__item">
        <span class="cloud-detail-list__label">{{ t('settingsEx.cloud.tier') }}</span>
        <span class="cloud-detail-list__value">{{ account?.tier || '—' }}</span>
      </li>
      <li class="cloud-detail-list__item">
        <span class="cloud-detail-list__label">{{ t('settingsEx.cloud.coinBalance') }}</span>
        <span class="cloud-detail-list__value cloud-detail-list__value--coin">
          <span v-if="coinBalanceText">{{ coinBalanceText }}</span>
          <span v-else>{{ t('settingsEx.cloud.balanceUnavailable') }}</span>
        </span>
      </li>
      <li v-if="typeof account?.honorLevel === 'number'" class="cloud-detail-list__item">
        <span class="cloud-detail-list__label">{{ t('settingsEx.cloud.honorLevel') }}</span>
        <span class="cloud-detail-list__value">Lv.{{ account.honorLevel }}</span>
      </li>
    </ul>

    <!-- 最近用量（usage 拉取失败/为空时降级提示，不阻塞页面） -->
    <div class="cloud-usage-subtitle">{{ t('settingsEx.cloud.usageRecentTitle') }}</div>
    <ul v-if="usage.length > 0" class="cloud-usage-list">
      <li v-for="(item, index) in usage" :key="`${item.model}-${index}`" class="cloud-usage-item">
        <div class="cloud-usage-item__top">
          <span class="cloud-usage-item__model">{{ item.model }}</span>
          <span v-if="usageTimeText(item.lastUsedAt)" class="cloud-usage-item__time">
            {{ usageTimeText(item.lastUsedAt) }}
          </span>
        </div>
        <div class="cloud-usage-item__meta">
          <span>{{ t('settingsEx.cloud.usageTokens', { amount: formatNumber(item.tokens) }) }}</span>
          <span v-if="item.requests > 0">{{ t('settingsEx.cloud.usageRequests', { count: item.requests }) }}</span>
          <span v-if="typeof item.coinsUsed === 'number' && item.coinsUsed > 0" class="cloud-usage-item__coins">
            {{ t('settingsEx.cloud.usageCoins', { amount: formatNumber(item.coinsUsed) }) }}
          </span>
        </div>
      </li>
    </ul>
    <p v-else class="cloud-usage-empty">{{ t('settingsEx.cloud.usageNoData') }}</p>
  </div>
</template>

<style scoped src="./cloud-shared.css"></style>

<style scoped>
/* ── 用量与配额面板 ── */
.cloud-usage-progress__labels {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-3);
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

.cloud-usage-progress__figures {
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.cloud-usage-progress__track {
  height: 6px;
  margin-top: var(--space-2);
  border-radius: 999px;
  background: var(--surface-hover);
  overflow: hidden;
}

.cloud-usage-progress__fill {
  height: 100%;
  border-radius: inherit;
  background: var(--lumi-primary);
  transition: width var(--duration-normal) ease-in-out;
}

.cloud-usage-progress__fill--hot {
  background: var(--lumi-warning);
}

.cloud-usage-subtitle {
  margin: var(--space-4) 0 var(--space-2);
  font-size: var(--text-xs);
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.cloud-usage-empty {
  margin: 0;
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.cloud-usage-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  max-height: 220px;
  overflow-y: auto;
}

.cloud-usage-item {
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background: var(--surface-hover);
}

.cloud-usage-item__top {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-2);
}

.cloud-usage-item__model {
  font-size: var(--text-sm);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cloud-usage-item__time {
  font-size: var(--text-xs);
  color: var(--text-muted);
  flex-shrink: 0;
}

.cloud-usage-item__meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-top: 2px;
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.cloud-usage-item__coins {
  color: var(--lumi-warning);
}

.cloud-detail-list__value--coin {
  color: var(--lumi-warning);
}
</style>

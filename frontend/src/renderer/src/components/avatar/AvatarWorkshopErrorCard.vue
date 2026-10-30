<script setup lang="ts">
/**
 * AvatarWorkshopErrorCard - 皮套工坊显式错误卡片
 *
 * 背景（审计 §1.4-3"失败显式化"）：清单为空 / 清单加载失败 / 内置资源 404 三层
 * 历史上只写日志，工坊 UI 只表现为"列表空/模型不显示"，用户无法区分"没做"与"坏了"。
 * 本卡片把工坊级错误（workshopError）显式摆到舞台上，并提供：
 * - 一键诊断：经 avatar:diagnoseResources IPC 核对后端清单文件与内置资源在位情况
 * - 重试加载：重新拉取 manifest
 * - 建议：重装最新版或带诊断结果反馈
 */
import { useI18n } from 'vue-i18n'
import { computed } from 'vue'
import { AlertCircle, Search, RefreshCw, CheckCircle2, FileWarning } from 'lucide-vue-next'
import LumiButton from '../common/LumiButton.vue'
import type { AvatarDiagnosticsResult } from '@shared/ipc-types'

const props = defineProps<{
  /** 工坊级错误文案（i18n 已解析） */
  error: string
  isDiagnosing: boolean
  diagnostics: AvatarDiagnosticsResult | null
}>()

const emit = defineEmits<{
  diagnose: []
  retry: []
}>()

const { t } = useI18n()

const missingItems = computed(() => props.diagnostics?.missing ?? [])
</script>

<template>
  <div class="workshop-error-card" role="alert">
    <div class="error-head">
      <AlertCircle :size="28" class="error-icon" />
      <div class="error-titles">
        <h3 class="error-title">{{ t('avatar.workshop.errorCardTitle') }}</h3>
        <p class="error-detail">{{ props.error }}</p>
      </div>
    </div>

    <p class="error-hint">{{ t('avatar.workshop.errorCardHint') }}</p>

    <!-- 诊断结果 -->
    <div v-if="props.diagnostics" class="diagnose-result" :class="props.diagnostics.ok ? 'is-ok' : 'is-missing'">
      <template v-if="props.diagnostics.ok">
        <CheckCircle2 :size="16" class="result-icon-ok" />
        <span>{{ t('avatar.workshop.diagnosePassed') }}</span>
      </template>
      <template v-else>
        <div class="result-missing-head">
          <FileWarning :size="16" class="result-icon-missing" />
          <span>{{ t('avatar.workshop.diagnoseMissing', { count: props.diagnostics.missing.length }) }}</span>
        </div>
        <ul class="missing-list">
          <li v-for="item in missingItems" :key="item.label" class="missing-item">
            <code class="missing-label">{{ item.label }}</code>
            <code v-for="p in item.paths" :key="p" class="missing-path">{{ p }}</code>
          </li>
        </ul>
      </template>
    </div>

    <div class="error-actions">
      <LumiButton variant="primary" size="sm" :loading="props.isDiagnosing" @click="emit('diagnose')">
        <template #icon><Search :size="16" /></template>
        <span>{{ props.isDiagnosing ? t('avatar.workshop.diagnoseRunning') : t('avatar.workshop.diagnoseButton') }}</span>
      </LumiButton>
      <LumiButton variant="secondary" size="sm" :disabled="props.isDiagnosing" @click="emit('retry')">
        <template #icon><RefreshCw :size="16" /></template>
        <span>{{ t('avatar.workshop.retryButton') }}</span>
      </LumiButton>
    </div>
  </div>
</template>

<style scoped>
/* 定位（absolute/z-index）交给挂载点的类（AvatarView 的 .workshop-error-float），本组件只管卡片外观 */
.workshop-error-card {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-5);
  border: 1px solid var(--lumi-danger-light);
  border-radius: var(--radius-lg);
  background: color-mix(in srgb, var(--surface) 92%, transparent);
  backdrop-filter: blur(6px);
  box-shadow: var(--shadow-lg);
  overflow-y: auto;
}

.error-head {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
}

.error-icon {
  flex-shrink: 0;
  margin-top: 2px;
  color: var(--lumi-danger);
}

.error-titles {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.error-title {
  margin: 0;
  font-size: var(--text-md);
  font-weight: var(--font-semibold);
  color: var(--text);
}

.error-detail {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--lumi-danger);
  word-break: break-word;
}

.error-hint {
  margin: 0;
  font-size: var(--text-sm);
  line-height: 1.6;
  color: var(--text-secondary);
}

.diagnose-result {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
}

.diagnose-result.is-ok {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: var(--space-2);
  color: var(--lumi-success);
  background: color-mix(in srgb, var(--lumi-success) 8%, transparent);
}

.diagnose-result.is-missing {
  color: var(--text);
  background: color-mix(in srgb, var(--lumi-danger) 6%, transparent);
}

.result-missing-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--lumi-danger);
}

.result-icon-ok {
  color: var(--lumi-success);
  flex-shrink: 0;
}

.result-icon-missing {
  color: var(--lumi-danger);
  flex-shrink: 0;
}

.missing-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.missing-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-left: var(--space-5);
}

.missing-label {
  font-weight: var(--font-semibold);
  color: var(--lumi-danger);
  font-size: var(--text-xs);
}

.missing-path {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  word-break: break-all;
}

.error-actions {
  display: flex;
  gap: var(--space-2);
}
</style>

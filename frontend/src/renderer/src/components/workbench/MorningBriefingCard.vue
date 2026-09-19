<script setup lang="ts">
/**
 * 晨间简报卡片（陪伴定位：记忆的消费形态）。
 * 应用启动/回到工作台时展示当日问候；可刷新、可关闭（当日不再打扰）。
 */
import { computed, ref } from 'vue'
import { Sunrise, RefreshCw, X } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import LumiButton from '../common/LumiButton.vue'

const props = defineProps<{
  date: string
  content: string
  loading?: boolean
}>()

const emit = defineEmits<{
  refresh: []
  dismiss: []
}>()

const { t } = useI18n()

const DISMISS_KEY = 'luominest.briefing.dismissed'
// dismissed 必须跟随 props.date 响应式重算（briefing 异步到达前 date 为空串，
// 若只在挂载时初始化一次，刷新后当日已关闭的简报会重新出现）
const dismissedTick = ref(0)
const isDismissed = computed(() => {
  void dismissedTick.value
  try {
    return !!props.date && localStorage.getItem(DISMISS_KEY) === props.date
  } catch {
    return false
  }
})

function dismiss(): void {
  try {
    localStorage.setItem(DISMISS_KEY, props.date)
  } catch { /* ignore */ }
  dismissedTick.value += 1
}
</script>

<template>
  <div v-if="content && !isDismissed" class="briefing-card">
    <div class="briefing-icon"><Sunrise :size="18" /></div>
    <div class="briefing-body">
      <div class="briefing-title">{{ t('memory.briefing.title') }}</div>
      <div class="briefing-content">{{ content }}</div>
    </div>
    <div class="briefing-actions">
      <LumiButton variant="ghost" :disabled="loading" @click="emit('refresh')">
        <RefreshCw :size="14" />
      </LumiButton>
      <LumiButton variant="ghost" @click="dismiss">
        <X :size="14" />
      </LumiButton>
    </div>
  </div>
</template>

<style scoped>
.briefing-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  margin: 0 0 12px;
  border-radius: 14px;
  border: 1px solid var(--lumi-border, #e5e7eb);
  background: linear-gradient(135deg, color-mix(in srgb, var(--lumi-primary, #6366f1) 7%, transparent), transparent);
}
.briefing-icon {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: color-mix(in srgb, var(--lumi-primary, #6366f1) 12%, transparent);
  color: var(--lumi-primary, #6366f1);
}
.briefing-body {
  flex: 1;
  min-width: 0;
}
.briefing-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--lumi-text-secondary, #6b7280);
  margin-bottom: 4px;
}
.briefing-content {
  font-size: 13.5px;
  line-height: 1.7;
  color: var(--lumi-text-primary, #1f2937);
  white-space: pre-wrap;
  word-break: break-word;
}
.briefing-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}
</style>

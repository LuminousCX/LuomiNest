<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  QrCode, RefreshCw, CheckCircle2, AlertCircle, Smartphone, Clock,
} from 'lucide-vue-next'
import { usePlatformStore } from '../../stores/platform'
import type { PlatformInstance } from '../../types'
import LumiModal from '../../components/common/LumiModal.vue'
import LumiButton from '../../components/common/LumiButton.vue'
import { createLuomiNestRendererLogger } from '../../utils/logger'

const { t } = useI18n()
const logger = createLuomiNestRendererLogger('WeChatQR')
const store = usePlatformStore()

const props = defineProps<{
  visible: boolean
  instance: PlatformInstance | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  'logged-in': []
}>()

const qrData = ref<string>('')
const qrUuid = ref<string>('')
const qrStatus = ref<'waiting_scan' | 'scanned' | 'logged_in' | 'expired' | 'loading' | 'error'>('loading')
const statusMessage = ref<string>(t('platform.wechat.init'))
let pollTimer: ReturnType<typeof setInterval> | null = null

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const fetchQrCode = async () => {
  if (!props.instance) return
  stopPolling()
  qrStatus.value = 'loading'
  statusMessage.value = t('platform.wechat.requesting')
  try {
    const res = await store.getWeChatQrCode(props.instance.id)
    if (res && res.qr_data) {
      qrData.value = res.qr_data
      qrUuid.value = res.uuid || ''
      qrStatus.value = (res.status as any) || 'waiting_scan'
      statusMessage.value = res.message || t('platform.wechat.scanHint')
      startPolling()
    } else {
      qrStatus.value = 'error'
      statusMessage.value = res?.message || t('platform.wechat.fetchFail')
    }
  } catch (e) {
    logger.error('Failed to fetch wechat qrcode:', e)
    qrStatus.value = 'error'
    statusMessage.value = t('platform.wechat.gatewayError')
  }
}

const pollStatus = async () => {
  if (!props.instance || !qrUuid.value || qrStatus.value === 'logged_in' || qrStatus.value === 'expired') return
  try {
    const res = await store.checkWeChatQrStatus(props.instance.id, qrUuid.value)
    if (res) {
      qrStatus.value = res.status || qrStatus.value
      statusMessage.value = res.message || statusMessage.value

      if (qrStatus.value === 'logged_in') {
        stopPolling()
        await store.fetchInstances()
        emit('logged-in')
        setTimeout(() => {
          closeDialog()
        }, 1500)
      } else if (qrStatus.value === 'expired') {
        stopPolling()
      }
    }
  } catch (e) {
    logger.debug('Poll wechat qr status failed:', e)
  }
}

const startPolling = () => {
  stopPolling()
  pollTimer = setInterval(pollStatus, 2500)
}

const closeDialog = () => {
  stopPolling()
  emit('update:visible', false)
}

watch(
  () => props.visible,
  (val) => {
    if (val && props.instance) {
      fetchQrCode()
    } else {
      stopPolling()
    }
  },
  { immediate: true },
)

onUnmounted(() => {
  stopPolling()
})
</script>

<template>
  <LumiModal
    :visible="visible"
    :title="`${t('platform.wechat.title')} - ${instance?.name || ''}`"
    size="md"
    @close="closeDialog"
    @update:visible="emit('update:visible', $event)"
  >
    <div class="wechat-qr-container">
      <div class="qr-header">
        <div class="header-icon">
          <QrCode :size="24" style="color: #07C160" />
        </div>
        <div class="header-text">
          <h3>{{ t('platform.wechat.headerTitle') }}</h3>
          <p>{{ t('platform.wechat.headerDesc') }}</p>
        </div>
      </div>

      <!-- 二维码展示核心区 -->
      <div class="qr-card">
        <div v-if="qrStatus === 'loading'" class="qr-state-box">
          <RefreshCw :size="32" class="spin-animation" style="color: var(--lumi-primary)" />
          <span>{{ t('platform.wechat.generating') }}</span>
        </div>

        <div v-else-if="qrStatus === 'error'" class="qr-state-box">
          <AlertCircle :size="36" style="color: var(--lumi-danger)" />
          <span>{{ statusMessage }}</span>
          <LumiButton variant="secondary" size="sm" @click="fetchQrCode">
            <RefreshCw :size="14" />
            {{ t('platform.wechat.retry') }}
          </LumiButton>
        </div>

        <div v-else class="qr-image-wrapper">
          <img :src="qrData" :alt="t('platform.wechat.qrAlt')" class="qr-image" />
          <div v-if="qrStatus === 'expired'" class="qr-overlay expired">
            <Clock :size="32" style="color: white" />
            <span>{{ t('platform.wechat.expired') }}</span>
            <LumiButton variant="primary" size="sm" @click="fetchQrCode">
              <RefreshCw :size="14" />
              {{ t('platform.wechat.refresh') }}
            </LumiButton>
          </div>
          <div v-else-if="qrStatus === 'scanned'" class="qr-overlay scanned">
            <Smartphone :size="32" style="color: white" />
            <span>{{ t('platform.wechat.scanned') }}</span>
            <small>{{ t('platform.wechat.confirmOnPhone') }}</small>
          </div>
          <div v-else-if="qrStatus === 'logged_in'" class="qr-overlay success">
            <CheckCircle2 :size="36" style="color: #07C160" />
            <span>{{ t('platform.wechat.loggedIn') }}</span>
          </div>
        </div>
      </div>

      <!-- 状态提示与操作条 -->
      <div class="qr-status-bar">
        <div :class="['status-pill', qrStatus]">
          <span class="status-dot"></span>
          <span class="status-text">{{ statusMessage }}</span>
        </div>
      </div>

      <div class="qr-actions">
        <LumiButton variant="ghost" size="sm" @click="fetchQrCode" :disabled="qrStatus === 'loading'">
          <RefreshCw :size="14" :class="{ 'spin-animation': qrStatus === 'loading' }" />
          {{ t('platform.wechat.manualRefresh') }}
        </LumiButton>
        <LumiButton variant="secondary" size="sm" @click="closeDialog">
          {{ t('close') }}
        </LumiButton>
      </div>
    </div>
  </LumiModal>
</template>

<style scoped>
.wechat-qr-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 12px 0 8px;
}

.qr-header {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 8px 12px;
  background: var(--surface-hover);
  border-radius: 8px;
  border: 1px solid var(--border-light);
}

.header-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  /* 微信品牌绿锚点 */
  background: color-mix(in srgb, #07C160 12%, transparent);
  border-radius: 8px;
  flex-shrink: 0;
}

.header-text h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}

.header-text p {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--text-muted);
}

.qr-card {
  position: relative;
  width: 220px;
  height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
  /* 二维码识别要求固定白底 */
  background: white;
  border-radius: 12px;
  padding: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(0, 0, 0, 0.1);
}

.qr-state-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  /* QR 卡固定白底，文字需恒为深色 */
  color: #555;
  text-align: center;
}

.qr-image-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
}

.qr-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

.qr-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: rgba(0, 0, 0, 0.78);
  border-radius: 6px;
  color: white;
  font-size: 13px;
  font-weight: 500;
  backdrop-filter: blur(2px);
}

.qr-overlay.scanned {
  background: color-mix(in srgb, var(--lumi-brand) 88%, transparent);
}

.qr-overlay.success {
  background: rgba(255, 255, 255, 0.95);
  color: #07C160;
  font-size: 15px;
}

.qr-status-bar {
  display: flex;
  justify-content: center;
  width: 100%;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 12px;
  background: var(--surface-hover);
  color: var(--text);
  border: 1px solid var(--border-light);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-muted);
}

.status-pill.waiting_scan .status-dot {
  background: var(--lumi-info);
  box-shadow: 0 0 6px var(--lumi-info);
}

.status-pill.scanned .status-dot {
  background: var(--lumi-warning);
  box-shadow: 0 0 6px var(--lumi-warning);
}

.status-pill.logged_in .status-dot {
  background: #07C160;
  box-shadow: 0 0 6px #07C160;
}

.status-pill.expired .status-dot {
  background: var(--lumi-danger);
}

.qr-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  width: 100%;
  border-top: 1px solid var(--border-light);
  padding-top: 12px;
}
</style>

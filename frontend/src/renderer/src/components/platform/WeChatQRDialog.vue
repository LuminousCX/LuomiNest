<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'
import {
  QrCode, RefreshCw, CheckCircle2, AlertCircle, Smartphone, Clock,
} from 'lucide-vue-next'
import { usePlatformStore } from '../../stores/platform'
import type { PlatformInstance } from '../../types'
import LumiModal from '../../components/common/LumiModal.vue'
import LumiButton from '../../components/common/LumiButton.vue'
import { createLuomiNestRendererLogger } from '../../utils/logger'

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
const statusMessage = ref<string>('正在获取二维码...')
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
  statusMessage.value = '正在请求微信登录二维码...'
  try {
    const res = await store.getWeChatQrCode(props.instance.id)
    if (res && res.qr_data) {
      qrData.value = res.qr_data
      qrUuid.value = res.uuid || ''
      qrStatus.value = (res.status as any) || 'waiting_scan'
      statusMessage.value = res.message || '请使用手机微信扫描二维码'
      startPolling()
    } else {
      qrStatus.value = 'error'
      statusMessage.value = res?.message || '获取二维码失败，请检查网关配置'
    }
  } catch (e) {
    logger.error('Failed to fetch wechat qrcode:', e)
    qrStatus.value = 'error'
    statusMessage.value = '连接微信网关服务异常，请重试'
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
    :title="`微信扫码登录 - ${instance?.name || ''}`"
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
          <h3>扫码登录个人微信</h3>
          <p>请使用手机微信扫一扫，扫描下方二维码并在手机端确认登录</p>
        </div>
      </div>

      <!-- 二维码展示核心区 -->
      <div class="qr-card">
        <div v-if="qrStatus === 'loading'" class="qr-state-box">
          <RefreshCw :size="32" class="spin-animation" style="color: var(--lumi-primary)" />
          <span>正在生成专属登录二维码...</span>
        </div>

        <div v-else-if="qrStatus === 'error'" class="qr-state-box">
          <AlertCircle :size="36" style="color: var(--lumi-danger)" />
          <span>{{ statusMessage }}</span>
          <LumiButton variant="secondary" size="sm" @click="fetchQrCode">
            <RefreshCw :size="14" />
            重试获取
          </LumiButton>
        </div>

        <div v-else class="qr-image-wrapper">
          <img :src="qrData" alt="微信登录二维码" class="qr-image" />
          <div v-if="qrStatus === 'expired'" class="qr-overlay expired">
            <Clock :size="32" style="color: white" />
            <span>二维码已失效</span>
            <LumiButton variant="primary" size="sm" @click="fetchQrCode">
              <RefreshCw :size="14" />
              刷新二维码
            </LumiButton>
          </div>
          <div v-else-if="qrStatus === 'scanned'" class="qr-overlay scanned">
            <Smartphone :size="32" style="color: white" />
            <span>已扫码</span>
            <small>请在手机微信上点击确认</small>
          </div>
          <div v-else-if="qrStatus === 'logged_in'" class="qr-overlay success">
            <CheckCircle2 :size="36" style="color: #07C160" />
            <span>登录成功！</span>
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
          手动刷新
        </LumiButton>
        <LumiButton variant="secondary" size="sm" @click="closeDialog">
          关闭
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
  background: var(--bg-hover, rgba(255, 255, 255, 0.04));
  border-radius: 8px;
  border: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.08));
}

.header-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  background: rgba(7, 193, 96, 0.12);
  border-radius: 8px;
  flex-shrink: 0;
}

.header-text h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-normal, #e0e0e0);
}

.header-text p {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--text-muted, #888);
}

.qr-card {
  position: relative;
  width: 220px;
  height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
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
  background: rgba(18, 150, 219, 0.88);
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
  background: var(--bg-hover, rgba(255, 255, 255, 0.06));
  color: var(--text-normal, #ccc);
  border: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.1));
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-muted, #888);
}

.status-pill.waiting_scan .status-dot {
  background: #1890ff;
  box-shadow: 0 0 6px #1890ff;
}

.status-pill.scanned .status-dot {
  background: #fa8c16;
  box-shadow: 0 0 6px #fa8c16;
}

.status-pill.logged_in .status-dot {
  background: #07C160;
  box-shadow: 0 0 6px #07C160;
}

.status-pill.expired .status-dot {
  background: #f5222d;
}

.qr-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  width: 100%;
  border-top: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.08));
  padding-top: 12px;
}

.spin-animation {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>

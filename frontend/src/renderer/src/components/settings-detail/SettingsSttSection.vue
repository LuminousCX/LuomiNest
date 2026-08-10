<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  Settings,
  Mic,
  Loader2,
  AlertCircle,
  Check,
  Wifi,
  WifiOff,
  Save,
  Globe
} from 'lucide-vue-next'
import { useModelStore } from '../../stores/model'
import LumiButton from '../common/LumiButton.vue'

const props = defineProps<{
  embedded?: boolean
}>()

const modelStore = useModelStore()

const sttLoading = ref(false)
const sttError = ref<string | null>(null)
const sttSaving = ref(false)
const sttSaveResult = ref<{ ok: boolean; msg: string } | null>(null)

const sttForm = ref({
  engine: 'auto',
  provider: '',
  model: 'whisper-1',
  language: 'zh-CN',
  autoSend: false,
  autoSendDelay: 2000,
})

const fetchSttInfo = async () => {
  sttLoading.value = true
  sttError.value = null
  try {
    await modelStore.fetchSTTEngines()
    syncSttForm()
  } catch (e) {
    sttError.value = e instanceof Error ? e.message : '获取 STT 信息失败'
  } finally {
    sttLoading.value = false
  }
}

const syncSttForm = () => {
  const cfg = modelStore.sttConfig
  sttForm.value.engine = cfg.engine || 'auto'
  sttForm.value.provider = cfg.provider || ''
  sttForm.value.model = cfg.model || 'whisper-1'
  sttForm.value.language = cfg.language || 'zh-CN'
  sttForm.value.autoSend = cfg.autoSend ?? false
  sttForm.value.autoSendDelay = cfg.autoSendDelay ?? 2000
}

const saveSttConfig = async () => {
  sttSaving.value = true
  sttSaveResult.value = null
  try {
    await modelStore.updateSTTConfig({
      engine: sttForm.value.engine,
      provider: sttForm.value.provider,
      model: sttForm.value.model,
      language: sttForm.value.language,
      autoSend: sttForm.value.autoSend,
      autoSendDelay: sttForm.value.autoSendDelay,
    })
    sttSaveResult.value = { ok: true, msg: '配置已保存' }
    setTimeout(() => { sttSaveResult.value = null }, 3000)
  } catch (e) {
    sttSaveResult.value = { ok: false, msg: e instanceof Error ? e.message : '保存失败' }
  } finally {
    sttSaving.value = false
  }
}

const sttEngineOptions = [
  { value: 'auto', label: '自动选择' },
  { value: 'whisper', label: 'OpenAI Whisper' },
  { value: 'sherpa-onnx', label: 'Sherpa-ONNX (本地)' },
  { value: 'browser', label: '浏览器内置' },
]

const sttModelOptions = computed(() => {
  const engine = sttForm.value.engine
  if (engine === 'whisper') {
    return [
      { value: 'whisper-1', label: 'Whisper-1' },
      { value: 'whisper-large-v3', label: 'Whisper Large V3' },
    ]
  }
  return [{ value: sttForm.value.model, label: sttForm.value.model }]
})

const delayLabel = computed(() => {
  const ms = sttForm.value.autoSendDelay
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`
  return `${ms}ms`
})

/** 计算设备徽标文案（与 TTS 设置一致） */
const sttDeviceLabel = computed(() => {
  const dev = modelStore.sttDevice
  if (!dev || dev.type !== 'gpu') return 'CPU'
  const vendor = dev.vendor || ''
  if (vendor === 'nvidia') return 'GPU (NVIDIA)'
  if (vendor === 'amd') return 'GPU (AMD)'
  if (vendor === 'intel') return 'GPU (Intel)'
  if (vendor === 'apple') return 'GPU (Apple MPS)'
  return 'GPU'
})

/** 设备检测提示语 */
const sttDeviceHint = computed(() => {
  const dev = modelStore.sttDevice
  if (!dev || dev.type !== 'gpu') {
    return '未检测到 GPU，本地 STT (Sherpa-ONNX / FunASR) 使用 CPU 推理。在线 STT 在云端识别，不受本地设备限制。'
  }
  const gpuCount = dev.gpu_count && dev.gpu_count > 1 ? `（${dev.gpu_count} 块 GPU）` : ''
  if (dev.cuda_available) {
    return `检测到 GPU${gpuCount}，硬件支持 CUDA 加速。Faster Whisper 可自动使用 GPU (CTranslate2)，本地推理延迟更低。`
  }
  return `检测到 GPU${gpuCount}，硬件支持图形/通用计算。未安装 CUDA 版 PyTorch，本地 STT 当前以 CPU 推理；在线 STT 在云端识别，不受本地设备限制。`
})

onMounted(() => {
  fetchSttInfo()
})
</script>

<template>
  <div :class="['settings-panel', 'animate-slide-up', { 'is-embedded': embedded }]">
    <!-- 加载 / 错误状态 -->
    <div v-if="sttLoading" class="settings-card">
      <div class="settings-card__body settings-card__body--compact stt-state">
        <Loader2 :size="20" class="spin-animation" />
        <span>正在检测 STT 引擎...</span>
      </div>
    </div>

    <div v-else-if="sttError" class="settings-card">
      <div class="settings-card__body settings-card__body--compact stt-state stt-state--error">
        <AlertCircle :size="18" />
        <span>{{ sttError }}</span>
        <LumiButton size="sm" @click="fetchSttInfo">重试</LumiButton>
      </div>
    </div>

    <template v-else>
      <!-- 引擎配置 -->
      <section class="settings-card settings-card--accent">
        <div class="settings-card__header">
          <Settings :size="18" />
          <span class="settings-card__title">引擎配置</span>
        </div>
        <div class="settings-card__body">
          <div class="settings-form-row">
            <label class="settings-form-label">STT 引擎</label>
            <select v-model="sttForm.engine" class="settings-form-select">
              <option v-for="opt in sttEngineOptions" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </div>

          <div class="settings-form-row">
            <label class="settings-form-label">模型</label>
            <select v-model="sttForm.model" class="settings-form-select">
              <option v-for="opt in sttModelOptions" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </div>

          <div class="settings-form-row">
            <label class="settings-form-label">识别语言</label>
            <select v-model="sttForm.language" class="settings-form-select">
              <option v-for="lang in modelStore.STT_LANGUAGES" :key="lang.value" :value="lang.value">
                {{ lang.label }}
              </option>
            </select>
          </div>

          <div class="settings-btn-row">
            <div
              v-if="sttSaveResult"
              :class="['settings-message', sttSaveResult.ok ? 'settings-message--success' : 'settings-message--error']"
            >
              <component :is="sttSaveResult.ok ? Check : AlertCircle" :size="14" />
              <span>{{ sttSaveResult.msg }}</span>
            </div>
            <LumiButton
              variant="primary"
              size="sm"
              :loading="sttSaving"
              :disabled="sttSaving"
              @click="saveSttConfig"
            >
              <Save :size="14" />
              <span>保存配置</span>
            </LumiButton>
          </div>
        </div>
      </section>

      <!-- 行为设置 -->
      <section class="settings-card">
        <div class="settings-card__header">
          <Mic :size="18" />
          <span class="settings-card__title">行为设置</span>
        </div>
        <div class="settings-card__body">
          <div class="settings-list-row">
            <div class="settings-list-row__info">
              <span class="settings-list-row__title">自动发送</span>
              <span class="settings-list-row__desc">语音识别完成后自动发送消息</span>
            </div>
            <div class="settings-list-row__control">
              <input
                type="checkbox"
                v-model="sttForm.autoSend"
                class="stt-checkbox"
              />
            </div>
          </div>

          <div v-if="sttForm.autoSend" class="settings-form-row">
            <label class="settings-form-label">自动发送延迟 ({{ delayLabel }})</label>
            <input
              v-model.number="sttForm.autoSendDelay"
              type="range"
              min="500"
              max="5000"
              step="100"
              class="settings-slider-row__input"
            />
          </div>
        </div>
      </section>

      <!-- 设备检测 -->
      <section class="settings-card">
        <div class="settings-card__header">
          <Cpu :size="18" />
          <span class="settings-card__title">设备检测</span>
        </div>
        <div class="settings-card__body settings-card__body--compact">
          <div class="settings-data-row">
            <span class="settings-data-row__label">计算设备</span>
            <span :class="['stt-badge', modelStore.sttDevice?.type === 'gpu' ? 'stt-badge--success' : 'stt-badge--primary']">
              {{ sttDeviceLabel }}
            </span>
          </div>
          <div class="settings-data-row">
            <span class="settings-data-row__label">设备名称</span>
            <span class="settings-data-row__value">{{ modelStore.sttDevice?.name || '未知' }}</span>
          </div>
          <div v-if="modelStore.sttDevice?.gpu_count && modelStore.sttDevice.gpu_count > 1" class="settings-data-row">
            <span class="settings-data-row__label">GPU 数量</span>
            <span class="settings-data-row__value">{{ modelStore.sttDevice.gpu_count }}</span>
          </div>
          <div v-if="modelStore.sttDevice?.cuda_available" class="settings-data-row">
            <span class="settings-data-row__label">CUDA 版本</span>
            <span class="settings-data-row__value">{{ modelStore.sttDevice.cuda_version || '未知' }}</span>
          </div>
          <p class="settings-card__hint" style="margin-top: var(--space-2); padding-top: var(--space-2); border-top: 1px solid var(--divider-soft);">
            {{ sttDeviceHint }}
          </p>
        </div>
      </section>

      <!-- 可用引擎 -->
      <section v-if="modelStore.sttEngines.length > 0" class="settings-card">
        <div class="settings-card__header">
          <Globe :size="18" />
          <span class="settings-card__title">可用引擎</span>
        </div>
        <div class="settings-card__body settings-card__body--compact">
          <div
            v-for="engine in modelStore.sttEngines"
            :key="engine.id"
            :class="['settings-list-row', { 'settings-list-row--disabled': !engine.available }]"
          >
            <div class="settings-list-row__info">
              <div class="stt-engine-name">
                <component
                  :is="engine.online ? Wifi : WifiOff"
                  :size="14"
                  :class="engine.online ? 'stt-engine-name__online' : 'stt-engine-name__offline'"
                />
                <span>{{ engine.name }}</span>
              </div>
              <span v-if="engine.description" class="settings-list-row__desc">
                {{ engine.description }}
              </span>
            </div>
            <span :class="['stt-badge', engine.available ? 'stt-badge--success' : 'stt-badge--danger']">
              <Check v-if="engine.available" :size="12" />
              <AlertCircle v-else :size="12" />
              <span>{{ engine.available ? '可用' : '未安装' }}</span>
            </span>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.stt-state {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  color: var(--text-muted);
  font-size: var(--text-base);
}

.stt-state--error {
  color: var(--lumi-danger);
  background: var(--lumi-danger-light);
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-4);
}

.stt-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-md);
}

.stt-badge--success {
  background: var(--lumi-success-light);
  color: var(--lumi-success);
}

.stt-badge--primary {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.stt-badge--danger {
  background: var(--lumi-danger-light);
  color: var(--lumi-danger);
}

.stt-engine-name {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--text-primary);
}

.stt-engine-name__online {
  color: var(--lumi-success);
}

.stt-engine-name__offline {
  color: var(--text-muted);
}

.stt-checkbox {
  width: 18px;
  height: 18px;
  accent-color: var(--lumi-primary);
  cursor: pointer;
}

.spin-animation {
  animation: lumi-spin 1s linear infinite;
}

/* ── 嵌入模式：去除 settings-card 边框 / 背景 / 蓝条 / 圆角 ── */
.is-embedded {
  max-width: none;
  margin: 0;
  padding: var(--space-6) var(--space-7);
  overflow: visible;
  flex: none;
  gap: var(--space-7);
}

.is-embedded .settings-card {
  background: transparent !important;
  border: none !important;
  border-radius: 0 !important;
  box-shadow: none !important;
}

.is-embedded .settings-card::before {
  display: none !important;
}

.is-embedded .settings-card:hover {
  box-shadow: none !important;
  border-color: transparent !important;
  transform: none !important;
}

.is-embedded .settings-card__header {
  padding-left: 0;
}

.is-embedded .settings-card__body {
  padding-left: 0;
  padding-right: 0;
}
</style>

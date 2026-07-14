<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  Settings,
  Cpu,
  Volume2,
  Palette,
  Loader2,
  AlertCircle,
  Check,
  Wifi,
  WifiOff,
  Save,
  Play
} from 'lucide-vue-next'
import { useModelStore } from '../../stores/model'
import { API_ENDPOINTS } from '../../config/api'
import type { TtsEngineInfo, TtsDeviceInfo, TtsBindingInfo } from './types'

const modelStore = useModelStore()

const ttsLoading = ref(false)
const ttsError = ref<string | null>(null)
const ttsEngines = ref<TtsEngineInfo[]>([])
const ttsDevice = ref<TtsDeviceInfo | null>(null)
const ttsBindings = ref<Record<string, TtsBindingInfo>>({})

const fetchTtsInfo = async () => {
  ttsLoading.value = true
  ttsError.value = null
  try {
    const token = await window.api.auth.getToken()
    const resp = await fetch(`${API_ENDPOINTS.V1}/chat/tts/engines`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!resp.ok) {
      throw new Error(`请求失败 (${resp.status})`)
    }
    const json = await resp.json()
    if (json.error) {
      throw new Error(json.error)
    }
    const data = json.data || {}
    ttsEngines.value = data.engines || []
    ttsDevice.value = data.device || null
    ttsBindings.value = data.avatar_bindings || {}
  } catch (e) {
    ttsError.value = e instanceof Error ? e.message : '获取 TTS 信息失败'
  } finally {
    ttsLoading.value = false
  }
}

const ttsConfigForm = ref({
  engine: 'auto',
  voice: '',
  model: '',
  apiKey: '',
  baseUrl: '',
  speed: 1.0,
})
const ttsConfigSaving = ref(false)
const ttsConfigTesting = ref(false)
const ttsTestText = '你好，这是语音合成测试。'
const ttsTestResult = ref<{ ok: boolean; msg: string } | null>(null)

const ttsNeedsApiKey = computed(() => {
  const opt = modelStore.TTS_ENGINE_OPTIONS.find(o => o.value === ttsConfigForm.value.engine)
  return opt?.needsApiKey ?? false
})

const ttsVoiceOptions = computed(() => {
  return modelStore.TTS_ENGINE_VOICES[ttsConfigForm.value.engine] || []
})

const ttsShowModel = computed(() => {
  return ['gemini', 'minimax', 'siliconflow'].includes(ttsConfigForm.value.engine)
})

const ttsShowSpeed = computed(() => {
  return ['minimax', 'siliconflow', 'sherpa-onnx'].includes(ttsConfigForm.value.engine)
})

const ttsShowBaseUrl = computed(() => {
  return ['gemini', 'minimax', 'siliconflow', 'fish-audio'].includes(ttsConfigForm.value.engine)
})

const onTtsEngineChange = () => {
  const engine = ttsConfigForm.value.engine
  const voices = modelStore.TTS_ENGINE_VOICES[engine] || []
  if (voices.length > 0 && voices[0].value) {
    ttsConfigForm.value.voice = voices[0].value
  } else {
    ttsConfigForm.value.voice = ''
  }
  const defaultModel = modelStore.TTS_ENGINE_DEFAULT_MODEL[engine]
  ttsConfigForm.value.model = defaultModel || ''
  ttsTestResult.value = null
}

const syncTtsConfigForm = () => {
  const cfg = modelStore.ttsConfig
  ttsConfigForm.value.engine = cfg.engine || cfg.provider || 'auto'
  ttsConfigForm.value.voice = cfg.voice || ''
  ttsConfigForm.value.model = cfg.model || ''
  ttsConfigForm.value.apiKey = cfg.apiKey || ''
  ttsConfigForm.value.baseUrl = cfg.baseUrl || ''
  ttsConfigForm.value.speed = cfg.speed ?? 1.0
}

const saveTtsConfig = async () => {
  ttsConfigSaving.value = true
  try {
    await modelStore.updateTTSConfig({
      engine: ttsConfigForm.value.engine,
      provider: ttsConfigForm.value.engine,
      voice: ttsConfigForm.value.voice,
      model: ttsConfigForm.value.model,
      apiKey: ttsConfigForm.value.apiKey,
      baseUrl: ttsConfigForm.value.baseUrl,
      speed: ttsConfigForm.value.speed,
      apiKeySet: !!ttsConfigForm.value.apiKey,
    })
    ttsTestResult.value = { ok: true, msg: '配置已保存' }
  } catch (e) {
    ttsTestResult.value = { ok: false, msg: e instanceof Error ? e.message : '保存失败' }
  } finally {
    ttsConfigSaving.value = false
  }
}

const testTtsSynthesize = async () => {
  ttsConfigTesting.value = true
  ttsTestResult.value = null
  try {
    const token = await window.api.auth.getToken()
    const resp = await fetch(`${API_ENDPOINTS.V1}/chat/tts/synthesize`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        text: ttsTestText,
        voice: ttsConfigForm.value.voice || 'default',
        engine: ttsConfigForm.value.engine,
        model: ttsConfigForm.value.model,
        speed: ttsConfigForm.value.speed,
        apiKey: ttsConfigForm.value.apiKey,
        baseUrl: ttsConfigForm.value.baseUrl,
      }),
    })
    if (!resp.ok) {
      const errJson = await resp.json().catch(() => null)
      throw new Error(errJson?.error || `请求失败 (${resp.status})`)
    }
    const blob = await resp.blob()
    if (blob.size === 0) {
      throw new Error('返回空音频')
    }
    const url = URL.createObjectURL(blob)
    const audio = new Audio(url)
    audio.onended = () => URL.revokeObjectURL(url)
    await audio.play()
    ttsTestResult.value = { ok: true, msg: '测试成功，正在播放' }
  } catch (e) {
    ttsTestResult.value = { ok: false, msg: e instanceof Error ? e.message : '测试失败' }
  } finally {
    ttsConfigTesting.value = false
  }
}

onMounted(() => {
  fetchTtsInfo()
  syncTtsConfigForm()
})
</script>

<template>
  <div class="tts-panel animate-slide-up">
    <div v-if="ttsLoading" class="tts-loading">
      <Loader2 :size="20" class="spin-animation" />
      <span>正在检测 TTS 引擎与设备...</span>
    </div>

    <div v-else-if="ttsError" class="tts-error">
      <AlertCircle :size="18" />
      <span>{{ ttsError }}</span>
      <button class="tts-retry-btn" @click="fetchTtsInfo">重试</button>
    </div>

    <template v-else>
      <div class="tts-card tts-config-card">
        <div class="tts-card-header">
          <Settings :size="18" />
          <span class="tts-card-title">引擎配置</span>
        </div>
        <div class="tts-config-form">
          <div class="tts-config-row">
            <label class="tts-config-label">TTS 引擎</label>
            <select
              v-model="ttsConfigForm.engine"
              class="tts-config-select"
              @change="onTtsEngineChange"
            >
              <option
                v-for="opt in modelStore.TTS_ENGINE_OPTIONS"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </option>
            </select>
          </div>

          <div v-if="ttsNeedsApiKey" class="tts-config-row">
            <label class="tts-config-label">API Key</label>
            <input
              v-model="ttsConfigForm.apiKey"
              type="password"
              class="tts-config-input"
              placeholder="输入 API Key"
            />
          </div>

          <div v-if="ttsVoiceOptions.length > 0" class="tts-config-row">
            <label class="tts-config-label">音色</label>
            <select v-model="ttsConfigForm.voice" class="tts-config-select">
              <option
                v-for="v in ttsVoiceOptions"
                :key="v.value"
                :value="v.value"
              >
                {{ v.label }}
              </option>
            </select>
          </div>

          <div
            v-else-if="ttsConfigForm.engine === 'fish-audio' || ttsConfigForm.engine === 'local'"
            class="tts-config-row"
          >
            <label class="tts-config-label">
              {{ ttsConfigForm.engine === 'fish-audio' ? 'Reference ID / 角色名' : '音色 ID' }}
            </label>
            <input
              v-model="ttsConfigForm.voice"
              type="text"
              class="tts-config-input"
              :placeholder="ttsConfigForm.engine === 'fish-audio' ? '32位十六进制 ID 或角色名称' : '系统语音 ID'"
            />
          </div>

          <div v-if="ttsShowModel" class="tts-config-row">
            <label class="tts-config-label">模型</label>
            <input
              v-model="ttsConfigForm.model"
              type="text"
              class="tts-config-input"
              :placeholder="modelStore.TTS_ENGINE_DEFAULT_MODEL[ttsConfigForm.engine] || '模型名称'"
            />
          </div>

          <div v-if="ttsShowSpeed" class="tts-config-row">
            <label class="tts-config-label">语速 ({{ ttsConfigForm.speed.toFixed(1) }}x)</label>
            <input
              v-model.number="ttsConfigForm.speed"
              type="range"
              min="0.5"
              max="2.0"
              step="0.1"
              class="tts-config-slider"
            />
          </div>

          <div v-if="ttsShowBaseUrl" class="tts-config-row">
            <label class="tts-config-label">API 地址（可选）</label>
            <input
              v-model="ttsConfigForm.baseUrl"
              type="text"
              class="tts-config-input"
              placeholder="留空使用默认地址"
            />
          </div>

          <div class="tts-config-actions">
            <button
              class="tts-btn tts-btn-primary"
              :disabled="ttsConfigSaving"
              @click="saveTtsConfig"
            >
              <Save :size="14" />
              <span>{{ ttsConfigSaving ? '保存中...' : '保存配置' }}</span>
            </button>
            <button
              class="tts-btn tts-btn-secondary"
              :disabled="ttsConfigTesting"
              @click="testTtsSynthesize"
            >
              <Loader2 v-if="ttsConfigTesting" :size="14" class="spin-animation" />
              <Play v-else :size="14" />
              <span>{{ ttsConfigTesting ? '测试中...' : '测试语音' }}</span>
            </button>
          </div>

          <div
            v-if="ttsTestResult"
            :class="['tts-test-result', ttsTestResult.ok ? 'success' : 'error']"
          >
            <component :is="ttsTestResult.ok ? Check : AlertCircle" :size="14" />
            <span>{{ ttsTestResult.msg }}</span>
          </div>
        </div>
      </div>

      <div class="tts-card">
        <div class="tts-card-header">
          <Cpu :size="18" />
          <span class="tts-card-title">设备检测</span>
        </div>
        <div class="tts-device-info">
          <div class="tts-device-row">
            <span class="tts-device-label">计算设备</span>
            <span :class="['tts-device-badge', ttsDevice?.type === 'gpu' ? 'gpu' : 'cpu']">
              {{ ttsDevice?.type === 'gpu' ? 'GPU (CUDA)' : 'CPU' }}
            </span>
          </div>
          <div class="tts-device-row">
            <span class="tts-device-label">设备名称</span>
            <span class="tts-device-value">{{ ttsDevice?.name || '未知' }}</span>
          </div>
          <div v-if="ttsDevice?.cuda_available" class="tts-device-row">
            <span class="tts-device-label">CUDA 版本</span>
            <span class="tts-device-value">{{ ttsDevice.cuda_version || '未知' }}</span>
          </div>
          <div class="tts-device-hint">
            {{ ttsDevice?.type === 'gpu'
              ? '检测到 GPU，可支持高性能 TTS 推理。当前本地 TTS 使用 pyttsx3 (CPU)，未来可扩展 GPU 加速引擎。'
              : '未检测到 GPU，本地 TTS 将使用 CPU 推理 (pyttsx3)。在线 TTS (Edge TTS) 不受设备限制。' }}
          </div>
        </div>
      </div>

      <div class="tts-card">
        <div class="tts-card-header">
          <Volume2 :size="18" />
          <span class="tts-card-title">可用引擎</span>
        </div>
        <div class="tts-engine-list">
          <div
            v-for="engine in ttsEngines"
            :key="engine.id"
            :class="['tts-engine-item', { unavailable: !engine.available }]"
          >
            <div class="tts-engine-info">
              <div class="tts-engine-name-row">
                <component
                  :is="engine.online ? Wifi : WifiOff"
                  :size="14"
                  :class="engine.online ? 'tts-online-icon' : 'tts-offline-icon'"
                />
                <span class="tts-engine-name">{{ engine.name }}</span>
              </div>
              <div class="tts-engine-desc">
                {{ engine.online ? '在线合成，需网络连接' : '离线合成，无需网络' }}
              </div>
            </div>
            <div :class="['tts-engine-status', engine.available ? 'available' : 'unavailable']">
              <Check v-if="engine.available" :size="14" />
              <AlertCircle v-else :size="14" />
              <span>{{ engine.available ? '可用' : '未安装' }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="tts-card">
        <div class="tts-card-header">
          <Palette :size="18" />
          <span class="tts-card-title">角色语音绑定</span>
        </div>
        <div class="tts-binding-list">
          <div
            v-for="(binding, modelId) in ttsBindings"
            :key="modelId"
            class="tts-binding-item"
          >
            <div class="tts-binding-model">{{ modelId }}</div>
            <div class="tts-binding-details">
              <div class="tts-binding-row">
                <span class="tts-binding-label">语音</span>
                <span class="tts-binding-value">{{ binding.voice }}</span>
              </div>
              <div class="tts-binding-row">
                <span class="tts-binding-label">语言</span>
                <span class="tts-binding-value">{{ binding.voice_lang }}</span>
              </div>
              <div class="tts-binding-row">
                <span class="tts-binding-label">默认表情</span>
                <span class="tts-binding-value">{{ binding.default_expression }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.tts-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  max-width: 640px;
}

.tts-loading {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-7) var(--space-5);
  justify-content: center;
  color: var(--text-muted);
  font-size: var(--text-base);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-lg);
}

.tts-error {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-4) var(--space-4);
  color: var(--lumi-danger);
  font-size: var(--text-base);
  background: var(--task-red-soft);
  border: 1px solid var(--task-red-border);
  border-radius: var(--radius-lg);
}

.tts-retry-btn {
  margin-left: auto;
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--lumi-primary);
  color: var(--text-inverse);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.tts-retry-btn:hover {
  background: var(--lumi-primary-hover);
}

.tts-card {
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.tts-card-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--workspace-border);
  color: var(--lumi-primary);
}

.tts-card-title {
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--text-primary);
}

.tts-device-info {
  padding: var(--space-4) var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.tts-device-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.tts-device-label {
  font-size: var(--text-base);
  color: var(--text-muted);
}

.tts-device-value {
  font-size: var(--text-base);
  color: var(--text-primary);
  font-weight: 500;
  font-family: monospace;
}

.tts-device-badge {
  font-size: var(--text-xs);
  font-weight: 600;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-md);
}

.tts-device-badge.gpu {
  background: var(--task-green-soft);
  color: var(--lumi-success);
}

.tts-device-badge.cpu {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.tts-device-hint {
  font-size: var(--text-sm);
  color: var(--text-muted);
  line-height: 1.6;
  padding-top: var(--space-2);
  border-top: 1px solid var(--divider-soft);
  margin-top: var(--space-1);
}

.tts-config-card {
  border: 1px solid var(--lumi-brand-border);
}

.tts-config-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-1) 0;
}

.tts-config-row {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.tts-config-label {
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--text-secondary);
}

.tts-config-select,
.tts-config-input {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-md);
  color: var(--text-primary);
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  outline: none;
  transition: border-color var(--transition-fast);
}

.tts-config-select:focus,
.tts-config-input:focus {
  border-color: var(--lumi-brand);
}

.tts-config-slider {
  width: 100%;
  height: var(--space-1);
  background: var(--border);
  border-radius: var(--space-1);
  outline: none;
  -webkit-appearance: none;
  appearance: none;
}

.tts-config-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: var(--space-4);
  height: var(--space-4);
  border-radius: var(--radius-full);
  background: var(--lumi-brand);
  cursor: pointer;
  transition: transform var(--duration-fast) var(--ease-in-out);
}

.tts-config-slider::-webkit-slider-thumb:hover {
  transform: scale(1.2);
}

.tts-config-actions {
  display: flex;
  gap: var(--space-3);
  margin-top: var(--space-1);
}

.tts-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  font-size: var(--text-base);
  font-weight: 500;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.tts-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.tts-btn-primary {
  background: var(--lumi-brand);
  color: var(--text-inverse);
}

.tts-btn-primary:hover:not(:disabled) {
  background: var(--lumi-brand-hover);
}

.tts-btn-secondary {
  background: var(--bg-secondary);
  color: var(--text-primary);
  border: 1px solid var(--border);
}

.tts-btn-secondary:hover:not(:disabled) {
  background: var(--surface-hover);
}

.tts-test-result {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  font-size: var(--text-base);
  border-radius: var(--radius-sm);
}

.tts-test-result.success {
  background: var(--lumi-success-light);
  color: var(--lumi-success);
}

.tts-test-result.error {
  background: var(--lumi-danger-light);
  color: var(--lumi-danger);
}

.tts-engine-list {
  padding: var(--space-2) 0;
}

.tts-engine-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  transition: background var(--transition-fast);
}

.tts-engine-item:not(:last-child) {
  border-bottom: 1px solid var(--divider-soft);
}

.tts-engine-item:hover {
  background: var(--workspace-hover);
}

.tts-engine-item.unavailable {
  opacity: 0.55;
}

.tts-engine-info {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.tts-engine-name-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.tts-online-icon {
  color: var(--lumi-success);
}

.tts-offline-icon {
  color: var(--text-muted);
}

.tts-engine-name {
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--text-primary);
}

.tts-engine-desc {
  font-size: var(--text-xs);
  color: var(--text-muted);
  padding-left: var(--space-5);
}

.tts-engine-status {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-sm);
  font-weight: 500;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-sm);
}

.tts-engine-status.available {
  background: var(--task-green-soft);
  color: var(--lumi-success);
}

.tts-engine-status.unavailable {
  background: var(--task-red-soft);
  color: var(--lumi-danger);
}

.tts-binding-list {
  padding: var(--space-2) 0;
}

.tts-binding-item {
  padding: var(--space-3) var(--space-4);
}

.tts-binding-item:not(:last-child) {
  border-bottom: 1px solid var(--divider-soft);
}

.tts-binding-model {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--lumi-primary);
  text-transform: capitalize;
  margin-bottom: var(--space-2);
}

.tts-binding-details {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.tts-binding-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.tts-binding-label {
  font-size: var(--text-sm);
  color: var(--text-muted);
  min-width: 60px;
}

.tts-binding-value {
  font-size: var(--text-sm);
  color: var(--text-primary);
  font-family: monospace;
}
</style>

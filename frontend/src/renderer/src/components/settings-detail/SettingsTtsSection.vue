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
import LumiButton from '../common/LumiButton.vue'
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
  <div class="settings-panel settings-panel--narrow animate-slide-up">
    <!-- 加载 / 错误状态 -->
    <div v-if="ttsLoading" class="settings-card">
      <div class="settings-card__body settings-card__body--compact tts-state">
        <Loader2 :size="20" class="spin-animation" />
        <span>正在检测 TTS 引擎与设备...</span>
      </div>
    </div>

    <div v-else-if="ttsError" class="settings-card">
      <div class="settings-card__body settings-card__body--compact tts-state tts-state--error">
        <AlertCircle :size="18" />
        <span>{{ ttsError }}</span>
        <LumiButton size="sm" @click="fetchTtsInfo">重试</LumiButton>
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
            <label class="settings-form-label">TTS 引擎</label>
            <select
              v-model="ttsConfigForm.engine"
              class="settings-form-select"
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

          <div v-if="ttsNeedsApiKey" class="settings-form-row">
            <label class="settings-form-label">API Key</label>
            <input
              v-model="ttsConfigForm.apiKey"
              type="password"
              class="settings-form-input"
              placeholder="输入 API Key"
            />
          </div>

          <div v-if="ttsVoiceOptions.length > 0" class="settings-form-row">
            <label class="settings-form-label">音色</label>
            <select v-model="ttsConfigForm.voice" class="settings-form-select">
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
            class="settings-form-row"
          >
            <label class="settings-form-label">
              {{ ttsConfigForm.engine === 'fish-audio' ? 'Reference ID / 角色名' : '音色 ID' }}
            </label>
            <input
              v-model="ttsConfigForm.voice"
              type="text"
              class="settings-form-input"
              :placeholder="ttsConfigForm.engine === 'fish-audio' ? '32位十六进制 ID 或角色名称' : '系统语音 ID'"
            />
          </div>

          <div v-if="ttsShowModel" class="settings-form-row">
            <label class="settings-form-label">模型</label>
            <input
              v-model="ttsConfigForm.model"
              type="text"
              class="settings-form-input"
              :placeholder="modelStore.TTS_ENGINE_DEFAULT_MODEL[ttsConfigForm.engine] || '模型名称'"
            />
          </div>

          <div v-if="ttsShowSpeed" class="settings-form-row">
            <label class="settings-form-label">语速 ({{ ttsConfigForm.speed.toFixed(1) }}x)</label>
            <input
              v-model.number="ttsConfigForm.speed"
              type="range"
              min="0.5"
              max="2.0"
              step="0.1"
              class="settings-slider-row__input"
            />
          </div>

          <div v-if="ttsShowBaseUrl" class="settings-form-row">
            <label class="settings-form-label">API 地址（可选）</label>
            <input
              v-model="ttsConfigForm.baseUrl"
              type="text"
              class="settings-form-input"
              placeholder="留空使用默认地址"
            />
          </div>

          <div class="settings-btn-row">
            <div
              v-if="ttsTestResult"
              :class="['settings-message', ttsTestResult.ok ? 'settings-message--success' : 'settings-message--error']"
            >
              <component :is="ttsTestResult.ok ? Check : AlertCircle" :size="14" />
              <span>{{ ttsTestResult.msg }}</span>
            </div>
            <LumiButton
              variant="primary"
              size="sm"
              :loading="ttsConfigSaving"
              :disabled="ttsConfigSaving"
              @click="saveTtsConfig"
            >
              <Save :size="14" />
              <span>保存配置</span>
            </LumiButton>
            <LumiButton
              variant="outline"
              size="sm"
              :loading="ttsConfigTesting"
              :disabled="ttsConfigTesting"
              @click="testTtsSynthesize"
            >
              <Play v-if="!ttsConfigTesting" :size="14" />
              <span>{{ ttsConfigTesting ? '测试中...' : '测试语音' }}</span>
            </LumiButton>
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
            <span :class="['tts-badge', ttsDevice?.type === 'gpu' ? 'tts-badge--success' : 'tts-badge--primary']">
              {{ ttsDevice?.type === 'gpu' ? 'GPU (CUDA)' : 'CPU' }}
            </span>
          </div>
          <div class="settings-data-row">
            <span class="settings-data-row__label">设备名称</span>
            <span class="settings-data-row__value">{{ ttsDevice?.name || '未知' }}</span>
          </div>
          <div v-if="ttsDevice?.cuda_available" class="settings-data-row">
            <span class="settings-data-row__label">CUDA 版本</span>
            <span class="settings-data-row__value">{{ ttsDevice.cuda_version || '未知' }}</span>
          </div>
          <p class="settings-card__hint" style="margin-top: var(--space-2); padding-top: var(--space-2); border-top: 1px solid var(--divider-soft);">
            {{ ttsDevice?.type === 'gpu'
              ? '检测到 GPU，可支持高性能 TTS 推理。当前本地 TTS 使用 pyttsx3 (CPU)，未来可扩展 GPU 加速引擎。'
              : '未检测到 GPU，本地 TTS 将使用 CPU 推理 (pyttsx3)。在线 TTS (Edge TTS) 不受设备限制。' }}
          </p>
        </div>
      </section>

      <!-- 可用引擎 -->
      <section class="settings-card">
        <div class="settings-card__header">
          <Volume2 :size="18" />
          <span class="settings-card__title">可用引擎</span>
        </div>
        <div class="settings-card__body settings-card__body--compact">
          <div
            v-for="engine in ttsEngines"
            :key="engine.id"
            :class="['settings-list-row', { 'settings-list-row--disabled': !engine.available }]"
          >
            <div class="settings-list-row__info">
              <div class="tts-engine-name">
                <component
                  :is="engine.online ? Wifi : WifiOff"
                  :size="14"
                  :class="engine.online ? 'tts-engine-name__online' : 'tts-engine-name__offline'"
                />
                <span>{{ engine.name }}</span>
              </div>
              <span class="settings-list-row__desc">
                {{ engine.online ? '在线合成，需网络连接' : '离线合成，无需网络' }}
              </span>
            </div>
            <span :class="['tts-badge', engine.available ? 'tts-badge--success' : 'tts-badge--danger']">
              <Check v-if="engine.available" :size="12" />
              <AlertCircle v-else :size="12" />
              <span>{{ engine.available ? '可用' : '未安装' }}</span>
            </span>
          </div>
        </div>
      </section>

      <!-- 角色语音绑定 -->
      <section class="settings-card">
        <div class="settings-card__header">
          <Palette :size="18" />
          <span class="settings-card__title">角色语音绑定</span>
        </div>
        <div class="settings-card__body settings-card__body--compact">
          <div
            v-for="(binding, modelId) in ttsBindings"
            :key="modelId"
            class="settings-list-row settings-list-row--stack"
          >
            <div class="settings-list-row__title">{{ modelId }}</div>
            <div class="tts-binding-meta">
              <span class="tts-binding-meta__item">
                <span class="tts-binding-meta__label">语音</span>
                <span class="tts-binding-meta__value">{{ binding.voice }}</span>
              </span>
              <span class="tts-binding-meta__item">
                <span class="tts-binding-meta__label">语言</span>
                <span class="tts-binding-meta__value">{{ binding.voice_lang }}</span>
              </span>
              <span class="tts-binding-meta__item">
                <span class="tts-binding-meta__label">默认表情</span>
                <span class="tts-binding-meta__value">{{ binding.default_expression }}</span>
              </span>
            </div>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.tts-state {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  color: var(--text-muted);
  font-size: var(--text-base);
}

.tts-state--error {
  color: var(--lumi-danger);
  background: var(--lumi-danger-light);
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-4);
}

.tts-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-md);
}

.tts-badge--primary {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.tts-badge--success {
  background: var(--lumi-success-light);
  color: var(--lumi-success);
}

.tts-badge--danger {
  background: var(--lumi-danger-light);
  color: var(--lumi-danger);
}

.tts-engine-name {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--text-primary);
}

.tts-engine-name__online {
  color: var(--lumi-success);
}

.tts-engine-name__offline {
  color: var(--text-muted);
}

.tts-binding-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.tts-binding-meta__item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
}

.tts-binding-meta__label {
  color: var(--text-muted);
}

.tts-binding-meta__value {
  color: var(--text-primary);
  font-family: var(--font-mono);
}

.spin-animation {
  animation: lumi-spin 1s linear infinite;
}
</style>

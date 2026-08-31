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
  Play,
  Languages
} from 'lucide-vue-next'
import { useModelStore } from '../../stores/model'
import { useToast } from '../../composables/useToast'
import { API_ENDPOINTS } from '../../config/api'
import LumiButton from '../common/LumiButton.vue'
import type { TtsEngineInfo, TtsDeviceInfo, TtsBindingInfo } from './types'

const props = defineProps<{
  embedded?: boolean
}>()

const modelStore = useModelStore()
const toast = useToast()

/** TTS 语言选项（v0.5 决策：auto/zh/en/ja/ko/yue 全量） */
const TTS_LANGUAGE_OPTIONS = [
  { value: 'auto', label: '自动检测' },
  { value: 'zh', label: '中文' },
  { value: 'en', label: 'English' },
  { value: 'ja', label: '日本語' },
  { value: 'ko', label: '한국어' },
  { value: 'yue', label: '粵語' },
] as const

const LANG_LABELS: Record<string, string> = Object.fromEntries(
  TTS_LANGUAGE_OPTIONS.map(o => [o.value, o.label]),
)

const ttsLoading = ref(false)
const ttsError = ref<string | null>(null)
const ttsEngines = ref<TtsEngineInfo[]>([])
const ttsDevice = ref<TtsDeviceInfo | null>(null)
const ttsBindings = ref<Record<string, TtsBindingInfo>>({})
/** 翻译管线开关（voice_config.translation.enabled，默认关闭） */
const translationEnabled = ref(false)

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
    // 同步读取全局语音配置（lang / translation，config_items 权威源）
    const cfgResp = await fetch(`${API_ENDPOINTS.V1}/voice/config`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (cfgResp.ok) {
      const cfgJson = await cfgResp.json()
      const cfg = cfgJson?.data || {}
      if (cfg.tts?.lang) ttsConfigForm.value.lang = cfg.tts.lang
      translationEnabled.value = !!cfg.translation?.enabled
    }
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
  lang: 'auto' as string,
})
const ttsConfigSaving = ref(false)
const ttsConfigTesting = ref(false)
const ttsTestText = '你好，这是语音合成测试。'
const ttsTestResult = ref<{ ok: boolean; msg: string } | null>(null)

/** 当前引擎的能力声明（后端 CAPABILITIES，G1：替代前端硬编码） */
const ttsEngineCaps = computed<TtsEngineInfo | null>(() => {
  return ttsEngines.value.find(e => e.id === ttsConfigForm.value.engine) || null
})

/** 引擎选项：优先后端 capabilities 动态生成，未加载时回退 store 硬编码 */
const ttsEngineOptions = computed(() => {
  if (ttsEngines.value.length > 0) {
    return [
      { value: 'auto', label: '自动（按降级链选择）', needsApiKey: false },
      ...ttsEngines.value.map(e => ({
        value: e.id,
        label: e.name || e.id,
        needsApiKey: e.needs_api_key ?? false,
      })),
    ]
  }
  return modelStore.TTS_ENGINE_OPTIONS
})

const ttsNeedsApiKey = computed(() => {
  const opt = ttsEngineOptions.value.find(o => o.value === ttsConfigForm.value.engine)
  return opt?.needsApiKey ?? false
})

/** 音色下拉（级联刷新核心）：capabilities.voices 按当前语言过滤 */
const ttsVoiceOptions = computed(() => {
  const caps = ttsEngineCaps.value
  if (!caps) return []
  const voices = (caps as { voices?: Array<{ value: string; label: string; langs?: string[] }> }).voices || []
  const lang = ttsConfigForm.value.lang
  if (lang === 'auto') return voices
  return voices.filter(v => !v.langs || v.langs.includes(lang))
})

/** 音色交互模式：list（下拉）/ dynamic（系统枚举）/ input（自由输入） */
const ttsVoiceMode = computed(() => {
  return ttsEngineCaps.value?.voice_mode || 'list'
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

/** 语言能力校验：显式引擎不支持目标语言 → 消息通知（§11.3） */
const checkLangSupport = (): boolean => {
  const lang = ttsConfigForm.value.lang
  const engine = ttsConfigForm.value.engine
  if (lang === 'auto' || engine === 'auto') return true
  const caps = ttsEngineCaps.value as { languages?: string[] } | null
  if (!caps?.languages?.length) return true
  if (!caps.languages.includes(lang)) {
    const engineName = ttsEngineCaps.value?.name || engine
    toast.warning(
      `当前语音引擎 ${engineName} 不支持${LANG_LABELS[lang] || lang}。可更换支持该语言的引擎，或开启翻译管线（翻译后合成）`,
    )
    return false
  }
  return true
}

/** 引擎切换 → 级联刷新（模型/音色/语言校验，§11.2） */
const onTtsEngineChange = () => {
  const engine = ttsConfigForm.value.engine
  const caps = ttsEngines.value.find(e => e.id === engine) as
    | { voices?: Array<{ value: string }>; default_voice?: string; default_model?: string }
    | undefined
  // 音色重置：该引擎默认音色或第一个音色
  const voices = caps?.voices || []
  ttsConfigForm.value.voice = caps?.default_voice || (voices[0]?.value ?? '')
  // 模型重置：引擎默认模型
  ttsConfigForm.value.model = caps?.default_model || modelStore.TTS_ENGINE_DEFAULT_MODEL[engine] || ''
  // 语言能力校验（不支持时通知，保留用户选择）
  checkLangSupport()
  ttsTestResult.value = null
}

/** 语言切换 → 音色联动过滤 + 能力校验 */
const onTtsLangChange = () => {
  const supported = checkLangSupport()
  // 音色重置为该语言下第一个可用音色（保持联动）
  const voices = ttsVoiceOptions.value
  if (voices.length > 0) {
    if (!voices.some(v => v.value === ttsConfigForm.value.voice)) {
      ttsConfigForm.value.voice = voices[0].value
    }
  } else if (supported && ttsVoiceMode.value === 'list') {
    ttsConfigForm.value.voice = ''
  }
}

/** 翻译管线开关切换（默认关，写 voice_config.translation） */
const onTranslationToggle = async () => {
  const next = !translationEnabled.value
  try {
    const token = await window.api.auth.getToken()
    const resp = await fetch(`${API_ENDPOINTS.V1}/voice/config`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ translation: { enabled: next } }),
    })
    if (!resp.ok) throw new Error(`请求失败 (${resp.status})`)
    translationEnabled.value = next
    toast.success(next ? '翻译管线已开启：语言不匹配时自动翻译后合成' : '翻译管线已关闭')
  } catch (e) {
    toast.error(e instanceof Error ? e.message : '翻译管线设置失败')
  }
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
    // 同步写后端语音画像权威源（voice_config.tts.lang）
    const token = await window.api.auth.getToken()
    await fetch(`${API_ENDPOINTS.V1}/voice/config`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        tts: {
          engine: ttsConfigForm.value.engine,
          voice: ttsConfigForm.value.voice,
          model: ttsConfigForm.value.model,
          lang: ttsConfigForm.value.lang,
          speed: ttsConfigForm.value.speed,
        },
      }),
    })
    ttsTestResult.value = { ok: true, msg: '配置已保存' }
    toast.success('TTS 配置已保存')
  } catch (e) {
    ttsTestResult.value = { ok: false, msg: e instanceof Error ? e.message : '保存失败' }
    toast.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    ttsConfigSaving.value = false
  }
}

/** 信封错误解析（统一 error 对象/旧字符串兼容） */
const parseEnvelopeError = (errJson: unknown, status: number): string => {
  const ej = errJson as { error?: string | { code?: string; message?: string }; message?: string } | null
  if (!ej) return `请求失败 (${status})`
  if (typeof ej.error === 'string') return ej.error
  return ej.error?.message || ej.message || `请求失败 (${status})`
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
        lang: ttsConfigForm.value.lang,
      }),
    })
    if (!resp.ok) {
      const errJson = await resp.json().catch(() => null)
      const errMsg = parseEnvelopeError(errJson, resp.status)
      // LANG_NOT_SUPPORTED → 行动建议通知（§11.3）
      const errCode = (errJson as { error?: { code?: string } } | null)?.error?.code
      if (errCode === 'LANG_NOT_SUPPORTED') {
        toast.warning(`${errMsg}。可更换引擎/音色，或开启翻译管线（翻译后合成）`)
      } else {
        toast.error(errMsg)
      }
      throw new Error(errMsg)
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
  <div :class="['settings-panel', 'animate-slide-up', { 'is-embedded': embedded }]">
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
                v-for="opt in ttsEngineOptions"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </option>
            </select>
          </div>

          <div class="settings-form-row">
            <label class="settings-form-label">语言</label>
            <select
              v-model="ttsConfigForm.lang"
              class="settings-form-select"
              @change="onTtsLangChange"
            >
              <option
                v-for="opt in TTS_LANGUAGE_OPTIONS"
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
            v-else-if="ttsVoiceMode === 'input' || ttsVoiceMode === 'dynamic'"
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

          <!-- 翻译管线开关（v0.5：默认关闭，语言不匹配时通知引导开启） -->
          <div class="settings-form-row tts-translation-row">
            <div class="tts-translation-row__info">
              <label class="settings-form-label">
                <Languages :size="14" />
                <span>翻译管线</span>
              </label>
              <span class="tts-translation-row__hint">
                开启后，目标语言与引擎/音色语言不匹配时自动翻译再合成（LLM 翻译，消耗 token）
              </span>
            </div>
            <button
              type="button"
              class="tts-toggle"
              role="switch"
              :aria-checked="translationEnabled"
              @click="onTranslationToggle"
            >
              <span class="tts-toggle__thumb" />
            </button>
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
              {{ ttsDeviceLabel }}
            </span>
          </div>
          <div class="settings-data-row">
            <span class="settings-data-row__label">设备名称</span>
            <span class="settings-data-row__value">{{ ttsDevice?.name || '未知' }}</span>
          </div>
          <div v-if="ttsDevice?.gpu_count && ttsDevice.gpu_count > 1" class="settings-data-row">
            <span class="settings-data-row__label">GPU 数量</span>
            <span class="settings-data-row__value">{{ ttsDevice.gpu_count }}</span>
          </div>
          <div v-if="ttsDevice?.cuda_available" class="settings-data-row">
            <span class="settings-data-row__label">CUDA 版本</span>
            <span class="settings-data-row__value">{{ ttsDevice.cuda_version || '未知' }}</span>
          </div>
          <p class="settings-card__hint" style="margin-top: var(--space-2); padding-top: var(--space-2); border-top: 1px solid var(--divider-soft);">
            {{ ttsDeviceHint }}
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

/* ── 翻译管线开关（minimalist，颜色全走 CSS 变量） ── */

.tts-translation-row {
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
}

.tts-translation-row__info {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.tts-translation-row__info .settings-form-label {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  margin-bottom: 0;
}

.tts-translation-row__hint {
  font-size: var(--font-size-xs, 12px);
  color: var(--text-tertiary);
  line-height: 1.4;
}

.tts-toggle {
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

.tts-toggle__thumb {
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

.tts-toggle[aria-checked='true'] {
  background: var(--accent-color);
  border-color: var(--accent-color);
}

.tts-toggle[aria-checked='true'] .tts-toggle__thumb {
  transform: translateX(16px);
  background: var(--bg-primary);
}

.tts-toggle:hover {
  border-color: var(--accent-color);
}
</style>

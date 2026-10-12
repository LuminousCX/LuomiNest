<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Info,
  ChevronRight,
  Check,
  AlertCircle,
  AlertTriangle,
  Loader2,
} from 'lucide-vue-next'
import { useModelStore } from '../../stores/model'
import { useApi } from '../../composables/useApi'
import { useToast } from '../../composables/useToast'

/**
 * 双脑路由设置（辰汐生态打通 W5）：
 * - 快脑槽 / 慢脑槽：值为 "provider_id/model_id"（空 = 关闭），走 PATCH /models/config；
 * - 选项 = 已启用供应商的模型列表（优先 selectedModels，回退 provider.models），
 *   按供应商 optgroup 分组；任意供应商（含云端 DeepSeek 等）均可选，无模型名特判；
 * - 皮套工具：注入开关 + motion 注册表（逗号分隔输入）+ 高级折叠项（翻译覆盖路径）；
 * - 完全信任模式（W6 补 T2 入口）：独立端点 GET/PATCH /chat/permission/trusted-mode，
 *   不随「保存」按钮提交（后端即时生效）。
 */
const modelStore = useModelStore()
const { apiGet, apiPatch } = useApi()
const toast = useToast()
const { t } = useI18n()

const showInfo = ref(false)
const showAdvanced = ref(false)
const saveStatus = ref<'idle' | 'saving' | 'saved' | 'error'>('idle')

// ── 表单状态 ──
const fastBrain = ref('')
const slowBrain = ref('')
const avatarToolsEnabled = ref(false)
/** motion 注册表的逗号分隔文本（保存时解析为数组） */
const motionRegistryText = ref('')
const translationOverride = ref('')

// ── 完全信任模式（T2 信任档：所有工具免确认；独立端点读写，不进「保存」表单） ──
const trustedMode = ref(false)
const trustedModeBusy = ref(false)

// ── 槽位下拉选项：所有供应商 × 其模型列表，值 = "provider_id/model_id" ──
interface SlotGroup {
  providerId: string
  providerName: string
  models: { id: string; name: string }[]
}

const slotGroups = computed<SlotGroup[]>(() =>
  modelStore.providers
    .map((p) => ({
      providerId: p.id,
      providerName: p.name,
      // 与 useProviderModelFetch 同一取数口径：优先 selectedModels，回退已拉取的 models
      models:
        p.selectedModels.length > 0
          ? p.selectedModels.map((id) => ({ id, name: id }))
          : p.models,
    }))
    .filter((g) => g.models.length > 0),
)

/** 回显兜底：已保存值暂不在选项中（模型列表未拉取等）时补一条原值选项，避免下拉显示空白 */
const isSlotMissing = (value: string) =>
  !!value && !slotGroups.value.some((g) => g.models.some((m) => `${g.providerId}/${m.id}` === value))
const fastBrainMissing = computed(() => isSlotMissing(fastBrain.value))
const slowBrainMissing = computed(() => isSlotMissing(slowBrain.value))

/** 无任何可用模型时的提示 */
const noModels = computed(() => slotGroups.value.length === 0)

// ── 保存 ──
const parseMotionRegistry = (text: string): string[] =>
  text.split(/[,，、]/).map((s) => s.trim()).filter(Boolean)

const handleSave = async () => {
  saveStatus.value = 'saving'
  try {
    await modelStore.updateModelConfig({
      fastBrain: fastBrain.value.trim(),
      slowBrain: slowBrain.value.trim(),
      avatarToolsEnabled: avatarToolsEnabled.value,
      avatarMotionRegistry: parseMotionRegistry(motionRegistryText.value),
      avatarTranslationOverride: translationOverride.value.trim(),
    })
    saveStatus.value = 'saved'
    toast.success(t('aiModel.dualBrain.savedToast'))
    setTimeout(() => { saveStatus.value = 'idle' }, 2000)
  } catch {
    saveStatus.value = 'error'
    toast.error(t('aiModel.dualBrain.saveErrorToast'))
    setTimeout(() => { saveStatus.value = 'idle' }, 3000)
  }
}

// ── 回显（设置页已先行 fetchModelConfig，与兄弟组件同款 onMounted 读取） ──
onMounted(() => {
  const cfg = modelStore.modelConfig
  fastBrain.value = cfg.fastBrain || ''
  slowBrain.value = cfg.slowBrain || ''
  avatarToolsEnabled.value = cfg.avatarToolsEnabled ?? false
  motionRegistryText.value = (cfg.avatarMotionRegistry || []).join(', ')
  translationOverride.value = cfg.avatarTranslationOverride || ''
  void fetchTrustedMode()
})

// ── 完全信任模式：独立端点读写（后端 set_trusted_mode 内存先行生效） ──
// useApi.request 已自动解包 ok() 信封（code===0 返回 data 负载），此处直取字段
const fetchTrustedMode = async () => {
  try {
    const payload = await apiGet<{ enabled?: boolean }>('/chat/permission/trusted-mode')
    trustedMode.value = !!payload?.enabled
  } catch {
    // 读取失败保持关闭态（默认 false），不阻塞设置页
  }
}

const handleTrustedModeToggle = async () => {
  if (trustedModeBusy.value) return
  const next = !trustedMode.value
  trustedModeBusy.value = true
  try {
    const payload = await apiPatch<{ enabled?: boolean; persisted?: boolean }>(
      '/chat/permission/trusted-mode',
      { enabled: next },
    )
    trustedMode.value = !!payload?.enabled
    // 持久化失败时后端内存态已生效但不落库（重启回落 false）：明确告知用户
    if (payload?.enabled && payload?.persisted === false) {
      toast.warning(t('aiModel.dualBrain.trustedModePersistWarn'))
    } else {
      toast.success(t(next ? 'aiModel.dualBrain.trustedModeOnToast' : 'aiModel.dualBrain.trustedModeOffToast'))
    }
  } catch {
    toast.error(t('aiModel.dualBrain.saveErrorToast'))
  } finally {
    trustedModeBusy.value = false
  }
}
</script>

<template>
  <div class="content-section lumi-stack-5">
    <div class="section-header">
      <div class="section-header-left lumi-row-3">
        <div class="section-header-text">
          <h3 class="lumi-section-title">{{ t('aiModel.dualBrain.title') }}</h3>
          <span class="section-tag">{{ t('aiModel.dualBrain.tag') }}</span>
        </div>
      </div>
      <button
        :class="['info-btn', { active: showInfo }]"
        @click="showInfo = !showInfo"
      >
        <Info :size="16" />
      </button>
    </div>
    <Transition name="info-expand">
      <div v-if="showInfo" class="section-info-panel">
        <p>{{ t('aiModel.dualBrain.info') }}</p>
        <p class="info-tip">{{ t('aiModel.dualBrain.infoTip') }}</p>
      </div>
    </Transition>

    <div class="config-form">
      <span v-if="noModels" class="form-hint hint-warn">
        {{ t('aiModel.dualBrain.noModelsHint') }}
      </span>

      <!-- 快脑（主对话）槽 -->
      <div class="form-group">
        <label class="form-label">{{ t('aiModel.dualBrain.fastBrainLabel') }}</label>
        <div class="form-select-wrap">
          <select v-model="fastBrain" class="form-select">
            <option value="">{{ t('aiModel.dualBrain.slotOff') }}</option>
            <optgroup
              v-for="g in slotGroups"
              :key="g.providerId"
              :label="g.providerName"
            >
              <option
                v-for="m in g.models"
                :key="`${g.providerId}/${m.id}`"
                :value="`${g.providerId}/${m.id}`"
              >
                {{ m.name === m.id ? m.id : `${m.name} (${m.id})` }}
              </option>
            </optgroup>
            <optgroup v-if="fastBrainMissing" :label="t('aiModel.dualBrain.missingGroup')">
              <option :value="fastBrain">{{ fastBrain }}</option>
            </optgroup>
          </select>
          <ChevronRight :size="14" class="select-icon" />
        </div>
        <span class="form-hint">{{ t('aiModel.dualBrain.fastBrainHint') }}</span>
      </div>

      <!-- 慢脑（派发推理）槽 -->
      <div class="form-group">
        <label class="form-label">{{ t('aiModel.dualBrain.slowBrainLabel') }}</label>
        <div class="form-select-wrap">
          <select v-model="slowBrain" class="form-select">
            <option value="">{{ t('aiModel.dualBrain.slotOff') }}</option>
            <optgroup
              v-for="g in slotGroups"
              :key="g.providerId"
              :label="g.providerName"
            >
              <option
                v-for="m in g.models"
                :key="`${g.providerId}/${m.id}`"
                :value="`${g.providerId}/${m.id}`"
              >
                {{ m.name === m.id ? m.id : `${m.name} (${m.id})` }}
              </option>
            </optgroup>
            <optgroup v-if="slowBrainMissing" :label="t('aiModel.dualBrain.missingGroup')">
              <option :value="slowBrain">{{ slowBrain }}</option>
            </optgroup>
          </select>
          <ChevronRight :size="14" class="select-icon" />
        </div>
        <span class="form-hint">{{ t('aiModel.dualBrain.slowBrainHint') }}</span>
      </div>

      <!-- 皮套工具注入开关 -->
      <div class="form-group toggle-row">
        <div class="toggle-info">
          <label class="form-label">{{ t('aiModel.dualBrain.avatarToolsLabel') }}</label>
          <span class="form-hint">{{ t('aiModel.dualBrain.avatarToolsHint') }}</span>
        </div>
        <button
          type="button"
          class="brain-toggle"
          role="switch"
          :aria-checked="avatarToolsEnabled"
          @click="avatarToolsEnabled = !avatarToolsEnabled"
        >
          <span class="brain-toggle__thumb" />
        </button>
      </div>

      <!-- motion 注册表（逗号分隔输入） -->
      <div class="form-group">
        <label class="form-label">{{ t('aiModel.dualBrain.motionRegistryLabel') }}</label>
        <input
          v-model="motionRegistryText"
          type="text"
          class="form-input"
          :placeholder="t('aiModel.dualBrain.motionRegistryPlaceholder')"
        />
        <span class="form-hint">{{ t('aiModel.dualBrain.motionRegistryHint') }}</span>
      </div>

      <!-- 完全信任模式（T2 信任档）：即时生效，独立端点，不随「保存」提交 -->
      <div :class="['form-group', 'toggle-row', 'trusted-row', { 'trusted-on': trustedMode }]">
        <div class="toggle-info">
          <label class="form-label">{{ t('aiModel.dualBrain.trustedModeLabel') }}</label>
          <span class="form-hint">{{ t('aiModel.dualBrain.trustedModeHint') }}</span>
          <span class="trusted-warn">
            <AlertTriangle :size="13" />
            {{ t('aiModel.dualBrain.trustedModeWarn') }}
          </span>
        </div>
        <button
          type="button"
          class="brain-toggle trusted-toggle"
          role="switch"
          :aria-checked="trustedMode"
          :disabled="trustedModeBusy"
          @click="handleTrustedModeToggle"
        >
          <span class="brain-toggle__thumb" />
        </button>
      </div>

      <!-- 高级折叠项：翻译映射覆盖路径 -->
      <div class="form-group">
        <button
          type="button"
          :class="['advanced-toggle', { open: showAdvanced }]"
          @click="showAdvanced = !showAdvanced"
        >
          <ChevronRight :size="14" class="advanced-chevron" />
          {{ t('aiModel.dualBrain.advancedTitle') }}
        </button>
        <div v-if="showAdvanced" class="advanced-panel">
          <label class="form-label">{{ t('aiModel.dualBrain.translationOverrideLabel') }}</label>
          <input
            v-model="translationOverride"
            type="text"
            class="form-input"
            :placeholder="t('aiModel.dualBrain.translationOverridePlaceholder')"
          />
          <span class="form-hint">{{ t('aiModel.dualBrain.translationOverrideHint') }}</span>
        </div>
      </div>

      <button
        :class="['save-btn', { saving: saveStatus === 'saving', saved: saveStatus === 'saved', error: saveStatus === 'error' }]"
        :disabled="saveStatus === 'saving'"
        @click="handleSave"
      >
        <Loader2 v-if="saveStatus === 'saving'" :size="16" class="spin-animation" />
        <Check v-else-if="saveStatus === 'saved'" :size="16" />
        <AlertCircle v-else-if="saveStatus === 'error'" :size="16" />
        <Check v-else :size="16" />
        {{ saveStatus === 'saving' ? t('aiModel.common.saving') : saveStatus === 'saved' ? t('aiModel.common.saved') : saveStatus === 'error' ? t('aiModel.common.saveFailed') : t('aiModel.common.saveConfig') }}
      </button>
    </div>
  </div>
</template>

<style scoped src="./ai-model-shared.css"></style>
<style scoped>
.config-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  max-width: 560px;
}

.form-hint {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-top: calc(var(--space-1) * -1);
}

.hint-warn {
  color: var(--lumi-amber);
}

.select-icon {
  position: absolute;
  right: var(--space-3);
  color: var(--text-muted);
  pointer-events: none;
  transform: rotate(90deg);
}

/* 文本输入框（motion 注册表 / 翻译覆盖路径），与 form-select 同款观感 */
.form-input {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-md);
  font-size: var(--text-base);
  color: var(--text-primary);
  transition: all var(--transition-normal);
}

.form-input:focus {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 var(--space-1) var(--lumi-primary-glow);
  outline: none;
}

.form-input::placeholder {
  color: var(--text-muted);
}

/* 皮套工具开关行（开关居右，样式对齐 TTS 翻译开关；覆盖全局 .form-group 的纵向排列） */
.toggle-row {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.toggle-info {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.toggle-info .form-hint {
  margin-top: 0;
}

.brain-toggle {
  position: relative;
  width: 36px;
  height: 20px;
  flex: none;
  border-radius: 999px;
  border: 1px solid var(--workspace-border);
  background: var(--workspace-panel);
  cursor: pointer;
  padding: 0;
  transition: background var(--duration-fast) ease-in-out,
    border-color var(--duration-fast) ease-in-out;
}

.brain-toggle__thumb {
  position: absolute;
  top: 1px;
  left: 1px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--text-primary);
  transition: transform var(--duration-fast) ease-in-out,
    background var(--duration-fast) ease-in-out;
}

.brain-toggle[aria-checked='true'] {
  background: var(--lumi-primary);
  border-color: var(--lumi-primary);
}

.brain-toggle[aria-checked='true'] .brain-toggle__thumb {
  transform: translateX(16px);
  background: var(--text-inverse);
}

.brain-toggle:hover {
  border-color: var(--lumi-primary);
}

/* 完全信任模式行：开启时红色描边 + 警示文案，醒目提示高危语义 */
.trusted-row {
  padding: var(--space-3);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-md);
  transition: border-color var(--transition-normal);
}

.trusted-row.trusted-on {
  border-color: var(--lumi-danger);
}

.trusted-warn {
  display: flex;
  align-items: flex-start;
  gap: var(--space-1);
  font-size: var(--text-xs);
  color: var(--lumi-danger);
}

.trusted-warn svg {
  flex: none;
  margin-top: 2px;
}

.trusted-toggle:disabled {
  cursor: wait;
  opacity: 0.6;
}

/* 高级折叠项 */
.advanced-toggle {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) 0;
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-muted);
  transition: color var(--transition-normal);
}

.advanced-toggle:hover {
  color: var(--lumi-primary);
}

.advanced-chevron {
  transition: transform var(--transition-normal);
}

.advanced-toggle.open .advanced-chevron {
  transform: rotate(90deg);
}

.advanced-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  margin-top: var(--space-2);
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-md);
}

.advanced-panel .form-hint {
  margin-top: 0;
}
</style>

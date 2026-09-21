<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Cpu, Image as ImageIcon, RefreshCw, RotateCcw,
  AlertCircle, CheckCircle2, XCircle, Clock,
  Sparkles, ShieldCheck, ShieldAlert, HelpCircle,
} from 'lucide-vue-next'
import { usePlatformStore } from '../../stores/platform'
import type { PlatformInstance, PlatformModelConfig } from '../../types'
import LumiModal from '../../components/common/LumiModal.vue'
import LumiButton from '../../components/common/LumiButton.vue'
import LumiInput from '../../components/common/LumiInput.vue'
import { createLuomiNestRendererLogger } from '../../utils/logger'

const logger = createLuomiNestRendererLogger('Platform')

const store = usePlatformStore()
const { t } = useI18n()

const props = defineProps<{
  visible: boolean
  instance: PlatformInstance | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'saved'): void
}>()

const editConfig = ref<Record<string, any>>({})
const modelConfigLoading = ref(false)
const modelConfigSaving = ref(false)
const modelEditConfig = ref<PlatformModelConfig>({})
// 高风险平台操作开关（W3-3 风险闸门）：绑定实例 config.platform_tools_risk_enabled，默认关闭
const platformRiskEnabled = ref(false)

const isGameCategory = computed(() => {
  const inst = props.instance
  if (!inst) return false
  return inst.category === 'game' || inst.adapterType === 'minecraft' || inst.adapterType === 'game_websocket'
})

const platformTip = computed(() => {
  const at = props.instance?.adapterType
  if (at === 'minecraft') return t('platform.minecraftTip')
  if (at === 'qq_onebot') return t('platform.qqOnebotTip')
  if (at === 'wechat_personal') return t('platform.wechatPersonalTip')
  if (at === 'discord') return t('platform.discordTip')
  return ''
})

const getFieldLabel = (key: string) => {
  const at = props.instance?.adapterType
  if (at === 'minecraft') {
    if (key === 'game_port') return '局域网/游戏端口 (game_port)'
    if (key === 'game_host') return '服务器地址 (game_host)'
    if (key === 'bot_name') return '伴侣玩家名称 (bot_name)'
    if (key === 'auto_spawn_bot') return '自动派遣伴侣入服 (auto_spawn_bot)'
    if (key === 'ws_port') return '模组通信端口 (ws_port)'
    if (key === 'rcon_password') return 'RCON 密码 (rcon_password)'
  } else if (at === 'qq_onebot') {
    if (key === 'ws_port') return '反向 WS 监听端口 (ws_port)'
    if (key === 'access_token') return '通信密钥 (access_token)'
  } else if (at === 'wechat_personal') {
    if (key === 'api_url') return 'GeweChat API 地址 (api_url)'
    if (key === 'token') return 'API Token (token)'
  } else if (at === 'discord') {
    if (key === 'bot_token') return 'Discord Bot Token (bot_token)'
  }
  return key
}

const getFieldTip = (key: string) => {
  const at = props.instance?.adapterType
  if (at === 'minecraft') {
    if (key === 'game_port') return '单人游戏“对局域网开放”时显示的5位数字端口（如 56587），或多人服务器端口'
    if (key === 'game_host') return 'Minecraft 服务器地址，单人局域网填 127.0.0.1'
    if (key === 'bot_name') return '虚拟玩家伴侣进服昵称。留空直接继承设置中设定的【主 Agent】名称'
    if (key === 'ws_port') return 'Mineflayer 具身伴侣与系统通信的本地 WebSocket 端口，默认 8081'
  } else if (at === 'qq_onebot') {
    if (key === 'ws_port') return 'NapCatQQ 或 OneBot v11 反向 WebSocket 连接的端口，默认 8080'
    if (key === 'access_token') return '鉴权令牌，需与 NapCat 配置的 access_token 保持一致'
  } else if (at === 'wechat_personal') {
    if (key === 'api_url') return 'GeweChat (iPad 协议网关) 本地或容器服务的 REST API 地址'
    if (key === 'token') return 'GeweChat 服务调用 token'
  } else if (at === 'discord') {
    if (key === 'bot_token') return 'Discord Developer Portal 中生成的 Bot Token。请务必开启 Message Content Intent'
  }
  return ''
}

const getFieldPlaceholder = (key: string) => {
  if (key === 'bot_name') return '留空继承主 Agent 名称'
  if (key === 'game_port') return '56587'
  return ''
}

const effectiveModelConfig = computed(() => store.instanceModelConfig)

const getStatusIcon = (status: string) => {
  switch (status) {
    case 'running': return CheckCircle2
    case 'stopped': return XCircle
    case 'error': return AlertCircle
    default: return Clock
  }
}

const getStatusColor = (status: string) => {
  switch (status) {
    case 'running': return 'var(--lumi-success)'
    case 'stopped': return 'var(--text-muted)'
    case 'error': return 'var(--lumi-danger)'
    default: return 'var(--text-muted)'
  }
}

const getStatusLabel = (status: string) => {
  switch (status) {
    case 'running': return t('platform.status.running')
    case 'stopped': return t('platform.status.stopped')
    case 'error': return t('platform.status.error')
    case 'pending': return t('platform.status.pending')
    default: return t('platform.status.unknown')
  }
}

const closeConfigDialog = () => {
  emit('update:visible', false)
}

const handleSaveConfig = async () => {
  if (!props.instance) return
  try {
    await store.updateInstance(props.instance.id, {
      name: props.instance.name,
      // 风险开关与连接字段合并为同一 config 提交（config 为自由 dict，后端透传合并持久化）
      config: {
        ...editConfig.value,
        platform_tools_risk_enabled: platformRiskEnabled.value,
      },
    })
    if (Object.keys(modelEditConfig.value).length > 0) {
      await store.updateInstanceModelConfig(props.instance.id, modelEditConfig.value)
    }
    closeConfigDialog()
    emit('saved')
  } catch (e: unknown) {
    logger.error('Failed to update platform instance:', e)
  }
}

const handleResetModelConfig = async () => {
  if (!props.instance) return
  modelConfigSaving.value = true
  try {
    await store.updateInstanceModelConfig(props.instance.id, {
      systemPrompt: '',
    })
    modelEditConfig.value = {
      systemPrompt: '',
    }
  } catch (e: unknown) {
    logger.error('Failed to reset model config:', e)
  } finally {
    modelConfigSaving.value = false
  }
}

const resetConfigState = () => {
  editConfig.value = {}
  modelEditConfig.value = {}
  platformRiskEnabled.value = false
}

const loadInstanceConfig = async (instance: PlatformInstance) => {
  editConfig.value = { ...instance.config }
  delete editConfig.value.model_config
  delete editConfig.value.enable
  // 风险开关由独立 ref 管理，从通用连接字段中剔除（避免被渲染成文本输入框）
  delete editConfig.value.platform_tools_risk_enabled
  platformRiskEnabled.value = Boolean(instance.config?.platform_tools_risk_enabled)
  modelEditConfig.value = {}
  modelConfigLoading.value = true
  try {
    await store.fetchInstanceModelConfig(instance.id)
    const cfg = store.instanceModelConfig
    if (cfg) {
      modelEditConfig.value = {
        systemPrompt: cfg.instanceConfig.systemPrompt || '',
      }
    }
  } catch (e: unknown) {
    logger.error('Failed to load model config:', e)
  } finally {
    modelConfigLoading.value = false
  }
}

watch(() => props.visible, async (visible) => {
  if (!visible) {
    resetConfigState()
    return
  }
  if (props.instance) {
    await loadInstanceConfig(props.instance)
  }
}, { immediate: true })

watch(() => props.instance, async (instance) => {
  if (!instance || !props.visible) {
    if (!instance) resetConfigState()
    return
  }
  await loadInstanceConfig(instance)
})
</script>

<template>
  <LumiModal :visible="visible" :title="t('platform.configTitle', { name: instance?.name || '' })" size="lg" @close="closeConfigDialog" @update:visible="emit('update:visible', $event)">
    <div class="dialog-body">
      <!-- Main Agent Persona & Identity Inheritance Banner -->
      <div class="main-agent-banner">
        <div class="banner-icon">
          <Sparkles :size="16" />
        </div>
        <div class="banner-content">
          <div class="banner-title">{{ t('platform.mainAgentBannerTitle') }}</div>
          <div class="banner-desc">{{ t('platform.mainAgentBannerDesc') }}</div>
        </div>
      </div>

      <!-- Platform Guidance & Anti-ban Tip Card -->
      <div v-if="platformTip" class="platform-tip-card">
        <div class="tip-icon">
          <ShieldCheck :size="16" />
        </div>
        <div class="tip-content">
          <span class="tip-text">{{ platformTip }}</span>
        </div>
      </div>

      <div class="form-group">
        <label class="form-label">{{ t('platform.statusLabel') }}</label>
        <div class="status-display">
          <component :is="getStatusIcon(instance?.status || '')" :size="16" :style="{ color: getStatusColor(instance?.status || '') }" />
          <span :style="{ color: getStatusColor(instance?.status || '') }">{{ getStatusLabel(instance?.status || '') }}</span>
        </div>
      </div>

      <div class="form-group">
        <label class="form-label">
          <Cpu :size="12" />
          {{ t('platform.modelConfig') }}
          <span v-if="effectiveModelConfig?.isOverridden" class="badge overridden">{{ t('platform.badgeOverridden') }}</span>
          <span v-else-if="effectiveModelConfig" class="badge inherited">{{ t('platform.badgeInherited') }}</span>
        </label>

        <div v-if="modelConfigLoading" class="model-config-loading">
          <RefreshCw :size="14" class="spin-animation" />
          <span>{{ t('platform.loadingModelConfig') }}</span>
        </div>

        <div v-else-if="effectiveModelConfig" class="model-config-section">
          <div v-if="isGameCategory" class="vision-hint">
            <ImageIcon :size="12" />
            <span>{{ t('platform.visionHint') }}</span>
          </div>

          <div class="model-current-info">
            <div class="info-row">
              <span class="info-label">{{ t('platform.currentEffective') }}</span>
              <span class="info-value">{{ effectiveModelConfig?.effective?.providerName || effectiveModelConfig?.effective?.provider || '-' }}</span>
              <span class="info-sep">/</span>
              <span class="info-value">{{ effectiveModelConfig?.effective?.model || '-' }}</span>
              <span
                :class="['vision-tag', { supported: effectiveModelConfig?.effective?.supportsMultimodal }]"
                :title="effectiveModelConfig?.effective?.supportsMultimodal ? t('platform.visionSupported') : t('platform.visionUnsupported')"
              >
                {{ effectiveModelConfig?.effective?.supportsMultimodal ? 'Vision' : 'No Vision' }}
              </span>
            </div>
          </div>

          <p class="global-model-hint">{{ t('platform.globalModelHint') }}</p>

          <div class="config-fields">
            <div class="config-field">
              <label class="config-field-label">{{ t('platform.systemPromptLabel') }}</label>
              <textarea
                v-model="modelEditConfig.systemPrompt"
                class="form-input form-textarea"
                rows="3"
                :placeholder="t('platform.systemPromptPlaceholder')"
              ></textarea>
            </div>
          </div>

          <button
            class="reset-btn"
            @click="handleResetModelConfig"
            :disabled="modelConfigSaving || !effectiveModelConfig.isOverridden"
          >
            <RotateCcw :size="12" />
            <span>{{ t('platform.resetToInherit') }}</span>
          </button>
        </div>
      </div>

      <div v-if="Object.keys(editConfig).length > 0" class="form-group">
        <label class="form-label">{{ t('platform.connectionConfig') }}</label>
        <div class="config-fields">
          <div v-for="(_val, key) in editConfig" :key="key" class="config-field">
            <div class="config-field-label-row">
              <label class="config-field-label">{{ getFieldLabel(String(key)) }}</label>
              <span v-if="getFieldTip(String(key))" class="field-tip-icon" :title="getFieldTip(String(key))">
                <HelpCircle :size="13" />
              </span>
            </div>
            <LumiInput v-model="editConfig[key]" type="text" :placeholder="getFieldPlaceholder(String(key))" />
          </div>
        </div>
      </div>

      <!-- 高风险平台操作开关（W3-3 风险闸门，默认关闭） -->
      <div class="form-group">
        <label class="form-label">
          <ShieldAlert :size="12" />
          {{ t('platform.highRiskSectionTitle') }}
        </label>
        <div class="risk-toggle-row" :class="{ enabled: platformRiskEnabled }">
          <div class="risk-toggle-text">
            <span class="risk-toggle-title">{{ t('platform.highRiskToggleLabel') }}</span>
            <span class="risk-toggle-desc">{{ t('platform.highRiskToggleDesc') }}</span>
          </div>
          <button
            type="button"
            class="risk-switch"
            role="switch"
            :aria-checked="platformRiskEnabled"
            @click="platformRiskEnabled = !platformRiskEnabled"
          >
            <span class="risk-switch-knob" />
          </button>
        </div>
      </div>
      <div v-if="instance?.errorMessage" class="form-group">
        <label class="form-label">{{ t('platform.errorLabel') }}</label>
        <div class="error-display">{{ instance.errorMessage }}</div>
      </div>
    </div>
    <template #footer>
      <LumiButton variant="secondary" size="sm" @click="closeConfigDialog">{{ t('platform.cancel') }}</LumiButton>
      <LumiButton variant="primary" size="sm" @click="handleSaveConfig">{{ t('platform.saveConfig') }}</LumiButton>
    </template>
  </LumiModal>
</template>

<style scoped>
.form-group {
  margin-bottom: var(--space-4);
}

.form-label {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--text-secondary);
  margin-bottom: var(--space-1);
}

.status-display {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-base);
  font-weight: var(--font-medium);
}

.error-display {
  padding: var(--space-2) var(--space-3);
  background: var(--lumi-danger-light);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  color: var(--lumi-danger);
}

.badge {
  margin-left: auto;
  padding: 2px var(--space-2);
  border-radius: var(--radius-xs);
  font-size: var(--text-2xs);
  font-weight: var(--font-medium);
}

.badge.overridden {
  background: var(--lumi-success-light);
  color: var(--lumi-success);
}

.badge.inherited {
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
}

.model-config-loading {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-3);
  color: var(--text-muted);
  font-size: var(--text-sm);
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
}


.model-config-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.vision-hint {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  background: var(--lumi-amber-soft);
  border: 1px solid var(--lumi-amber-border);
  border-radius: var(--radius-sm);
  color: var(--lumi-amber);
  font-size: var(--text-xs);
}

.model-current-info {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-light);
}

.info-row {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-sm);
  flex-wrap: wrap;
}

.info-label {
  color: var(--text-muted);
  font-weight: var(--font-medium);
}

.info-value {
  color: var(--text-primary);
  font-weight: var(--font-medium);
}

.info-sep {
  color: var(--text-muted);
}

.main-agent-info {
  font-size: var(--text-xs);
  opacity: 0.8;
}

.vision-tag {
  padding: 1px var(--space-1);
  border-radius: var(--radius-xs);
  font-size: var(--text-2xs);
  font-weight: var(--font-semibold);
  background: var(--lumi-danger-light);
  color: var(--lumi-danger);
}

.vision-tag.supported {
  background: var(--lumi-success-light);
  color: var(--lumi-success);
}

.config-fields {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.config-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.config-field-label {
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: var(--text-muted);
}

.form-select {
  cursor: pointer;
  appearance: auto;
  background-image: none;
  padding-right: var(--space-3);
}

.form-select:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.form-textarea {
  resize: vertical;
  font-family: inherit;
  min-height: 80px;
}

.config-field-row {
  display: flex;
  gap: var(--space-3);
}

.config-field-row .config-field {
  flex: 1;
}

.reset-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  background: transparent;
  color: var(--text-muted);
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  cursor: pointer;
  transition: all var(--transition-fast);
  align-self: flex-start;
}

.reset-btn:hover:not(:disabled) {
  color: var(--lumi-danger);
  border-color: var(--lumi-danger);
  background: var(--lumi-danger-light);
}

.reset-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.main-agent-banner {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-3);
  margin-bottom: var(--space-4);
  background: var(--lumi-brand-light);
  border: 1px solid var(--lumi-brand-border, rgba(59, 130, 246, 0.2));
  border-radius: var(--radius-md);
}

.main-agent-banner .banner-icon {
  color: var(--lumi-brand);
  margin-top: 2px;
  flex-shrink: 0;
}

.main-agent-banner .banner-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.main-agent-banner .banner-title {
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  color: var(--lumi-brand);
}

.main-agent-banner .banner-desc {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  line-height: 1.4;
}

.platform-tip-card {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-3);
  margin-bottom: var(--space-4);
  background: var(--lumi-amber-soft);
  border: 1px solid var(--lumi-amber-border);
  border-radius: var(--radius-md);
}

.platform-tip-card .tip-icon {
  color: var(--lumi-amber);
  margin-top: 2px;
  flex-shrink: 0;
}

.platform-tip-card .tip-content {
  font-size: var(--text-xs);
  color: var(--lumi-amber-text, #b45309);
  line-height: 1.4;
}

.config-field-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.field-tip-icon {
  display: inline-flex;
  align-items: center;
  color: var(--text-muted);
  cursor: help;
  transition: color var(--transition-fast);
}

.field-tip-icon:hover {
  color: var(--lumi-brand);
}

.risk-toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3);
  background: var(--bg-secondary);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  transition: border-color var(--transition-fast);
}

.risk-toggle-row.enabled {
  border-color: var(--lumi-danger);
  background: var(--lumi-danger-light);
}

.risk-toggle-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.risk-toggle-title {
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: var(--text-primary);
}

.risk-toggle-desc {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  line-height: 1.4;
}

.risk-toggle-row.enabled .risk-toggle-desc {
  color: var(--lumi-danger);
}

.risk-switch {
  position: relative;
  width: 44px;
  height: 24px;
  border-radius: var(--radius-full);
  background: var(--workspace-border);
  border: none;
  cursor: pointer;
  transition: background var(--transition-normal);
  padding: 0;
  flex-shrink: 0;
}

.risk-switch[aria-checked="true"] {
  background: var(--lumi-danger);
}

.risk-switch-knob {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 20px;
  height: 20px;
  border-radius: var(--radius-full);
  background: white;
  transition: transform var(--transition-normal);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

.risk-switch[aria-checked="true"] .risk-switch-knob {
  transform: translateX(20px);
}
</style>

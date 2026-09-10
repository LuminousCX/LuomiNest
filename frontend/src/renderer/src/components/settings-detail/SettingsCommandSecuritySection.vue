<script setup lang="ts">
/**
 * LuomiNest 命令安全设置 — 命令白名单 / 黑名单管理
 *
 * 与后端 GET/PUT /console/policy 对接：
 * - 默认白名单（内置安全命令，只读展示）
 * - 额外白名单（用户放行的命令，可增删）
 * - 黑名单（用户强制拒绝的命令，可增删，优先级最高）
 *
 * 保存后立即生效：控制台手动执行、AI 工具调用（cli / console.execute）共用同一策略。
 */
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Shield, Plus, Trash2, Check, AlertCircle, Loader2, Info, Save } from 'lucide-vue-next'
import { useApi } from '../../composables/useApi'
import { createLuomiNestRendererLogger } from '../../utils/logger'
import LumiButton from '../common/LumiButton.vue'

const logger = createLuomiNestRendererLogger('Settings')

const { apiGet, apiPut } = useApi()
const { t } = useI18n()

interface CommandPolicy {
  default_whitelist: string[]
  extra_whitelist: string[]
  blacklist: string[]
  effective_whitelist: string[]
}

const loading = ref(false)
const saving = ref(false)
const policy = ref<CommandPolicy>({
  default_whitelist: [],
  extra_whitelist: [],
  blacklist: [],
  effective_whitelist: [],
})
const saveMsg = ref<{ type: 'success' | 'error'; text: string } | null>(null)

// 新增输入
const extraInput = ref('')
const blacklistInput = ref('')

const extraError = ref('')
const blacklistError = ref('')

const loadPolicy = async (): Promise<void> => {
  loading.value = true
  try {
    policy.value = await apiGet<CommandPolicy>('/console/policy')
  } catch (e) {
    logger.error('加载命令策略失败:', e)
  } finally {
    loading.value = false
  }
}

/** 解析逗号/空格分隔的命令输入为清洗后的数组 */
const parseInput = (raw: string): string[] => {
  return raw
    .split(/[\s,，、]+/)
    .map((s) => s.trim().toLowerCase())
    .filter((s) => s.length > 0)
}

const handleAddExtra = (): void => {
  const items = parseInput(extraInput.value)
  if (items.length === 0) {
    extraError.value = t('settingsEx.cmdSecurity.errEmptyCommand')
    return
  }
  extraError.value = ''
  const existing = new Set(policy.value.extra_whitelist)
  for (const item of items) {
    existing.add(item)
  }
  policy.value.extra_whitelist = [...existing].sort()
  extraInput.value = ''
}

const handleAddBlacklist = (): void => {
  const items = parseInput(blacklistInput.value)
  if (items.length === 0) {
    blacklistError.value = t('settingsEx.cmdSecurity.errEmptyCommand')
    return
  }
  blacklistError.value = ''
  const existing = new Set(policy.value.blacklist)
  for (const item of items) {
    existing.add(item)
  }
  policy.value.blacklist = [...existing].sort()
  blacklistInput.value = ''
}

const removeExtra = (cmd: string): void => {
  policy.value.extra_whitelist = policy.value.extra_whitelist.filter((c) => c !== cmd)
}

const removeBlacklist = (cmd: string): void => {
  policy.value.blacklist = policy.value.blacklist.filter((c) => c !== cmd)
}

const handleSave = async (): Promise<void> => {
  saving.value = true
  saveMsg.value = null
  try {
    policy.value = await apiPut<CommandPolicy>('/console/policy', {
      extra_whitelist: policy.value.extra_whitelist,
      blacklist: policy.value.blacklist,
    })
    saveMsg.value = { type: 'success', text: t('settingsEx.cmdSecurity.savedMsg') }
    setTimeout(() => { saveMsg.value = null }, 3000)
  } catch (e) {
    saveMsg.value = { type: 'error', text: t('settingsEx.cmdSecurity.saveFailed', { message: e instanceof Error ? e.message : String(e) }) }
  } finally {
    saving.value = false
  }
}

const hasChanges = computed(() => {
  return (
    policy.value.extra_whitelist.join(',') !== initialExtra.value.join(',') ||
    policy.value.blacklist.join(',') !== initialBlacklist.value.join(',')
  )
})

// 初始快照用于判断是否有修改
const initialExtra = ref<string[]>([])
const initialBlacklist = ref<string[]>([])

onMounted(async () => {
  await loadPolicy()
  initialExtra.value = [...policy.value.extra_whitelist]
  initialBlacklist.value = [...policy.value.blacklist]
})
</script>

<template>
  <div class="settings-panel animate-slide-up">
    <div v-if="loading" class="settings-card">
      <div class="settings-card__body settings-card__body--compact command-loading">
        <Loader2 :size="20" class="spin-animation" />
        <span>{{ t('settingsEx.cmdSecurity.loading') }}</span>
      </div>
    </div>

    <template v-else>
      <section class="settings-card">
        <div class="settings-card__header">
          <Shield :size="18" />
          <span class="settings-card__title">{{ t('settingsEx.cmdSecurity.title') }}</span>
        </div>
        <div class="settings-card__body">
          <div class="settings-form-hint command-policy-hint">
            <Info :size="14" />
            <span>{{ t('settingsEx.cmdSecurity.policyHint') }}</span>
          </div>

          <!-- 默认白名单（只读） -->
          <div class="settings-form-row">
            <label class="settings-form-label">{{ t('settingsEx.cmdSecurity.defaultWhitelist') }}</label>
            <div class="command-tags">
              <span
                v-for="cmd in policy.default_whitelist"
                :key="cmd"
                class="command-tag command-tag--default"
              >{{ cmd }}</span>
            </div>
            <span class="settings-form-hint">{{ t('settingsEx.cmdSecurity.defaultWhitelistHint') }}</span>
          </div>

          <!-- 额外白名单 -->
          <div class="settings-form-row">
            <label class="settings-form-label">{{ t('settingsEx.cmdSecurity.extraWhitelist') }}</label>
            <div class="command-add-row">
              <input
                v-model="extraInput"
                class="settings-form-input command-add-input"
                :placeholder="t('settingsEx.cmdSecurity.inputPlaceholder')"
                @keydown.enter.prevent="handleAddExtra"
              />
              <LumiButton variant="primary" size="sm" @click="handleAddExtra">
                <Plus :size="14" />
                <span>{{ t('settingsEx.cmdSecurity.add') }}</span>
              </LumiButton>
            </div>
            <span v-if="extraError" class="settings-form-error">{{ extraError }}</span>
            <div class="command-tags">
              <span
                v-for="cmd in policy.extra_whitelist"
                :key="cmd"
                class="command-tag command-tag--extra"
              >
                {{ cmd }}
                <button class="command-tag__remove" :title="t('settingsEx.cmdSecurity.removeCommand', { cmd })"" @click="removeExtra(cmd)">
                  <Trash2 :size="12" />
                </button>
              </span>
              <span v-if="policy.extra_whitelist.length === 0" class="command-tag--empty">
                {{ t('settingsEx.cmdSecurity.extraEmpty') }}
              </span>
            </div>
          </div>

          <!-- 黑名单 -->
          <div class="settings-form-row">
            <label class="settings-form-label">{{ t('settingsEx.cmdSecurity.blacklist') }}</label>
            <div class="command-add-row">
              <input
                v-model="blacklistInput"
                class="settings-form-input command-add-input"
                :placeholder="t('settingsEx.cmdSecurity.inputPlaceholder')"
                @keydown.enter.prevent="handleAddBlacklist"
              />
              <LumiButton variant="danger" size="sm" @click="handleAddBlacklist">
                <Plus :size="14" />
                <span>{{ t('settingsEx.cmdSecurity.add') }}</span>
              </LumiButton>
            </div>
            <span v-if="blacklistError" class="settings-form-error">{{ blacklistError }}</span>
            <div class="command-tags">
              <span
                v-for="cmd in policy.blacklist"
                :key="cmd"
                class="command-tag command-tag--blacklist"
              >
                {{ cmd }}
                <button class="command-tag__remove" :title="t('settingsEx.cmdSecurity.removeCommand', { cmd })"" @click="removeBlacklist(cmd)">
                  <Trash2 :size="12" />
                </button>
              </span>
              <span v-if="policy.blacklist.length === 0" class="command-tag--empty">
                {{ t('settingsEx.cmdSecurity.blacklistEmpty') }}
              </span>
            </div>
            <span class="settings-form-hint">{{ t('settingsEx.cmdSecurity.blacklistHint') }}</span>
          </div>
        </div>
      </section>

      <div class="settings-btn-row">
        <div
          v-if="saveMsg"
          :class="['settings-message', saveMsg.type === 'success' ? 'settings-message--success' : 'settings-message--error']"
        >
          <component :is="saveMsg.type === 'success' ? Check : AlertCircle" :size="14" />
          <span>{{ saveMsg.text }}</span>
        </div>
        <LumiButton
          variant="primary"
          size="sm"
          :loading="saving"
          :disabled="saving || !hasChanges"
          @click="handleSave"
        >
          <Save :size="14" />
          <span>{{ saving ? t('settingsEx.cmdSecurity.saving') : t('settingsEx.cmdSecurity.savePolicy') }}</span>
        </LumiButton>
      </div>
    </template>
  </div>
</template>

<style scoped>
.command-loading {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  justify-content: center;
  color: var(--text-muted);
  font-size: var(--text-base);
  padding: var(--space-6) 0;
}

.command-policy-hint {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  padding: var(--space-3);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  color: var(--text-muted);
  font-size: var(--text-sm);
  line-height: 1.6;
}

.command-add-row {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}

.command-add-input {
  flex: 1;
  min-width: 0;
}

.command-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.command-tag {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 2px var(--space-2);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  font-family: var(--font-mono, monospace);
  line-height: 1.6;
}

.command-tag--default {
  background: var(--bg-secondary);
  color: var(--text-muted);
}

.command-tag--extra {
  background: color-mix(in srgb, var(--lumi-success) 12%, transparent);
  color: var(--lumi-success);
}

.command-tag--blacklist {
  background: color-mix(in srgb, var(--lumi-danger, #e5484d) 12%, transparent);
  color: var(--lumi-danger, #e5484d);
}

.command-tag--empty {
  color: var(--text-muted);
  font-size: var(--text-sm);
}

.command-tag__remove {
  display: inline-flex;
  align-items: center;
  padding: 0;
  border: none;
  background: transparent;
  color: inherit;
  opacity: 0.6;
  cursor: pointer;
  transition: opacity var(--transition-fast);
}

.command-tag__remove:hover {
  opacity: 1;
}

.settings-form-error {
  color: var(--lumi-danger, #e5484d);
  font-size: var(--text-sm);
  margin-top: var(--space-1);
}

</style>

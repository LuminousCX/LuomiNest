<script setup lang="ts">
/**
 * LuomiNest 数据备份与恢复设置 — 与后端 /backup API 对接
 *
 * 04-用户数据存储链路审查 P0-2：恢复能力此前为死代码（无端点无 UI）。
 * - 列出 data/backups 内的备份（GET /backup/list）
 * - 立即备份（POST /backup/create，凭据文件不入包）
 * - 从备份恢复（POST /backup/restore，强确认：覆盖当前数据，不可撤销）
 * - 删除备份（POST /backup/delete）
 *
 * 恢复完成后展示"需要重新配置的凭据"清单（来自备份包内 manifest）。
 */
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { DatabaseBackup, HardDriveDownload, Trash2, Loader2, Info, ShieldAlert, RotateCcw } from 'lucide-vue-next'
import { useApi } from '../../composables/useApi'
import { useToast } from '../../composables/useToast'
import { createLuomiNestRendererLogger } from '../../utils/logger'
import { formatDateTime } from '../../utils/format'
import LumiButton from '../common/LumiButton.vue'
import ConfirmDialog from '../common/ConfirmDialog.vue'

const logger = createLuomiNestRendererLogger('Settings')

const { apiGet, apiPost } = useApi()
const { t } = useI18n()
const toast = useToast()

interface BackupItem {
  name: string
  path: string
  size_mb: number
  created_at: string
}

interface CredentialHint {
  path: string
  hint: string
}

interface RestoreResult {
  ok: boolean
  backup: string
  db_restore_method: string
  restored: string[]
  failed: { item: string; error: string }[]
  credentials_to_reconfigure: CredentialHint[]
  restart_recommended: boolean
  message: string
}

const loading = ref(false)
const creating = ref(false)
const restoring = ref(false)
const deleting = ref(false)
const backups = ref<BackupItem[]>([])
const lastRestoreResult = ref<RestoreResult | null>(null)

// 确认弹窗状态（恢复 / 删除共用 ConfirmDialog，分别挂两个实例）
const restoreTarget = ref<BackupItem | null>(null)
const restoreDialogVisible = ref(false)
const deleteTarget = ref<BackupItem | null>(null)
const deleteDialogVisible = ref(false)

const loadBackups = async (): Promise<void> => {
  loading.value = true
  try {
    backups.value = await apiGet<BackupItem[]>('/backup/list')
  } catch (e) {
    logger.error('加载备份列表失败:', e)
    toast.error(t('settingsEx.backup.listFailed'))
  } finally {
    loading.value = false
  }
}

const handleCreate = async (): Promise<void> => {
  creating.value = true
  try {
    // 打包整个 DATA_DIR 可能较慢，给 5 分钟超时（默认 15s 不够）
    await apiPost<{ name: string }>('/backup/create', {}, { timeout: 300000 })
    toast.success(t('settingsEx.backup.createSuccess'))
    await loadBackups()
  } catch (e) {
    toast.error(t('settingsEx.backup.createFailed', { message: e instanceof Error ? e.message : String(e) }))
  } finally {
    creating.value = false
  }
}

const askRestore = (item: BackupItem): void => {
  restoreTarget.value = item
  restoreDialogVisible.value = true
}

const handleRestore = async (): Promise<void> => {
  if (!restoreTarget.value) return
  restoring.value = true
  try {
    // 解包 + 库完整性校验 + 整库写回可能较慢，给 5 分钟超时（默认 15s 不够）
    lastRestoreResult.value = await apiPost<RestoreResult>(
      '/backup/restore',
      { name: restoreTarget.value.name },
      { timeout: 300000 }
    )
    restoreDialogVisible.value = false
    toast.success(t('settingsEx.backup.restoreSuccess'))
  } catch (e) {
    toast.error(t('settingsEx.backup.restoreFailed', { message: e instanceof Error ? e.message : String(e) }))
  } finally {
    restoring.value = false
    restoreTarget.value = null
  }
}

const askDelete = (item: BackupItem): void => {
  deleteTarget.value = item
  deleteDialogVisible.value = true
}

const handleDelete = async (): Promise<void> => {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await apiPost('/backup/delete', { name: deleteTarget.value.name })
    toast.success(t('settingsEx.backup.deleteSuccess'))
    if (deleteTarget.value.name === lastRestoreResult.value?.backup) {
      lastRestoreResult.value = null
    }
    await loadBackups()
    deleteDialogVisible.value = false
  } catch (e) {
    toast.error(t('settingsEx.backup.deleteFailed', { message: e instanceof Error ? e.message : String(e) }))
  } finally {
    deleting.value = false
    deleteTarget.value = null
  }
}

onMounted(loadBackups)
</script>

<template>
  <div class="settings-panel animate-slide-up">
    <section class="settings-card">
      <div class="settings-card__header">
        <DatabaseBackup :size="18" />
        <span class="settings-card__title">{{ t('settingsEx.backup.title') }}</span>
      </div>
      <div class="settings-card__body">
        <div class="settings-form-hint backup-hint">
          <Info :size="14" />
          <span>{{ t('settingsEx.backup.subtitle') }}</span>
        </div>

        <div class="backup-actions">
          <LumiButton variant="primary" size="sm" :loading="creating" :disabled="creating" @click="handleCreate">
            <DatabaseBackup :size="14" />
            <span>{{ creating ? t('settingsEx.backup.creating') : t('settingsEx.backup.createNow') }}</span>
          </LumiButton>
        </div>

        <div v-if="loading" class="backup-loading">
          <Loader2 :size="18" class="spin-animation" />
          <span>{{ t('settingsEx.backup.loading') }}</span>
        </div>

        <template v-else>
          <div v-if="backups.length === 0" class="backup-empty">
            {{ t('settingsEx.backup.empty') }}
          </div>
          <ul v-else class="backup-list">
            <li v-for="item in backups" :key="item.name" class="backup-item">
              <HardDriveDownload :size="16" class="backup-item__icon" />
              <div class="backup-item__info">
                <span class="backup-item__name">{{ item.name }}</span>
                <span class="backup-item__meta">{{ formatDateTime(item.created_at) }} · {{ item.size_mb }} MB</span>
              </div>
              <div class="backup-item__actions">
                <LumiButton variant="danger" size="sm" @click="askRestore(item)">
                  <RotateCcw :size="13" />
                  <span>{{ t('settingsEx.backup.restore') }}</span>
                </LumiButton>
                <LumiButton variant="ghost" size="sm" @click="askDelete(item)">
                  <Trash2 :size="13" />
                  <span>{{ t('settingsEx.backup.remove') }}</span>
                </LumiButton>
              </div>
            </li>
          </ul>
        </template>

        <!-- 最近一次恢复结果摘要：含需要重新配置的凭据清单 -->
        <div v-if="lastRestoreResult" class="backup-restore-result">
          <div class="backup-restore-result__header">
            <ShieldAlert :size="15" />
            <span>{{ t('settingsEx.backup.credentialNoteTitle') }}</span>
          </div>
          <p class="backup-restore-result__note">{{ t('settingsEx.backup.credentialHint') }}</p>
          <ul class="backup-restore-result__list">
            <li v-for="cred in lastRestoreResult.credentials_to_reconfigure" :key="cred.path">
              <code>{{ cred.path }}</code>
              <span v-if="cred.hint"> — {{ cred.hint }}</span>
            </li>
          </ul>
        </div>
      </div>
    </section>

    <!-- 恢复强确认：明确列出覆盖后果 -->
    <ConfirmDialog
      :visible="restoreDialogVisible"
      :title="t('settingsEx.backup.confirmRestoreTitle')"
      :message="t('settingsEx.backup.confirmRestoreMessage')"
      danger
      :loading="restoring"
      :confirm-text="t('settingsEx.backup.confirmRestore')"
      :cancel-text="t('settingsEx.backup.cancel')"
      @update:visible="restoreDialogVisible = $event"
      @confirm="handleRestore"
    />

    <ConfirmDialog
      :visible="deleteDialogVisible"
      :title="t('settingsEx.backup.confirmDeleteTitle')"
      :message="deleteTarget ? t('settingsEx.backup.confirmDeleteMessage', { name: deleteTarget.name }) : ''"
      danger
      :loading="deleting"
      :confirm-text="t('settingsEx.backup.confirmDelete')"
      :cancel-text="t('settingsEx.backup.cancel')"
      @update:visible="deleteDialogVisible = $event"
      @confirm="handleDelete"
    />
  </div>
</template>

<style scoped>
.backup-hint {
  margin-bottom: var(--space-3);
}

.backup-actions {
  display: flex;
  justify-content: flex-end;
  margin-bottom: var(--space-3);
}

.backup-loading {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-4) 0;
  color: var(--text-muted);
  font-size: var(--text-sm);
}

.backup-empty {
  padding: var(--space-4) 0;
  color: var(--text-muted);
  font-size: var(--text-sm);
  text-align: center;
}

.backup-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.backup-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--divider-soft);
}

.backup-item:last-child {
  border-bottom: none;
}

.backup-item__icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.backup-item__info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.backup-item__name {
  font-size: var(--text-sm);
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.backup-item__meta {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.backup-item__actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}

.backup-restore-result {
  margin-top: var(--space-3);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--lumi-warning) 8%, transparent);
  border: 1px solid color-mix(in srgb, var(--lumi-warning) 30%, transparent);
}

.backup-restore-result__header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--lumi-warning);
  margin-bottom: var(--space-2);
}

.backup-restore-result__note {
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin: 0 0 var(--space-2);
}

.backup-restore-result__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

.backup-restore-result__list code {
  font-size: var(--text-xs);
  color: var(--text);
}
</style>

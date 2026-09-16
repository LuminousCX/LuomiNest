/**
 * LuomiNest 工作台云端群聊（UI 胶水层）
 *
 * 数据与轮询都在 stores/social.ts（cloudGroups / cloudMessages / openCloudGroup ...），
 * 本组合式只收纳对话框状态与动作：创建云端群、按用户 ID 邀请成员、错误提示。
 * 服务端未上线（kind='unavailable'）时 store 已降级为空态，这里只做文案映射。
 */
import { ref, computed } from 'vue'
import type { Ref, ComputedRef } from 'vue'
import type { CloudGroupVo } from '@shared/ipc-types'
import { useSocialStore } from '../stores/social'
import { createLuomiNestRendererLogger } from '../utils/logger'

const logger = createLuomiNestRendererLogger('WorkspaceCloudGroups')

export interface UseWorkspaceCloudGroupsOptions {
  /** 当前选中的云端群 id（视图持有，选中/返回由视图驱动） */
  selectedCloudGroupId: Ref<string | null>
  /** 选中云端群回调（视图切换 selectedType 并调 openCloudGroup） */
  selectCloudGroup: (group: CloudGroupVo) => void
}

export const useWorkspaceCloudGroups = (options: UseWorkspaceCloudGroupsOptions) => {
  const socialStore = useSocialStore()
  const { selectedCloudGroupId, selectCloudGroup } = options

  const showCreateCloudGroupDialog = ref(false)
  const showInviteCloudDialog = ref(false)
  const newCloudGroupName = ref('')
  const inviteCloudUserId = ref('')
  /** 对话框内的错误提示（如仅群主可邀请）；关闭对话框时清空 */
  const cloudDialogError = ref('')
  const creatingCloudGroup = ref(false)
  const invitingCloudMember = ref(false)

  const currentCloudGroup: ComputedRef<CloudGroupVo | null> = computed(
    () => socialStore.cloudGroups.find(g => g.id === selectedCloudGroupId.value) || null,
  )

  const clearDialogError = (): void => {
    cloudDialogError.value = ''
  }

  const openCreateDialog = (): void => {
    clearDialogError()
    newCloudGroupName.value = ''
    showCreateCloudGroupDialog.value = true
  }

  const openInviteDialog = (): void => {
    clearDialogError()
    inviteCloudUserId.value = ''
    showInviteCloudDialog.value = true
  }

  /** 创建云端群：成功后关闭对话框并选中新群 */
  const createCloudGroup = async (): Promise<void> => {
    const name = newCloudGroupName.value.trim()
    if (!name || creatingCloudGroup.value) return
    creatingCloudGroup.value = true
    try {
      const group = await socialStore.createCloudGroup(name)
      if (group) {
        showCreateCloudGroupDialog.value = false
        newCloudGroupName.value = ''
        selectCloudGroup(group)
      } else {
        cloudDialogError.value = 'createFailed'
      }
    } catch (e: unknown) {
      logger.error('Failed to create cloud group:', e)
      cloudDialogError.value = 'createFailed'
    } finally {
      creatingCloudGroup.value = false
    }
  }

  /** 邀请成员：成功关对话框；forbidden（仅群主/管理员）等在对话框内提示 */
  const inviteCloudMember = async (): Promise<void> => {
    const userId = inviteCloudUserId.value.trim()
    const groupId = selectedCloudGroupId.value
    if (!userId || !groupId || invitingCloudMember.value) return
    invitingCloudMember.value = true
    try {
      const result = await socialStore.inviteCloudMember(groupId, userId)
      if (result.ok) {
        showInviteCloudDialog.value = false
        inviteCloudUserId.value = ''
      } else {
        cloudDialogError.value = result.kind || 'failed'
      }
    } catch (e: unknown) {
      logger.error('Failed to invite cloud member:', e)
      cloudDialogError.value = 'failed'
    } finally {
      invitingCloudMember.value = false
    }
  }

  return {
    showCreateCloudGroupDialog,
    showInviteCloudDialog,
    newCloudGroupName,
    inviteCloudUserId,
    cloudDialogError,
    creatingCloudGroup,
    invitingCloudMember,
    currentCloudGroup,
    openCreateDialog,
    openInviteDialog,
    createCloudGroup,
    inviteCloudMember,
  }
}

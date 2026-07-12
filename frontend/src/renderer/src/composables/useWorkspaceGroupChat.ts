/**
 * LuomiNest 工作台群聊 + 协作模式
 *
 * 从 WorkspaceView.vue 拆分：收纳群聊发送、创建/删除群、添加/移除成员、协作流式等逻辑。
 * 群选择（selectGroup）与当前群被删除后的联系人清空交回视图处理，保持解耦。
 */
import { ref, computed, nextTick } from 'vue'
import type { Ref } from 'vue'
import type { GroupInfo } from '../types'
import { useSocialStore } from '../stores/social'
import { useAgentStore } from '../stores/agent'
import { createLuomiNestRendererLogger } from '../utils/logger'
import { generateId } from '../utils/id'

const logger = createLuomiNestRendererLogger('WorkspaceGroupChat')

/** 群聊子组件实例的最小接口（避免依赖具体组件类型） */
interface GroupChatComponent {
  scrollToBottom: () => void
}

export interface UseWorkspaceGroupChatOptions {
  selectedGroupId: Ref<string | null>
  selectGroup: (group: GroupInfo) => void
  /** 当前群被删除时回调（视图清空 selectedGroupId / selectedType） */
  onCurrentGroupDeleted: () => void
  groupChatRef: Ref<GroupChatComponent | null>
}

export const useWorkspaceGroupChat = (options: UseWorkspaceGroupChatOptions) => {
  const socialStore = useSocialStore()
  const agentStore = useAgentStore()
  const { selectedGroupId, selectGroup, onCurrentGroupDeleted, groupChatRef } = options

  const groupChatInput = ref('')
  const sendingGroupMessage = ref(false)
  const collaborationMode = ref(false)
  const showAddAgentDialog = ref(false)
  const showCreateGroupDialog = ref(false)
  const addAgentRole = ref('')
  const addAgentId = ref('')
  const newGroupName = ref('')
  const newGroupDesc = ref('')

  const selectedGroup = computed(() => {
    if (!selectedGroupId.value) return null
    return socialStore.groups.find(g => g.id === selectedGroupId.value) || null
  })

  const groupMessages = computed(() => socialStore.groupMessages)

  const availableAgentsForGroup = computed(() => {
    if (!selectedGroup.value) return agentStore.agents
    const memberIds = selectedGroup.value.members.map(m => m.agent_id)
    return agentStore.agents.filter(a => !memberIds.includes(a.id))
  })

  const collaborationPhase = computed(() => socialStore.collaborationPhase)
  const collaborationActive = computed(() => socialStore.collaborationActive)
  const collaborationTasks = computed(() => socialStore.collaborationTasks)
  const agentsResponding = computed(() => socialStore.agentsResponding)
  const respondingAgentNames = computed(() => socialStore.respondingAgentNames)

  const sendGroupMessage = async (): Promise<void> => {
    if (!groupChatInput.value.trim() || !selectedGroupId.value) return
    sendingGroupMessage.value = true
    const userContent = groupChatInput.value
    groupChatInput.value = ''

    try {
      if (collaborationMode.value) {
        socialStore.groupMessages.push({
          id: generateId('user'),
          groupId: selectedGroupId.value,
          senderId: 'user',
          senderType: 'user',
          content: userContent,
          timestamp: new Date().toISOString(),
        })

        await socialStore.collaborateStream(
          selectedGroupId.value,
          userContent,
          () => {},
          (err: unknown) => { logger.error('Collaboration error:', err) },
          () => {},
        )
      } else {
        await socialStore.sendGroupMessage(selectedGroupId.value, userContent)
      }
      await nextTick()
      groupChatRef.value?.scrollToBottom()
    } catch (e: unknown) {
      logger.error('Failed to send message:', e)
    } finally {
      sendingGroupMessage.value = false
    }
  }

  const createGroup = async (): Promise<void> => {
    if (!newGroupName.value.trim()) return
    try {
      const group = await socialStore.createGroup(newGroupName.value.trim(), newGroupDesc.value.trim())
      newGroupName.value = ''
      newGroupDesc.value = ''
      showCreateGroupDialog.value = false
      if (group) {
        selectGroup(group)
      }
    } catch (e: unknown) {
      logger.error('Failed to create group:', e)
    }
  }

  const deleteGroup = async (groupId: string): Promise<void> => {
    try {
      await socialStore.deleteGroup(groupId)
      if (selectedGroupId.value === groupId) {
        onCurrentGroupDeleted()
      }
    } catch (e: unknown) {
      logger.error('Failed to delete group:', e)
    }
  }

  const addAgentToGroup = async (): Promise<void> => {
    if (!addAgentId.value || !selectedGroupId.value) return
    try {
      await socialStore.addAgentToGroup(selectedGroupId.value, addAgentId.value, addAgentRole.value || '成员')
      addAgentId.value = ''
      addAgentRole.value = ''
      showAddAgentDialog.value = false
    } catch (e: unknown) {
      logger.error('Failed to add agent:', e)
    }
  }

  const removeAgentFromGroup = async (groupId: string, agentId: string): Promise<void> => {
    try {
      await socialStore.removeAgentFromGroup(groupId, agentId)
    } catch (e: unknown) {
      logger.error('Failed to remove agent:', e)
    }
  }

  return {
    groupChatInput,
    sendingGroupMessage,
    collaborationMode,
    showAddAgentDialog,
    showCreateGroupDialog,
    addAgentRole,
    addAgentId,
    newGroupName,
    newGroupDesc,
    selectedGroup,
    groupMessages,
    availableAgentsForGroup,
    collaborationPhase,
    collaborationActive,
    collaborationTasks,
    agentsResponding,
    respondingAgentNames,
    sendGroupMessage,
    createGroup,
    deleteGroup,
    addAgentToGroup,
    removeAgentFromGroup,
  }
}

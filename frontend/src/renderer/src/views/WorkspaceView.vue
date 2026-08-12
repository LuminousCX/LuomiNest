<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { MessageCircle } from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import { useChatStore } from '../stores/chat'
import { useAgentStore } from '../stores/agent'
import { useModelStore } from '../stores/model'
import { useSocialStore } from '../stores/social'
import { useChatTrashStore } from '../stores/chat-trash'
import { useTTS } from '../composables/useTTS'
import FilePreview from '../components/FilePreview.vue'
import { useFileUpload } from '../composables/useFileUpload'
import { useClipboard } from '../composables/useClipboard'
import { useFileDrop } from '../composables/useFileDrop'
import { useToast } from '../composables/useToast'
import { isUploadAllowed } from '../utils/file'
import WorkspaceContactPanel from '../components/workspace/WorkspaceContactPanel.vue'
import WorkspaceAgentHistory from '../components/workspace/WorkspaceAgentHistory.vue'
import WorkspaceGroupInfo from '../components/workspace/WorkspaceGroupInfo.vue'
import WorkspaceAgentChat from '../components/workspace/WorkspaceAgentChat.vue'
import WorkspaceGroupChat from '../components/workspace/WorkspaceGroupChat.vue'
import WorkspaceDialogs from '../components/workspace/WorkspaceDialogs.vue'
import WorkspaceDropOverlay from '../components/workspace/WorkspaceDropOverlay.vue'
import type { GroupInfo, AgentProfile } from '../types'
import { useWorkspaceAgentDialogs } from '../composables/useWorkspaceAgentDialogs'
import { useWorkspaceGroupChat } from '../composables/useWorkspaceGroupChat'
import { useWorkspaceConvList } from '../composables/useWorkspaceConvList'
import { useWorkspaceMessages } from '../composables/useWorkspaceMessages'

const router = useRouter()
const chatStore = useChatStore()
const agentStore = useAgentStore()
const modelStore = useModelStore()
const socialStore = useSocialStore()
const chatTrashStore = useChatTrashStore()
const toast = useToast()
const { isSpeaking: isTTSSpeaking, speakingMessageId: ttsSpeakingMsgId, speak: ttsSpeak, stopSpeaking: ttsStopSpeaking } = useTTS()

// —— 文件上传 ——
const { isUploading, uploadingFile, parsedContent, fileType, fileName, uploadAndForward, clearUploadState } = useFileUpload()
const { copiedId, copy: copyMessage } = useClipboard()

// —— 子组件 ref ——
const agentChatRef = ref<InstanceType<typeof WorkspaceAgentChat> | null>(null)
const groupChatRef = ref<InstanceType<typeof WorkspaceGroupChat> | null>(null)

// —— 联系人选择状态（视图持有，供 composable 共享） ——
type ContactType = 'agent' | 'group'
const selectedType = ref<ContactType | null>(null)
const contactSearchQuery = ref('')
const localSelectedAgent = ref<AgentProfile | null>(null)
const localSelectedConvId = ref<string | null>(null)
const selectedGroupId = ref<string | null>(null)

const selectAgent = async (agent: AgentProfile) => {
  localSelectedAgent.value = agent
  selectedType.value = 'agent'
  selectedGroupId.value = null
  localSelectedConvId.value = null
  await chatStore.fetchConversations(agent.id)
  chatTrashStore.fetchTrash(agent.id)
}

const selectGroup = (group: GroupInfo) => {
  selectedType.value = 'group'
  selectedGroupId.value = group.id
  socialStore.currentGroup = group
  socialStore.fetchGroupMessages(group.id)
}

const backToContacts = () => {
  selectedType.value = null
  localSelectedAgent.value = null
  localSelectedConvId.value = null
  selectedGroupId.value = null
  convList.resetBatchState()
}

// —— 文件拖放 ——
const { showOverlay: showGlobalDropOverlay } = useFileDrop({
  isUploading,
  isAllowed: isUploadAllowed,
  onUpload: (file: File) => uploadAndForward(file),
  onError: (message: string) => toast.error(message),
})

// —— 文件预览 ——
const showFilePreview = ref(false)
const previewFile = ref<{ name: string; type?: string; content?: string } | null>(null)

const openFilePreview = (file: { name: string; type?: string; content?: string }) => {
  previewFile.value = file
  showFilePreview.value = true
}

const closeFilePreview = () => {
  showFilePreview.value = false
  previewFile.value = null
}

// —— composable 集成 ——
const agentDialogs = useWorkspaceAgentDialogs({
  onAgentDeleted: (deletedId: string) => {
    if (localSelectedAgent.value?.id === deletedId) {
      selectedType.value = null
      localSelectedAgent.value = null
      localSelectedConvId.value = null
    }
  },
})

const groupChat = useWorkspaceGroupChat({
  selectedGroupId,
  selectGroup,
  onCurrentGroupDeleted: () => {
    selectedGroupId.value = null
    selectedType.value = null
  },
  groupChatRef,
})

const convList = useWorkspaceConvList({
  localSelectedAgent,
  localSelectedConvId,
})

const messages_ = useWorkspaceMessages({
  localSelectedAgent,
  localSelectedConvId,
  agentChatRef,
  fileUpload: { isUploading, parsedContent, fileName, fileType, uploadingFile, clearUploadState },
  openConfirmDialog: agentDialogs.openConfirmDialog,
})

// 从 composable 解构常用项（template 直接引用）
const {
  agentColors, presetAvatars, showCreateDialog, newAgentForm, createDialogError,
  showConfirmDialog, confirmDialogMessage, confirmDialogIsDanger,
  showEditDialog, editAgentForm,
  handleConfirmDialogConfirm, handleConfirmDialogCancel,
  handleCreateAgent, openEditDialog, handleUpdateAgent, handleDeleteAgent,
  openConfirmDialog,
} = agentDialogs

const {
  groupChatInput, sendingGroupMessage, collaborationMode,
  showAddAgentDialog, showCreateGroupDialog, addAgentRole, addAgentId,
  newGroupName, newGroupDesc,
  selectedGroup, groupMessages, availableAgentsForGroup,
  collaborationPhase, collaborationActive, collaborationTasks,
  agentsResponding, respondingAgentNames,
  sendGroupMessage, createGroup, deleteGroup, addAgentToGroup, removeAgentFromGroup,
} = groupChat

const {
  convSearchQuery, searchResults, isSearching, isSearchMode,
  timeGroups, batchMode, selectedIds, renamingConvId, renamingTitle,
  selectConversation, handleDeleteConversation, handleNewConversation,
  toggleBatchMode, toggleSelect, selectAll, handleBatchDelete,
  startRename, confirmRename, cancelRename,
} = convList

const {
  inputText, selectedSkillIds, showModelDropdown, showReasoning,
  messages, isStreaming, isLoadingCurrentConv, isBackendReady, currentConvId,
  currentModel, currentProvider, currentProviderLogo, hasProvider, availableModelOptions,
  selectModel, canSend, sendMessage, cancelStreaming,
  chatMode, chatModeOptions, selectChatMode,
  contextUsage, contextTokens, contextPercent, currentSuggestionMessageId,
  handleSwitchVersion, handleSuggestionClick, handleRegenerate,
  handleDeleteMessage, handleGoBackToStart, handleQuoteMessage, toggleReasoning,
} = messages_

// —— 外部点击与触发器 ——
const handleClickOutsideModel = (e: MouseEvent) => {
  const target = e.target as HTMLElement
  if (!target.closest('.model-dropdown-container')) {
    showModelDropdown.value = false
  }
}

function handleChatTrigger(event: CustomEvent) {
  if (event.detail?.message) {
    inputText.value = event.detail.message
  }
}

function handleMemoryChatTrigger(event: CustomEvent) {
  const text = event.detail?.text
  if (text) {
    inputText.value = `关于我之前提到的「${text.slice(0, 80)}」，请帮我进一步分析。`
  }
}

function handleMemoryChatTriggerDirect(text: string) {
  inputText.value = `关于我之前提到的「${text.slice(0, 80)}」，请帮我进一步分析。`
}

(window as unknown as Record<string, unknown>).__memoryChatTrigger = handleMemoryChatTriggerDirect

onMounted(async () => {
  await chatStore.checkBackend()
  if (chatStore.isBackendReady) {
    await Promise.all([
      agentStore.fetchAgents(),
      modelStore.fetchProviders(),
      modelStore.fetchModelConfig(),
      socialStore.fetchGroups(),
      socialStore.fetchAvailableAgents(),
      socialStore.fetchAgentRoles(),
    ])
  }
  document.addEventListener('click', handleClickOutsideModel)
  window.addEventListener('luominest:chat-trigger', handleChatTrigger as EventListener)
  window.addEventListener('luominest:memory-chat-trigger', handleMemoryChatTrigger as EventListener)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutsideModel)
  window.removeEventListener('luominest:chat-trigger', handleChatTrigger as EventListener)
  window.removeEventListener('luominest:memory-chat-trigger', handleMemoryChatTrigger as EventListener)
  ;(window as unknown as Record<string, unknown>).__memoryChatTrigger = undefined
  ttsStopSpeaking()
})
</script>

<template>
  <div class="workspace-layout">
    <aside class="left-panel">
      <WorkspaceContactPanel
        v-if="!selectedType"
        :agents="agentStore.agents"
        :groups="socialStore.groups"
        :search-query="contactSearchQuery"
        :selected-type="selectedType"
        :selected-agent-id="localSelectedAgent?.id || null"
        :selected-group-id="selectedGroupId"
        @update:search-query="contactSearchQuery = $event"
        @select-agent="selectAgent"
        @select-group="selectGroup"
        @create-agent="showCreateDialog = true"
        @create-group="showCreateGroupDialog = true"
        @delete-group="deleteGroup"
        @edit-agent="openEditDialog"
      />
      <WorkspaceAgentHistory
        v-else-if="selectedType === 'agent'"
        :agent="localSelectedAgent"
        :search-query="convSearchQuery"
        :is-search-mode="isSearchMode"
        :search-results="searchResults"
        :is-searching="isSearching"
        :time-groups="timeGroups"
        :batch-mode="batchMode"
        :selected-ids="selectedIds"
        :current-conv-id="currentConvId"
        :renaming-conv-id="renamingConvId"
        :renaming-title="renamingTitle"
        @back="backToContacts"
        @update:search-query="convSearchQuery = $event"
        @update:renaming-title="renamingTitle = $event"
        @new-conversation="handleNewConversation"
        @toggle-batch-mode="toggleBatchMode"
        @select-all="selectAll"
        @batch-delete="handleBatchDelete"
        @select-conversation="selectConversation"
        @start-rename="startRename"
        @confirm-rename="confirmRename"
        @cancel-rename="cancelRename"
        @delete-conversation="handleDeleteConversation"
        @toggle-select="toggleSelect"
      />
      <WorkspaceGroupInfo
        v-else-if="selectedType === 'group' && selectedGroup"
        :group="selectedGroup"
        :collaboration-mode="collaborationMode"
        @back="backToContacts"
        @toggle-collaboration-mode="collaborationMode = !collaborationMode"
        @add-agent="showAddAgentDialog = true"
        @remove-agent="removeAgentFromGroup(selectedGroup!.id, $event)"
      />
    </aside>

    <main class="chat-panel">
      <WorkspaceAgentChat
        v-if="selectedType === 'agent'"
        ref="agentChatRef"
        :messages="messages"
        :is-loading-current-conv="isLoadingCurrentConv"
        :is-streaming="isStreaming"
        :is-backend-ready="isBackendReady"
        :has-provider="hasProvider"
        :current-model="currentModel"
        :current-provider="currentProvider"
        :current-provider-logo="currentProviderLogo"
        :available-model-options="availableModelOptions"
        :show-model-dropdown="showModelDropdown"
        :chat-mode="chatMode"
        :chat-mode-options="chatModeOptions"
        :input-text="inputText"
        :can-send="canSend"
        :is-uploading="isUploading"
        :quoted-message="chatStore.quotedMessage"
        :context-usage="contextUsage"
        :context-percent="contextPercent"
        :context-tokens="contextTokens"
        :copied-id="copiedId"
        :show-reasoning="showReasoning"
        :current-suggestion-message-id="currentSuggestionMessageId"
        :is-tts-speaking="isTTSSpeaking"
        :tts-speaking-msg-id="ttsSpeakingMsgId"
        :agent="localSelectedAgent"
        :selected-skill-ids="selectedSkillIds"
        @check-backend="chatStore.checkBackend()"
        @go-settings="router.push('/settings/ai-model')"
        @toggle-reasoning="toggleReasoning"
        @copy-message="copyMessage"
        @quote-message="handleQuoteMessage"
        @tts-speak="ttsSpeak"
        @tts-stop="ttsStopSpeaking"
        @regenerate="handleRegenerate"
        @delete-message="handleDeleteMessage"
        @go-back-to-start="handleGoBackToStart"
        @switch-version="handleSwitchVersion"
        @suggestion-click="handleSuggestionClick"
        @update:input-text="inputText = $event"
        @update:selected-skill-ids="selectedSkillIds = $event"
        @send="sendMessage"
        @cancel="cancelStreaming"
        @toggle-model-dropdown="showModelDropdown = !showModelDropdown"
        @select-model="selectModel"
        @select-chat-mode="selectChatMode"
        @clear-quote="chatStore.quotedMessage = null"
        @file-preview="openFilePreview"
      />
      <WorkspaceGroupChat
        v-else-if="selectedType === 'group' && selectedGroup"
        ref="groupChatRef"
        :group="selectedGroup"
        :messages="groupMessages"
        :collaboration-mode="collaborationMode"
        :collaboration-active="collaborationActive"
        :collaboration-phase="collaborationPhase"
        :collaboration-tasks="collaborationTasks"
        :agents-responding="agentsResponding"
        :responding-agent-names="respondingAgentNames"
        :sending-group-message="sendingGroupMessage"
        :group-chat-input="groupChatInput"
        @toggle-collaboration-mode="collaborationMode = !collaborationMode"
        @add-agent="showAddAgentDialog = true"
        @update:group-chat-input="groupChatInput = $event"
        @send-group-message="sendGroupMessage"
      />
      <div v-else class="chat-empty-state">
        <div class="empty-visual">
          <div class="empty-orb">
            <MessageCircle :size="36" />
          </div>
        </div>
        <h3>选择一个联系人开始对话</h3>
        <p>在左侧选择 Agent 或群聊，开始你的对话</p>
      </div>
    </main>

    <WorkspaceDropOverlay :visible="showGlobalDropOverlay" />

    <FilePreview
      :visible="showFilePreview"
      :file-name="previewFile?.name || ''"
      :file-type="previewFile?.type"
      :file-content="previewFile?.content"
      @close="closeFilePreview"
    />

    <WorkspaceDialogs
      :show-create-dialog="showCreateDialog"
      :show-edit-dialog="showEditDialog"
      :show-confirm-dialog="showConfirmDialog"
      :show-create-group-dialog="showCreateGroupDialog"
      :show-add-agent-dialog="showAddAgentDialog"
      :create-form="newAgentForm"
      :edit-form="editAgentForm"
      :create-error="createDialogError"
      :confirm-message="confirmDialogMessage"
      :confirm-is-danger="confirmDialogIsDanger"
      :new-group-name="newGroupName"
      :new-group-desc="newGroupDesc"
      :add-agent-id="addAgentId"
      :add-agent-role="addAgentRole"
      :available-agents-for-group="availableAgentsForGroup"
      :agent-colors="agentColors"
      :preset-avatars="presetAvatars"
      :agent-roles="socialStore.agentRoles"
      @update:show-create-dialog="showCreateDialog = $event"
      @update:create-form="newAgentForm = $event"
      @update:create-error="createDialogError = $event"
      @create-agent="handleCreateAgent"
      @update:show-edit-dialog="showEditDialog = $event"
      @update:edit-form="editAgentForm = $event"
      @update-agent="handleUpdateAgent"
      @delete-agent="openConfirmDialog('确定要删除该 Agent 吗？此操作无法撤销。', handleDeleteAgent, true)"
      @confirm="handleConfirmDialogConfirm"
      @cancel="handleConfirmDialogCancel"
      @update:show-create-group-dialog="showCreateGroupDialog = $event"
      @update:new-group-name="newGroupName = $event"
      @update:new-group-desc="newGroupDesc = $event"
      @create-group="createGroup"
      @update:show-add-agent-dialog="showAddAgentDialog = $event"
      @update:add-agent-id="addAgentId = $event"
      @update:add-agent-role="addAgentRole = $event"
      @add-agent-to-group="addAgentToGroup"
    />
  </div>
</template>

<style scoped>
.workspace-layout {
  display: flex;
  height: 100%;
  overflow: hidden;
  background: var(--workspace-bg);
}

.left-panel {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--workspace-sidebar);
  border-right: 1px solid var(--workspace-border);
  overflow: hidden;
}

.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--workspace-bg);
  position: relative;
}

.chat-empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: var(--text-muted);
  gap: var(--space-4);
}

.chat-empty-state .empty-visual {
  position: relative;
}

.chat-empty-state .empty-orb {
  width: 100px;
  height: 100px;
  border-radius: var(--radius-full);
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 60px var(--lumi-brand-glow);
  animation: lumi-pulse 3s var(--ease-in-out) infinite;
}

.chat-empty-state h3 {
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.chat-empty-state p {
  font-size: var(--text-base);
  color: var(--text-muted);
  margin: 0;
}

@keyframes lumi-pulse {
  0%, 100% { transform: scale(1); opacity: 0.9; }
  50% { transform: scale(1.05); opacity: 1; }
}
</style>

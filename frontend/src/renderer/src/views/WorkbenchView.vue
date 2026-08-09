<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useChatStore } from '../stores/chat'
import { useAgentStore } from '../stores/agent'
import { useModelStore } from '../stores/model'
import { useMemoryStore } from '../stores/memory'
import { usePlatformStore } from '../stores/platform'
import { useAvatarControlStore } from '../stores/avatar-control'
import { useWorkflowStore } from '../stores/workflow'
import { useTaskNavigation } from '../composables/useTaskNavigation'
import { useWorkbenchSubAgents } from '../composables/useWorkbenchSubAgents'
import { useWorkbenchLive2D } from '../composables/useWorkbenchLive2D'
import { useWorkbenchSidebar } from '../composables/useWorkbenchSidebar'
import { useWorkbenchHistory } from '../composables/useWorkbenchHistory'
import { useWorkbenchMessages } from '../composables/useWorkbenchMessages'
import { LUOMINEST_BUILTIN_MODELS } from '../config/luominest-models'
import { MAIN_AGENT_ID, MAIN_AGENT_PROFILE } from '../constants'
import type { WorkflowPendingPlan } from '../components/workbench/types'
import WorkbenchHistoryPanel from '../components/workbench/WorkbenchHistoryPanel.vue'
import WorkbenchChatArea from '../components/workbench/WorkbenchChatArea.vue'
import WorkbenchInputArea from '../components/workbench/WorkbenchInputArea.vue'
import WorkbenchAvatarPanel from '../components/workbench/WorkbenchAvatarPanel.vue'
import WorkbenchToolPanel from '../components/workbench/WorkbenchToolPanel.vue'

// Store 初始化
const chatStore = useChatStore()
const agentStore = useAgentStore()
const modelStore = useModelStore()
const memoryStore = useMemoryStore()
const platformStore = usePlatformStore()
const avatarControl = useAvatarControlStore()
const workflowStore = useWorkflowStore()
const { navigateToTask } = useTaskNavigation()

// 桌面宠物模式：通过全局 store 状态统一管理，与 AvatarView 共享同一状态源
const isDesktopMode = computed(() => avatarControl.isDesktopPetRunning)

// 5 个 composable 组合（解构到顶层，确保 template 中 ref 自动解包）
const {
  toolActivities,
  expandedToolOutputs,
  subagentActivities,
  expandedSubagents,
  expandedSubagentTools,
  toggleToolOutput,
  toggleSubagent,
  toggleSubagentTools,
  handleSubagentEvent,
} = useWorkbenchSubAgents()

const {
  setCanvasRef,
  isModelReady,
  isModelLoading,
  loadError,
  loadModel,
  teardownLive2D,
  ttsEnabled,
  subtitleEnabled,
  currentModelInfo,
  isSpeaking,
  isSynthesizing,
  subtitleText,
  subtitleVisible,
  stopTts,
  dismissSubtitle,
  switchModel,
  showModelDropdown,
  currentModel,
  currentProvider,
  currentProviderLogo,
  availableModelOptions,
  selectModel,
  feedChunk,
  finishStream,
  filterCodeForTts,
  resetCodeBlockFilter,
} = useWorkbenchLive2D({ isDesktopMode })

const {
  isHistoryCollapsed,
  mcpStatus,
  sidePanelCollapsed,
  toggleSidePanel,
  fetchMcpStatus,
  memorySummaryPreview,
  activePlatformCount,
} = useWorkbenchSidebar()

const {
  searchQuery,
  searchResults,
  isSearching,
  isSearchMode,
  timeGroups,
  selectConversation,
  handleNewConversation,
  handleDeleteConversation,
  renamingConvId,
  renamingTitle,
  startRename,
  confirmRename,
  cancelRename,
} = useWorkbenchHistory({ agentId: MAIN_AGENT_ID })

// 输入区组件引用（view 定义，传入 composable，与 useWorkspaceMessages 的 agentChatRef 模式一致）
const inputAreaRef = ref<InstanceType<typeof WorkbenchInputArea> | null>(null)

const {
  inputText,
  selectedSkillIds,
  showReasoning,
  isNearBottom,
  showScrollToBottomBtn,
  chatMode,
  CHAT_MODE_OPTIONS,
  messages: messageList,
  isStreaming,
  isBackendReady,
  isLoadingCurrentConv,
  canSend,
  chatAreaRef,
  scrollToBottom,
  handleMessagesScroll,
  selectChatMode,
  sendMessage,
  cancelStreaming,
  handleRegenerate,
  contextTokens,
  contextMaxTokens,
  contextPercent,
  isCompressing,
  handleCompressContext,
} = useWorkbenchMessages({
  agentId: MAIN_AGENT_ID,
  handleSubagentEvent,
  toolActivities,
  subagentActivities,
  feedChunk,
  finishStream,
  filterCodeForTts,
  resetCodeBlockFilter,
  navigateToTask,
  selectModel,
  availableModelOptions,
  stopTts,
  inputAreaRef,
})

// 模型下拉外部点击关闭
const handleClickOutsideModel = (e: MouseEvent): void => {
  const target = e.target as HTMLElement
  if (!target.closest('.model-dropdown-container')) {
    showModelDropdown.value = false
  }
}

onMounted(async () => {
  agentStore.setActiveAgent(MAIN_AGENT_PROFILE)

  await chatStore.checkBackend()
  if (chatStore.isBackendReady) {
    await Promise.all([
      agentStore.fetchAgents(),
      modelStore.fetchProviders(),
      modelStore.fetchModelConfig(),
      platformStore.fetchMainAgent(),
      chatStore.fetchConversations(MAIN_AGENT_ID),
      memoryStore.fetchMemory(MAIN_AGENT_ID),
      memoryStore.fetchSummary(MAIN_AGENT_ID),
      platformStore.fetchInstances(),
      fetchMcpStatus(),
    ])
  }
  await avatarControl.checkDesktopPetStatus()
  if (!isDesktopMode.value) {
    const defaultModel = LUOMINEST_BUILTIN_MODELS[0]
    await loadModel(defaultModel.url, defaultModel.scale)
  }
  document.addEventListener('click', handleClickOutsideModel)
  nextTick(() => chatAreaRef.value?.setupResizeObserver())
})

onBeforeUnmount(() => {
  chatAreaRef.value?.teardownResizeObserver()
  document.removeEventListener('click', handleClickOutsideModel)
  // 桌宠模式下 TTS 引擎是全局 store，不随 WorkbenchView 卸载而停止（陪伴优先）；
  // 普通模式下 TTS 随页面切换中断（原有行为）。
  // teardownLive2D 在桌宠模式下已是 no-op（watch isDesktopMode 已卸载 canvas）。
  if (!isDesktopMode.value) {
    stopTts()
    teardownLive2D()
  }
})
</script>

<template>
  <div class="workbench-layout">
    <WorkbenchHistoryPanel
      v-model:search-query="searchQuery"
      v-model:renaming-title="renamingTitle"
      :is-search-mode="isSearchMode"
      :search-results="searchResults"
      :is-searching="isSearching"
      :time-groups="timeGroups"
      :current-conv-id="chatStore.currentConvId"
      :renaming-conv-id="renamingConvId"
      :is-history-collapsed="isHistoryCollapsed"
      @select="selectConversation"
      @new-conversation="handleNewConversation"
      @start-rename="startRename"
      @confirm-rename="confirmRename"
      @cancel-rename="cancelRename"
      @delete-conversation="handleDeleteConversation"
      @collapse="isHistoryCollapsed = true"
      @expand="isHistoryCollapsed = false"
    />

    <div class="workbench-chat">
      <WorkbenchChatArea
        ref="chatAreaRef"
        :messages="messageList"
        :is-loading-current-conv="isLoadingCurrentConv"
        :is-streaming="isStreaming"
        :is-backend-ready="isBackendReady"
        :current-model="currentModel"
        :tool-activities="toolActivities"
        :subagent-activities="subagentActivities"
        :expanded-tool-outputs="expandedToolOutputs"
        :expanded-subagents="expandedSubagents"
        :expanded-subagent-tools="expandedSubagentTools"
        :show-reasoning="showReasoning"
        :workflow-pending-plan="(workflowStore.pendingPlan as WorkflowPendingPlan | null)"
        :confirmation-feedback="workflowStore.confirmationFeedback"
        :is-near-bottom="isNearBottom"
        :show-scroll-to-bottom-btn="showScrollToBottomBtn"
        :context-tokens="contextTokens"
        :context-max-tokens="contextMaxTokens"
        :context-percent="contextPercent"
        :is-compressing="isCompressing"
        @toggle-reasoning="(id: string) => { showReasoning = { ...showReasoning, [id]: !showReasoning[id] } }"
        @regenerate="handleRegenerate"
        @toggle-tool-output="toggleToolOutput"
        @toggle-subagent="toggleSubagent"
        @toggle-subagent-tools="toggleSubagentTools"
        @confirm-plan="workflowStore.confirmPlan"
        @reject-plan="workflowStore.rejectPlan"
        @update:confirmation-feedback="(v: string) => workflowStore.confirmationFeedback = v"
        @scroll="handleMessagesScroll"
        @scroll-to-bottom="scrollToBottom(true)"
        @retry-backend="chatStore.checkBackend()"
        @set-input-text="(text: string) => inputText = text"
        @navigate-to-workflow="navigateToTask('workflow')"
        @compress-context="handleCompressContext"
      />

      <WorkbenchInputArea
        ref="inputAreaRef"
        v-model:input-text="inputText"
        :chat-mode="chatMode"
        v-model:selected-skill-ids="selectedSkillIds"
        :is-backend-ready="isBackendReady"
        :is-streaming="isStreaming"
        :can-send="canSend"
        :current-model="currentModel"
        :current-provider="currentProvider"
        :current-provider-logo="currentProviderLogo"
        :available-model-options="availableModelOptions"
        :show-model-dropdown="showModelDropdown"
        :chat-mode-options="CHAT_MODE_OPTIONS"
        @send="sendMessage"
        @cancel="cancelStreaming"
        @toggle-model-dropdown="showModelDropdown = !showModelDropdown"
        @select-model="selectModel"
        @select-chat-mode="selectChatMode"
      />
    </div>

    <div class="workbench-avatar">
      <WorkbenchAvatarPanel
        :is-desktop-mode="isDesktopMode"
        :current-model-info="currentModelInfo"
        :is-model-loading="isModelLoading"
        :is-model-ready="isModelReady"
        :load-error="loadError"
        :is-speaking="isSpeaking"
        :is-synthesizing="isSynthesizing"
        :subtitle-visible="subtitleVisible"
        :subtitle-text="subtitleText"
        :tts-enabled="ttsEnabled"
        :subtitle-enabled="subtitleEnabled"
        :builtin-models="LUOMINEST_BUILTIN_MODELS"
        :set-canvas-ref="setCanvasRef"
        @switch-model="switchModel"
        @toggle-tts="ttsEnabled = !ttsEnabled"
        @toggle-subtitle="subtitleEnabled = !subtitleEnabled"
        @stop-tts="stopTts"
        @dismiss-subtitle="dismissSubtitle"
      />

      <WorkbenchToolPanel
        :memory-fact-count="memoryStore.facts.length"
        :memory-profile-name="memoryStore.profile.name"
        :memory-summary-preview="memorySummaryPreview"
        :mcp-status="mcpStatus"
        :platform-instances="platformStore.instances"
        :active-platform-count="activePlatformCount"
        :subagent-activities="subagentActivities"
        :collapsed="sidePanelCollapsed"
        @toggle-panel="toggleSidePanel"
      />
    </div>
  </div>
</template>

<style scoped>
.workbench-layout {
  display: flex;
  width: 100%;
  height: 100%;
  background: transparent;
  overflow: hidden;
  position: relative;
}

.workbench-chat {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: transparent;
  position: relative;
}

.workbench-avatar {
  width: 340px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: color-mix(in srgb, var(--surface) 92%, transparent);
  border-left: 1px solid var(--border-light);
  flex-shrink: 0;
  overflow: hidden;
  -webkit-backdrop-filter: var(--glass-blur);
  backdrop-filter: var(--glass-blur);
  transition: background-color var(--transition-normal);
}

/* 有全局背景壁纸时，右侧面板使用更强的毛玻璃表面。
   支持全部运行时背景激活标记（与 variables.css 保持一致） */
.lumi-app.lumi-app--bg-active .workbench-avatar,
.lumi-app.has-background .workbench-avatar,
[data-lumi-background="active"] .lumi-app .workbench-avatar {
  background: var(--glass-surface);
  border-left-color: var(--glass-border);
}
</style>

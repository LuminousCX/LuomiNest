<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ChevronLeft, ChevronRight } from 'lucide-vue-next'
import { useAgentStore } from '../stores/agent'
import { useChatStore } from '../stores/chat'
import { useChatTrashStore } from '../stores/chat-trash'
import SidebarNav from './SidebarNav.vue'
import SidebarHistory from './SidebarHistory.vue'
import SidebarTrash from './SidebarTrash.vue'

const route = useRoute()
const agentStore = useAgentStore()
const chatStore = useChatStore()
const chatTrashStore = useChatTrashStore()

const isHistoryCollapsed = ref(false)
const showTrash = ref(false)

const trashCount = computed(() => chatTrashStore.trashItems.length)

const showHistoryPanel = computed(() => route.path === '/workspace')

const openTrash = async () => {
  showTrash.value = true
  await chatTrashStore.fetchTrash(agentStore.activeAgent?.id)
}

const closeTrash = () => {
  showTrash.value = false
}

onMounted(async () => {
  await agentStore.fetchAgents()
  if (agentStore.activeAgent?.id) {
    await chatStore.fetchConversations(agentStore.activeAgent.id)
    chatTrashStore.fetchTrash(agentStore.activeAgent.id)
  }
})
</script>

<template>
  <div class="lumi-sidebar">
    <SidebarNav />

    <div class="history-panel-wrapper">
      <Transition name="history-slide">
        <div v-if="showHistoryPanel && !isHistoryCollapsed" class="sidebar-history-panel">
          <SidebarHistory v-if="!showTrash" :trash-count="trashCount" @open-trash="openTrash" />
          <SidebarTrash v-else @close="closeTrash" />
        </div>
      </Transition>
    </div>

    <button
      v-if="showHistoryPanel && !isHistoryCollapsed"
      class="collapse-history-btn"
      title="收起历史记录"
      @click="isHistoryCollapsed = true"
    >
      <ChevronLeft :size="14" />
    </button>

    <button
      v-if="showHistoryPanel && isHistoryCollapsed"
      class="history-expand-toggle"
      title="展开历史记录"
      @click="isHistoryCollapsed = false"
    >
      <ChevronRight :size="14" />
    </button>
  </div>
</template>

<style scoped>
.lumi-sidebar {
  display: flex;
  height: 100%;
  background: var(--surface);
  box-shadow: var(--shadow-sm);
  position: relative;
  overflow: visible;
  z-index: 1;
}

.history-panel-wrapper {
  display: flex;
  height: 100%;
  align-items: stretch;
  position: relative;
}

.sidebar-history-panel {
  width: 220px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-secondary);
  overflow: hidden;
  flex-shrink: 0;
  position: relative;
}

.collapse-history-btn {
  width: 16px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 0 6px 6px 0;
  color: var(--text-muted);
  cursor: pointer;
  background: var(--surface);
  border: none;
  border-left: 1px solid var(--divider-soft);
  transition: all var(--transition-fast);
  position: absolute;
  right: -16px;
  top: 50%;
  transform: translateY(-50%);
  z-index: 20;
  padding: 0;
}

.collapse-history-btn:hover {
  color: var(--lumi-primary);
  background: var(--surface-hover);
}

.history-expand-toggle {
  width: 16px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 0 6px 6px 0;
  color: var(--text-muted);
  cursor: pointer;
  background: var(--surface);
  border: none;
  border-left: 1px solid var(--divider-soft);
  transition: all var(--transition-fast);
  position: absolute;
  right: -16px;
  top: 50%;
  transform: translateY(-50%);
  z-index: 20;
  padding: 0;
}

.history-expand-toggle:hover {
  color: var(--lumi-primary);
  background: var(--surface-hover);
}

.history-slide-enter-active {
  animation: history-slide-in 0.2s ease-in-out;
}

.history-slide-leave-active {
  animation: history-slide-out 0.15s ease-in-out;
}

@keyframes history-slide-in {
  from { opacity: 0; transform: translateX(-10px); }
  to { opacity: 1; transform: translateX(0); }
}

@keyframes history-slide-out {
  from { opacity: 1; transform: translateX(0); }
  to { opacity: 0; transform: translateX(-10px); }
}
</style>

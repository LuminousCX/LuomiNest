<script setup lang="ts">
import { onMounted } from 'vue'
import { useAgentStore } from '../stores/agent'
import { useChatStore } from '../stores/chat'
import { useChatTrashStore } from '../stores/chat-trash'
import SidebarNav from './SidebarNav.vue'

const agentStore = useAgentStore()
const chatStore = useChatStore()
const chatTrashStore = useChatTrashStore()

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
  z-index: var(--z-base);
}
</style>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Send, Square, X } from 'lucide-vue-next'

const input = ref('')
const streaming = ref(false)
const canSend = computed(() => input.value.trim().length > 0 && !streaming.value)
let streamingHandler: ((event: unknown, value: boolean) => void) | null = null

const send = () => {
  const text = input.value.trim()
  if (!text || streaming.value) return
  input.value = ''
  streaming.value = true
  window.api.desktopPetChat.sendMessage(text)
}

const cancel = () => window.api.desktopPetChat.cancel()
const closeWindow = () => window.close()
const keydown = (event: KeyboardEvent) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    send()
  }
}

onMounted(() => {
  document.documentElement.classList.add('desktop-pet-chat')
  streamingHandler = (_event, value) => { streaming.value = value }
  window.electron?.ipcRenderer.on('desktop-pet:streaming-state', streamingHandler)
})

onBeforeUnmount(() => {
  document.documentElement.classList.remove('desktop-pet-chat')
  if (streamingHandler) {
    window.electron?.ipcRenderer.removeListener('desktop-pet:streaming-state', streamingHandler)
  }
})
</script>

<template>
  <main class="dialog-bar">
    <span class="drag-handle" aria-hidden="true"></span>
    <input
      v-model="input"
      type="text"
      :disabled="streaming"
      :placeholder="streaming ? 'Luomi 正在思考…' : '和 Luomi 说点什么…'"
      autofocus
      @keydown="keydown"
    />
    <button v-if="!streaming" class="action send" :disabled="!canSend" title="发送" @click="send">
      <Send :size="17" />
    </button>
    <button v-else class="action stop" title="停止生成" @click="cancel">
      <Square :size="14" />
    </button>
    <button class="action close" title="关闭对话框" @click="closeWindow">
      <X :size="17" />
    </button>
  </main>
</template>

<style scoped>
:global(html.desktop-pet-chat),
:global(html.desktop-pet-chat body),
:global(html.desktop-pet-chat #app) {
  width: 100%;
  height: 100%;
  margin: 0;
  overflow: hidden;
  background: transparent !important;
}

.dialog-bar {
  box-sizing: border-box;
  width: calc(100% - 12px);
  height: 62px;
  margin: 6px;
  padding: 7px 7px 7px 18px;
  display: flex;
  align-items: center;
  gap: 7px;
  overflow: hidden;
  border: 1px solid rgba(133, 105, 190, 0.24);
  border-radius: 19px;
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.97), rgba(248, 244, 255, 0.95));
  box-shadow: 0 12px 34px rgba(60, 43, 93, 0.22), inset 0 1px rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(24px) saturate(135%);
  -webkit-app-region: drag;
}

.drag-handle {
  width: 4px;
  height: 22px;
  flex: 0 0 auto;
  border-radius: 99px;
  background: linear-gradient(#a78cdd, #d09aca);
  opacity: 0.72;
}

input {
  min-width: 0;
  flex: 1;
  height: 42px;
  padding: 0 4px;
  border: 0;
  outline: 0;
  color: #302b3a;
  background: transparent;
  font: 500 14px/1.4 inherit;
  -webkit-app-region: no-drag;
}

input::placeholder { color: #a09aa9; }
input:disabled { opacity: 0.72; }

.action {
  width: 38px;
  height: 38px;
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  border: 0;
  border-radius: 13px;
  cursor: pointer;
  transition: transform 150ms ease, background 150ms ease, color 150ms ease, opacity 150ms ease;
  -webkit-app-region: no-drag;
}

.action:hover { transform: translateY(-1px); }
.send { color: white; background: linear-gradient(135deg, #8066d1, #bd7bc9); box-shadow: 0 6px 14px rgba(126, 94, 196, 0.28); }
.send:disabled { opacity: 0.35; cursor: default; transform: none; box-shadow: none; }
.stop { color: white; background: linear-gradient(135deg, #d75f78, #e58d91); }
.close { color: #81798c; background: rgba(116, 91, 157, 0.07); }
.close:hover { color: #5d526d; background: rgba(116, 91, 157, 0.14); }
</style>

<script setup lang="ts">
import { ref } from 'vue'
import { Play, X } from 'lucide-vue-next'

const input = ref('')
const output = ref('')
const mode = ref<'script' | 'dom'>('script')

const emit = defineEmits<{
  execute: [script: string]
  close: []
}>()

function handleExecute() {
  if (!input.value.trim()) return
  emit('execute', input.value)
}
</script>

<template>
  <div class="dev-panel">
    <div class="dev-header">
      <div class="dev-tabs">
        <button 
          :class="['dev-tab', { active: mode === 'script' }]"
          @click="mode = 'script'"
        >
          脚本
        </button>
        <button 
          :class="['dev-tab', { active: mode === 'dom' }]"
          @click="mode = 'dom'"
        >
          DOM
        </button>
      </div>
      <button class="dev-close" @click="emit('close')">
        <X :size="16" />
      </button>
    </div>
    
    <div class="dev-content">
      <div class="dev-input-area">
        <textarea
          v-model="input"
          :placeholder="mode === 'script' ? '输入 JavaScript 代码...' : 'DOM 内容将显示在这里'"
          class="dev-input"
          :readonly="mode === 'dom'"
        ></textarea>
        <button 
          v-if="mode === 'script'"
          class="dev-execute"
          :disabled="!input.trim()"
          @click="handleExecute"
        >
          <Play :size="14" />
          执行
        </button>
      </div>
      
      <div class="dev-output">
        <pre v-if="output">{{ output }}</pre>
        <span v-else class="output-placeholder">输出将显示在这里</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dev-panel {
  height: 220px;
  background: #1c1917;
  border-top: 1px solid #292524;
  display: flex;
  flex-direction: column;
}

.dev-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid #292524;
}

.dev-tabs {
  display: flex;
  gap: 4px;
}

.dev-tab {
  padding: 4px 12px;
  border-radius: 4px;
  background: transparent;
  border: none;
  color: #a8a29e;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.dev-tab:hover {
  color: #d6d3d1;
}

.dev-tab.active {
  background: #292524;
  color: #fafaf9;
}

.dev-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 4px;
  background: transparent;
  border: none;
  color: #78716c;
  cursor: pointer;
  transition: all 0.15s ease;
}

.dev-close:hover {
  background: #292524;
  color: #d6d3d1;
}

.dev-content {
  flex: 1;
  display: flex;
  gap: 1px;
  overflow: hidden;
}

.dev-input-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #292524;
}

.dev-input {
  flex: 1;
  padding: 12px;
  background: transparent;
  border: none;
  color: #fafaf9;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  resize: none;
  outline: none;
}

.dev-input::placeholder {
  color: #57534e;
}

.dev-execute {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 16px;
  margin: 8px;
  border-radius: 6px;
  background: #3b82f6;
  border: none;
  color: #ffffff;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.dev-execute:hover:not(:disabled) {
  background: #2563eb;
}

.dev-execute:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.dev-output {
  flex: 1;
  background: #292524;
  padding: 12px;
  overflow: auto;
}

.dev-output pre {
  margin: 0;
  color: #a8a29e;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}

.output-placeholder {
  color: #57534e;
  font-size: 12px;
}
</style>

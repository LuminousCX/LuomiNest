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
  background: var(--text);
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
}

.dev-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border);
}

.dev-tabs {
  display: flex;
  gap: var(--space-1);
}

.dev-tab {
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-sm);
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-size: var(--text-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.dev-tab:hover {
  color: var(--text-secondary);
}

.dev-tab.active {
  background: var(--border);
  color: var(--text-inverse);
}

.dev-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: var(--radius-sm);
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.dev-close:hover {
  background: var(--border);
  color: var(--text-secondary);
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
  background: var(--border);
}

.dev-input {
  flex: 1;
  padding: var(--space-3);
  background: transparent;
  border: none;
  color: var(--text-inverse);
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  resize: none;
  outline: none;
}

.dev-input::placeholder {
  color: var(--text-muted);
}

.dev-execute {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-4);
  margin: var(--space-2);
  border-radius: var(--radius-sm);
  background: var(--lumi-info);
  border: none;
  color: var(--text-inverse);
  font-size: var(--text-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.dev-execute:hover:not(:disabled) {
  background: var(--lumi-info-hover);
}

.dev-execute:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.dev-output {
  flex: 1;
  background: var(--border);
  padding: var(--space-3);
  overflow: auto;
}

.dev-output pre {
  margin: 0;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  white-space: pre-wrap;
  word-break: break-all;
}

.output-placeholder {
  color: var(--text-muted);
  font-size: var(--text-sm);
}
</style>

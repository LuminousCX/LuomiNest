<script setup lang="ts">
import { ref } from 'vue'
import { Play, X } from 'lucide-vue-next'
import LumiButton from '../common/LumiButton.vue'

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
      <LumiButton variant="ghost" size="sm" icon-only aria-label="关闭" @click="emit('close')">
        <template #icon>
          <X :size="16" />
        </template>
      </LumiButton>
    </div>
    
    <div class="dev-content">
      <div class="dev-input-area">
        <textarea
          v-model="input"
          :placeholder="mode === 'script' ? '输入 JavaScript 代码...' : 'DOM 内容将显示在这里'"
          class="dev-input"
          :readonly="mode === 'dom'"
        ></textarea>
        <LumiButton
          v-if="mode === 'script'"
          variant="primary"
          size="sm"
          :disabled="!input.trim()"
          @click="handleExecute"
        >
          <template #icon>
            <Play :size="14" />
          </template>
          执行
        </LumiButton>
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
  height: calc(var(--space-9) * 4 + var(--btn-height-sm));
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

.dev-content {
  flex: 1;
  display: flex;
  gap: calc(var(--space-1) / 4);
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

.dev-input-area .lumi-btn {
  margin: var(--space-2);
  align-self: flex-start;
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

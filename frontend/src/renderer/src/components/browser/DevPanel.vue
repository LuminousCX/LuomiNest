<script setup lang="ts">
import { ref, watch } from 'vue'
import { Play, X, RefreshCw } from 'lucide-vue-next'
import LumiButton from '../common/LumiButton.vue'

/**
 * 浏览器开发者面板。
 * - 脚本 tab：输入并执行 JavaScript，结果输出到下方
 * - DOM tab：读取当前页面的索引化 DOM 树（data-luomi-index），供快速定位元素
 *
 * 通过 preload 暴露的 window.api.browserAutomation.execute 调用 main 进程的
 * luomiAutomationExecutor（与后端 AI 工具走同一执行器）。
 */

const input = ref('')
const output = ref('')
const loading = ref(false)
const mode = ref<'script' | 'dom'>('script')

const emit = defineEmits<{
  close: []
}>()

const MAX_OUTPUT = 8000

/** 截断过长输出，附加提示 */
const truncate = (text: string): string => {
  if (text.length > MAX_OUTPUT) {
    return text.slice(0, MAX_OUTPUT) + '\n\n...（已截断，完整结果见控制台）'
  }
  return text
}

/** 执行 JavaScript 脚本 */
const executeScript = async (): Promise<void> => {
  const script = input.value.trim()
  if (!script || loading.value) return
  loading.value = true
  output.value = '执行中...'
  try {
    const result = await window.api?.browserAutomation?.execute('execute_js', { script })
    if (result?.success) {
      const data = result.data?.result
      output.value = truncate(typeof data === 'string' ? data : JSON.stringify(data, null, 2))
    } else {
      output.value = `[错误] ${result?.error || '脚本执行失败'}`
    }
  } catch (e: any) {
    output.value = `[错误] 浏览器脚本执行失败：${e?.message || e}`
  } finally {
    loading.value = false
  }
}

/** 读取索引化 DOM 树 */
const fetchDomTree = async (): Promise<void> => {
  if (loading.value) return
  loading.value = true
  output.value = '正在读取 DOM 树...'
  try {
    const result = await window.api?.browserAutomation?.execute('get_dom_tree', { maxDepth: 8, maxElements: 150 })
    if (result?.success) {
      const tree = result.data?.tree
      const total = result.data?.totalCount ?? 0
      const header = `共索引 ${total} 个可交互元素\n页面：${result.data?.title || ''}\n${result.data?.url || ''}\n${'─'.repeat(40)}\n`
      output.value = truncate(header + formatDomTree(tree, 0))
    } else {
      output.value = `[错误] ${result?.error || '读取 DOM 失败'}`
    }
  } catch (e: any) {
    output.value = `[错误] DOM 读取失败：${e?.message || e}`
  } finally {
    loading.value = false
  }
}

/** 递归格式化 DOM 树节点为缩进文本 */
const formatDomTree = (node: any, depth: number): string => {
  if (!node || typeof node !== 'object') return String(node ?? '')
  const indent = '  '.repeat(depth)
  const tag = node.tag || '?'
  const index = node.index
  const indexMark = (index !== undefined && index !== null && index !== 0) ? `[${index}]` : ''
  const role = node.role ? ` role=${node.role}` : ''
  const text = String(node.text || '').trim().slice(0, 60)
  const textMark = text ? ` "${text}"` : ''
  const lines = [`${indent}<${tag}>${indexMark}${role}${textMark}`]
  const children = node.children
  if (Array.isArray(children)) {
    for (const child of children.slice(0, 20)) {
      lines.push(formatDomTree(child, depth + 1))
    }
  }
  return lines.join('\n')
}

// 切换到 DOM tab 时自动获取 DOM 树
watch(mode, (m) => {
  if (m === 'dom') {
    fetchDomTree()
  }
})

/** 切换 tab 模式（供父组件通过 ref 调用） */
const switchMode = (m: 'script' | 'dom'): void => {
  mode.value = m
}

defineExpose({ switchMode })
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
      <div class="dev-actions">
        <LumiButton
          v-if="mode === 'dom'"
          variant="ghost"
          size="sm"
          icon-only
          aria-label="刷新 DOM"
          :disabled="loading"
          @click="fetchDomTree"
        >
          <template #icon>
            <RefreshCw :size="14" />
          </template>
        </LumiButton>
        <LumiButton variant="ghost" size="sm" icon-only aria-label="关闭" @click="emit('close')">
          <template #icon>
            <X :size="16" />
          </template>
        </LumiButton>
      </div>
    </div>

    <div class="dev-content">
      <div class="dev-input-area">
        <textarea
          v-model="input"
          :placeholder="mode === 'script' ? '输入 JavaScript 代码...' : 'DOM 内容将显示在这里'"
          class="dev-input"
          :readonly="mode === 'dom'"
          :class="{ 'is-readonly': mode === 'dom' }"
        ></textarea>
        <LumiButton
          v-if="mode === 'script'"
          variant="primary"
          size="sm"
          :disabled="!input.trim() || loading"
          @click="executeScript"
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

.dev-actions {
  display: flex;
  gap: var(--space-1);
  align-items: center;
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

.dev-input.is-readonly {
  cursor: default;
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

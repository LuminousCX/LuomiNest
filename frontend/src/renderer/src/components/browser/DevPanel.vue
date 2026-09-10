<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Play, X, RefreshCw } from 'lucide-vue-next'
import LumiButton from '../common/LumiButton.vue'

const { t } = useI18n()

/**
 * 浏览器开发者面板。
 * - 脚本 tab：输入并执行 JavaScript，结果输出到下方
 * - DOM tab：读取当前页面的索引化 DOM 树（data-luomi-index），供快速定位元素
 * - 源码 tab：读取当前页面 HTML（outerHTML）
 *
 * 通过 preload 暴露的 window.api.browserAutomation.execute 调用 main 进程的
 * luomiAutomationExecutor（与后端 AI 工具走同一执行器）。
 */

const input = ref('')
const output = ref('')
const loading = ref(false)
const mode = ref<'script' | 'dom' | 'html'>('script')

const emit = defineEmits<{
  close: []
}>()

const MAX_OUTPUT = 8000

/** 索引化 DOM 树节点（由 browserAutomation.execute('get_dom_tree') 返回） */
interface DomTreeNode {
  tag?: string
  index?: number
  role?: string
  text?: string
  children?: DomTreeNode[]
  [key: string]: unknown
}

/** 截断过长输出，附加提示 */
const truncate = (text: string): string => {
  if (text.length > MAX_OUTPUT) {
    return text.slice(0, MAX_OUTPUT) + '\n\n' + t('browser.dev.truncated')
  }
  return text
}

/** 执行 JavaScript 脚本 */
const executeScript = async (): Promise<void> => {
  const script = input.value.trim()
  if (!script || loading.value) return
  loading.value = true
  output.value = t('browser.dev.executing')
  try {
    const result = await window.api?.browserAutomation?.execute('execute_js', { script })
    if (result?.success) {
      const data = result.data?.result
      output.value = truncate(typeof data === 'string' ? data : JSON.stringify(data, null, 2))
    } else {
      output.value = t('browser.dev.errorPrefix', { msg: result?.error || t('browser.dev.scriptFailed') })
    }
  } catch (e: unknown) {
    output.value = t('browser.dev.scriptError', { msg: e instanceof Error ? e.message : String(e) })
  } finally {
    loading.value = false
  }
}

/** 读取索引化 DOM 树 */
const fetchDomTree = async (): Promise<void> => {
  if (loading.value) return
  loading.value = true
  output.value = t('browser.dev.readingDom')
  try {
    const result = await window.api?.browserAutomation?.execute('get_dom_tree', { maxDepth: 8, maxElements: 150 })
    if (result?.success) {
      const tree = result.data?.tree
      const total = result.data?.totalCount ?? 0
      const header = t('browser.dev.domHeader', { n: total, title: result.data?.title || '', url: result.data?.url || '' })
      output.value = truncate(header + '─'.repeat(40) + '\n' + formatDomTree(tree as DomTreeNode | undefined, 0))
    } else {
      output.value = t('browser.dev.errorPrefix', { msg: result?.error || t('browser.dev.domFailed') })
    }
  } catch (e: unknown) {
    output.value = t('browser.dev.domError', { msg: e instanceof Error ? e.message : String(e) })
  } finally {
    loading.value = false
  }
}

/** 递归格式化 DOM 树节点为缩进文本 */
const formatDomTree = (node: DomTreeNode | undefined, depth: number): string => {
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

/** 读取当前页 HTML 源码 */
const fetchHtml = async (): Promise<void> => {
  if (loading.value) return
  loading.value = true
  output.value = t('browser.dev.readingHtml')
  try {
    const result = await window.api?.browserAutomation?.execute('get_html', {})
    if (result?.success) {
      const data = result.data as { html?: string } | undefined
      output.value = truncate(typeof data?.html === 'string' ? data.html : JSON.stringify(data, null, 2))
    } else {
      output.value = t('browser.dev.errorPrefix', { msg: result?.error || t('browser.dev.htmlFailed') })
    }
  } catch (e: unknown) {
    output.value = t('browser.dev.htmlError', { msg: e instanceof Error ? e.message : String(e) })
  } finally {
    loading.value = false
  }
}

// 切换到 DOM/源码 tab 时自动获取
watch(mode, (m) => {
  if (m === 'dom') {
    fetchDomTree()
  } else if (m === 'html') {
    fetchHtml()
  }
})

/** 切换 tab 模式（供父组件通过 ref 调用） */
const switchMode = (m: 'script' | 'dom' | 'html'): void => {
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
          {{ t('browser.dev.tabScript') }}
        </button>
        <button
          :class="['dev-tab', { active: mode === 'dom' }]"
          @click="mode = 'dom'"
        >
          DOM
        </button>
        <button
          :class="['dev-tab', { active: mode === 'html' }]"
          @click="mode = 'html'"
        >
          {{ t('browser.dev.tabHtml') }}
        </button>
      </div>
      <div class="dev-actions">
        <LumiButton
          v-if="mode === 'dom'"
          variant="ghost"
          size="sm"
          icon-only
          :aria-label="t('browser.dev.refreshDom')"
          :disabled="loading"
          @click="fetchDomTree"
        >
          <template #icon>
            <RefreshCw :size="14" />
          </template>
        </LumiButton>
        <LumiButton variant="ghost" size="sm" icon-only :aria-label="t('browser.dev.close')" @click="emit('close')">
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
          :placeholder="mode === 'script' ? t('browser.dev.scriptPlaceholder') : mode === 'html' ? t('browser.dev.htmlPlaceholder') : t('browser.dev.domPlaceholder')"
          class="dev-input"
          :readonly="mode !== 'script'"
          :class="{ 'is-readonly': mode !== 'script' }"
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
          {{ t('browser.dev.execute') }}
        </LumiButton>
      </div>

      <div class="dev-output">
        <pre v-if="output">{{ output }}</pre>
        <span v-else class="output-placeholder">{{ t('browser.dev.outputPlaceholder') }}</span>
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

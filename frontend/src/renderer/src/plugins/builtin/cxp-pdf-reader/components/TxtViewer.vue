<script setup lang="ts">
/**
 * TxtViewer — TXT 文档查看器。
 *
 * 简单地以等宽字体显示纯文本内容（pre 标签渲染）。
 */
import { computed } from 'vue'
import { FileText } from 'lucide-vue-next'

const props = defineProps<{
  text: string
}>()

// 文本统计
const stats = computed(() => {
  const text = props.text ?? ''
  return {
    chars: text.length,
    lines: text ? text.split(/\r?\n/).length : 0,
  }
})
</script>

<template>
  <div class="txt-viewer">
    <div v-if="!text" class="txt-empty">
      <FileText :size="48" class="empty-icon" />
      <p class="empty-text">文档内容为空</p>
      <p class="empty-hint">后端可能未提取到文本内容</p>
    </div>

    <div v-else class="txt-container">
      <div class="txt-meta">
        <span>{{ stats.lines }} 行</span>
        <span>{{ stats.chars }} 字符</span>
      </div>
      <pre class="txt-content">{{ text }}</pre>
    </div>
  </div>
</template>

<style scoped>
.txt-viewer {
  flex: 1;
  overflow: auto;
  background: var(--bg-secondary);
  padding: var(--space-6) var(--space-8);
}

.txt-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-10) var(--space-4);
  color: var(--text-muted);
  text-align: center;
}

.empty-icon {
  opacity: 0.4;
}

.empty-text {
  font-size: var(--text-md);
  color: var(--text-secondary);
}

.empty-hint {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.txt-container {
  max-width: 960px;
  margin: 0 auto;
  background: var(--surface);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.txt-meta {
  display: flex;
  gap: var(--space-4);
  padding: var(--space-2) var(--space-4);
  background: var(--surface-hover);
  border-bottom: 1px solid var(--border);
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}

.txt-content {
  margin: 0;
  padding: var(--space-5) var(--space-6);
  font-family: var(--font-mono);
  font-size: var(--text-base);
  line-height: var(--leading-relaxed);
  color: var(--text);
  white-space: pre-wrap;
  word-break: break-word;
  tab-size: 4;
}
</style>

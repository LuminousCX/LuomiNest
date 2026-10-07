<script setup lang="ts">
/**
 * 群聊线程头部（本地群/云群共用）。
 * 图标 + 标题 + 副标题 + 右侧动作区；动作按钮由宿主通过 actions 插槽提供
 * （按钮的 hover/active 样式留在宿主，插槽内容归宿主 scoped 作用域）。
 */
import type { Component } from 'vue'

defineProps<{
  icon: Component
  title: string
  subtitle: string
}>()
</script>

<template>
  <div class="chat-thread-header">
    <div class="chat-title-area">
      <div class="chat-avatar-mini">
        <component :is="icon" :size="14" />
      </div>
      <div class="chat-title-text">
        <h3 class="lumi-title-md">{{ title }}</h3>
        <span class="chat-status-line">{{ subtitle }}</span>
      </div>
    </div>
    <div class="chat-actions lumi-row-1">
      <slot name="actions" />
    </div>
  </div>
</template>

<style scoped>
.chat-thread-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-5);
  border-bottom: 1px solid var(--border-light);
  background: var(--surface);
  flex-shrink: 0;
}

.chat-title-area {
  display: flex;
  align-items: center;
  gap: 10px;
}

.chat-avatar-mini {
  width: var(--space-7);
  height: var(--space-7);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--lumi-brand-glow);
  color: var(--lumi-brand);
}

/* 颜色/字号/字重由全局 .lumi-title-md 提供，本地只留 margin 复位 */
.chat-title-text h3 {
  margin: 0;
}

.chat-status-line {
  font-size: var(--text-xs);
  color: var(--text-muted);
}
</style>

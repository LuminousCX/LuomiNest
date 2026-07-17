<script setup lang="ts">
import { ref } from 'vue'
import { Sparkles, Bell } from 'lucide-vue-next'
import type { CxPluginContext } from '../../types'

defineProps<{
  /** 由路由注入的插件上下文（可选，用于演示） */
  context?: CxPluginContext
}>()

const clickCount = ref(0)
const lastMessage = ref('')

const handleSayHello = () => {
  clickCount.value++
  lastMessage.value = `Hello from LuomiNest frontend plugin! (第 ${clickCount.value} 次点击)`
}

const handleNotify = () => {
  if (window.Notification?.permission === 'granted') {
    new Notification('LuomiNest 插件系统', { body: '示例插件通知已触发' })
  } else if (window.Notification?.permission !== 'denied') {
    window.Notification?.requestPermission().then((perm) => {
      if (perm === 'granted') {
        new Notification('LuomiNest 插件系统', { body: '示例插件通知已触发' })
      }
    })
  }
}
</script>

<template>
  <div class="hello-panel-view">
    <div class="panel-header animate-fade-in">
      <div class="header-icon">
        <Sparkles :size="28" />
      </div>
      <div>
        <h1 class="page-title">示例面板</h1>
        <p class="page-subtitle">由 hello-panel 前端插件贡献 — 验证 LuomiNest 双轨扩展系统</p>
      </div>
    </div>

    <div class="panel-body">
      <div class="info-card animate-slide-up">
        <h3 class="card-title">插件信息</h3>
        <dl class="info-list">
          <div class="info-row">
            <dt>插件 ID</dt>
            <dd><code>hello-panel</code></dd>
          </div>
          <div class="info-row">
            <dt>版本</dt>
            <dd><code>1.0.0</code></dd>
          </div>
          <div class="info-row">
            <dt>贡献点</dt>
            <dd>视图（本页面）+ 命令（say-hello）</dd>
          </div>
          <div class="info-row">
            <dt>路由路径</dt>
            <dd><code>/plugins/hello-panel/panel</code></dd>
          </div>
        </dl>
      </div>

      <div class="action-card animate-slide-up" style="animation-delay: 80ms">
        <h3 class="card-title">交互演示</h3>
        <p class="card-desc">点击下方按钮触发插件命令，验证贡献点机制端到端可用。</p>
        <div class="actions">
          <button class="action-btn primary" @click="handleSayHello">
            <Sparkles :size="16" />
            <span>执行 say-hello 命令</span>
          </button>
          <button class="action-btn" @click="handleNotify">
            <Bell :size="16" />
            <span>发送系统通知</span>
          </button>
        </div>
        <Transition name="fade-slide">
          <div v-if="lastMessage" class="message-box">
            {{ lastMessage }}
          </div>
        </Transition>
      </div>
    </div>
  </div>
</template>

<style scoped>
.hello-panel-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg);
  overflow-y: auto;
  padding: var(--space-7) var(--space-8);
}

.panel-header {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  margin-bottom: var(--space-7);
}

.header-icon {
  width: var(--space-12);
  height: var(--space-12);
  border-radius: var(--radius-lg);
  background: var(--lumi-brand-gradient-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--lumi-primary);
  flex-shrink: 0;
}

.page-title {
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
  color: var(--text);
  letter-spacing: -0.3px;
}

.page-subtitle {
  font-size: var(--text-base);
  color: var(--text-muted);
  margin-top: var(--space-1);
}

.panel-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  max-width: 720px;
}

.info-card,
.action-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
}

.card-title {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--text);
  margin-bottom: var(--space-4);
}

.card-desc {
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin-bottom: var(--space-4);
}

.info-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--divider-soft);
}

.info-row:last-child {
  border-bottom: none;
}

.info-row dt {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.info-row dd {
  font-size: var(--text-sm);
  color: var(--text);
}

code {
  padding: 2px 6px;
  border-radius: var(--radius-xs);
  background: var(--surface-hover);
  font-family: var(--font-mono, monospace);
  font-size: var(--text-xs);
}

.actions {
  display: flex;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.action-btn:hover {
  background: var(--surface-hover);
  border-color: var(--lumi-primary);
}

.action-btn.primary {
  background: var(--lumi-primary);
  border-color: var(--lumi-primary);
  color: var(--text-inverse);
}

.action-btn.primary:hover {
  background: var(--lumi-primary-hover);
}

.message-box {
  margin-top: var(--space-4);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  background: var(--lumi-primary-light, rgba(99, 102, 241, 0.1));
  color: var(--lumi-primary);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
}

.fade-slide-enter-active {
  transition: opacity 0.25s var(--ease-in-out), transform 0.25s var(--ease-in-out);
}

.fade-slide-leave-active {
  transition: opacity 0.2s var(--ease-in-out);
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.fade-slide-leave-to {
  opacity: 0;
}
</style>

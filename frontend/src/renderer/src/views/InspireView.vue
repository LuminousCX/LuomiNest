<script setup lang="ts">
import { ref } from 'vue'
import {
  Lightbulb,
  Sparkles,
  Wand2,
  BookOpen,
  Brain,
  ArrowRight
} from 'lucide-vue-next'

const ideas = ref([
  { title: '今日灵感', desc: '基于你的对话历史生成的创意方向', icon: Sparkles, color: '#147EBC' },
  { title: '写作助手', desc: 'AI辅助文案创作与润色', icon: Wand2, color: '#6366f1' },
  { title: '知识图谱', desc: '探索你的记忆与认知网络', icon: Brain, color: '#f59e0b' },
  { title: '阅读推荐', desc: '根据兴趣为你精选内容', icon: BookOpen, color: '#f43f5e' }
])
</script>

<template>
  <div class="inspire-view">
    <div class="inspire-header animate-fade-in">
      <div class="header-icon-wrap">
        <Lightbulb :size="24" />
      </div>
      <div>
        <h1 class="page-title">灵感工坊</h1>
        <p class="page-subtitle">让 AI 激发你的创造力</p>
      </div>
    </div>

    <div class="inspire-grid">
      <div
        v-for="(idea, idx) in ideas"
        :key="idea.title"
        class="idea-card animate-slide-up"
        :style="{ animationDelay: `${idx * 80}ms`, '--card-accent': idea.color }"
      >
        <div class="idea-icon" :style="{ background: idea.color + '14', color: idea.color }">
          <component :is="idea.icon" :size="24" />
        </div>
        <div class="idea-content">
          <h3>{{ idea.title }}</h3>
          <p>{{ idea.desc }}</p>
        </div>
        <button class="idea-action">
          <ArrowRight :size="16" />
        </button>
      </div>
    </div>

    <div class="inspire-empty-state animate-scale-in">
      <div class="empty-icon">
        <Lightbulb :size="48" />
      </div>
      <p>选择一个灵感方向开始探索</p>
    </div>
  </div>
</template>

<style scoped>
.inspire-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--workspace-bg);
  overflow-y: auto;
  padding: 28px 32px;
}

.inspire-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 32px;
}

.header-icon-wrap {
  width: 52px;
  height: 52px;
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, #fef3c7, #fde68a);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #d97706;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
}

.page-subtitle {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 2px;
}

.inspire-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-bottom: 32px;
}

.idea-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  border-radius: var(--radius-lg);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  cursor: pointer;
  transition: all var(--transition-normal);
}

.idea-card:hover {
  border-color: var(--card-accent);
  box-shadow: 0 4px 20px color-mix(in srgb, var(--card-accent) 10%, transparent);
  transform: translateY(-2px);
}

.idea-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.idea-content {
  flex: 1;
}

.idea-content h3 {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.idea-content p {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
}

.idea-action {
  width: 34px;
  height: 34px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.idea-card:hover .idea-action {
  color: var(--card-accent);
  background: color-mix(in srgb, var(--card-accent) 8%, transparent);
}

.inspire-empty-state {
  text-align: center;
  padding: 60px 0;
}

.empty-icon {
  width: 88px;
  height: 88px;
  border-radius: 50%;
  background: var(--workspace-panel);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  margin: 0 auto 16px;
}

.inspire-empty-state p {
  font-size: 14px;
  color: var(--text-muted);
}
</style>

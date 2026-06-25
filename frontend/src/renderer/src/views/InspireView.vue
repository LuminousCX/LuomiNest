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
import LumiCard from '../components/common/LumiCard.vue'
import LumiButton from '../components/common/LumiButton.vue'
import LumiEmptyState from '../components/common/LumiEmptyState.vue'

const ideas = ref([
  { title: '今日灵感', desc: '基于你的对话历史生成的创意方向', icon: Sparkles, color: 'var(--lumi-brand)' },
  { title: '写作助手', desc: 'AI辅助文案创作与润色', icon: Wand2, color: 'var(--lumi-indigo)' },
  { title: '知识图谱', desc: '探索你的记忆与认知网络', icon: Brain, color: 'var(--lumi-amber)' },
  { title: '阅读推荐', desc: '根据兴趣为你精选内容', icon: BookOpen, color: 'var(--lumi-accent)' }
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
      <LumiCard
        v-for="(idea, idx) in ideas"
        :key="idea.title"
        class="idea-card animate-slide-up"
        hoverable
        padding="none"
        :style="{ animationDelay: `${idx * 80}ms`, '--card-accent': idea.color }"
      >
        <div class="idea-icon">
          <component :is="idea.icon" :size="24" />
        </div>
        <div class="idea-content">
          <h3>{{ idea.title }}</h3>
          <p>{{ idea.desc }}</p>
        </div>
        <LumiButton variant="ghost" icon-only class="idea-action">
          <template #icon>
            <ArrowRight :size="16" />
          </template>
        </LumiButton>
      </LumiCard>
    </div>

    <LumiEmptyState
      class="inspire-empty-state animate-scale-in"
      icon="inbox"
      title="选择一个灵感方向开始探索"
      size="lg"
    />
  </div>
</template>

<style scoped>
.inspire-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--workspace-bg);
  overflow-y: auto;
  padding: var(--space-7);
}

.inspire-header {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  margin-bottom: var(--space-7);
}

.header-icon-wrap {
  width: calc(var(--space-8) + var(--space-3));
  height: calc(var(--space-8) + var(--space-3));
  border-radius: var(--radius-lg);
  background: var(--lumi-amber-soft);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--lumi-amber-dark);
}

.page-title {
  font-size: var(--text-3xl);
  font-weight: 700;
  color: var(--text-primary);
}

.page-subtitle {
  font-size: var(--text-base);
  color: var(--text-muted);
  margin-top: var(--space-1);
}

.inspire-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-4);
  margin-bottom: var(--space-7);
}

.idea-card {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-5);
  cursor: pointer;
  transition: all var(--transition-normal);
}

.idea-card:hover {
  border-color: var(--card-accent);
}

.idea-icon {
  width: var(--space-9);
  height: var(--space-9);
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--card-accent) 10%, transparent);
  color: var(--card-accent);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.idea-content {
  flex: 1;
}

.idea-content h3 {
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--space-1);
}

.idea-content p {
  font-size: var(--text-sm);
  color: var(--text-muted);
  line-height: var(--leading-normal);
}

.idea-card:hover .idea-action {
  color: var(--card-accent);
  background: color-mix(in srgb, var(--card-accent) 8%, transparent);
}

</style>

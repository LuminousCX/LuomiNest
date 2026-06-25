<script setup lang="ts">
import LumiButton from '../common/LumiButton.vue'
import LumiCard from '../common/LumiCard.vue'
import {
  Palette,
  Wand2,
  UserCircle,
  Mic,
  Music,
} from 'lucide-vue-next'
import type { PersonaConfig } from './types'

interface Props {
  personas: PersonaConfig[]
}

defineProps<Props>()
</script>

<template>
  <LumiCard class="panel-card persona-panel" padding="none">
    <template #title>
      <div class="panel-title-group">
        <Palette :size="18" class="panel-icon shrink-0" style="color: var(--task-pink)" />
        <h3>皮套工坊</h3>
        <span class="panel-badge pink">Avatar Studio</span>
      </div>
    </template>
    <template #header>
      <LumiButton variant="primary" size="sm">
        <template #icon>
          <Wand2 :size="14" />
        </template>
        自定义
      </LumiButton>
    </template>
    <div class="persona-grid">
      <div
        v-for="p in personas"
        :key="p.id"
        :class="['persona-card lumi-card', { active: p.active }]"
      >
        <div class="persona-avatar-preview">
          <UserCircle :size="36" />
          <div v-if="p.active" class="active-ring" />
        </div>
        <div class="persona-detail">
          <span class="persona-name">{{ p.name }}</span>
          <div class="persona-tags">
            <span class="p-tag"><Mic :size="10" /> {{ p.voice }}</span>
            <span class="p-tag"><Music :size="10" /> {{ p.tone }}</span>
          </div>
        </div>
      </div>
    </div>
  </LumiCard>
</template>

<style scoped>
.panel-card {
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.panel-card :deep(.lumi-card__body) {
  display: contents;
}

.panel-title-group {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.panel-title-group h3 {
  font-size: var(--text-lg);
  font-weight: var(--font-semibold);
  color: var(--text);
}

.panel-badge {
  font-size: var(--text-2xs);
  padding: calc(var(--space-1) / 2) var(--space-3);
  border-radius: var(--radius-full);
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  font-weight: var(--font-medium);
  letter-spacing: 0.3px;
}

.panel-badge.pink { background: var(--task-pink-soft); color: var(--task-pink); }

.persona-panel {
  flex: 1;
}

.persona-grid {
  padding: var(--space-3) var(--space-4);
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-2);
}

.persona-card {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  cursor: pointer;
  transition: all var(--transition-normal);
}

.persona-card:hover {
  border-color: var(--task-pink);
  background: var(--lumi-accent-light);
}

.persona-card.active {
  border-color: var(--task-pink);
  background: var(--lumi-accent-glow);
}

.persona-avatar-preview {
  position: relative;
  flex-shrink: 0;
  color: var(--text-muted);
}

.active-ring {
  position: absolute;
  inset: calc(var(--space-1) / -2);
  border-radius: var(--radius-full);
  border: 2px solid var(--task-pink);
  animation: ringPulse var(--duration-slow) var(--ease-in-out) infinite;
}

@keyframes ringPulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.1); }
}

.persona-detail {
  flex: 1;
  min-width: 0;
}

.persona-name {
  display: block;
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--text);
  margin-bottom: var(--space-1);
}

.persona-tags {
  display: flex;
  gap: var(--space-1);
  flex-wrap: wrap;
}

.p-tag {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-2xs);
  padding: var(--badge-padding);
  border-radius: var(--radius-xs);
  background: var(--bg-secondary);
  color: var(--text-muted);
}
</style>

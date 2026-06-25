<script setup lang="ts">
import LumiButton from '../common/LumiButton.vue'
import LumiCard from '../common/LumiCard.vue'
import {
  Palette,
  Wand2,
  UserCircle,
  Sparkles,
  Volume2,
  Music,
  Plus,
} from 'lucide-vue-next'
import type { PersonaConfig } from './types'

interface Props {
  personas: PersonaConfig[]
}

defineProps<Props>()
</script>

<template>
  <section class="dash-section full-panel">
    <LumiCard class="full-height" padding="none">
      <template #title>
        <div class="panel-title-group">
          <Palette :size="20" class="panel-icon shrink-0" style="color: var(--task-pink)" />
          <h3>皮套工坊</h3>
          <span class="panel-badge pink">Avatar Workshop</span>
        </div>
      </template>
      <template #header>
        <LumiButton variant="primary" size="sm">
          <template #icon>
            <Wand2 :size="14" />
          </template>
          创建新皮套
        </LumiButton>
      </template>
      <div class="persona-workshop-grid">
        <div
          v-for="p in personas"
          :key="p.id"
          :class="['pw-card lumi-card', { active: p.active }]"
        >
          <div class="pw-visual">
            <div class="pw-avatar-large">
              <UserCircle :size="64" />
            </div>
            <div v-if="p.active" class="pw-active-badge">
              <Sparkles :size="12" /> 使用中
            </div>
          </div>
          <div class="pw-info">
            <h4>{{ p.name }}</h4>
            <p>{{ p.style }} 风格</p>
          </div>
          <div class="pw-config-list">
            <div class="pw-config-item">
              <UserCircle :size="14" />
              <span>形象：{{ p.avatar }}</span>
            </div>
            <div class="pw-config-item">
              <Volume2 :size="14" />
              <span>语音：{{ p.voice }}</span>
            </div>
            <div class="pw-config-item">
              <Music :size="14" />
              <span>音色：{{ p.tone }}</span>
            </div>
          </div>
          <LumiButton
            variant="outline"
            size="sm"
            block
            class="pw-action-btn"
            :class="{ active: p.active }"
          >
            {{ p.active ? '正在使用' : '切换使用' }}
          </LumiButton>
        </div>
        <div class="pw-card add-new">
          <div class="add-new-content">
            <Plus :size="32" />
            <span>创建新皮套</span>
          </div>
        </div>
      </div>
    </LumiCard>
  </section>
</template>

<style scoped>
.full-panel {
  flex: 1;
}

.full-height {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.full-height :deep(.lumi-card__body) {
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
</style>

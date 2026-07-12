<script setup lang="ts">
/**
 * 智能体创建向导 - 步骤2：技能配置
 *
 * 展示可用技能列表，支持开关启停
 */
import { Plus } from 'lucide-vue-next'
import { SKILL_ITEMS, type AgentFormData } from '../../composables/useAgentCreateForm'

defineProps<{
  formData: AgentFormData
}>()

const emit = defineEmits<{
  'toggle-skill': [skillId: string]
}>()
</script>

<template>
  <div class="step-content step-layout-full">
    <div class="skills-intro">
      <p>基于智能体定位推荐的能力模块，创建时全量启用。可用开关控制是否启能。</p>
    </div>
    <div class="skills-list">
      <div
        v-for="skill in SKILL_ITEMS"
        :key="skill.id"
        class="skill-item"
      >
        <div class="skill-icon-wrap">
          <component :is="skill.icon" :size="18" />
        </div>
        <div class="skill-info">
          <h4 class="skill-name">{{ skill.name }}</h4>
          <p class="skill-desc">{{ skill.desc }}</p>
        </div>
        <button
          :class="['lumi-toggle', { 'is-active': formData.skills[skill.id] }]"
          @click="emit('toggle-skill', skill.id)"
          :aria-label="formData.skills[skill.id] ? '关闭' : '开启'"
        ></button>
      </div>
    </div>
    <button class="add-skill-pack-btn">
      <Plus :size="16" />
      <span>从推荐技能包添加</span>
    </button>
  </div>
</template>

<style scoped>
.step-content {
  min-height: 100%;
}

.step-layout-full {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.skills-intro {
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  background: var(--lumi-brand-light);
  color: var(--text-secondary);
  font-size: var(--text-base);
  line-height: var(--leading-relaxed);
  border: 1px solid color-mix(in srgb, var(--lumi-brand) 10%, transparent);
}

.skills-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.skill-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  background: var(--surface);
  border: 1px solid var(--border-light);
  transition: all var(--transition-fast);
}

.skill-item:hover {
  border-color: var(--border);
  box-shadow: var(--shadow-xs);
}

.skill-icon-wrap {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.skill-info {
  flex: 1;
  min-width: 0;
}

.skill-name {
  font-size: var(--text-md);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin-bottom: 2px;
}

.skill-desc {
  font-size: var(--text-sm);
  color: var(--text-muted);
  line-height: 1.5;
}

.add-skill-pack-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-3);
  border-radius: var(--radius-md);
  border: 1px dashed var(--lumi-brand);
  color: var(--lumi-brand);
  font-size: var(--text-base);
  font-weight: var(--font-medium);
  background: transparent;
  cursor: pointer;
  transition: all var(--transition-fast);
  margin-top: var(--space-2);
}

.add-skill-pack-btn:hover {
  background: var(--lumi-brand-light);
}
</style>

<script setup lang="ts">
/**
 * 智能体创建向导 - 步骤4：确认创建
 *
 * 错误通知 + 主确认卡片（头像/名称/详情）+ 侧栏（已启用技能列表）
 */
import { computed } from 'vue'
import LumiCard from '../common/LumiCard.vue'
import {
  SKILL_ITEMS, STYLE_TAGS,
  type AvatarOption, type AgentFormData
} from '../../composables/useAgentCreateForm'

const props = defineProps<{
  formData: AgentFormData
  errorMessage: string
  selectedAvatar: AvatarOption
}>()

const emit = defineEmits<{
  'dismiss-error': []
}>()

const enabledSkills = computed(() =>
  SKILL_ITEMS.filter(s => props.formData.skills[s.id])
)
</script>

<template>
  <div class="step-content step-layout-full">
    <Transition name="toast-slide">
      <div v-if="errorMessage" class="error-notification">
        <div class="notification-icon error">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <line x1="15" y1="9" x2="9" y2="15"/>
            <line x1="9" y1="9" x2="15" y2="15"/>
          </svg>
        </div>
        <span class="notification-message">{{ errorMessage }}</span>
        <button class="notification-close" @click="emit('dismiss-error')">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>
    </Transition>
    <div class="confirm-grid">
      <LumiCard class="confirm-card main-confirm" padding="md">
        <div class="confirm-header-row">
          <div
            class="confirm-avatar-lg"
            :style="{ '--avatar-color': selectedAvatar.color }"
          >
            <img v-if="selectedAvatar.imageUrl" :src="selectedAvatar.imageUrl" class="confirm-avatar-img" />
            <span v-else class="confirm-avatar-emoji">{{ selectedAvatar.emoji }}</span>
          </div>
          <div>
            <h2 class="confirm-name">{{ formData.name }}</h2>
            <p class="confirm-style">{{ STYLE_TAGS.find(t => t.id === formData.selectedStyle)?.label }} 风格</p>
          </div>
        </div>
        <div class="confirm-divider"></div>
        <div class="confirm-details">
          <div class="detail-row">
            <span class="detail-label">描述</span>
            <span class="detail-value">{{ formData.description || '未设置' }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">已选技能</span>
            <span class="detail-value">{{ enabledSkills.length }} 项</span>
          </div>
        </div>
      </LumiCard>

      <LumiCard class="confirm-card side-confirm" padding="md">
        <h4 class="side-title">已启用技能</h4>
        <div class="enabled-skills-list">
          <div
            v-for="skill in enabledSkills"
            :key="skill.id"
            class="enabled-skill-tag"
          >
            <component :is="skill.icon" :size="14" />
            <span>{{ skill.name }}</span>
          </div>
          <p v-if="enabledSkills.length === 0" class="no-skills">暂无启用技能</p>
        </div>
      </LumiCard>
    </div>
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

.confirm-grid {
  display: grid;
  grid-template-columns: 1.2fr 0.8fr;
  gap: var(--space-5);
}

.confirm-card {
  display: flex;
  flex-direction: column;
}

.confirm-card :deep(.lumi-card__body) {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.main-confirm {
  gap: var(--space-3);
}

.confirm-header-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.confirm-avatar-lg {
  width: 56px;
  height: 56px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: linear-gradient(135deg, var(--avatar-color, var(--lumi-brand)), color-mix(in srgb, var(--avatar-color, var(--lumi-brand)) 60%, transparent));
  box-shadow: var(--shadow-md);
  overflow: hidden;
}

.confirm-avatar-img {
  width: 100%;
  height: 100%;
  border-radius: inherit;
  object-fit: cover;
}

.confirm-avatar-emoji {
  font-size: var(--text-4xl);
}

.confirm-name {
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
}

.confirm-style {
  font-size: var(--text-base);
  color: var(--text-muted);
}

.confirm-divider {
  height: 1px;
  background: var(--divider-soft);
}

.confirm-details {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.detail-label {
  font-size: var(--text-base);
  color: var(--text-muted);
  font-weight: var(--font-medium);
}

.detail-value {
  font-size: var(--text-base);
  color: var(--text-primary);
  font-weight: var(--font-semibold);
}

.side-title {
  font-size: var(--text-md);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  margin-bottom: var(--space-2);
}

.enabled-skills-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.enabled-skill-tag {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--surface);
  font-size: var(--text-sm);
  color: var(--text-secondary);
  font-weight: var(--font-medium);
}

.enabled-skill-tag svg {
  color: var(--lumi-brand);
  flex-shrink: 0;
}

.no-skills {
  font-size: var(--text-base);
  color: var(--text-muted);
  text-align: center;
  padding: var(--space-4);
}

.error-notification {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: var(--task-red-soft);
  border: 1px solid var(--task-red-border);
  border-radius: var(--radius-lg);
  color: var(--lumi-danger);
  font-size: var(--text-md);
  font-weight: var(--font-medium);
  margin-bottom: var(--space-5);
  box-shadow: var(--shadow-sm);
}

.notification-icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.notification-icon.error {
  color: var(--lumi-danger);
}

.notification-message {
  flex: 1;
  line-height: 1.4;
}

.notification-close {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--space-6);
  height: var(--space-6);
  border: none;
  background: var(--lumi-danger-light);
  border-radius: var(--radius-xs);
  color: var(--lumi-danger);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.notification-close:hover {
  background: color-mix(in srgb, var(--lumi-danger) 18%, transparent);
  transform: rotate(90deg);
}

.toast-slide-enter-active {
  transition: all var(--duration-normal) var(--ease-out-expo);
}

.toast-slide-leave-active {
  transition: all var(--duration-leave) var(--ease-in-out);
}

.toast-slide-enter-from {
  opacity: 0;
  transform: translateY(-10px);
}

.toast-slide-leave-to {
  opacity: 0;
  transform: translateY(-10px) scale(0.95);
}

@media (max-width: 768px) {
  .confirm-grid {
    grid-template-columns: 1fr;
  }
}
</style>

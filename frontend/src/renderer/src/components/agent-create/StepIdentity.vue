<script setup lang="ts">
/**
 * 智能体创建向导 - 步骤1：身份与模型
 *
 * 表单区（名称/头像/描述/风格/模型）+ 实时预览区
 */
import { Upload, CircleDot } from 'lucide-vue-next'
import LumiInput from '../common/LumiInput.vue'
import LumiCard from '../common/LumiCard.vue'
import {
  AVATAR_CATEGORIES, STYLE_TAGS, TOTAL_STEPS,
  type AvatarOption, type AgentFormData
} from '../../composables/useAgentCreateForm'

defineProps<{
  formData: AgentFormData
  activeAvatarCategory: string
  currentAvatars: AvatarOption[]
  selectedAvatar: AvatarOption
  currentStep: number
}>()

const emit = defineEmits<{
  'select-avatar': [avatarId: string]
  'select-style': [styleId: string]
  'select-category': [categoryId: string]
}>()
</script>

<template>
  <div class="step-content step-layout-split">
    <div class="form-area">
      <div class="form-group">
        <label class="form-label">名称<span class="required">*</span></label>
        <LumiInput
          v-model="formData.name"
          type="text"
          placeholder="给你的智能体起个名字..."
        />
      </div>

      <div class="form-group">
        <label class="form-label">智能体头像</label>
        <div class="avatar-section">
          <div class="avatar-categories">
            <button
              v-for="cat in AVATAR_CATEGORIES"
              :key="cat.id"
              :class="['cat-tab', { active: activeAvatarCategory === cat.id }]"
              @click="emit('select-category', cat.id)"
            >
              {{ cat.label }}
            </button>
          </div>
          <div class="avatar-grid">
            <button
              v-for="avatar in currentAvatars"
              :key="avatar.id"
              :class="['avatar-item', { selected: formData.selectedAvatarId === avatar.id }]"
              :style="{ '--avatar-color': avatar.color }"
              :title="avatar.imageUrl ? avatar.imageUrl.split('/').pop()?.replace('.png','') : ''"
              @click="emit('select-avatar', avatar.id)"
            >
              <img v-if="avatar.imageUrl" :src="avatar.imageUrl" class="avatar-img" :alt="avatar.id" />
              <span v-else class="avatar-emoji">{{ avatar.emoji }}</span>
            </button>
            <button class="avatar-item upload-avatar" title="上传自定义头像">
              <Upload :size="18" />
            </button>
          </div>
        </div>
      </div>

      <div class="form-group">
        <label class="form-label">描述</label>
        <textarea
          v-model="formData.description"
          class="lumi-textarea"
          rows="3"
          placeholder="简要描述这个智能体的定位和能力..."
        ></textarea>
      </div>

      <div class="form-group">
        <label class="form-label">风格</label>
        <div class="tag-list">
          <button
            v-for="tag in STYLE_TAGS"
            :key="tag.id"
            :class="['style-tag', { active: formData.selectedStyle === tag.id }]"
            @click="emit('select-style', tag.id)"
          >
            {{ tag.label }}
          </button>
        </div>
      </div>
    </div>

    <div class="preview-area">
      <div class="preview-header">
        <CircleDot :size="14" />
        <span>智能体预览</span>
      </div>
      <p class="preview-hint">实时预览智能体效果</p>

      <LumiCard class="preview-card" padding="md">
        <div
          class="preview-avatar-ring"
          :style="{ '--avatar-color': selectedAvatar.color }"
        >
          <img v-if="selectedAvatar.imageUrl" :src="selectedAvatar.imageUrl" class="preview-avatar-img" />
          <span v-else class="preview-avatar-emoji">{{ selectedAvatar.emoji }}</span>
        </div>
        <h3 class="preview-name">{{ formData.name || '未命名智能体' }}</h3>
        <p class="preview-badge">{{ STYLE_TAGS.find(t => t.id === formData.selectedStyle)?.label || '风格' }} · 已验证</p>
        <p class="preview-desc">{{ formData.description || '暂无描述信息。添加描述可帮助理解智能体的定位与用途。' }}</p>
      </LumiCard>

      <div class="step-indicator">
        简览步骤 • 第 {{ currentStep + 1 }} / {{ TOTAL_STEPS }} 步
      </div>
    </div>
  </div>
</template>

<style scoped>
.step-content {
  min-height: 100%;
}

.step-layout-split {
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: var(--space-8);
  align-items: start;
}

.form-group {
  margin-bottom: var(--space-5);
}

.form-label {
  display: block;
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}

.required {
  color: var(--lumi-accent);
  margin-left: 2px;
}

.avatar-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.avatar-categories {
  display: flex;
  gap: var(--space-1);
  flex-wrap: wrap;
}

.cat-tab {
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-full);
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--text-secondary);
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  transition: all var(--transition-fast);
}

.cat-tab.active {
  background: var(--surface);
  color: var(--text-primary);
  border-color: var(--text-primary);
  box-shadow: var(--shadow-xs);
}

.cat-tab:hover:not(.active) {
  border-color: var(--text-muted);
}

.avatar-grid {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.avatar-item {
  width: 52px;
  height: 52px;
  border-radius: var(--radius-full);
  border: 2px solid transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-3xl);
  cursor: pointer;
  transition: all var(--transition-normal);
  background: var(--bg-secondary);
  overflow: hidden;
}

.avatar-img {
  width: 100%;
  height: 100%;
  border-radius: inherit;
  object-fit: cover;
}

.avatar-item:hover {
  transform: scale(1.08);
}

.avatar-item.selected {
  border-color: var(--avatar-color, var(--lumi-brand));
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--avatar-color, var(--lumi-brand)) 20%, transparent);
}

.upload-avatar {
  color: var(--text-muted);
  border-style: dashed;
  border-color: var(--border);
}

.upload-avatar:hover {
  border-color: var(--lumi-brand);
  color: var(--lumi-brand);
  background: var(--lumi-brand-light);
}

.tag-list {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.style-tag {
  padding: 7px var(--space-4);
  border-radius: var(--radius-full);
  font-size: var(--text-base);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  transition: all var(--transition-fast);
}

.style-tag:hover:not(.active) {
  border-color: var(--text-muted);
}

.style-tag.active {
  background: var(--text-primary);
  color: var(--text-inverse);
  border-color: transparent;
}

.preview-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
}

.preview-header {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--text-secondary);
  width: 100%;
}

.preview-header svg {
  color: var(--lumi-brand);
}

.preview-hint {
  font-size: var(--text-sm);
  color: var(--text-muted);
  width: 100%;
}

.preview-card {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  text-align: center;
}

.preview-card :deep(.lumi-card__body) {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  text-align: center;
}

.preview-avatar-ring {
  width: var(--space-10);
  height: var(--space-10);
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--avatar-color, var(--lumi-brand)), color-mix(in srgb, var(--avatar-color, var(--lumi-brand)) 60%, transparent));
  box-shadow: var(--shadow-md);
  overflow: hidden;
}

.preview-avatar-img {
  width: 100%;
  height: 100%;
  border-radius: inherit;
  object-fit: cover;
}

.preview-avatar-emoji {
  font-size: var(--text-4xl);
}

.preview-name {
  font-size: var(--text-xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
}

.preview-badge {
  font-size: var(--text-xs);
  color: var(--text-muted);
  padding: 3px var(--space-2);
  border-radius: var(--radius-full);
  background: var(--surface);
  border: 1px solid var(--border-light);
}

.preview-desc {
  font-size: var(--text-sm);
  color: var(--text-muted);
  line-height: var(--leading-relaxed);
  text-align: left;
  width: 100%;
}

.step-indicator {
  font-size: var(--text-sm);
  color: var(--text-muted);
  width: 100%;
  text-align: right;
  padding-top: var(--space-1);
}

@media (max-width: 768px) {
  .step-layout-split {
    grid-template-columns: 1fr;
  }

  .preview-area {
    order: -1;
  }
}
</style>

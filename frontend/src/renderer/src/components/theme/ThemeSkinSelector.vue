<script setup lang="ts">
import { computed } from 'vue'
import { Check, Plus, Pencil } from 'lucide-vue-next'
import { useThemeStore } from '../../stores/theme'
import type { Skin } from '../../stores/theme-types'
import { getThemePreviewColors } from '../../stores/theme-presets'
import { MAX_CUSTOM_SKINS } from '../../stores/theme-types'

const props = defineProps<{
  modelValue: string
}>()

const emit = defineEmits<{
  apply: [id: string]
  edit: [id: string]
  create: []
}>()

const themeStore = useThemeStore()

const activeId = computed(() => props.modelValue)
const presetSkins = computed(() => themeStore.allSkins.filter((s) => s.type === 'preset'))
const customSkins = computed(() => themeStore.allSkins.filter((s) => s.type === 'custom'))
const canAddCustom = computed(() => customSkins.value.length < MAX_CUSTOM_SKINS)

function isGradient(image: string | null): boolean {
  return !!image && /^(?:linear|radial|conic)-gradient\(/.test(image)
}

function getSkinPreviewStyle(skin: Skin): Record<string, string> {
  const image = skin.background.image
  if (!image) {
    return { background: 'var(--surface-hover)' }
  }
  if (isGradient(image)) {
    return { background: image }
  }
  return {
    backgroundImage: `url('${image}')`,
    backgroundSize: skin.background.fit === 'contain' ? 'contain' : 'cover',
    backgroundPosition: skin.background.fit === 'right' ? 'right center' : 'center',
    backgroundRepeat: 'no-repeat'
  }
}

function getSkinPreviewColors(skin: Skin): string[] {
  // 传入自定义主题列表，使自定义主题皮肤预览使用真实配色而非蓝色兜底
  return getThemePreviewColors(skin.colorThemeId, themeStore.customThemes)
}

// 合并 preset/custom 重复的 apply/edit 处理为统一函数
function handleApply(skin: Skin) {
  emit('apply', skin.id)
}

function handleEdit(skin: Skin) {
  emit('edit', skin.id)
}

// 卡片键盘激活：Enter/Space 触发应用（与点击等价，可访问性）
function onCardKeydown(e: KeyboardEvent, skin: Skin) {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    emit('apply', skin.id)
  }
}

function handleCreate() {
  emit('create')
}
</script>

<template>
  <div class="skin-selector">
    <!-- 预设皮肤：海报网格，点击应用，悬浮显示编辑 -->
    <div class="skin-selector__section">
      <div class="skin-selector__label">预设皮肤</div>
      <div class="preset-grid">
        <div
          v-for="skin in presetSkins"
          :key="skin.id"
          :class="[
            'preset-card',
            { 'preset-card--active': activeId === skin.id }
          ]"
          role="button"
          tabindex="0"
          :aria-label="`应用${skin.name}皮肤`"
          @click="handleApply(skin)"
          @keydown="onCardKeydown($event, skin)"
        >
          <div class="preset-card__preview" :style="getSkinPreviewStyle(skin)">
            <div v-if="activeId === skin.id" class="preset-card__check">
              <Check :size="14" />
            </div>
            <div class="preset-card__actions">
              <span
                v-if="activeId === skin.id"
                class="preset-card__edit"
                role="button"
                tabindex="0"
                :aria-label="`以${skin.name}为基础编辑`"
                @click.stop="handleEdit(skin)"
                @keydown.enter.stop="handleEdit(skin)"
                @keydown.space.stop.prevent="handleEdit(skin)"
              >
                <Pencil :size="12" />
                <span>编辑</span>
              </span>
            </div>
            <div class="preset-card__overlay" />
          </div>
          <div class="preset-card__footer">
            <span class="preset-card__name">{{ skin.name }}</span>
            <div class="preset-card__colors">
              <span
                v-for="(color, idx) in getSkinPreviewColors(skin)"
                :key="idx"
                class="preset-card__dot"
                :style="{ background: color }"
              />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 自定义皮肤：长条状列表，点击编辑 -->
    <div v-if="customSkins.length > 0 || canAddCustom" class="skin-selector__section">
      <div class="skin-selector__label">
        <span>自定义皮肤</span>
        <span class="skin-selector__count">{{ customSkins.length }}/{{ MAX_CUSTOM_SKINS }}</span>
      </div>
      <div class="custom-list">
        <div
          v-for="skin in customSkins"
          :key="skin.id"
          :class="[
            'custom-card',
            { 'custom-card--active': activeId === skin.id }
          ]"
          role="button"
          tabindex="0"
          :aria-label="`应用${skin.name}皮肤`"
          @click="handleApply(skin)"
          @keydown="onCardKeydown($event, skin)"
        >
          <div class="custom-card__thumb" :style="getSkinPreviewStyle(skin)" />
          <div class="custom-card__info">
            <span class="custom-card__name">{{ skin.name }}</span>
            <div class="custom-card__colors">
              <span
                v-for="(color, idx) in getSkinPreviewColors(skin)"
                :key="idx"
                class="custom-card__dot"
                :style="{ background: color }"
              />
            </div>
          </div>
          <div class="custom-card__actions">
            <div v-if="activeId === skin.id" class="custom-card__check">
              <Check :size="14" />
            </div>
            <span
              class="custom-card__edit-btn"
              role="button"
              tabindex="0"
              :aria-label="`编辑${skin.name}皮肤`"
              @click.stop="handleEdit(skin)"
              @keydown.enter.stop="handleEdit(skin)"
              @keydown.space.stop.prevent="handleEdit(skin)"
            >
              <Pencil :size="14" />
            </span>
          </div>
        </div>

        <button
          v-if="canAddCustom"
          class="custom-card custom-card--add"
          aria-label="新建自定义皮肤"
          @click="handleCreate"
        >
          <div class="custom-card__thumb custom-card__thumb--add">
            <Plus :size="20" />
          </div>
          <div class="custom-card__info">
            <span class="custom-card__name">新建自定义皮肤</span>
            <span class="custom-card__hint">创建一套新的视觉方案</span>
          </div>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.skin-selector {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  width: 100%;
}

.skin-selector__section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.skin-selector__label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--text-secondary);
}

.skin-selector__count {
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: var(--text-muted);
}

/* ── 预设皮肤网格 ── */
.preset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: var(--space-3);
}

.preset-card {
  display: flex;
  flex-direction: column;
  padding: 0;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  background: var(--surface);
  cursor: pointer;
  overflow: hidden;
  transition:
    transform var(--transition-fast),
    box-shadow var(--transition-fast),
    border-color var(--transition-fast);
  text-align: left;
}

.preset-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
  border-color: var(--lumi-brand-border);
}

/* div 替代 button 后需显式提供键盘聚焦轮廓 */
.preset-card:focus-visible {
  outline: 2px solid var(--lumi-brand);
  outline-offset: 2px;
}

.preset-card--active {
  border-color: var(--lumi-brand);
  box-shadow: 0 0 0 2px var(--lumi-brand-light), var(--shadow-md);
}

.preset-card__preview {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 10;
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  overflow: hidden;
}

.preset-card__overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, transparent 40%, rgba(0, 0, 0, 0.22) 100%);
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.preset-card:hover .preset-card__overlay {
  opacity: 1;
}

.preset-card__check {
  position: absolute;
  top: var(--space-2);
  right: var(--space-2);
  width: 22px;
  height: 22px;
  border-radius: var(--radius-full);
  background: var(--lumi-brand);
  color: var(--text-inverse);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-sm);
  z-index: 2;
}

.preset-card__actions {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity var(--transition-fast);
  z-index: 3;
}

.preset-card:hover .preset-card__actions,
.preset-card:focus-within .preset-card__actions {
  opacity: 1;
}

.preset-card__edit {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-3);
  border: none;
  border-radius: var(--radius-md);
  background: var(--surface);
  color: var(--text-primary);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  cursor: pointer;
  box-shadow: var(--shadow-md);
  transition: background var(--transition-fast), color var(--transition-fast);
}

.preset-card__edit:hover {
  background: var(--lumi-brand);
  color: var(--text-inverse);
}

.preset-card__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  min-height: 42px;
}

.preset-card__name {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.preset-card__colors {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.preset-card__dot {
  width: 12px;
  height: 12px;
  border-radius: var(--radius-full);
  border: 1px solid rgba(0, 0, 0, 0.08);
  flex-shrink: 0;
}

/* ── 自定义皮肤长条列表 ── */
.custom-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.custom-card {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  background: var(--surface);
  cursor: pointer;
  text-align: left;
  transition:
    border-color var(--transition-fast),
    background-color var(--transition-fast),
    box-shadow var(--transition-fast);
}

.custom-card:hover {
  border-color: var(--lumi-brand-border);
  background: var(--surface-hover);
  box-shadow: var(--shadow-sm);
}

/* div 替代 button 后需显式提供键盘聚焦轮廓 */
.custom-card:focus-visible {
  outline: 2px solid var(--lumi-brand);
  outline-offset: 2px;
}

.custom-card--active {
  border-color: var(--lumi-brand);
  background: var(--lumi-brand-subtle);
  box-shadow: 0 0 0 1px var(--lumi-brand-light);
}

.custom-card__thumb {
  width: 80px;
  height: 48px;
  border-radius: var(--radius-md);
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  flex-shrink: 0;
}

.custom-card__thumb--add {
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface-hover);
  color: var(--text-muted);
}

.custom-card--add:hover .custom-card__thumb--add {
  color: var(--lumi-brand);
  background: var(--lumi-primary-light);
}

.custom-card__info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.custom-card__name {
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.custom-card__hint {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.custom-card__colors {
  display: flex;
  gap: 4px;
}

.custom-card__dot {
  width: 10px;
  height: 10px;
  border-radius: var(--radius-full);
  border: 1px solid rgba(0, 0, 0, 0.08);
}

.custom-card__actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
  margin-left: auto;
}

.custom-card__check {
  width: 22px;
  height: 22px;
  border-radius: var(--radius-full);
  background: var(--lumi-brand);
  color: var(--text-inverse);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-sm);
}

.custom-card__edit-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.custom-card__edit-btn:hover {
  background: var(--surface-hover);
  color: var(--lumi-brand);
}

.custom-card--active .custom-card__edit-btn:hover {
  background: var(--surface);
}
</style>

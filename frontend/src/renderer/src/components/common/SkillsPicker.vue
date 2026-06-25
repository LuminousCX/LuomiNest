<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import {
  Sparkles,
  X,
  Search,
  Blocks,
  Check,
  ChevronDown,
} from 'lucide-vue-next'
import { useMarketplaceStore } from '../../stores/marketplace'
import type { MarketplaceItem } from '../../types/marketplace'

const props = defineProps<{
  selectedIds: string[]
}>()

const emit = defineEmits<{
  'update:selectedIds': [ids: string[]]
}>()

const router = useRouter()
const marketplaceStore = useMarketplaceStore()

const showDropdown = ref(false)
const dropdownRef = ref<HTMLElement | null>(null)
const searchQuery = ref('')
const triggerBtnRef = ref<HTMLElement | null>(null)

const installedSkills = computed(() => marketplaceStore.installedSkills)

const filteredSkills = computed(() => {
  if (!searchQuery.value) return installedSkills.value
  const q = searchQuery.value.toLowerCase()
  return installedSkills.value.filter(
    (s) => s.name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q)
  )
})

const selectedSkills = computed(() => {
  return props.selectedIds
    .map((id) => installedSkills.value.find((s) => s.id === id))
    .filter((s): s is MarketplaceItem => Boolean(s))
})

const toggleDropdown = () => {
  showDropdown.value = !showDropdown.value
  if (showDropdown.value) {
    nextTick(() => {
      const input = dropdownRef.value?.querySelector('.luomi-skills-search-input') as HTMLInputElement | null
      input?.focus()
    })
  }
}

const closeDropdown = () => {
  showDropdown.value = false
  searchQuery.value = ''
}

const toggleSkill = (skillId: string) => {
  const next = props.selectedIds.includes(skillId)
    ? props.selectedIds.filter((id) => id !== skillId)
    : [...props.selectedIds, skillId]
  emit('update:selectedIds', next)
}

const removeSkill = (skillId: string) => {
  emit('update:selectedIds', props.selectedIds.filter((id) => id !== skillId))
}

const clearAll = () => {
  emit('update:selectedIds', [])
}

const goToMarket = () => {
  closeDropdown()
  router.push('/market?tab=skill')
}

const handleClickOutside = (e: MouseEvent) => {
  if (!showDropdown.value) return
  const target = e.target as Node
  if (dropdownRef.value?.contains(target)) return
  if (triggerBtnRef.value?.contains(target)) return
  closeDropdown()
}

const handleEscape = (e: KeyboardEvent) => {
  if (e.key === 'Escape' && showDropdown.value) {
    closeDropdown()
    triggerBtnRef.value?.focus()
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside, true)
  document.addEventListener('keydown', handleEscape)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside, true)
  document.removeEventListener('keydown', handleEscape)
})
</script>

<template>
  <div class="luomi-skills-picker">
    <!-- 选中技能 chips 区（显示在输入框上方，由父组件决定插入位置） -->
    <Transition name="luomi-skills-chips-fade">
      <div v-if="selectedSkills.length > 0" class="luomi-skills-chips">
        <TransitionGroup name="luomi-skill-chip">
          <span
            v-for="skill in selectedSkills"
            :key="skill.id"
            class="luomi-skill-chip"
            :title="skill.description"
          >
            <Sparkles :size="11" class="luomi-skill-chip-icon" />
            <span class="luomi-skill-chip-name">{{ skill.name }}</span>
            <button
              class="luomi-skill-chip-remove"
              :title="`移除 ${skill.name}`"
              @click.stop="removeSkill(skill.id)"
            >
              <X :size="11" />
            </button>
          </span>
        </TransitionGroup>
        <button class="luomi-skills-clear" @click.stop="clearAll">清空</button>
      </div>
    </Transition>

    <!-- 触发按钮 -->
    <button
      ref="triggerBtnRef"
      :class="['luomi-skills-trigger', { active: selectedIds.length > 0 }]"
      :title="selectedIds.length > 0 ? `已选 ${selectedIds.length} 个技能` : '选择已安装的技能'"
      @click.stop="toggleDropdown"
    >
      <Sparkles :size="15" />
      <span class="luomi-skills-trigger-text">技能</span>
      <span v-if="selectedIds.length > 0" class="luomi-skills-badge">{{ selectedIds.length }}</span>
      <ChevronDown :size="12" class="luomi-skills-trigger-chevron" :class="{ rotated: showDropdown }" />
    </button>

    <!-- 下拉面板 -->
    <Transition name="luomi-skills-dropdown-fade">
      <div v-if="showDropdown" ref="dropdownRef" class="luomi-skills-dropdown">
        <div class="luomi-skills-dropdown-header">
          <div class="luomi-skills-search">
            <Search :size="13" class="luomi-skills-search-icon" />
            <input
              v-model="searchQuery"
              type="text"
              class="luomi-skills-search-input"
              placeholder="搜索已安装的技能..."
            />
          </div>
        </div>

        <div class="luomi-skills-dropdown-list">
          <button
            v-for="skill in filteredSkills"
            :key="skill.id"
            :class="['luomi-skills-item', { selected: selectedIds.includes(skill.id) }]"
            @click.stop="toggleSkill(skill.id)"
          >
            <div class="luomi-skills-item-icon">
              <Sparkles :size="14" />
            </div>
            <div class="luomi-skills-item-info">
              <span class="luomi-skills-item-name">{{ skill.name }}</span>
              <span class="luomi-skills-item-desc">{{ skill.description }}</span>
            </div>
            <div v-if="selectedIds.includes(skill.id)" class="luomi-skills-item-check">
              <Check :size="13" />
            </div>
          </button>

          <div v-if="filteredSkills.length === 0" class="luomi-skills-empty">
            <Blocks :size="28" />
            <p class="luomi-skills-empty-title">
              {{ installedSkills.length === 0 ? '暂无已安装技能' : '未找到匹配的技能' }}
            </p>
            <p class="luomi-skills-empty-desc">
              {{ installedSkills.length === 0 ? '前往市场安装技能后即可在此选择' : '试试其他关键词' }}
            </p>
            <button v-if="installedSkills.length === 0" class="luomi-skills-empty-action" @click.stop="goToMarket">
              去市场看看
            </button>
          </div>
        </div>

        <div class="luomi-skills-dropdown-footer">
          <span class="luomi-skills-count">已选 {{ selectedIds.length }} / {{ installedSkills.length }} 个</span>
          <button class="luomi-skills-manage" @click.stop="goToMarket">
            管理技能
          </button>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.luomi-skills-picker {
  position: relative;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-1);
  padding: 0 var(--space-1);
}

/* ─── 选中 chips 区 ─── */
.luomi-skills-chips {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-1);
  flex: 1;
  min-width: 0;
}

.luomi-skill-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px 3px 6px;
  border-radius: var(--radius-full);
  background: var(--lumi-brand-light);
  border: 1px solid var(--lumi-brand-border);
  color: var(--lumi-brand);
  font-size: var(--text-xs);
  font-weight: 500;
  line-height: 1.4;
  transition: all var(--transition-fast);
}

.luomi-skill-chip:hover {
  background: var(--lumi-brand-glow);
  border-color: var(--lumi-brand);
}

.luomi-skill-chip-icon {
  flex-shrink: 0;
  opacity: 0.8;
}

.luomi-skill-chip-name {
  white-space: nowrap;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.luomi-skill-chip-remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  border-radius: var(--radius-full);
  background: transparent;
  border: none;
  color: inherit;
  cursor: pointer;
  padding: 0;
  opacity: 0.6;
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.luomi-skill-chip-remove:hover {
  opacity: 1;
  background: var(--lumi-brand);
  color: var(--text-inverse);
}

.luomi-skills-clear {
  margin-left: var(--space-1);
  padding: 3px 8px;
  border-radius: var(--radius-full);
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-size: var(--text-xs);
  cursor: pointer;
  transition: color var(--transition-fast);
}

.luomi-skills-clear:hover {
  color: var(--lumi-accent);
}

/* ─── 触发按钮 ─── */
.luomi-skills-trigger {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  color: var(--text-muted);
  background: var(--surface-hover);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-in-out);
  white-space: nowrap;
  position: relative;
}

.luomi-skills-trigger:hover {
  color: var(--text-primary);
  background: var(--surface-active);
}

.luomi-skills-trigger.active {
  color: var(--lumi-brand);
  background: var(--lumi-brand-light);
  border-color: var(--lumi-brand-border);
}

.luomi-skills-trigger-text {
  font-weight: 500;
}

.luomi-skills-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: var(--radius-full);
  background: var(--lumi-brand);
  color: var(--text-inverse);
  font-size: var(--text-2xs);
  font-weight: 700;
  line-height: 1;
}

.luomi-skills-trigger-chevron {
  opacity: 0.6;
  transition: transform var(--duration-normal) var(--ease-in-out);
}

.luomi-skills-trigger-chevron.rotated {
  transform: rotate(180deg);
}

/* ─── 下拉面板 ─── */
.luomi-skills-dropdown {
  position: absolute;
  bottom: calc(100% + var(--space-2));
  left: 0;
  width: 320px;
  max-height: 380px;
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  border: 1px solid var(--border-light);
  z-index: 9999;
  overflow: hidden;
}

.luomi-skills-dropdown-header {
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--divider-soft);
  flex-shrink: 0;
}

.luomi-skills-search {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 6px 10px;
  background: var(--surface-hover);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-light);
  transition: all var(--transition-fast);
}

.luomi-skills-search:focus-within {
  border-color: var(--lumi-brand-border);
  background: var(--surface);
}

.luomi-skills-search-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.luomi-skills-search-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: var(--text-sm);
  color: var(--text-primary);
  min-width: 0;
}

.luomi-skills-search-input::placeholder {
  color: var(--text-muted);
}

.luomi-skills-dropdown-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-1);
}

.luomi-skills-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-2) 10px;
  border-radius: var(--radius-md);
  text-align: left;
  background: transparent;
  border: none;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.luomi-skills-item:hover {
  background: var(--surface-hover);
}

.luomi-skills-item.selected {
  background: var(--lumi-brand-light);
}

.luomi-skills-item-icon {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  background: var(--lumi-brand-glow);
  color: var(--lumi-brand);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.luomi-skills-item.selected .luomi-skills-item-icon {
  background: var(--lumi-brand);
  color: var(--text-inverse);
}

.luomi-skills-item-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.luomi-skills-item-name {
  font-size: var(--text-md);
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.luomi-skills-item-desc {
  font-size: var(--text-xs);
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.luomi-skills-item-check {
  width: 18px;
  height: 18px;
  border-radius: var(--radius-full);
  background: var(--lumi-brand);
  color: var(--text-inverse);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.luomi-skills-empty {
  padding: var(--space-6) var(--space-4);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-muted);
  text-align: center;
}

.luomi-skills-empty p {
  margin: 0;
}

.luomi-skills-empty-title {
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-secondary);
}

.luomi-skills-empty-desc {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.luomi-skills-empty-action {
  margin-top: var(--space-2);
  padding: 6px 14px;
  border-radius: var(--radius-full);
  background: var(--lumi-brand-light);
  border: 1px solid var(--lumi-brand-border);
  color: var(--lumi-brand);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.luomi-skills-empty-action:hover {
  background: var(--lumi-brand);
  color: var(--text-inverse);
}

.luomi-skills-dropdown-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) var(--space-3);
  border-top: 1px solid var(--divider-soft);
  flex-shrink: 0;
}

.luomi-skills-count {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.luomi-skills-manage {
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  background: transparent;
  border: none;
  color: var(--lumi-brand);
  font-size: var(--text-xs);
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.luomi-skills-manage:hover {
  background: var(--lumi-brand-light);
}

/* ─── 动画 ─── */
.luomi-skills-dropdown-fade-enter-active,
.luomi-skills-dropdown-fade-leave-active {
  transition: opacity var(--transition-fast), transform var(--transition-fast);
}

.luomi-skills-dropdown-fade-enter-from,
.luomi-skills-dropdown-fade-leave-to {
  opacity: 0;
  transform: translateY(4px);
}

.luomi-skills-chips-fade-enter-active,
.luomi-skills-chips-fade-leave-active {
  transition: opacity var(--transition-fast);
}

.luomi-skills-chips-fade-enter-from,
.luomi-skills-chips-fade-leave-to {
  opacity: 0;
}

.luomi-skill-chip-enter-active {
  transition: all var(--transition-fast);
}

.luomi-skill-chip-leave-active {
  transition: all var(--transition-fast);
  position: absolute;
}

.luomi-skill-chip-enter-from {
  opacity: 0;
  transform: scale(0.8);
}

.luomi-skill-chip-leave-to {
  opacity: 0;
  transform: scale(0.8);
}
</style>

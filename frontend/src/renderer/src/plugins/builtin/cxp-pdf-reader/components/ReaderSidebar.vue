<script setup lang="ts">
/**
 * ReaderSidebar — PDF 阅读器左侧大纲侧边栏。
 *
 * 显示文档大纲（目录），支持树形缩进、当前章节高亮、点击跳页。
 * 可折叠（由 isOpen 控制）。
 */
import { computed } from 'vue'
import { ChevronRight, ListTree, PanelLeftClose } from 'lucide-vue-next'
import type { CxPdfOutlineItem } from '../services/pdfApi'

const props = defineProps<{
  outline: CxPdfOutlineItem[]
  currentPage: number
  isOpen: boolean
}>()

const emit = defineEmits<{
  'page-change': [page: number]
  toggle: []
}>()

// 扁平化大纲（用于当前章节判定）
interface FlatItem {
  item: CxPdfOutlineItem
  level: number
  index: number
}

const flatOutline = computed<FlatItem[]>(() => {
  const result: FlatItem[] = []
  const walk = (items: CxPdfOutlineItem[], level: number) => {
    items.forEach((item, idx) => {
      result.push({ item, level, index: idx })
      if (item.children && item.children.length > 0) {
        walk(item.children, level + 1)
      }
    })
  }
  walk(props.outline, 0)
  return result
})

// 当前章节（最后一项 page <= currentPage 的项）
const currentChapterIdx = computed(() => {
  let idx = -1
  flatOutline.value.forEach((flat, i) => {
    if (flat.item.page <= props.currentPage) idx = i
  })
  return idx
})

const handleClick = (item: CxPdfOutlineItem) => {
  if (item.page > 0) emit('page-change', item.page)
}

const isCurrent = (idx: number): boolean => idx === currentChapterIdx.value
</script>

<template>
  <Transition name="slide-side">
    <aside v-if="isOpen" class="reader-sidebar">
      <div class="sidebar-header">
        <div class="header-title">
          <ListTree :size="16" />
          <span>大纲</span>
        </div>
        <button
          class="sidebar-close"
          title="折叠侧边栏"
          @click="emit('toggle')"
        >
          <PanelLeftClose :size="16" />
        </button>
      </div>

      <div class="sidebar-body">
        <div v-if="flatOutline.length === 0" class="empty-outline">
          <ListTree :size="32" class="empty-icon" />
          <p class="empty-text">该文档没有大纲</p>
          <p class="empty-hint">PDF 内置目录将为空</p>
        </div>

        <ul v-else class="outline-list">
          <li
            v-for="(flat, idx) in flatOutline"
            :key="`${flat.item.page}-${flat.index}-${idx}`"
            class="outline-item"
            :class="{ current: isCurrent(idx) }"
            :style="{ paddingLeft: `${12 + flat.level * 16}px` }"
            :title="flat.item.title"
            @click="handleClick(flat.item)"
          >
            <ChevronRight
              v-if="flat.item.children && flat.item.children.length > 0"
              :size="12"
              class="item-arrow"
            />
            <span
              v-else
              class="item-dot"
            />
            <span class="item-title">{{ flat.item.title }}</span>
            <span class="item-page">{{ flat.item.page }}</span>
          </li>
        </ul>
      </div>
    </aside>
  </Transition>
</template>

<style scoped>
.reader-sidebar {
  width: 240px;
  flex-shrink: 0;
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.header-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--text);
}

.sidebar-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  border-radius: var(--radius-xs);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.sidebar-close:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.sidebar-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-2) 0;
}

.empty-outline {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-8) var(--space-4);
  gap: var(--space-2);
  color: var(--text-muted);
  text-align: center;
}

.empty-icon {
  opacity: 0.4;
}

.empty-text {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.empty-hint {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.outline-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.outline-item {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  padding-right: var(--space-2);
  cursor: pointer;
  font-size: var(--text-sm);
  color: var(--text-secondary);
  border-left: 2px solid transparent;
  transition: all var(--transition-fast);
  white-space: nowrap;
  overflow: hidden;
}

.outline-item:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.outline-item.current {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  border-left-color: var(--lumi-primary);
  font-weight: var(--font-medium);
}

.item-arrow {
  flex-shrink: 0;
  color: var(--text-muted);
}

.outline-item.current .item-arrow {
  color: var(--lumi-primary);
}

.item-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--text-muted);
  flex-shrink: 0;
}

.outline-item.current .item-dot {
  background: var(--lumi-primary);
}

.item-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-page {
  flex-shrink: 0;
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}

.outline-item.current .item-page {
  color: var(--lumi-primary);
}

.slide-side-enter-active,
.slide-side-leave-active {
  transition: width var(--transition-normal), opacity var(--transition-fast);
  overflow: hidden;
}

.slide-side-enter-from,
.slide-side-leave-to {
  width: 0;
  opacity: 0;
}
</style>

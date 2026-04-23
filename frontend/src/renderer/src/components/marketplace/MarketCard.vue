<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Heart, Download, Star } from 'lucide-vue-next'
import type { MarketItem } from '../../types/marketplace'
import { useMarketplaceStore } from '../../stores/marketplace'
import MarketIcon from './MarketIcon.vue'
import RatingStars from './RatingStars.vue'

const props = defineProps<{
  item: MarketItem
}>()

const router = useRouter()
const store = useMarketplaceStore()

const typeLabel = computed(() => props.item.type === 'plugin' ? '插件' : 'Skill')
const typeColor = computed(() => props.item.type === 'plugin' ? '#6366f1' : '#0d9488')

function goToDetail() {
  router.push(`/marketplace/${props.item.type}/${props.item.id}`)
}

function handleFavorite(e: Event) {
  e.stopPropagation()
  store.toggleFavorite(props.item.id)
}
</script>

<template>
  <div class="market-card" @click="goToDetail">
    <div class="card-header">
      <div class="card-icon" :style="{ background: typeColor + '14', color: typeColor }">
        <MarketIcon :name="item.icon" :size="22" />
      </div>
      <div class="card-badge" :style="{ background: typeColor + '18', color: typeColor }">
        {{ typeLabel }}
      </div>
      <button
        :class="['fav-btn', { active: item.isFavorite }]"
        @click="handleFavorite"
        :aria-label="item.isFavorite ? '取消收藏' : '收藏'"
      >
        <Heart :size="16" />
      </button>
    </div>

    <div class="card-body">
      <h3 class="card-title">{{ item.name }}</h3>
      <p class="card-desc">{{ item.description }}</p>
    </div>

    <div class="card-tags">
      <span v-for="tag in item.tags.slice(0, 3)" :key="tag" class="tag-chip">{{ tag }}</span>
    </div>

    <div class="card-footer">
      <div class="card-stats">
        <div class="stat">
          <Star :size="12" class="stat-icon star" />
          <span>{{ item.rating.toFixed(1) }}</span>
        </div>
        <div class="stat">
          <Download :size="12" class="stat-icon" />
          <span>{{ item.downloadCount >= 1000 ? (item.downloadCount / 1000).toFixed(1) + 'k' : item.downloadCount }}</span>
        </div>
      </div>
      <span class="card-version">v{{ item.version }}</span>
    </div>

    <div v-if="item.isInstalled" class="installed-indicator">
      已安装
    </div>
  </div>
</template>

<style scoped>
.market-card {
  display: flex;
  flex-direction: column;
  padding: 18px;
  border-radius: var(--radius-lg);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  cursor: pointer;
  transition: all var(--transition-normal);
  position: relative;
  overflow: hidden;
}

.market-card:hover {
  border-color: var(--lumi-primary);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}

.card-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.card-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  letter-spacing: 0.3px;
}

.fav-btn {
  margin-left: auto;
  width: 30px;
  height: 30px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.fav-btn:hover {
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
}

.fav-btn.active {
  color: var(--lumi-accent);
}

.fav-btn.active :deep(svg) {
  fill: var(--lumi-accent);
}

.card-body {
  flex: 1;
  min-height: 0;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-desc {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-tags {
  display: flex;
  gap: 6px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.tag-chip {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  background: var(--bg-secondary);
  color: var(--text-secondary);
  font-weight: 500;
}

.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--border-light);
}

.card-stats {
  display: flex;
  gap: 12px;
}

.stat {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--text-muted);
}

.stat-icon {
  color: var(--text-muted);
}

.stat-icon.star {
  color: #f59e0b;
}

.card-version {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 500;
}

.installed-indicator {
  position: absolute;
  top: 12px;
  right: 12px;
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  background: rgba(34, 197, 94, 0.1);
  color: #22c55e;
}

@media (max-width: 768px) {
  .market-card {
    padding: 14px;
  }

  .card-icon {
    width: 38px;
    height: 38px;
  }
}
</style>

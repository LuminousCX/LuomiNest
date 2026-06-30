<script setup lang="ts">
import { computed } from 'vue'
import { Star, Download, Heart, ArrowRight, PackageCheck } from 'lucide-vue-next'
import type { MarketplaceItem, MarketplaceType } from '../../types/marketplace'
import { useRouter } from 'vue-router'
import { ITEM_ICON_MAP, DEFAULT_ICON } from '../../utils/marketplace-icons'
import { formatCount } from '../../utils/format'
import LumiCardIcon from '../common/LumiCardIcon.vue'

const props = defineProps<{
  items: MarketplaceItem[]
  title: string
  type: MarketplaceType
}>()

const router = useRouter()

const displayItems = computed(() => props.items.slice(0, 10))

function navigateToDetail(item: MarketplaceItem) {
  router.push(`/market/detail/${item.type}/${item.id}`)
}

function navigateToList() {
  router.push(`/market?tab=${props.type}`)
}
</script>

<template>
  <div class="market-banner">
    <div class="banner-header">
      <div class="banner-title-row">
        <PackageCheck :size="16" class="installed-icon" />
        <h2 class="banner-title">{{ title }}</h2>
      </div>
      <button class="view-all-btn" @click="navigateToList()">
        查看全部
        <ArrowRight :size="14" />
      </button>
    </div>

    <div v-if="displayItems.length > 0" class="banner-scroll custom-scrollbar--thin">
      <div
        v-for="entry in displayItems"
        :key="entry.id"
        class="banner-card"
        @click="navigateToDetail(entry)"
      >
        <LumiCardIcon
          :icon="ITEM_ICON_MAP[entry.icon] || DEFAULT_ICON"
          :size="20"
          :theme="entry.icon"
        />
        <div class="banner-card-info">
          <h4>{{ entry.name }}</h4>
          <p>{{ entry.summary }}</p>
          <div class="banner-card-stats">
            <span class="mini-stat">
              <Star :size="11" class="star-icon" />
              {{ entry.rating?.toFixed(1) || '0.0' }}
            </span>
            <span class="mini-stat">
              <Download :size="11" />
              {{ formatCount(entry.downloadCount || 0) }}
            </span>
            <span class="mini-stat">
              <Heart :size="11" class="like-icon" />
              {{ formatCount(entry.likeCount || 0) }}
            </span>
          </div>
        </div>
      </div>
    </div>
    <div v-else class="banner-empty">
      <PackageCheck :size="24" />
      <p>暂无已安装的内容</p>
    </div>
  </div>
</template>

<style scoped>
.market-banner {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.banner-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.banner-title-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.installed-icon {
  color: var(--lumi-success);
}

.banner-title {
  font-size: var(--text-xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
}

.view-all-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: var(--lumi-brand);
  transition: all var(--transition-fast);
}

.view-all-btn:hover {
  gap: var(--space-2);
}

.banner-scroll {
  display: flex;
  gap: var(--space-3);
  overflow-x: auto;
  padding-bottom: var(--space-1);
  scroll-snap-type: x mandatory;
}

.banner-card {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4);
  min-width: calc(var(--space-8) * 6 + var(--space-5));
  border-radius: var(--radius-lg);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  cursor: pointer;
  transition: all var(--transition-normal);
  scroll-snap-align: start;
  flex-shrink: 0;
}

.banner-card:hover {
  border-color: var(--lumi-brand);
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}

.banner-card-info {
  flex: 1;
  min-width: 0;
}

.banner-card-info h4 {
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin-bottom: var(--space-1);
}

.banner-card-info p {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: var(--space-1);
}

.banner-card-stats {
  display: flex;
  gap: var(--space-3);
}

.mini-stat {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

.star-icon {
  color: var(--lumi-warning);
}

.like-icon {
  color: var(--lumi-accent);
}

.banner-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-6);
  color: var(--text-muted);
  font-size: var(--text-sm);
}
</style>

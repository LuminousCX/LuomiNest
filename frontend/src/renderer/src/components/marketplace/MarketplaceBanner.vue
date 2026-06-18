<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { Star, Download, Heart, ArrowRight, Trophy } from 'lucide-vue-next'
import type { MarketplaceItem, MarketplaceType } from '../../types/marketplace'
import { useRouter } from 'vue-router'
import { useMarketplaceStore } from '../../stores/marketplace'
import { ITEM_ICON_MAP, DEFAULT_ICON } from '../../utils/marketplace-icons'
import LumiCardIcon from '../common/LumiCardIcon.vue'

const props = defineProps<{
  items: MarketplaceItem[]
  title: string
  type: MarketplaceType
}>()

const router = useRouter()
const store = useMarketplaceStore()

const sortBy = ref<'composite' | 'downloads' | 'likes'>('composite')

// 根据 sortBy 排序 items
const sortedItems = computed(() => {
  const list = [...props.items]
  if (sortBy.value === 'downloads') {
    list.sort((a, b) => b.downloadCount - a.downloadCount)
  } else if (sortBy.value === 'likes') {
    list.sort((a, b) => b.likeCount - a.likeCount)
  } else {
    // 综合排序：downloadCount + likeCount * 3
    list.sort((a, b) => (b.downloadCount + b.likeCount * 3) - (a.downloadCount + a.likeCount * 3))
  }
  return list.slice(0, 10)
})

// 排行榜数据：从后端获取
const leaderboardLoading = ref(false)

async function fetchLeaderboard() {
  leaderboardLoading.value = true
  try {
    await store.fetchLeaderboard(props.type, sortBy.value, 10)
  } finally {
    leaderboardLoading.value = false
  }
}

watch(() => props.type, () => {
  fetchLeaderboard()
})

watch(sortBy, () => {
  fetchLeaderboard()
})

onMounted(() => {
  fetchLeaderboard()
})

// 合并排行榜后端数据与本地 item 信息
// 始终使用 store 中已同步的 item 数据，确保与卡片/详情页一致
const displayItems = computed(() => {
  const lbItems = store.leaderboardItems
  if (lbItems.length === 0) {
    // 没有后端数据时使用本地排序
    return sortedItems.value.map((item, index) => ({
      ...item,
      _rank: index + 1,
    }))
  }
  // 有后端排行榜数据时，用排行榜排序，但统计数据取自 store 中已同步的 item
  return lbItems.map((entry, index) => {
    const item = props.items.find(i => i.id === entry.itemId)
    return {
      ...(item || {}),
      id: entry.itemId,
      name: item?.name || entry.name,
      icon: item?.icon || entry.icon,
      summary: item?.summary || entry.summary || '',
      type: entry.type,
      // 使用 store 中已同步的统计数据，确保与其他页面一致
      downloadCount: item?.downloadCount ?? entry.downloadCount,
      likeCount: item?.likeCount ?? entry.likeCount,
      isLiked: item?.isLiked,
      rating: item?.rating || 0,
      _rank: index + 1,
    } as (MarketplaceItem & { _rank: number })
  })
})

function navigateToDetail(item: MarketplaceItem & { _rank?: number }) {
  router.push(`/market/detail/${item.type}/${item.id}`)
}

function navigateToList() {
  router.push(`/market?tab=${props.type}`)
}

function getRankClass(rank: number): string {
  if (rank === 1) return 'rank-gold'
  if (rank === 2) return 'rank-silver'
  if (rank === 3) return 'rank-bronze'
  return ''
}

function formatCount(n: number): string {
  return n >= 1000 ? (n / 1000).toFixed(1) + 'k' : String(n)
}
</script>

<template>
  <div class="market-banner">
    <div class="banner-header">
      <div class="banner-title-row">
        <Trophy :size="16" class="trophy-icon" />
        <h2 class="banner-title">{{ title }}</h2>
      </div>
      <div class="banner-actions">
        <div class="banner-sort">
          <button
            :class="['sort-btn', { active: sortBy === 'composite' }]"
            @click="sortBy = 'composite'"
          >综合</button>
          <button
            :class="['sort-btn', { active: sortBy === 'downloads' }]"
            @click="sortBy = 'downloads'"
          >下载</button>
          <button
            :class="['sort-btn', { active: sortBy === 'likes' }]"
            @click="sortBy = 'likes'"
          >喜欢</button>
        </div>
        <button class="view-all-btn" @click="navigateToList()">
          查看全部
          <ArrowRight :size="14" />
        </button>
      </div>
    </div>

    <div class="banner-scroll">
      <div
        v-for="entry in displayItems"
        :key="entry.id"
        class="banner-card"
        @click="navigateToDetail(entry)"
      >
        <div :class="['banner-rank', getRankClass(entry._rank)]">
          {{ entry._rank }}
        </div>
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
  </div>
</template>

<style scoped>
.market-banner {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.banner-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.banner-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.trophy-icon {
  color: #f59e0b;
}

.banner-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.banner-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.banner-sort {
  display: flex;
  gap: 2px;
  padding: 2px;
  background: var(--workspace-panel);
  border-radius: var(--radius-sm);
}

.sort-btn {
  padding: 3px 8px;
  border-radius: var(--radius-xs);
  font-size: 11px;
  font-weight: 500;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.sort-btn:hover {
  color: var(--text-secondary);
}

.sort-btn.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.view-all-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 500;
  color: var(--lumi-primary);
  transition: all var(--transition-fast);
}

.view-all-btn:hover {
  gap: 6px;
}

.banner-scroll {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 4px;
  scroll-snap-type: x mandatory;
}

.banner-scroll::-webkit-scrollbar {
  height: 3px;
}

.banner-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  min-width: 260px;
  border-radius: var(--radius-lg);
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  cursor: pointer;
  transition: all var(--transition-normal);
  scroll-snap-align: start;
  flex-shrink: 0;
}

.banner-card:hover {
  border-color: var(--lumi-primary);
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}

.banner-rank {
  width: 22px;
  height: 22px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  background: var(--workspace-panel);
  flex-shrink: 0;
}

.rank-gold {
  background: linear-gradient(135deg, #fbbf24, #f59e0b);
  color: #fff;
}

.rank-silver {
  background: linear-gradient(135deg, #d1d5db, #9ca3af);
  color: #fff;
}

.rank-bronze {
  background: linear-gradient(135deg, #f97316, #ea580c);
  color: #fff;
}

.banner-card-info {
  flex: 1;
  min-width: 0;
}

.banner-card-info h4 {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 3px;
}

.banner-card-info p {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.banner-card-stats {
  display: flex;
  gap: 10px;
}

.mini-stat {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 10px;
  color: var(--text-muted);
}

.star-icon {
  color: var(--lumi-star);
}

.like-icon {
  color: var(--lumi-accent);
}
</style>

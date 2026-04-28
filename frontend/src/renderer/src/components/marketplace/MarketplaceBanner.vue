<script setup lang="ts">
import {
  Star, Download, ArrowRight, Package,
  Brain, Home, MessageSquare, Search, Volume2, Zap, User, RefreshCw,
  Globe, Laptop, PenTool, BookOpen, Palette, HeartPulse, Users, BarChart3,
  Bot, Lightbulb, Terminal, GraduationCap, TrendingUp, Shield, Scale,
} from 'lucide-vue-next'
import type { MarketplaceItem } from '../../types/marketplace'
import { useRouter } from 'vue-router'

const ITEM_ICON_MAP: Record<string, any> = {
  Brain, Home, MessageSquare, Search, Volume2, Zap, User, RefreshCw,
  Globe, Laptop, PenTool, BookOpen, Palette, HeartPulse, Users, BarChart3,
  Bot, Lightbulb, Terminal, GraduationCap, TrendingUp, Shield, Scale,
  Package,
}

const props = defineProps<{
  items: MarketplaceItem[]
  title: string
  type: 'plugin' | 'skill' | 'agent'
}>()

const router = useRouter()

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
      <h2 class="banner-title">{{ title }}</h2>
      <button class="view-all-btn" @click="navigateToList()">
        查看全部
        <ArrowRight :size="14" />
      </button>
    </div>

    <div class="banner-scroll">
      <div
        v-for="item in items"
        :key="item.id"
        class="banner-card"
        @click="navigateToDetail(item)"
      >
        <div class="banner-card-icon">
          <component :is="ITEM_ICON_MAP[item.icon] || Package" :size="20" />
        </div>
        <div class="banner-card-info">
          <h4>{{ item.name }}</h4>
          <p>{{ item.summary }}</p>
          <div class="banner-card-stats">
            <span class="mini-stat">
              <Star :size="11" class="star-icon" />
              {{ item.rating.toFixed(1) }}
            </span>
            <span class="mini-stat">
              <Download :size="11" />
              {{ item.downloadCount >= 1000 ? (item.downloadCount / 1000).toFixed(1) + 'k' : item.downloadCount }}
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

.banner-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
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
  gap: 12px;
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

.banner-card-icon {
  width: 42px;
  height: 42px;
  border-radius: var(--radius-md);
  background: var(--workspace-panel);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--lumi-primary);
  flex-shrink: 0;
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
</style>

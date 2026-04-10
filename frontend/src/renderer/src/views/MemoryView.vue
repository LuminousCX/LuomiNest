<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  Brain,
  Database,
  Search,
  Layers,
  Clock,
  BookOpen,
  User,
  Cpu,
  ArrowRight,
  Activity,
  TrendingUp,
  Filter,
  RefreshCw,
  Zap,
  Archive
} from 'lucide-vue-next'

interface MemoryLayer {
  id: string
  name: string
  sub: string
  icon: typeof Brain
  color: string
  capacity: number
  used: number
  unit: string
  desc: string
  items: { text: string; time: string; tag: string }[]
}

const layers = ref<MemoryLayer[]>([
  {
    id: 'working',
    name: '工作记忆',
    sub: 'Working Memory',
    icon: Cpu,
    color: '#f59e0b',
    capacity: 100,
    used: 67,
    unit: 'Token',
    desc: '当前会话上下文 · 内存/Redis',
    items: [
      { text: '用户询问了 LuomiNest 的架构设计', time: '刚刚', tag: '对话' },
      { text: '正在讨论皮套渲染方案', time: '2min', tag: '上下文' },
      { text: '用户偏好：深色主题', time: '5min', tag: '偏好' }
    ]
  },
  {
    id: 'episodic',
    name: '情景记忆',
    sub: 'Episodic Memory',
    icon: Clock,
    color: '#22c55e',
    capacity: 7,
    used: 5.3,
    unit: '天',
    desc: '近期事件回忆 · SQLite + 向量索引',
    items: [
      { text: '昨天讨论了 MCP 工具域的实现方案', time: '1天前', tag: '技术' },
      { text: '用户提到喜欢 ease-in-out 动画风格', time: '3天前', tag: '偏好' },
      { text: '完成了桌面客户端 UI 布局规范文档', time: '4天前', tag: '工作' },
      { text: '首次配置了后端连接', time: '5天前', tag: '系统' }
    ]
  },
  {
    id: 'semantic',
    name: '语义记忆',
    sub: 'Semantic Memory',
    icon: Database,
    color: '#8b5cf6',
    capacity: 1000,
    used: 342,
    unit: '万 Token',
    desc: '永久认知 · PGVector + 知识图谱',
    items: [
      { text: '用户是全栈开发者，擅长 Vue/Python', time: '长期', tag: '画像' },
      { text: '项目代号：LuomiNest，分布式AI伴侣平台', time: '长期', tag: '知识' },
      { text: '核心架构：统一后端 + 多端渲染 + 插件生态', time: '长期', tag: '知识' },
      { text: '用户习惯夜间工作，偏好简洁界面', time: '长期', tag: '画像' }
    ]
  }
])

const activeLayer = ref(0)

const activeLayerData = computed(() => layers.value[activeLayer.value])

const userPortrait = ref({
  tags: ['开发者', '夜猫子', '极客', 'Vue爱好者'],
  interests: ['AI Agent', '嵌入式开发', '开源项目', '游戏化交互'],
  interactionCount: 12847,
  memoryHealth: 94
})

const searchQuery = ref('')
const isSearching = ref(false)

function switchLayer(idx: number) {
  activeLayer.value = idx
}

function handleSearch() {
  if (!searchQuery.value.trim()) return
  isSearching.value = true
  setTimeout(() => { isSearching.value = false }, 1200)
}
</script>

<template>
  <div class="memory-view">
    <div class="memory-header">
      <div class="header-left">
        <Brain :size="20" />
        <h2>记忆中枢</h2>
        <span class="header-badge">MaaS · 三层记忆架构</span>
      </div>
      <div class="header-actions">
        <div class="search-bar">
          <Search :size="14" class="search-icon" />
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索记忆..."
            @keydown.enter="handleSearch"
          />
          <RefreshCw :size="13" :class="{ spinning: isSearching }" class="search-refresh" />
        </div>
        <button class="h-btn"><Filter :size="15" /> 筛选</button>
      </div>
    </div>

    <div class="memory-body">
      <div class="layer-stack animate-fade-up">
        <div class="stack-visual">
          <div
            v-for="(layer, idx) in layers"
            :key="layer.id"
            :class="['layer-card', { active: activeLayer === idx }]"
            :style="{ '--layer-color': layer.color, '--layer-delay': `${idx * 0.12}s` }"
            @click="switchLayer(idx)"
          >
            <div class="layer-top">
              <div class="layer-icon-wrap" :style="{ background: layer.color + '18' }">
                <component :is="layer.icon" :size="20" :style="{ color: layer.color }" />
              </div>
              <div class="layer-meta">
                <span class="layer-name">{{ layer.name }}</span>
                <span class="layer-sub">{{ layer.sub }}</span>
              </div>
              <Layers :size="14" class="layer-indicator" />
            </div>

            <div class="layer-bar-wrap">
              <div class="layer-bar-track">
                <div
                  class="layer-bar-fill"
                  :style="{ width: (layer.used / layer.capacity * 100) + '%', background: layer.color }"
                ></div>
              </div>
              <span class="layer-bar-label">{{ layer.used }} / {{ layer.capacity }} {{ layer.unit }}</span>
            </div>

            <p class="layer-desc">{{ layer.desc }}</p>
          </div>

          <div class="flow-arrow">
            <ArrowRight :size="16" />
            <span>MemCell 提取 → 分类 → 压缩 → 检索</span>
          </div>
        </div>
      </div>

      <div class="memory-detail animate-slide-left">
        <div class="detail-header">
          <component :is="activeLayerData.icon" :size="22" :style="{ color: activeLayerData.color }" />
          <h3>{{ activeLayerData.name }}</h3>
          <span class="detail-sub">{{ activeLayerData.sub }}</span>
        </div>

        <div class="detail-capacity">
          <div class="cap-ring">
            <svg viewBox="0 0 100 100" class="cap-svg">
              <circle cx="50" cy="50" r="42" fill="none" stroke="var(--border)" stroke-width="8"/>
              <circle
                cx="50" cy="50" r="42" fill="none"
                :stroke="activeLayerData.color"
                stroke-width="8"
                stroke-linecap="round"
                :stroke-dasharray="264"
                :stroke-dashoffset="264 - (264 * activeLayerData.used / activeLayerData.capacity)"
                class="cap-progress"
              />
            </svg>
            <div class="cap-text">
              <span class="cap-value">{{ Math.round(activeLayerData.used / activeLayerData.capacity * 100) }}%</span>
              <span class="cap-unit">已用</span>
            </div>
          </div>
          <div class="cap-stats">
            <div class="stat-item">
              <Activity :size="14" />
              <span>{{ activeLayerData.items.length }} 条记录</span>
            </div>
            <div class="stat-item">
              <TrendingUp :size="14" />
              <span>+{{ Math.floor(Math.random() * 20) + 5 }} 今日新增</span>
            </div>
            <div class="stat-item">
              <Zap :size="14" />
              <span>RAG 就绪</span>
            </div>
          </div>
        </div>

        <div class="detail-list">
          <div class="list-title">记忆片段</div>
          <TransitionGroup name="memo-list" tag="div" class="memo-items">
            <div
              v-for="(item, idx) in activeLayerData.items"
              :key="idx"
              class="memo-item"
              :style="{ '--item-delay': `${idx * 0.08}s` }"
            >
              <div class="memo-dot" :style="{ background: activeLayerData.color }"></div>
              <div class="memo-content">
                <p class="memo-text">{{ item.text }}</p>
                <div class="memo-footer">
                  <span class="memo-tag">{{ item.tag }}</span>
                  <span class="memo-time">{{ item.time }}</span>
                </div>
              </div>
            </div>
          </TransitionGroup>
        </div>

        <div class="portrait-card">
          <div class="portrait-header">
            <User :size="15" />
            <span>用户画像</span>
          </div>
          <div class="portrait-tags">
            <span v-for="tag in userPortrait.tags" :key="tag" class="p-tag">{{ tag }}</span>
          </div>
          <div class="portrait-interests">
            <BookOpen :size="13" />
            <span v-for="int in userPortrait.interests" :key="int" class="i-tag">{{ int }}</span>
          </div>
          <div class="portrait-stats-row">
            <div class="ps-item">
              <Archive :size="13" />
              <span>{{ userPortrait.interactionCount.toLocaleString() }} 次互动</span>
            </div>
            <div class="ps-item">
              <Activity :size="13" />
              <span>记忆健康 {{ userPortrait.memoryHealth }}%</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.memory-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg);
  color: var(--text);
  overflow: hidden;
}

.memory-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-muted);
}

.header-left h2 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text);
}

.header-badge {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 20px;
  background: rgba(139, 92, 246, 0.1);
  color: #8b5cf6;
  font-weight: 500;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.search-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 14px;
  border-radius: 10px;
  background: var(--surface);
  border: 1px solid var(--border);
  transition: all 300ms ease-in-out;
}

.search-bar:focus-within {
  border-color: #8b5cf6;
  box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.15);
}

.search-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.search-bar input {
  width: 180px;
  font-size: 13px;
  background: transparent;
  color: var(--text);
}

.search-bar input::placeholder {
  color: var(--text-muted);
}

.search-refresh {
  color: var(--text-muted);
  cursor: pointer;
  transition: transform 300ms ease-in-out;
}

.search-refresh.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.h-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border-radius: 8px;
  font-size: 13px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 300ms ease-in-out;
  white-space: nowrap;
}

.h-btn:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.memory-body {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.layer-stack {
  width: 340px;
  padding: 20px;
  border-right: 1px solid var(--border);
  overflow-y: auto;
  flex-shrink: 0;
  background: var(--surface);
}

.stack-visual {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.layer-card {
  padding: 16px;
  border-radius: 14px;
  border: 1px solid var(--border);
  background: var(--bg);
  cursor: pointer;
  transition: all 300ms ease-in-out;
  opacity: 0;
  animation: card-enter 0.45s cubic-bezier(0.22, 1, 0.36, 1) both;
  animation-delay: var(--layer-delay);
}

@keyframes card-enter {
  from { opacity: 0; transform: translateX(-16px); }
  to { opacity: 1; transform: translateX(0); }
}

.layer-card:hover {
  border-color: var(--layer-color);
  box-shadow: 0 4px 20px color-mix(in srgb, var(--layer-color) 10%, transparent);
}

.layer-card.active {
  border-color: var(--layer-color);
  background: color-mix(in srgb, var(--layer-color) 4%, transparent);
}

.layer-top {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.layer-icon-wrap {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.layer-meta {
  flex: 1;
  min-width: 0;
}

.layer-name {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}

.layer-sub {
  display: block;
  font-size: 11px;
  color: var(--text-muted);
}

.layer-indicator {
  color: var(--text-muted);
  opacity: 0.4;
}

.layer-bar-wrap {
  margin-bottom: 8px;
}

.layer-bar-track {
  height: 5px;
  background: var(--border);
  border-radius: 3px;
  overflow: hidden;
}

.layer-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 800ms cubic-bezier(0.22, 1, 0.36, 1);
}

.layer-bar-label {
  display: block;
  text-align: right;
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 4px;
  font-family: monospace;
}

.layer-desc {
  font-size: 11px;
  color: var(--text-muted);
  line-height: 1.5;
}

.flow-arrow {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 10px;
  background: rgba(139, 92, 246, 0.06);
  font-size: 11px;
  color: var(--text-muted);
}

.flow-arrow svg {
  color: #8b5cf6;
  flex-shrink: 0;
}

.memory-detail {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.detail-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.detail-header h3 {
  font-size: 20px;
  font-weight: 700;
  color: var(--text);
}

.detail-sub {
  font-size: 12px;
  color: var(--text-muted);
}

.detail-capacity {
  display: flex;
  align-items: center;
  gap: 28px;
  padding: 20px;
  border-radius: 14px;
  background: var(--surface);
  border: 1px solid var(--border);
}

.cap-ring {
  position: relative;
  width: 90px;
  height: 90px;
  flex-shrink: 0;
}

.cap-svg {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}

.cap-progress {
  transition: stroke-dashoffset 1s cubic-bezier(0.22, 1, 0.36, 1);
}

.cap-text {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.cap-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--text);
}

.cap-unit {
  font-size: 10px;
  color: var(--text-muted);
}

.cap-stats {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-muted);
}

.stat-item svg {
  color: #8b5cf6;
}

.detail-list {
  flex: 1;
}

.list-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--text);
}

.memo-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.memo-item {
  display: flex;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 12px;
  background: var(--surface);
  border: 1px solid transparent;
  transition: all 300ms ease-in-out;
  opacity: 0;
  animation: memo-in 0.4s cubic-bezier(0.22, 1, 0.36, 1) both;
  animation-delay: var(--item-delay);
}

@keyframes memo-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.memo-item:hover {
  border-color: var(--border);
  transform: translateX(4px);
}

.memo-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  margin-top: 7px;
  flex-shrink: 0;
}

.memo-content {
  flex: 1;
  min-width: 0;
}

.memo-text {
  font-size: 13px;
  color: var(--text);
  line-height: 1.5;
  margin-bottom: 6px;
}

.memo-footer {
  display: flex;
  align-items: center;
  gap: 10px;
}

.memo-tag {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 8px;
  background: rgba(139, 92, 246, 0.1);
  color: #8b5cf6;
  font-weight: 500;
}

.memo-time {
  font-size: 11px;
  color: var(--text-muted);
}

.portrait-card {
  padding: 18px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.06), rgba(13, 148, 136, 0.04));
  border: 1px solid var(--border);
}

.portrait-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 14px;
  color: var(--text);
}

.portrait-header svg {
  color: #8b5cf6;
}

.portrait-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.p-tag {
  font-size: 12px;
  padding: 4px 12px;
  border-radius: 20px;
  background: rgba(139, 92, 246, 0.1);
  color: #a78bfa;
  font-weight: 500;
}

.portrait-interests {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.portrait-interests > svg {
  color: var(--text-muted);
  flex-shrink: 0;
}

.i-tag {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 8px;
  background: var(--surface);
  color: var(--text-muted);
}

.portrait-stats-row {
  display: flex;
  gap: 20px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.ps-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
}

.ps-item svg {
  color: var(--lumi-primary);
}

@keyframes fade-up {
  0% { opacity: 0; transform: translateY(16px); }
  100% { opacity: 1; transform: translateY(0); }
}

.animate-fade-up {
  animation: fade-up 0.5s cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes slide-left {
  0% { opacity: 0; transform: translateX(24px); }
  100% { opacity: 1; transform: translateX(0); }
}

.animate-slide-left {
  animation: slide-left 0.5s cubic-bezier(0.22, 1, 0.36, 1) both;
}

.memo-list-enter-active,
.memo-list-leave-active {
  transition: all 300ms ease-in-out;
}
.memo-list-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.memo-list-leave-to {
  opacity: 0;
  transform: translateX(-12px);
}
</style>

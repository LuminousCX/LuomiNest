<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import {
  Search,
  Bot,
  BarChart3,
  Terminal,
  Lightbulb,
  GraduationCap,
  TrendingUp,
  Shield,
  Scale,
  Sparkles,
  Download,
  Check,
  Loader2,
  Star,
  ExternalLink,
  Plus,
} from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import LumiModal from '../common/LumiModal.vue'
import { useMarketplaceStore } from '../../stores/marketplace'
import { useAgentStore } from '../../stores/agent'
import type { MarketplaceItem } from '../../types/marketplace'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  'update:visible': [visible: boolean]
  'agent-installed': [agentId: string]
}>()

const router = useRouter()
const marketplaceStore = useMarketplaceStore()
const agentStore = useAgentStore()

const searchQuery = ref('')
const installingIds = ref<Set<string>>(new Set())
const createdMarketIds = ref<Set<string>>(new Set())
const unwatchFns: Array<() => void> = []

const iconMap: Record<string, typeof Bot> = {
  Bot,
  BarChart3,
  Terminal,
  Lightbulb,
  GraduationCap,
  TrendingUp,
  Shield,
  Scale,
  Sparkles,
}

const getAgentIcon = (iconName: string) => iconMap[iconName] || Sparkles

const marketAgents = computed(() => marketplaceStore.agentItems)

const filteredAgents = computed(() => {
  if (!searchQuery.value) return marketAgents.value
  const q = searchQuery.value.toLowerCase()
  return marketAgents.value.filter(
    (a) => a.name.toLowerCase().includes(q) || a.description.toLowerCase().includes(q)
  )
})

const getInstallProgress = (itemId: string) => marketplaceStore.installProgress[itemId]

const isAgentAlreadyCreated = (marketAgent: MarketplaceItem): boolean => {
  return agentStore.agents.some((a) => a.name === marketAgent.name)
}

const getAgentStatus = (agent: MarketplaceItem): 'none' | 'installing' | 'installed' | 'added' => {
  if (createdMarketIds.value.has(agent.id) || isAgentAlreadyCreated(agent)) return 'added'
  const progress = getInstallProgress(agent.id)
  if (progress) {
    if (progress.status === 'installed') return 'installed'
    if (progress.status === 'downloading' || progress.status === 'installing') return 'installing'
  }
  if (agent.installStatus === 'installed') return 'installed'
  return 'none'
}

const luomiGenerateSystemPrompt = (agent: MarketplaceItem): string => {
  const tags = agent.tags?.map((t) => t.name || t).filter(Boolean).join('、')
  return [
    `你是${agent.name}。`,
    agent.description,
    tags ? `你擅长：${tags}。` : '',
    '你的目标是帮助用户解决问题，提供专业、友好、准确的回答。',
  ].filter(Boolean).join('')
}

const createAgentFromMarket = async (agent: MarketplaceItem) => {
  if (isAgentAlreadyCreated(agent)) {
    const existing = agentStore.agents.find((a) => a.name === agent.name)
    if (existing) {
      createdMarketIds.value.add(agent.id)
      emit('agent-installed', existing.id)
    }
    return
  }

  try {
    const result = await agentStore.createAgent({
      name: agent.name,
      description: agent.summary || agent.description,
      systemPrompt: luomiGenerateSystemPrompt(agent),
      color: '#147EBC',
      capabilities: ['chat'],
    })
    createdMarketIds.value.add(agent.id)
    emit('agent-installed', result.id)
  } catch (err) {
    console.error('[AgentMarketPanel] 创建智能体失败:', err)
  }
}

const handleInstall = (agent: MarketplaceItem) => {
  const status = getAgentStatus(agent)
  if (status === 'installing' || status === 'added') return

  if (status === 'installed') {
    createAgentFromMarket(agent)
    return
  }

  marketplaceStore.startInstall(agent.id)
  installingIds.value.add(agent.id)

  const stopWatch = watch(
    () => marketplaceStore.installProgress[agent.id]?.status,
    (newStatus) => {
      if (newStatus === 'installed') {
        stopWatch()
        const idx = unwatchFns.indexOf(stopWatch)
        if (idx >= 0) unwatchFns.splice(idx, 1)
        installingIds.value.delete(agent.id)
        createAgentFromMarket(agent)
      }
    }
  )
  unwatchFns.push(stopWatch)
}

const handleClose = () => {
  emit('update:visible', false)
}

const goToMarketPage = () => {
  handleClose()
  router.push('/market?tab=agent')
}

onBeforeUnmount(() => {
  unwatchFns.forEach((fn) => fn())
  unwatchFns.length = 0
})
</script>

<template>
  <LumiModal
    :visible="visible"
    title="智能体市场"
    size="lg"
    @update:visible="emit('update:visible', $event)"
    @close="handleClose"
  >
    <div class="luomi-agent-market">
      <!-- 搜索栏 -->
      <div class="luomi-market-search-bar">
        <div class="luomi-market-search">
          <Search :size="14" class="luomi-market-search-icon" />
          <input
            v-model="searchQuery"
            type="text"
            placeholder="搜索智能体..."
            class="luomi-market-search-input"
          />
        </div>
        <button class="luomi-market-more" title="前往市场页面" @click="goToMarketPage">
          <ExternalLink :size="14" />
          <span>更多市场</span>
        </button>
      </div>

      <!-- 智能体列表 -->
      <div class="luomi-market-list">
        <div
          v-for="agent in filteredAgents"
          :key="agent.id"
          class="luomi-market-card"
        >
          <div class="luomi-market-card-icon">
            <component :is="getAgentIcon(agent.icon)" :size="20" />
          </div>

          <div class="luomi-market-card-body">
            <div class="luomi-market-card-header">
              <span class="luomi-market-card-name">{{ agent.name }}</span>
              <span v-if="agent.rating" class="luomi-market-card-rating">
                <Star :size="11" class="luomi-market-star-icon" />
                {{ agent.rating.toFixed(1) }}
              </span>
            </div>
            <p class="luomi-market-card-desc">{{ agent.description }}</p>
            <div class="luomi-market-card-meta">
              <span class="luomi-market-card-author">{{ agent.author.name }}</span>
              <span v-if="agent.category" class="luomi-market-card-category">{{ agent.category }}</span>
            </div>
          </div>

          <div class="luomi-market-card-action">
            <!-- 未安装 -->
            <button
              v-if="getAgentStatus(agent) === 'none'"
              class="luomi-market-btn install"
              @click="handleInstall(agent)"
            >
              <Download :size="13" />
              <span>安装</span>
            </button>

            <!-- 安装中 -->
            <div v-else-if="getAgentStatus(agent) === 'installing'" class="luomi-market-progress">
              <Loader2 :size="13" class="luomi-market-spin" />
              <div class="luomi-market-progress-bar">
                <div
                  class="luomi-market-progress-fill"
                  :style="{ width: `${getInstallProgress(agent.id)?.progress || 0}%` }"
                ></div>
              </div>
              <span class="luomi-market-progress-text">
                {{ Math.round(getInstallProgress(agent.id)?.progress || 0) }}%
              </span>
            </div>

            <!-- 已安装但未添加到对话 -->
            <button
              v-else-if="getAgentStatus(agent) === 'installed'"
              class="luomi-market-btn add"
              @click="handleInstall(agent)"
            >
              <Plus :size="13" />
              <span>添加到对话</span>
            </button>

            <!-- 已添加到对话 -->
            <div v-else class="luomi-market-added">
              <Check :size="13" />
              <span>已添加</span>
            </div>
          </div>
        </div>

        <!-- 空状态 -->
        <div v-if="filteredAgents.length === 0" class="luomi-market-empty">
          <Bot :size="32" />
          <p class="luomi-market-empty-title">
            {{ searchQuery ? '未找到匹配的智能体' : '暂无智能体' }}
          </p>
          <p class="luomi-market-empty-desc">
            {{ searchQuery ? '试试其他关键词' : '前往市场发现更多智能体' }}
          </p>
        </div>
      </div>
    </div>
  </LumiModal>
</template>

<style scoped>
.luomi-agent-market {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  max-height: 60vh;
}

/* ─── 搜索栏 ─── */
.luomi-market-search-bar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}

.luomi-market-search {
  flex: 1;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 8px 12px;
  background: var(--surface-hover);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-light);
  transition: all var(--transition-fast);
}

.luomi-market-search:focus-within {
  border-color: var(--lumi-brand-border);
  background: var(--surface);
}

.luomi-market-search-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.luomi-market-search-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: var(--text-sm);
  color: var(--text-primary);
  min-width: 0;
}

.luomi-market-search-input::placeholder {
  color: var(--text-muted);
}

.luomi-market-more {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  background: transparent;
  border: 1px solid var(--border-light);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
  white-space: nowrap;
}

.luomi-market-more:hover {
  border-color: var(--lumi-brand-border);
  color: var(--lumi-brand);
  background: var(--lumi-brand-light);
}

/* ─── 智能体列表 ─── */
.luomi-market-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding-right: var(--space-1);
}

.luomi-market-card {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--surface);
  border: 1px solid var(--border-light);
  transition: all var(--duration-normal) var(--ease-in-out);
}

.luomi-market-card:hover {
  border-color: var(--lumi-brand-border);
  box-shadow: var(--shadow-sm);
}

.luomi-market-card-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-sm);
  background: var(--lumi-brand-glow);
  color: var(--lumi-brand);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.luomi-market-card-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.luomi-market-card-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.luomi-market-card-name {
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.luomi-market-card-rating {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: var(--text-xs);
  color: var(--text-muted);
  flex-shrink: 0;
}

.luomi-market-star-icon {
  color: #f5a623;
  fill: #f5a623;
}

.luomi-market-card-desc {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: 1.5;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.luomi-market-card-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.luomi-market-card-category {
  padding: 1px 6px;
  border-radius: var(--radius-full);
  background: var(--surface-hover);
}

/* ─── 操作区 ─── */
.luomi-market-card-action {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  min-width: 100px;
  justify-content: flex-end;
}

.luomi-market-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
  border: 1px solid transparent;
  white-space: nowrap;
}

.luomi-market-btn.install {
  background: var(--lumi-brand);
  color: var(--text-inverse);
}

.luomi-market-btn.install:hover {
  background: var(--lumi-brand-hover, var(--lumi-brand));
  filter: brightness(1.1);
}

.luomi-market-btn.add {
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
  border-color: var(--lumi-brand-border);
}

.luomi-market-btn.add:hover {
  background: var(--lumi-brand);
  color: var(--text-inverse);
}

.luomi-market-progress {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  width: 100%;
}

.luomi-market-spin {
  color: var(--lumi-brand);
  animation: luomi-spin 1s linear infinite;
  flex-shrink: 0;
}

@keyframes luomi-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.luomi-market-progress-bar {
  flex: 1;
  height: 4px;
  background: var(--surface-hover);
  border-radius: var(--radius-full);
  overflow: hidden;
  min-width: 50px;
}

.luomi-market-progress-fill {
  height: 100%;
  background: var(--lumi-brand);
  border-radius: var(--radius-full);
  transition: width var(--duration-normal) var(--ease-in-out);
}

.luomi-market-progress-text {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  flex-shrink: 0;
  min-width: 30px;
  text-align: right;
}

.luomi-market-added {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  color: var(--text-muted);
  background: var(--surface-hover);
}

/* ─── 空状态 ─── */
.luomi-market-empty {
  padding: var(--space-8) var(--space-4);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-muted);
  text-align: center;
}

.luomi-market-empty p {
  margin: 0;
}

.luomi-market-empty-title {
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-secondary);
}

.luomi-market-empty-desc {
  font-size: var(--text-xs);
  color: var(--text-muted);
}
</style>

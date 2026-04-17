<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Settings,
  User,
  Palette,
  Bell,
  Shield,
  Database,
  Globe,
  Cpu,
  ChevronRight
} from 'lucide-vue-next'

defineProps<{
  version?: string
}>()

const router = useRouter()

const settingGroups = ref([
  {
    title: '账户与偏好',
    items: [
      { icon: User, label: '个人资料', desc: '管理你的账户信息', route: '/settings/profile' },
      { icon: Palette, label: '外观主题', desc: '自定义界面颜色与风格', route: '/settings/appearance' },
      { icon: Bell, label: '通知设置', desc: '配置消息提醒方式', route: '/settings/notifications' }
    ]
  },
  {
    title: '系统配置',
    items: [
      { icon: Cpu, label: 'AI 模型', desc: '选择 LLM 推理引擎', route: '/settings/ai-model' },
      { icon: Database, label: '记忆系统', desc: '三层记忆架构配置', route: '/settings/memory' },
      { icon: Shield, label: '隐私安全', desc: '数据加密与访问控制', route: '/settings/privacy' }
    ]
  },
  {
    title: '连接与扩展',
    items: [
      { icon: Globe, label: '消息平台', desc: 'QQ / 微信 / Discord 等', route: '/settings/platforms' },
      { icon: Settings, label: 'MCP 工具', desc: '外部工具接入协议', route: '/settings/mcp' }
    ]
  }
])

const navigateTo = (route: string) => {
  router.push(route)
}
</script>

<template>
  <div class="settings-view">
    <div class="settings-header animate-fade-in">
      <div class="header-icon">
        <Settings :size="24" />
      </div>
      <div>
        <h1 class="page-title">设置</h1>
        <p class="page-subtitle">自定义你的 LuomiNest 体验</p>
      </div>
    </div>

    <div class="settings-body">
      <div
        v-for="(group, gIdx) in settingGroups"
        :key="group.title"
        class="setting-group animate-slide-up"
        :style="{ animationDelay: `${gIdx * 100}ms` }"
      >
        <h3 class="group-title">{{ group.title }}</h3>
        <div class="setting-items">
          <button
            v-for="item in group.items"
            :key="item.label"
            class="setting-item"
            @click="navigateTo(item.route)"
          >
            <div class="item-icon-wrap">
              <component :is="item.icon" :size="20" />
            </div>
            <div class="item-info">
              <span class="item-label">{{ item.label }}</span>
              <span class="item-desc">{{ item.desc }}</span>
            </div>
            <ChevronRight :size="16" class="item-arrow" />
          </button>
        </div>
      </div>
    </div>

    <div class="settings-footer">
      <span v-if="version" class="version-text">LuomiNest v{{ version }} · 辰汐项目研发组</span>
    </div>
  </div>
</template>

<style scoped>
.settings-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--workspace-bg);
  overflow-y: auto;
  padding: 28px 32px;
}

.settings-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 32px;
}

.header-icon {
  width: 52px;
  height: 52px;
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, rgba(13, 148, 136, 0.1), rgba(20, 184, 166, 0.1));
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--lumi-primary);
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
}

.page-subtitle {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 2px;
}

.settings-body {
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.setting-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.group-title {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: var(--text-muted);
  padding-left: 4px;
}

.setting-items {
  background: var(--workspace-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  overflow: hidden;
  box-shadow: var(--shadow-xs);
}

.setting-item {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
  padding: 16px 18px;
  text-align: left;
  cursor: pointer;
  transition: all var(--transition-fast);
  position: relative;
}

.setting-item::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 18px;
  right: 18px;
  height: 1px;
  background: var(--divider-soft);
}

.setting-item:last-child::after {
  display: none;
}

.setting-item:hover {
  background: var(--workspace-hover);
}

.item-icon-wrap {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, rgba(13,148,136,0.06), rgba(99,102,241,0.04));
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.item-info {
  flex: 1;
  min-width: 0;
}

.item-label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 2px;
}

.item-desc {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
}

.item-arrow {
  color: var(--text-muted);
  flex-shrink: 0;
  transition: transform var(--transition-fast);
}

.setting-item:hover .item-arrow {
  transform: translateX(3px);
  color: var(--lumi-primary);
}

.settings-footer {
  margin-top: auto;
  padding-top: 24px;
  text-align: center;
}

.version-text {
  font-size: 11px;
  color: var(--text-muted);
}
</style>

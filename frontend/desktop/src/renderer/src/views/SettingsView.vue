<script setup lang="ts">
import { ref } from 'vue'
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
  version: string
}>()

const settingGroups = ref([
  {
    title: '账户与偏好',
    items: [
      { icon: User, label: '个人资料', desc: '管理你的账户信息' },
      { icon: Palette, label: '外观主题', desc: '自定义界面颜色与风格' },
      { icon: Bell, label: '通知设置', desc: '配置消息提醒方式' }
    ]
  },
  {
    title: '系统配置',
    items: [
      { icon: Cpu, label: 'AI 模型', desc: '选择 LLM 推理引擎' },
      { icon: Database, label: '记忆系统', desc: '三层记忆架构配置' },
      { icon: Shield, label: '隐私安全', desc: '数据加密与访问控制' }
    ]
  },
  {
    title: '连接与扩展',
    items: [
      { icon: Globe, label: '消息平台', desc: 'QQ / 微信 / Discord 等' },
      { icon: Settings, label: 'MCP 工具', desc: '外部工具接入协议' }
    ]
  }
])
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
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
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
  border-bottom: 1px solid var(--workspace-border);
}

.setting-item:last-child {
  border-bottom: none;
}

.setting-item:hover {
  background: var(--workspace-hover);
}

.item-icon-wrap {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  background: var(--workspace-panel);
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

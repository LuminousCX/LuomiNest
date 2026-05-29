<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Settings,
  Palette,
  Bell,
  Shield,
  Database,
  Globe,
  Cpu,
  ChevronRight
} from 'lucide-vue-next'
import LumiCardIcon from '../components/common/LumiCardIcon.vue'
import LumiBrandStar from '../components/common/LumiBrandStar.vue'

defineProps<{
  version?: string
}>()

const router = useRouter()

const settingGroups = ref([
  {
    title: '偏好',
    items: [
      { icon: Palette, label: '外观主题', desc: '自定义界面颜色与风格', route: '/settings/appearance', theme: 'Palette' },
      { icon: Bell, label: '通知设置', desc: '配置消息提醒方式', route: '/settings/notifications', theme: 'Lightbulb' }
    ]
  },
  {
    title: '系统配置',
    items: [
      { icon: Cpu, label: 'AI 模型', desc: '选择 LLM 推理引擎', route: '/settings/ai-model', theme: 'Cpu' },
      { icon: Database, label: '记忆系统', desc: '三层记忆架构配置', route: '/settings/memory', theme: 'Brain' },
      { icon: Shield, label: '隐私安全', desc: '数据加密与访问控制', route: '/settings/privacy', theme: 'Shield' }
    ]
  },
  {
    title: '连接与扩展',
    items: [
      { icon: Globe, label: '消息平台', desc: 'QQ / 微信 / Discord 等', route: '/settings/platforms', theme: 'Globe' }
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
      <LumiCardIcon :icon="Settings" :size="24" theme="Wrench" />
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
            <LumiCardIcon
              :icon="item.icon"
              :size="20"
              :theme="item.theme"
              :animated="false"
            />
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
      <LumiBrandStar :size="14" :animated="false" />
      <span v-if="version" class="version-text">LuomiNest v{{ version }} · LuminousChenXi</span>
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
  backdrop-filter: blur(8px);
}

.setting-item {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
  padding: 16px 18px;
  text-align: left;
  cursor: pointer;
  transition: all 0.25s ease-in-out;
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

.setting-item:hover::before {
  content: '';
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--lumi-primary);
  opacity: 0.6;
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
  transition: transform 0.25s ease-in-out, color 0.25s ease-in-out;
}

.setting-item:hover .item-arrow {
  transform: translateX(3px);
  color: var(--lumi-primary);
}

.settings-footer {
  margin-top: auto;
  padding-top: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.version-text {
  font-size: 11px;
  color: var(--text-muted);
}
</style>

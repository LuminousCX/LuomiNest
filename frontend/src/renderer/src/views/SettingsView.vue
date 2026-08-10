<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ChevronRight,
  Palette,
  Bell,
  Bot,
  Brain,
  Shield,
  MessageCircle,
  Puzzle,
  User,
  LogIn
} from 'lucide-vue-next'
import type { Component } from 'vue'
import LumiCard from '../components/common/LumiCard.vue'
import LumiButton from '../components/common/LumiButton.vue'

interface SettingItem {
  label: string
  desc: string
  route: string
  icon: Component
  iconColor: string
}

interface SettingGroup {
  title: string
  items: SettingItem[]
}

defineProps<{
  version?: string
}>()

const router = useRouter()

const settingGroups = ref<SettingGroup[]>([
  {
    title: '偏好',
    items: [
      { label: '外观主题', desc: '自定义界面颜色与风格', route: '/settings/appearance', icon: Palette, iconColor: 'var(--lumi-brand)' },
      { label: '通知设置', desc: '配置消息提醒方式', route: '/settings/notifications', icon: Bell, iconColor: 'var(--lumi-warning)' }
    ]
  },
  {
    title: '系统配置',
    items: [
      { label: '主智能体', desc: '工作台主 Agent 的人格、模型与行为', route: '/settings/main-agent', icon: Bot, iconColor: 'var(--lumi-primary)' },
      { label: '模型设置', desc: 'LLM 推理引擎、语音合成与语音识别', route: '/settings/ai-model', icon: Brain, iconColor: 'var(--lumi-accent)' },
      { label: '登录 / 注册', desc: '本地账户登录、注册与 JWT 管理', route: '/settings/auth', icon: LogIn, iconColor: 'var(--lumi-warning)' },
      { label: '隐私安全', desc: '数据加密与访问控制', route: '/settings/privacy', icon: Shield, iconColor: 'var(--lumi-danger)' }
    ]
  },
  {
    title: '连接与扩展',
    items: [
      { label: '消息平台', desc: 'QQ / 微信 / Discord 等', route: '/settings/platforms', icon: MessageCircle, iconColor: 'var(--lumi-secondary)' },
      { label: '插件与技能', desc: '前端插件 / 后端插件 / 技能管理', route: '/settings/plugins', icon: Puzzle, iconColor: 'var(--lumi-brand)' }
    ]
  }
])

const footerLinks = [
  { label: '关于开发者', route: '/settings/about' },
  { label: '项目参考', route: '/settings/license' },
  { label: '隐私与合规', route: '/settings/privacy-detail' }
]

const navigateTo = (route: string) => {
  router.push(route)
}
</script>

<template>
  <div class="settings-view">
    <div class="settings-view__content">
      <div class="settings-hero animate-fade-in">
        <div class="settings-hero__avatar">
          <User :size="28" />
        </div>
        <div class="settings-hero__content">
          <h1 class="settings-hero__title">设置</h1>
          <p class="settings-hero__subtitle">自定义你的 LuomiNest 体验</p>
        </div>
        <div class="settings-hero__line">
          <span class="settings-hero__dot" />
          <span class="settings-hero__dash" />
          <span class="settings-hero__dot" />
        </div>
      </div>

      <div class="settings-body">
        <div
          v-for="(group, gIdx) in settingGroups"
          :key="group.title"
          class="setting-group animate-slide-up"
          :style="{ animationDelay: `${gIdx * 80}ms` }"
        >
          <div class="group-header">
            <span class="group-header__dot" />
            <h3 class="group-header__title">{{ group.title }}</h3>
          </div>
          <LumiCard class="setting-items" padding="none">
            <button
              v-for="item in group.items"
              :key="item.label"
              class="setting-item"
              @click="navigateTo(item.route)"
            >
              <div class="setting-item__icon" :style="{ color: item.iconColor }">
                <component :is="item.icon" :size="20" />
              </div>
              <div class="setting-item__info">
                <span class="setting-item__label">{{ item.label }}</span>
                <span class="setting-item__desc">{{ item.desc }}</span>
              </div>
              <ChevronRight :size="16" class="setting-item__arrow" />
            </button>
          </LumiCard>
        </div>
      </div>

      <div class="settings-footer">
        <div class="footer-brand">
          <span v-if="version" class="version-text">LuomiNest v{{ version }} · LuminousChenXi</span>
        </div>
        <div class="footer-links">
          <LumiButton
            v-for="link in footerLinks"
            :key="link.label"
            variant="ghost"
            size="sm"
            @click="navigateTo(link.route)"
          >
            {{ link.label }}
          </LumiButton>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg);
  overflow-y: auto;
  padding: var(--space-6) var(--space-8) var(--space-5);
}

.settings-view__content {
  max-width: 860px;
  width: 100%;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

/* ── Hero ── */
.settings-hero {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-5) 0;
  margin-bottom: var(--space-4);
  position: relative;
}

.settings-hero__avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border-radius: var(--radius-full);
  background: var(--surface);
  border: 1px solid var(--border-light);
  color: var(--text-secondary);
  flex-shrink: 0;
}

.settings-hero__content {
  flex: 1;
}

.settings-hero__title {
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  letter-spacing: -0.3px;
  margin-bottom: var(--space-1);
}

.settings-hero__subtitle {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.settings-hero__line {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-left: auto;
  padding-left: var(--space-4);
}

.settings-hero__dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  background: var(--lumi-brand);
  opacity: 0.6;
}

.settings-hero__dash {
  width: 48px;
  height: 1px;
  background: var(--border-light);
}

/* ── Body ── */
.settings-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.setting-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.group-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding-left: var(--space-1);
}

.group-header__dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
  background: var(--lumi-brand);
}

.group-header__title {
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--text-muted);
}

.setting-items {
  overflow: hidden;
  border: 1px solid var(--border-light);
  box-shadow: var(--shadow-sm);
  transition: box-shadow var(--transition-fast);
}

.setting-items:hover {
  box-shadow: var(--shadow-md);
}

/* ── Item ── */
.setting-item {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  width: 100%;
  padding: var(--space-4) var(--space-4);
  text-align: left;
  cursor: pointer;
  background: transparent;
  border: none;
  transition: background-color var(--transition-fast);
  position: relative;
}

.setting-item::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 64px;
  right: var(--space-4);
  height: 1px;
  background: var(--divider-soft);
}

.setting-item:last-child::after {
  display: none;
}

.setting-item:hover {
  background: var(--surface-hover);
}

.setting-item:focus-visible {
  outline: none;
  background: var(--surface-hover);
  box-shadow: inset 0 0 0 1px var(--focus-ring);
}

.setting-item__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: var(--radius-lg);
  background: color-mix(in srgb, currentColor 12%, transparent);
  flex-shrink: 0;
  transition: transform var(--transition-fast);
}

.setting-item:hover .setting-item__icon {
  transform: scale(1.05);
}

.setting-item__info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.setting-item__label {
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--text);
}

.setting-item__desc {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.setting-item__arrow {
  color: var(--text-muted);
  flex-shrink: 0;
  opacity: 0.5;
  transition: transform var(--transition-fast), opacity var(--transition-fast), color var(--transition-fast);
}

.setting-item:hover .setting-item__arrow {
  transform: translateX(var(--space-1));
  opacity: 1;
  color: var(--lumi-brand);
}

/* ── Footer ── */
.settings-footer {
  margin-top: auto;
  padding-top: var(--space-6);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
}

.footer-brand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.version-text {
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

.footer-links {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

/* ── 响应式 ── */
@media (max-width: 768px) {
  .settings-view {
    padding: var(--space-4) var(--space-5) var(--space-3);
  }

  .settings-hero {
    flex-wrap: wrap;
    padding: var(--space-4) 0;
  }

  .settings-hero__line {
    display: none;
  }

  .setting-item {
    padding: var(--space-3);
  }

  .setting-item__icon {
    width: 36px;
    height: 36px;
  }
}

@media (max-width: 480px) {
  .settings-view {
    padding: var(--space-3) var(--space-4) var(--space-2);
  }

  .settings-hero__avatar {
    width: 44px;
    height: 44px;
  }

  .settings-hero__title {
    font-size: var(--text-xl);
  }

  .setting-item__desc {
    display: none;
  }
}
</style>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ChevronRight } from 'lucide-vue-next'
import LumiBrandStar from '../components/common/LumiBrandStar.vue'

defineProps<{
  version?: string
}>()

const router = useRouter()

const settingGroups = ref([
  {
    title: '偏好',
    items: [
      { label: '外观主题', desc: '自定义界面颜色与风格', route: '/settings/appearance' },
      { label: '通知设置', desc: '配置消息提醒方式', route: '/settings/notifications' }
    ]
  },
  {
    title: '系统配置',
    items: [
      { label: '主智能体', desc: '工作台主 Agent 的人格、模型与行为', route: '/settings/main-agent' },
      { label: 'AI 模型', desc: '选择 LLM 推理引擎', route: '/settings/ai-model' },
      { label: '语音合成 (TTS)', desc: '本地/在线 TTS 引擎与设备检测', route: '/settings/tts' },
      { label: '语音识别 (STT)', desc: '本地/在线 STT 引擎与语音输入', route: '/settings/stt' },
      { label: '隐私安全', desc: '数据加密与访问控制', route: '/settings/privacy' }
    ]
  },
  {
    title: '连接与扩展',
    items: [
      { label: '消息平台', desc: 'QQ / 微信 / Discord 等', route: '/settings/platforms' }
    ]
  }
])

const footerLinks = [
  { label: '关于开发者', route: '/settings/about' },
  { label: '开源协议', route: '/settings/license' },
  { label: '用户隐私', route: '/settings/privacy-detail' }
]

const navigateTo = (route: string) => {
  router.push(route)
}
</script>

<template>
  <div class="settings-view">
    <div class="settings-header animate-fade-in">
      <h1 class="page-title">设置</h1>
      <p class="page-subtitle">自定义你的 LuomiNest 体验</p>
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
            <div class="item-info">
              <span class="item-label">{{ item.label }}</span>
              <span class="item-desc">{{ item.desc }}</span>
            </div>
            <ChevronRight :size="15" class="item-arrow" />
          </button>
        </div>
      </div>
    </div>

    <div class="settings-footer">
      <div class="footer-brand">
        <LumiBrandStar :size="14" :animated="false" />
        <span v-if="version" class="version-text">LuomiNest v{{ version }} · LuminousChenXi</span>
      </div>
      <div class="footer-links">
        <button
          v-for="link in footerLinks"
          :key="link.label"
          class="footer-link"
          @click="navigateTo(link.route)"
        >
          {{ link.label }}
        </button>
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
  padding: var(--space-7) var(--space-8) var(--space-5);
}

.settings-header {
  margin-bottom: var(--space-7);
}

.page-title {
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
  color: var(--text);
  letter-spacing: -0.3px;
}

.page-subtitle {
  font-size: var(--text-base);
  color: var(--text-muted);
  margin-top: var(--space-1);
}

.settings-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.setting-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.group-title {
  font-size: var(--text-2xs);
  font-weight: var(--font-semibold);
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--text-muted);
  padding-left: var(--space-1);
  opacity: 0.7;
}

.setting-items {
  background: var(--surface);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  overflow: hidden;
  box-shadow: var(--shadow-xs);
}

.setting-item {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  width: 100%;
  padding: var(--space-4);
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
  left: var(--space-4);
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

.setting-item:hover::before {
  content: '';
  position: absolute;
  left: 0;
  top: 10px;
  bottom: 10px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--lumi-brand);
  opacity: 0.5;
}

.setting-item:focus-visible {
  outline: none;
  background: var(--surface-hover);
  box-shadow: inset 0 0 0 1px var(--focus-ring);
}

.item-info {
  flex: 1;
  min-width: 0;
}

.item-label {
  display: block;
  font-size: var(--text-md);
  font-weight: var(--font-medium);
  color: var(--text);
  margin-bottom: 2px;
}

.item-desc {
  display: block;
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.item-arrow {
  color: var(--text-muted);
  flex-shrink: 0;
  opacity: 0.5;
  transition: transform var(--transition-fast), opacity var(--transition-fast), color var(--transition-fast);
}

.setting-item:hover .item-arrow {
  transform: translateX(2px);
  opacity: 1;
  color: var(--lumi-brand);
}

.settings-footer {
  margin-top: auto;
  padding-top: var(--space-5);
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

.footer-link {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-sm);
  transition: all var(--transition-fast);
  cursor: pointer;
  background: transparent;
  border: none;
}

.footer-link:hover {
  color: var(--lumi-brand);
  background: var(--lumi-brand-light);
}

.footer-link:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px var(--focus-ring);
}

@media (prefers-reduced-motion: reduce) {
  .setting-item,
  .item-arrow,
  .footer-link {
    transition: none;
  }

  .setting-item:hover .item-arrow {
    transform: none;
  }
}
</style>

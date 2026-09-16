<script setup lang="ts">
/**
 * 欢迎向导 - 步骤3：新手指引（功能亮点步进卡）
 *
 * 6 张功能亮点卡（对话 / 皮套工坊 / 群聊协作 / AI 浏览器 / 记忆中枢 / 智能设备）
 * 步进式浏览，最后一卡「开始使用」结束教程（父级记录 onboarding.tutorialDone）。
 * 文案走 welcome.tour.* i18n 命名空间。
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { MessageCircle, Palette, Users, Globe, Brain, Home, ChevronRight, Rocket } from 'lucide-vue-next'
import LumiButton from '../common/LumiButton.vue'
import type { Component } from 'vue'

const emit = defineEmits<{
  finish: []
  prev: []
}>()

const { t } = useI18n()

/** 功能亮点卡（图标 + 主色 + i18n key，按应用实际已有功能编写） */
const tourCards: Array<{ icon: Component; color: string; key: string }> = [
  { icon: MessageCircle, color: 'var(--lumi-brand)', key: 'chat' },
  { icon: Palette, color: 'var(--task-pink)', key: 'avatar' },
  { icon: Users, color: 'var(--lumi-secondary)', key: 'group' },
  { icon: Globe, color: 'var(--lumi-info)', key: 'browser' },
  { icon: Brain, color: 'var(--lumi-accent)', key: 'memory' },
  { icon: Home, color: 'var(--lumi-warning)', key: 'smartHome' }
]

const index = ref(0)
const total = tourCards.length
const isLast = computed(() => index.value === total - 1)

const current = computed(() => tourCards[index.value])

const nextCard = (): void => {
  if (index.value < total - 1) index.value++
}

const finish = (): void => {
  emit('finish')
}
</script>

<template>
  <div class="welcome-step step-tour">
    <div class="step-hero animate-fade-in">
      <div class="step-hero-icon tour-hero-icon">
        <Rocket :size="24" />
      </div>
      <div>
        <h2 class="step-hero-title">{{ t('welcome.tourTitle') }}</h2>
        <p class="step-hero-desc">{{ t('welcome.tourDesc') }}</p>
      </div>
    </div>

    <!-- 当前亮点卡 -->
    <div class="tour-card animate-slide-up">
      <div class="tour-card__icon" :style="{ color: current.color, background: 'var(--surface-hover)' }">
        <component :is="current.icon" :size="30" />
      </div>
      <h3 class="tour-card__title">{{ t(`welcome.tour.${current.key}`) }}</h3>
      <p class="tour-card__desc">{{ t(`welcome.tour.${current.key}Desc`) }}</p>
    </div>

    <!-- 步进点 -->
    <div class="tour-dots">
      <button
        v-for="(c, i) in tourCards"
        :key="c.key"
        :class="['tour-dot', { active: i === index }]"
        @click="index = i"
        :aria-label="t(`welcome.tour.${c.key}`)"
      ></button>
    </div>

    <div class="step-actions animate-fade-in">
      <LumiButton variant="ghost" size="lg" @click="emit('prev')">
        {{ t('welcome.btnBack') }}
      </LumiButton>
      <LumiButton v-if="!isLast" variant="primary" size="lg" block @click="nextCard">
        <span>{{ t('welcome.tourNext') }}</span>
        <ChevronRight :size="16" />
      </LumiButton>
      <LumiButton v-else class="tour-finish-btn" variant="primary" size="lg" block @click="finish">
        <template #icon>
          <Rocket :size="16" />
        </template>
        <span>{{ t('welcome.tourFinish') }}</span>
      </LumiButton>
    </div>
  </div>
</template>

<style scoped>
.welcome-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-6);
}

.step-hero {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  width: 100%;
}

.step-hero-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: var(--shadow-sm);
}

.tour-hero-icon {
  background: var(--lumi-brand-gradient-soft);
  color: var(--lumi-brand);
}

.step-hero-title {
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--text);
}

.step-hero-desc {
  font-size: var(--text-sm);
  color: var(--text-muted);
  margin-top: var(--space-1);
}

/* 亮点卡 */
.tour-card {
  width: 100%;
  min-height: 180px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-6);
  border-radius: var(--radius-xl);
  border: 1px solid var(--border);
  background: var(--surface);
  text-align: center;
  box-shadow: var(--shadow-sm);
}

.tour-card__icon {
  width: 60px;
  height: 60px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
}

.tour-card__title {
  font-size: var(--text-xl);
  font-weight: var(--font-bold);
  color: var(--text);
}

.tour-card__desc {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: var(--leading-relaxed);
  margin: 0;
  max-width: 340px;
}

/* 步进点 */
.tour-dots {
  display: flex;
  gap: var(--space-2);
}

.tour-dot {
  width: var(--space-2);
  height: var(--space-2);
  border-radius: var(--radius-full);
  background: var(--border);
  border: none;
  cursor: pointer;
  transition: all var(--transition-normal);
  padding: 0;
}

.tour-dot.active {
  width: var(--space-6);
  border-radius: var(--radius-xs);
  background: var(--lumi-brand);
}

.step-actions {
  display: flex;
  gap: var(--space-3);
  width: 100%;
  margin-top: var(--space-1);
}

.step-actions .lumi-btn--block {
  flex: 1;
}

.tour-finish-btn {
  background: linear-gradient(135deg, var(--lumi-brand), var(--lumi-brand-soft));
}

button:focus-visible,
.lumi-btn:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px var(--focus-ring);
}
</style>

<script setup lang="ts">
/**
 * 设置 - 语言 / Language 分节
 *
 * 三语言卡片选择，写回 stores/locale.ts（同步 vue-i18n + <html lang> + 双端持久化）。
 * 与欢迎向导 StepLanguage 同一视觉语言（lang-card 样式）。
 */
import { Check, Languages } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import { useLocaleStore } from '../../stores/locale'
import { SUPPORTED_LOCALES } from '../../i18n'
import '../../styles/views/settings-shared.css'

const { t } = useI18n()
const localeStore = useLocaleStore()
</script>

<template>
  <div class="settings-panel language-panel">
    <section class="settings-card">
      <div class="settings-card__header">
        <Languages :size="18" />
        <span class="settings-card__title">{{ t('settings.languageSection') }}</span>
      </div>
      <div class="settings-card__body">
        <div class="lang-options">
          <button
            v-for="item in SUPPORTED_LOCALES"
            :key="item.code"
            :class="['lang-card', { active: localeStore.locale === item.code }]"
            @click="localeStore.setLocale(item.code)"
          >
            <span class="lang-flag">{{ item.flag }}</span>
            <span class="lang-label">{{ item.name }}</span>
            <Check v-if="localeStore.locale === item.code" :size="16" class="lang-check" />
          </button>
        </div>
        <p class="settings-card__hint">{{ t('settings.languageSectionDesc') }}</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.lang-options {
  display: flex;
  gap: var(--space-3);
}

.lang-card {
  flex: 1;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  background: var(--surface);
  cursor: pointer;
  transition: all var(--transition-normal);
  position: relative;
}

.lang-card:hover {
  border-color: var(--lumi-brand-border);
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}

.lang-card.active {
  border-color: var(--lumi-brand);
  background: var(--lumi-brand-light);
  box-shadow: var(--shadow-sm);
}

.lang-flag {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  background: var(--bg-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-md);
  font-weight: var(--font-bold);
  color: var(--text-secondary);
  flex-shrink: 0;
}

.lang-label {
  font-size: var(--text-md);
  font-weight: var(--font-medium);
  color: var(--text);
}

.lang-check {
  margin-left: auto;
  color: var(--lumi-brand);
}

@media (max-width: 560px) {
  .lang-options {
    flex-direction: column;
  }
}
</style>

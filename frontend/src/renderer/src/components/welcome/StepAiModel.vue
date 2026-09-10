<script setup lang="ts">
/**
 * 欢迎向导 - 步骤2：AI 模型供应商配置
 *
 * 从 modelStore 直接读取模板列表（Pinia 单例），表单状态由父级 composable 管理。
 */
import { computed } from 'vue'
import { Cpu, ChevronRight, Check, AlertCircle, Cloud, Monitor, Network } from 'lucide-vue-next'
import LumiButton from '../common/LumiButton.vue'
import LumiInput from '../common/LumiInput.vue'
import LumiEmptyState from '../common/LumiEmptyState.vue'
import { useModelStore } from '../../stores/model'
import type { WelcomeI18nText, TemplateCategory, NewProvider } from '../../composables/useWelcomeWizard'

const props = defineProps<{
  i18n: WelcomeI18nText
  addTemplateCategory: TemplateCategory
  selectedTemplate: string
  aiModelError: string
  aiModelSaving: boolean
  newProvider: NewProvider
  newProviderFormValid: boolean
  testState: 'idle' | 'testing' | 'ok' | 'fail'
  testResultText: string
}>()

const emit = defineEmits<{
  'update:addTemplateCategory': [category: TemplateCategory]
  'select-template': [templateId: string]
  'add-provider-and-next': []
  'test-connection': []
  next: []
  prev: []
}>()

const modelStore = useModelStore()

const templateCategories = computed(() => [
  { id: 'cloud' as const, label: props.i18n.aiModelCategoryCloud, icon: Cloud },
  { id: 'local' as const, label: props.i18n.aiModelCategoryLocal, icon: Monitor },
  { id: 'aggregator' as const, label: props.i18n.aiModelCategoryAggregator, icon: Network },
])

const currentTemplates = computed(() =>
  modelStore.templatesByCategory[props.addTemplateCategory] || []
)
</script>

<template>
  <div class="welcome-step step-ai-model">
    <div class="step-hero animate-fade-in">
      <div class="step-hero-icon ai-hero-icon">
        <Cpu :size="24" />
      </div>
      <div>
        <h2 class="step-hero-title">{{ i18n.aiModelTitle }}</h2>
        <p class="step-hero-desc">{{ i18n.aiModelDesc }}</p>
      </div>
    </div>

    <div class="ai-model-form animate-slide-up">
      <div v-if="aiModelError" class="form-error-banner">
        <AlertCircle :size="14" />
        <span>{{ aiModelError }}</span>
      </div>

      <div class="category-tabs">
        <button
          v-for="cat in templateCategories"
          :key="cat.id"
          :class="['category-tab', { active: addTemplateCategory === cat.id }]"
          @click="emit('update:addTemplateCategory', cat.id)"
        >
          <component :is="cat.icon" :size="14" />
          <span>{{ cat.label }}</span>
        </button>
      </div>

      <div class="template-scroll">
        <LumiEmptyState
          v-if="!currentTemplates.length"
          icon="inbox"
          :title="i18n.aiModelNoProviders"
        />
        <button
          v-for="tmpl in currentTemplates"
          :key="tmpl.id"
          :class="['template-card', { selected: selectedTemplate === tmpl.id }]"
          @click="emit('select-template', tmpl.id)"
        >
          <div class="lumi-icon-wrap lumi-icon-wrap--sm template-card-logo" :style="{ background: tmpl.svgIcon ? undefined : tmpl.color }">
            <span v-if="tmpl.svgIcon" class="template-svg-logo" v-html="tmpl.svgIcon"></span>
            <span v-else class="template-initials">{{ tmpl.initials }}</span>
          </div>
          <div class="template-card-info">
            <span class="template-card-name">{{ tmpl.name }}</span>
            <span class="template-card-desc">{{ tmpl.description }}</span>
          </div>
          <Check v-if="selectedTemplate === tmpl.id" :size="16" class="template-card-check" />
        </button>
      </div>

      <div v-if="selectedTemplate" class="provider-config">
        <div class="form-group">
          <label>{{ i18n.aiModelApiUrl }}</label>
          <LumiInput v-model="newProvider.baseUrl" type="text" placeholder="https://api.openai.com/v1" />
        </div>
        <div class="form-group">
          <label>{{ i18n.aiModelApiKey }}</label>
          <LumiInput v-model="newProvider.apiKey" type="password" placeholder="sk-..." />
        </div>
        <div class="form-group">
          <label>{{ i18n.aiModelDefaultModel }}</label>
          <LumiInput v-model="newProvider.defaultModel" type="text" placeholder="gpt-4o-mini" />
        </div>
        <div class="test-row">
          <LumiButton
            variant="ghost"
            size="md"
            :loading="testState === 'testing'"
            :disabled="!newProvider.baseUrl.trim() || testState === 'testing'"
            @click="$emit('test-connection')"
          >
            {{ testState === 'testing' ? i18n.testTesting : i18n.testBtn }}
          </LumiButton>
          <span
            v-if="testResultText"
            :class="['test-result', { ok: testState === 'ok', fail: testState === 'fail' }]"
          >
            {{ testResultText }}
          </span>
        </div>
      </div>

      <p class="skip-hint">{{ i18n.aiModelSkipHint }}</p>
    </div>

    <div class="step-actions">
      <LumiButton variant="ghost" size="lg" @click="$emit('prev')">
        {{ i18n.btnBack }}
      </LumiButton>
      <LumiButton
        v-if="selectedTemplate && newProviderFormValid"
        variant="primary"
        size="lg"
        block
        :loading="aiModelSaving"
        @click="$emit('add-provider-and-next')"
      >
        <span>{{ aiModelSaving ? i18n.aiModelSaving : i18n.aiModelAdd }}</span>
        <ChevronRight v-if="!aiModelSaving" :size="16" />
      </LumiButton>
      <LumiButton v-else variant="primary" size="lg" block @click="$emit('next')">
        <span>{{ i18n.aiModelNext }}</span>
        <ChevronRight :size="16" />
      </LumiButton>
    </div>
  </div>
</template>

<style scoped>
.welcome-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-7);
}

.step-hero {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  width: 100%;
}

.step-hero-icon {
  width: 52px;
  height: 52px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.ai-hero-icon {
  background: linear-gradient(135deg, var(--task-sky-soft), color-mix(in srgb, var(--task-sky) 4%, transparent));
  color: var(--task-sky);
}

.step-hero-title {
  font-size: var(--text-3xl);
  font-weight: var(--font-bold);
  color: var(--text);
}

.step-hero-desc {
  font-size: var(--text-base);
  color: var(--text-muted);
  margin-top: var(--space-1);
  line-height: var(--leading-normal);
}

.ai-model-form {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.form-error-banner {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background: var(--lumi-danger-light);
  color: var(--lumi-danger);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
}

.category-tabs {
  display: flex;
  gap: var(--space-1);
}

.category-tab {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-full);
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
  background: var(--surface);
  border: 1px solid var(--border);
  transition: all var(--transition-normal);
  cursor: pointer;
}

.category-tab:hover {
  border-color: var(--lumi-brand);
  color: var(--lumi-brand);
}

.category-tab.active {
  background: var(--lumi-brand-light);
  border-color: var(--lumi-brand);
  color: var(--lumi-brand);
  font-weight: var(--font-semibold);
}

.template-scroll {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  max-height: 200px;
  overflow-y: auto;
  padding-right: var(--space-1);
}

.template-card {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  background: var(--surface);
  border: 1px solid var(--border);
  transition: all var(--transition-normal);
  cursor: pointer;
  text-align: left;
  width: 100%;
}

.template-card:hover {
  border-color: var(--lumi-brand-border);
  box-shadow: var(--shadow-sm);
}

.template-card.selected {
  border-color: var(--lumi-brand);
  background: var(--lumi-brand-light);
}

.template-card-logo {
  flex-shrink: 0;
}

.template-initials {
  font-size: var(--text-2xs);
  font-weight: var(--font-bold);
  color: var(--text-inverse);
  letter-spacing: 0.5px;
}

.template-svg-logo {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
}

.template-svg-logo :deep(svg) {
  width: 20px;
  height: 20px;
}

.template-card-info {
  display: flex;
  flex-direction: column;
  gap: calc(var(--space-1) / 4);
  flex: 1;
  min-width: 0;
}

.template-card-name {
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--text);
}

.template-card-desc {
  font-size: var(--text-xs);
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.template-card-check {
  color: var(--lumi-brand);
  flex-shrink: 0;
}

.provider-config {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-3);
  border-radius: var(--radius-lg);
  background: var(--surface);
  border: 1px solid var(--border);
}

.provider-config .form-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.provider-config .form-group label {
  font-size: var(--text-xs);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
}

.test-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.test-result {
  font-size: var(--text-xs);
  line-height: 1.5;
  min-width: 0;
}

.test-result.ok {
  color: var(--lumi-success);
}

.test-result.fail {
  color: var(--lumi-danger);
}

.skip-hint {
  font-size: var(--text-xs);
  color: var(--text-muted);
  text-align: center;
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

.step-actions .lumi-btn-text > svg {
  margin-left: var(--space-1);
}

button:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px var(--focus-ring);
}
</style>

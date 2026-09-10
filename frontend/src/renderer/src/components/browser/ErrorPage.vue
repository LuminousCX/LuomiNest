<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { WifiOff, ShieldAlert, SearchX, Globe, ServerCrash, LockKeyhole, RefreshCw } from 'lucide-vue-next'
import LumiButton from '../common/LumiButton.vue'

const props = defineProps<{
  code: number
  title?: string
  message?: string
  url?: string
}>()

const emit = defineEmits<{
  retry: []
  newTab: []
}>()

const { t } = useI18n()

const errorConfig = computed(() => {
  const c = props.code
  if (c === -2 || c === -105) return { icon: Globe, heading: t('browser.error.notFound'), suggestion: t('browser.error.notFoundHint') }
  if (c === -3) return { icon: WifiOff, heading: t('browser.error.cannotReach'), suggestion: t('browser.error.cannotReachHint') }
  if (c === -7 || c === -118) return { icon: WifiOff, heading: t('browser.error.timeout'), suggestion: t('browser.error.timeoutHint') }
  if (c === -21) return { icon: ShieldAlert, heading: t('browser.error.denied'), suggestion: t('browser.error.deniedHint') }
  if (c === -100 || c === -324) return { icon: ServerCrash, heading: t('browser.error.reset'), suggestion: t('browser.error.resetHint') }
  if (c === -101) return { icon: ServerCrash, heading: t('browser.error.refused'), suggestion: t('browser.error.refusedHint') }
  if (c === -102 || c === -106) return { icon: WifiOff, heading: t('browser.error.noInternet'), suggestion: t('browser.error.noInternetHint') }
  if (c === -200) return { icon: LockKeyhole, heading: t('browser.error.notPrivate'), suggestion: t('browser.error.notPrivateHint') }
  if (c === -300) return { icon: SearchX, heading: t('browser.error.invalidUrl'), suggestion: t('browser.error.invalidUrlHint') }
  if (c === -502) return { icon: ServerCrash, heading: t('browser.error.server502'), suggestion: t('browser.error.server502Hint') }
  if (c === -503) return { icon: ServerCrash, heading: t('browser.error.server503'), suggestion: t('browser.error.server503Hint') }
  if (c === -504) return { icon: ServerCrash, heading: t('browser.error.server504'), suggestion: t('browser.error.server504Hint') }
  return { icon: SearchX, heading: t('browser.error.cannotReach'), suggestion: t('browser.error.defaultHint') }
})

const displayHeading = computed(() => props.title || errorConfig.value.heading)
const displayMessage = computed(() => props.message || errorConfig.value.suggestion)
const displayUrl = computed(() => {
  if (props.url) {
    try {
      const u = new URL(props.url)
      return u.hostname
    } catch {
      return props.url
    }
  }
  return ''
})
</script>

<template>
  <div class="error-page">
    <div class="error-content">
      <component :is="errorConfig.icon" :size="48" class="error-icon" />
      
      <h1 class="error-heading">{{ displayHeading }}</h1>
      
      <div v-if="displayUrl" class="error-url">
        <span>{{ displayUrl }}</span> {{ t('browser.error.refusedSuffix') }}
      </div>
      
      <p class="error-suggestion">{{ displayMessage }}</p>
      
      <div class="error-details">
        <details>
          <summary>{{ t('browser.error.details') }}</summary>
          <div class="details-content">
            <p>{{ t('browser.error.code', { n: Math.abs(code) }) }}</p>
            <p v-if="url">{{ t('browser.error.requestUrl', { url }) }}</p>
          </div>
        </details>
      </div>

      <div class="error-actions">
        <LumiButton variant="primary" @click="emit('retry')">
          <template #icon>
            <RefreshCw :size="16" />
          </template>
          {{ t('browser.error.reload') }}
        </LumiButton>
      </div>

      <div class="error-suggestions">
        <h3>{{ t('browser.error.tryTitle') }}</h3>
        <ul>
          <li>{{ t('browser.error.checkNetwork') }}</li>
          <li>{{ t('browser.error.checkProxy') }}</li>
          <li>{{ t('browser.error.checkUrl') }}</li>
          <li>
            <button class="btn-link" @click="emit('newTab')">{{ t('browser.error.newTab') }}</button>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<style scoped>
.error-page {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  padding: var(--space-10) var(--space-8) var(--space-8);
  background: var(--surface);
  font-family: var(--font-sans);
  overflow-y: auto;
}

.error-content {
  max-width: 480px;
  width: 100%;
}

.error-icon {
  color: var(--text-muted);
  margin-bottom: var(--space-6);
}

.error-heading {
  font-size: var(--text-2xl);
  font-weight: var(--font-normal);
  color: var(--text);
  margin: 0 0 var(--space-3);
  line-height: var(--leading-snug);
}

.error-url {
  font-size: var(--text-md);
  color: var(--text-muted);
  margin: 0 0 var(--space-4);
  line-height: var(--leading-normal);
}

.error-url span {
  color: var(--text);
  font-weight: var(--font-medium);
}

.error-suggestion {
  font-size: var(--text-md);
  color: var(--text-muted);
  margin: 0 0 var(--space-5);
  line-height: var(--leading-normal);
}

.error-details {
  margin-bottom: var(--space-6);
}

.error-details details {
  font-size: var(--text-base);
}

.error-details summary {
  color: var(--lumi-brand);
  cursor: pointer;
  font-size: var(--text-md);
  padding: var(--space-1) 0;
  user-select: none;
  list-style: none;
}

.error-details summary::-webkit-details-marker {
  display: none;
}

.error-details summary::before {
  content: '▶';
  display: inline-block;
  font-size: var(--text-2xs);
  margin-right: var(--space-2);
  transition: transform var(--transition-fast);
}

.error-details details[open] summary::before {
  transform: rotate(90deg);
}

.details-content {
  padding: var(--space-3) 0 0 var(--space-5);
  color: var(--text-muted);
  font-size: var(--text-base);
  line-height: var(--leading-relaxed);
}

.details-content p {
  margin: 0;
}

.error-actions {
  margin-bottom: var(--space-7);
}

.error-suggestions {
  border-top: 1px solid var(--border);
  padding-top: var(--space-5);
}

.error-suggestions h3 {
  font-size: var(--text-md);
  font-weight: var(--font-medium);
  color: var(--text);
  margin: 0 0 var(--space-3);
}

.error-suggestions ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.error-suggestions li {
  font-size: var(--text-md);
  color: var(--text-muted);
  padding: var(--space-1) 0;
  padding-left: var(--space-4);
  position: relative;
  line-height: 1.6;
}

.error-suggestions li::before {
  content: '•';
  position: absolute;
  left: 0;
  color: var(--text-muted);
}

.btn-link {
  background: none;
  border: none;
  color: var(--lumi-brand);
  font-size: var(--text-md);
  cursor: pointer;
  padding: 0;
  text-decoration: underline;
}

.btn-link:hover {
  color: var(--lumi-brand-hover);
}

</style>

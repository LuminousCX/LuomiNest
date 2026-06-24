<script setup lang="ts">
import { computed } from 'vue'
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

const errorConfig = computed(() => {
  const c = props.code
  if (c === -2 || c === -105) return { icon: Globe, heading: '找不到网址', suggestion: '请检查网址是否有拼写错误。' }
  if (c === -3) return { icon: WifiOff, heading: '无法访问此网站', suggestion: '请检查您的网络连接。' }
  if (c === -7 || c === -118) return { icon: WifiOff, heading: '连接超时', suggestion: '服务器响应时间过长，请稍后重试。' }
  if (c === -21) return { icon: ShieldAlert, heading: '访问被拒绝', suggestion: '您没有权限访问此页面。' }
  if (c === -100 || c === -324) return { icon: ServerCrash, heading: '连接被重置', suggestion: '连接被服务器重置，请稍后重试。' }
  if (c === -101) return { icon: ServerCrash, heading: '连接被拒绝', suggestion: '服务器拒绝了连接请求。' }
  if (c === -102 || c === -106) return { icon: WifiOff, heading: '无法连接到互联网', suggestion: '请检查您的网络设置，包括防火墙和代理配置。' }
  if (c === -200) return { icon: LockKeyhole, heading: '您的连接不是私密连接', suggestion: '攻击者可能正试图窃取您的信息。建议不要继续访问此网站。' }
  if (c === -300) return { icon: SearchX, heading: '网址无效', suggestion: '输入的网址格式不正确，请检查后重试。' }
  if (c === -502) return { icon: ServerCrash, heading: '服务器错误 (502)', suggestion: '服务器作为网关或代理时收到了无效响应。' }
  if (c === -503) return { icon: ServerCrash, heading: '服务器错误 (503)', suggestion: '服务器暂时无法处理请求，请稍后重试。' }
  if (c === -504) return { icon: ServerCrash, heading: '服务器错误 (504)', suggestion: '网关服务器响应超时。' }
  return { icon: SearchX, heading: '无法访问此网站', suggestion: '页面加载失败。' }
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
        <span>{{ displayUrl }}</span> 拒绝了连接。
      </div>
      
      <p class="error-suggestion">{{ displayMessage }}</p>
      
      <div class="error-details">
        <details>
          <summary>详细信息</summary>
          <div class="details-content">
            <p>错误代码: ERR_{{ Math.abs(code) }}</p>
            <p v-if="url">请求 URL: {{ url }}</p>
          </div>
        </details>
      </div>

      <div class="error-actions">
        <LumiButton variant="primary" @click="emit('retry')">
          <template #icon>
            <RefreshCw :size="16" />
          </template>
          重新加载
        </LumiButton>
      </div>

      <div class="error-suggestions">
        <h3>请尝试以下办法：</h3>
        <ul>
          <li>检查网络连接</li>
          <li>检查代理服务器和防火墙</li>
          <li>检查网址是否正确</li>
          <li>
            <button class="btn-link" @click="emit('newTab')">打开新标签页</button>
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
  line-height: 1.4;
}

.error-url {
  font-size: var(--text-md);
  color: var(--text-muted);
  margin: 0 0 var(--space-4);
  line-height: 1.5;
}

.error-url span {
  color: var(--text);
  font-weight: var(--font-medium);
}

.error-suggestion {
  font-size: var(--text-md);
  color: var(--text-muted);
  margin: 0 0 var(--space-5);
  line-height: 1.5;
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
  line-height: 1.8;
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

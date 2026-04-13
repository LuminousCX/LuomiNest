<script setup lang="ts">
import { computed } from 'vue'
import { WifiOff, ShieldAlert, SearchX, Globe, ServerCrash, LockKeyhole, RefreshCw } from 'lucide-vue-next'

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
        <button class="btn-reload" @click="emit('retry')">
          <RefreshCw :size="16" />
          <span>重新加载</span>
        </button>
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
  padding: 80px 40px 40px;
  background: #ffffff;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  overflow-y: auto;
}

.error-content {
  max-width: 480px;
  width: 100%;
}

.error-icon {
  color: #5f6368;
  margin-bottom: 24px;
}

.error-heading {
  font-size: 20px;
  font-weight: 400;
  color: #202124;
  margin: 0 0 12px;
  line-height: 1.4;
}

.error-url {
  font-size: 14px;
  color: #5f6368;
  margin: 0 0 16px;
  line-height: 1.5;
}

.error-url span {
  color: #202124;
  font-weight: 500;
}

.error-suggestion {
  font-size: 14px;
  color: #5f6368;
  margin: 0 0 20px;
  line-height: 1.5;
}

.error-details {
  margin-bottom: 24px;
}

.error-details details {
  font-size: 13px;
}

.error-details summary {
  color: #1a73e8;
  cursor: pointer;
  font-size: 14px;
  padding: 4px 0;
  user-select: none;
  list-style: none;
}

.error-details summary::-webkit-details-marker {
  display: none;
}

.error-details summary::before {
  content: '▶';
  display: inline-block;
  font-size: 10px;
  margin-right: 8px;
  transition: transform 0.2s ease;
}

.error-details details[open] summary::before {
  transform: rotate(90deg);
}

.details-content {
  padding: 12px 0 0 18px;
  color: #5f6368;
  font-size: 13px;
  line-height: 1.8;
}

.details-content p {
  margin: 0;
}

.error-actions {
  margin-bottom: 32px;
}

.btn-reload {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 24px;
  background: #1a73e8;
  color: #ffffff;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s ease;
}

.btn-reload:hover {
  background: #1765cc;
}

.btn-reload:active {
  background: #1558b0;
}

.error-suggestions {
  border-top: 1px solid #e0e0e0;
  padding-top: 20px;
}

.error-suggestions h3 {
  font-size: 14px;
  font-weight: 500;
  color: #202124;
  margin: 0 0 12px;
}

.error-suggestions ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.error-suggestions li {
  font-size: 14px;
  color: #5f6368;
  padding: 4px 0;
  padding-left: 16px;
  position: relative;
  line-height: 1.6;
}

.error-suggestions li::before {
  content: '•';
  position: absolute;
  left: 0;
  color: #5f6368;
}

.btn-link {
  background: none;
  border: none;
  color: #1a73e8;
  font-size: 14px;
  cursor: pointer;
  padding: 0;
  text-decoration: underline;
}

.btn-link:hover {
  color: #1765cc;
}
</style>

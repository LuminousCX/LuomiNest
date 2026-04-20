<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowLeft,
  Cloud,
  Cpu,
  Gauge,
  Atom,
  Camera,
  Pencil,
  Mic,
  Volume2,
  Plus,
  ChevronRight,
  Copy,
  Key,
  Search,
  Trash2,
  Eye,
  EyeOff,
  Bot
} from 'lucide-vue-next'

const router = useRouter()

const activeTile = ref('service')

const modelTiles = [
  { id: 'service', label: '模型服务', icon: Cloud },
  { id: 'main', label: '主模型', icon: Cpu },
  { id: 'fast', label: '快速模型', icon: Gauge },
  { id: 'reasoner', label: '推理模型', icon: Atom },
  { id: 'vision', label: '视觉模型', icon: Camera },
  { id: 'text2img', label: '文生图', icon: Pencil },
  { id: 'asr', label: '语音识别', icon: Mic },
  { id: 'tts', label: '语音合成', icon: Volume2 }
]

const providers = ref([
  {
    id: 1,
    vendor: 'OpenAI',
    url: 'https://api.openai.com/v1',
    apiKey: 'sk-****...****',
    modelId: 'gpt-4o',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'o1', 'o1-mini', 'o3-mini']
  },
  {
    id: 2,
    vendor: 'DeepSeek',
    url: 'https://api.deepseek.com/v1',
    apiKey: 'sk-****...****',
    modelId: 'deepseek-chat',
    models: ['deepseek-chat', 'deepseek-reasoner']
  }
])

const showApiKey = ref<Record<number, boolean>>({})

const toggleApiKeyVisibility = (id: number) => {
  showApiKey.value[id] = !showApiKey.value[id]
}

const mainModelConfig = ref({
  selectedProvider: 'OpenAI',
  model: 'gpt-4o',
  temperature: 0.7,
  topP: 0.9,
  maxTokens: 4096,
  maxRounds: 20,
  reasoningEffort: 'medium'
})

const fastModelConfig = ref({
  selectedProvider: 'DeepSeek',
  model: 'deepseek-chat',
  temperature: 0.5,
  topP: 0.9,
  maxTokens: 2048
})

const reasonerModelConfig = ref({
  selectedProvider: 'DeepSeek',
  model: 'deepseek-reasoner',
  temperature: 0.3,
  maxTokens: 8192,
  stopWords: ''
})

const visionModelConfig = ref({
  selectedProvider: 'OpenAI',
  model: 'gpt-4o',
  temperature: 0.5,
  enableDesktopVision: false,
  wakeWord: ''
})

const currentTileLabel = computed(() => {
  const tile = modelTiles.find(t => t.id === activeTile.value)
  return tile?.label ?? ''
})
</script>

<template>
  <div class="ai-model-settings">
    <div class="settings-detail-header animate-fade-in">
      <button class="back-btn" @click="router.push('/settings')">
        <ArrowLeft :size="18" />
      </button>
      <div class="header-icon">
        <Cpu :size="24" />
      </div>
      <div>
        <h1 class="page-title">AI 模型</h1>
        <p class="page-subtitle">配置大语言模型推理引擎与参数</p>
      </div>
    </div>

    <div class="settings-detail-body">
      <div class="detail-sidebar animate-slide-up">
        <nav class="tile-nav">
          <button
            v-for="tile in modelTiles"
            :key="tile.id"
            :class="['tile-item', { active: activeTile === tile.id }]"
            @click="activeTile = tile.id"
          >
            <component :is="tile.icon" :size="18" />
            <span>{{ tile.label }}</span>
          </button>
        </nav>
      </div>

      <div class="detail-content animate-slide-up" :style="{ animationDelay: '100ms' }">
        <!-- 模型服务 -->
        <div v-if="activeTile === 'service'" class="content-section">
          <div class="section-banner">
            <div class="banner-accent">MODELS</div>
            <div class="banner-body">
              <div class="banner-icon-box">
                <Bot :size="24" />
              </div>
              <div class="banner-text">
                <h3>模型服务配置</h3>
                <p>
                  1. 所有配置均保存在本地，不会上传至任何服务器<br>
                  2. 添加供应商后，输入 API Key 即可获取可用模型列表<br>
                  3. 支持所有兼容 OpenAI API 格式的供应商
                </p>
              </div>
            </div>
          </div>

          <div class="provider-grid">
            <div
              v-for="provider in providers"
              :key="provider.id"
              class="provider-card"
            >
              <div class="card-header">
                <div class="vendor-badge">
                  <Bot :size="18" />
                  <span class="vendor-name">{{ provider.vendor }}</span>
                </div>
                <div class="card-actions">
                  <button class="action-btn" title="复制配置">
                    <Copy :size="14" />
                  </button>
                  <button class="action-btn" title="获取 API Key">
                    <Key :size="14" />
                  </button>
                  <button class="action-btn" title="获取模型列表">
                    <Search :size="14" />
                  </button>
                  <button class="action-btn danger" title="删除">
                    <Trash2 :size="14" />
                  </button>
                </div>
              </div>

              <div class="card-fields">
                <div class="field-item">
                  <label>API 地址</label>
                  <div class="field-input-wrap">
                    <input type="text" :value="provider.url" class="field-input" readonly />
                    <button class="field-action" title="复制">
                      <Copy :size="13" />
                    </button>
                  </div>
                </div>
                <div class="field-item">
                  <label>API Key</label>
                  <div class="field-input-wrap">
                    <input
                      :type="showApiKey[provider.id] ? 'text' : 'password'"
                      :value="provider.apiKey"
                      class="field-input"
                      readonly
                    />
                    <button
                      class="field-action"
                      title="显示/隐藏"
                      @click="toggleApiKeyVisibility(provider.id)"
                    >
                      <Eye v-if="!showApiKey[provider.id]" :size="13" />
                      <EyeOff v-else :size="13" />
                    </button>
                  </div>
                </div>
                <div class="field-item">
                  <label>模型 ID</label>
                  <div class="field-input-wrap">
                    <input type="text" :value="provider.modelId" class="field-input" readonly />
                    <ChevronRight :size="14" class="field-select-icon" />
                  </div>
                </div>
              </div>
            </div>

            <button class="provider-card add-card">
              <Plus :size="32" />
              <span>添加供应商</span>
            </button>
          </div>
        </div>

        <!-- 主模型 -->
        <div v-if="activeTile === 'main'" class="content-section">
          <div class="section-banner">
            <div class="banner-accent">MAIN</div>
            <div class="banner-body">
              <div class="banner-icon-box">
                <Cpu :size="24" />
              </div>
              <div class="banner-text">
                <h3>主模型配置</h3>
                <p>主模型用于日常对话与复杂任务处理，首次使用请先前往模型服务添加供应商</p>
              </div>
            </div>
          </div>

          <div class="config-form">
            <div class="form-group">
              <label class="form-label">供应商</label>
              <div class="form-select-wrap">
                <select v-model="mainModelConfig.selectedProvider" class="form-select">
                  <option value="OpenAI">OpenAI</option>
                  <option value="DeepSeek">DeepSeek</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">模型</label>
              <div class="form-select-wrap">
                <select v-model="mainModelConfig.model" class="form-select">
                  <option value="gpt-4o">gpt-4o</option>
                  <option value="gpt-4o-mini">gpt-4o-mini</option>
                  <option value="deepseek-chat">deepseek-chat</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
            </div>

            <div class="form-group">
              <div class="form-label-row">
                <label class="form-label">Temperature</label>
                <span class="form-value">{{ mainModelConfig.temperature }}</span>
              </div>
              <input
                type="range"
                v-model.number="mainModelConfig.temperature"
                min="0"
                max="2"
                step="0.1"
                class="form-slider"
              />
              <div class="slider-labels">
                <span>精确</span>
                <span>创意</span>
              </div>
            </div>

            <div class="form-group">
              <div class="form-label-row">
                <label class="form-label">Top P</label>
                <span class="form-value">{{ mainModelConfig.topP }}</span>
              </div>
              <input
                type="range"
                v-model.number="mainModelConfig.topP"
                min="0"
                max="1"
                step="0.05"
                class="form-slider"
              />
            </div>

            <div class="form-group">
              <div class="form-label-row">
                <label class="form-label">Max Tokens</label>
                <span class="form-value">{{ mainModelConfig.maxTokens }}</span>
              </div>
              <input
                type="range"
                v-model.number="mainModelConfig.maxTokens"
                min="256"
                max="16384"
                step="256"
                class="form-slider"
              />
            </div>

            <div class="form-group">
              <div class="form-label-row">
                <label class="form-label">最大对话轮数</label>
                <span class="form-value">{{ mainModelConfig.maxRounds }}</span>
              </div>
              <input
                type="range"
                v-model.number="mainModelConfig.maxRounds"
                min="5"
                max="50"
                step="5"
                class="form-slider"
              />
            </div>

            <div class="form-group">
              <label class="form-label">推理强度</label>
              <div class="form-select-wrap">
                <select v-model="mainModelConfig.reasoningEffort" class="form-select">
                  <option value="low">低</option>
                  <option value="medium">中</option>
                  <option value="high">高</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
            </div>
          </div>
        </div>

        <!-- 快速模型 -->
        <div v-if="activeTile === 'fast'" class="content-section">
          <div class="section-banner">
            <div class="banner-accent">FAST</div>
            <div class="banner-body">
              <div class="banner-icon-box">
                <Gauge :size="24" />
              </div>
              <div class="banner-text">
                <h3>快速模型配置</h3>
                <p>快速模型用于简单问答、分类判断等低延迟场景，优先选择响应速度快的轻量模型</p>
              </div>
            </div>
          </div>

          <div class="config-form">
            <div class="form-group">
              <label class="form-label">供应商</label>
              <div class="form-select-wrap">
                <select v-model="fastModelConfig.selectedProvider" class="form-select">
                  <option value="OpenAI">OpenAI</option>
                  <option value="DeepSeek">DeepSeek</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">模型</label>
              <div class="form-select-wrap">
                <select v-model="fastModelConfig.model" class="form-select">
                  <option value="gpt-4o-mini">gpt-4o-mini</option>
                  <option value="deepseek-chat">deepseek-chat</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
            </div>
            <div class="form-group">
              <div class="form-label-row">
                <label class="form-label">Temperature</label>
                <span class="form-value">{{ fastModelConfig.temperature }}</span>
              </div>
              <input
                type="range"
                v-model.number="fastModelConfig.temperature"
                min="0"
                max="2"
                step="0.1"
                class="form-slider"
              />
            </div>
            <div class="form-group">
              <div class="form-label-row">
                <label class="form-label">Max Tokens</label>
                <span class="form-value">{{ fastModelConfig.maxTokens }}</span>
              </div>
              <input
                type="range"
                v-model.number="fastModelConfig.maxTokens"
                min="256"
                max="8192"
                step="256"
                class="form-slider"
              />
            </div>
          </div>
        </div>

        <!-- 推理模型 -->
        <div v-if="activeTile === 'reasoner'" class="content-section">
          <div class="section-banner">
            <div class="banner-accent">REASONER</div>
            <div class="banner-body">
              <div class="banner-icon-box">
                <Atom :size="24" />
              </div>
              <div class="banner-text">
                <h3>推理模型配置</h3>
                <p>推理模型用于复杂逻辑推理、数学计算、代码分析等需要深度思考的场景</p>
              </div>
            </div>
          </div>

          <div class="config-form">
            <div class="form-group">
              <label class="form-label">供应商</label>
              <div class="form-select-wrap">
                <select v-model="reasonerModelConfig.selectedProvider" class="form-select">
                  <option value="DeepSeek">DeepSeek</option>
                  <option value="OpenAI">OpenAI</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">模型</label>
              <div class="form-select-wrap">
                <select v-model="reasonerModelConfig.model" class="form-select">
                  <option value="deepseek-reasoner">deepseek-reasoner</option>
                  <option value="o1">o1</option>
                  <option value="o3-mini">o3-mini</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
            </div>
            <div class="form-group">
              <div class="form-label-row">
                <label class="form-label">Temperature</label>
                <span class="form-value">{{ reasonerModelConfig.temperature }}</span>
              </div>
              <input
                type="range"
                v-model.number="reasonerModelConfig.temperature"
                min="0"
                max="2"
                step="0.1"
                class="form-slider"
              />
            </div>
            <div class="form-group">
              <div class="form-label-row">
                <label class="form-label">Max Tokens</label>
                <span class="form-value">{{ reasonerModelConfig.maxTokens }}</span>
              </div>
              <input
                type="range"
                v-model.number="reasonerModelConfig.maxTokens"
                min="1024"
                max="32768"
                step="1024"
                class="form-slider"
              />
            </div>
            <div class="form-group">
              <label class="form-label">停止词</label>
              <input
                type="text"
                v-model="reasonerModelConfig.stopWords"
                class="form-input"
                placeholder="用逗号分隔多个停止词"
              />
            </div>
          </div>
        </div>

        <!-- 视觉模型 -->
        <div v-if="activeTile === 'vision'" class="content-section">
          <div class="section-banner">
            <div class="banner-accent">VISION</div>
            <div class="banner-body">
              <div class="banner-icon-box">
                <Camera :size="24" />
              </div>
              <div class="banner-text">
                <h3>视觉模型配置</h3>
                <p>视觉模型用于图像理解、屏幕截图分析等需要多模态能力的场景</p>
              </div>
            </div>
          </div>

          <div class="config-form">
            <div class="form-group">
              <label class="form-label">供应商</label>
              <div class="form-select-wrap">
                <select v-model="visionModelConfig.selectedProvider" class="form-select">
                  <option value="OpenAI">OpenAI</option>
                  <option value="DeepSeek">DeepSeek</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">模型</label>
              <div class="form-select-wrap">
                <select v-model="visionModelConfig.model" class="form-select">
                  <option value="gpt-4o">gpt-4o</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
            </div>
            <div class="form-group">
              <div class="form-label-row">
                <label class="form-label">Temperature</label>
                <span class="form-value">{{ visionModelConfig.temperature }}</span>
              </div>
              <input
                type="range"
                v-model.number="visionModelConfig.temperature"
                min="0"
                max="2"
                step="0.1"
                class="form-slider"
              />
            </div>
            <div class="form-group">
              <div class="toggle-row">
                <label class="form-label">桌面视觉</label>
                <button
                  :class="['toggle-switch', { active: visionModelConfig.enableDesktopVision }]"
                  @click="visionModelConfig.enableDesktopVision = !visionModelConfig.enableDesktopVision"
                >
                  <span class="toggle-thumb" />
                </button>
              </div>
              <p class="form-hint">启用后 Agent 可截取屏幕内容进行分析</p>
            </div>
            <div class="form-group">
              <label class="form-label">唤醒词</label>
              <input
                type="text"
                v-model="visionModelConfig.wakeWord"
                class="form-input"
                placeholder="输入唤醒词触发视觉分析"
              />
            </div>
          </div>
        </div>

        <!-- 文生图 -->
        <div v-if="activeTile === 'text2img'" class="content-section">
          <div class="section-banner">
            <div class="banner-accent">IMAGE</div>
            <div class="banner-body">
              <div class="banner-icon-box">
                <Pencil :size="24" />
              </div>
              <div class="banner-text">
                <h3>文生图模型配置</h3>
                <p>配置图像生成模型，支持 DALL-E、Stable Diffusion 等文生图服务</p>
              </div>
            </div>
          </div>

          <div class="config-form">
            <div class="form-group">
              <label class="form-label">供应商</label>
              <div class="form-select-wrap">
                <select class="form-select">
                  <option value="openai">OpenAI (DALL-E)</option>
                  <option value="stability">Stability AI</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">模型</label>
              <div class="form-select-wrap">
                <select class="form-select">
                  <option value="dall-e-3">dall-e-3</option>
                  <option value="stable-diffusion-xl">stable-diffusion-xl</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">默认尺寸</label>
              <div class="form-select-wrap">
                <select class="form-select">
                  <option value="1024x1024">1024 x 1024</option>
                  <option value="1792x1024">1792 x 1024</option>
                  <option value="1024x1792">1024 x 1792</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">默认质量</label>
              <div class="form-select-wrap">
                <select class="form-select">
                  <option value="standard">标准</option>
                  <option value="hd">高清</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
            </div>
          </div>
        </div>

        <!-- 语音识别 -->
        <div v-if="activeTile === 'asr'" class="content-section">
          <div class="section-banner">
            <div class="banner-accent">ASR</div>
            <div class="banner-body">
              <div class="banner-icon-box">
                <Mic :size="24" />
              </div>
              <div class="banner-text">
                <h3>语音识别模型配置</h3>
                <p>配置语音转文字服务，支持 Whisper 等语音识别模型</p>
              </div>
            </div>
          </div>

          <div class="config-form">
            <div class="form-group">
              <label class="form-label">供应商</label>
              <div class="form-select-wrap">
                <select class="form-select">
                  <option value="openai">OpenAI</option>
                  <option value="azure">Azure Speech</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">模型</label>
              <div class="form-select-wrap">
                <select class="form-select">
                  <option value="whisper-1">whisper-1</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">默认语言</label>
              <div class="form-select-wrap">
                <select class="form-select">
                  <option value="zh">中文</option>
                  <option value="en">English</option>
                  <option value="ja">日本語</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
            </div>
          </div>
        </div>

        <!-- 语音合成 -->
        <div v-if="activeTile === 'tts'" class="content-section">
          <div class="section-banner">
            <div class="banner-accent">TTS</div>
            <div class="banner-body">
              <div class="banner-icon-box">
                <Volume2 :size="24" />
              </div>
              <div class="banner-text">
                <h3>语音合成模型配置</h3>
                <p>配置文字转语音服务，为 Agent 赋予语音输出能力</p>
              </div>
            </div>
          </div>

          <div class="config-form">
            <div class="form-group">
              <label class="form-label">供应商</label>
              <div class="form-select-wrap">
                <select class="form-select">
                  <option value="openai">OpenAI</option>
                  <option value="azure">Azure TTS</option>
                  <option value="edge">Edge TTS</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">模型</label>
              <div class="form-select-wrap">
                <select class="form-select">
                  <option value="tts-1">tts-1</option>
                  <option value="tts-1-hd">tts-1-hd</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">默认语音</label>
              <div class="form-select-wrap">
                <select class="form-select">
                  <option value="alloy">Alloy</option>
                  <option value="echo">Echo</option>
                  <option value="fable">Fable</option>
                  <option value="onyx">Onyx</option>
                  <option value="nova">Nova</option>
                  <option value="shimmer">Shimmer</option>
                </select>
                <ChevronRight :size="14" class="select-icon" />
              </div>
            </div>
            <div class="form-group">
              <div class="form-label-row">
                <label class="form-label">语速</label>
                <span class="form-value">1.0x</span>
              </div>
              <input type="range" min="0.5" max="2" step="0.1" value="1" class="form-slider" />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ai-model-settings {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--workspace-bg);
  overflow: hidden;
}

.settings-detail-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 28px;
  border-bottom: 1px solid var(--workspace-border);
  flex-shrink: 0;
}

.back-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.back-btn:hover {
  background: var(--workspace-hover);
  color: var(--lumi-primary);
}

.header-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, rgba(13, 148, 136, 0.1), rgba(20, 184, 166, 0.1));
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--lumi-primary);
}

.page-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}

.page-subtitle {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 1px;
}

.settings-detail-body {
  display: flex;
  flex: 1;
  overflow: hidden;
  min-height: 0;
}

.detail-sidebar {
  width: 180px;
  flex-shrink: 0;
  border-right: 1px solid var(--workspace-border);
  padding: 16px 12px;
  overflow-y: auto;
}

.tile-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tile-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  text-align: left;
  transition: all var(--transition-fast);
}

.tile-item:hover {
  background: var(--workspace-hover);
  color: var(--text-primary);
}

.tile-item.active {
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
}

.detail-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px 28px;
  min-width: 0;
}

.content-section {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.section-banner {
  display: flex;
  border-radius: var(--radius-lg);
  overflow: hidden;
  background: linear-gradient(135deg, var(--lumi-primary), #14b8a6);
  color: white;
  min-height: 100px;
}

.banner-accent {
  width: 48px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  writing-mode: vertical-rl;
  text-orientation: mixed;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
  background: rgba(0, 0, 0, 0.15);
  padding: 12px 0;
}

.banner-body {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 24px;
  flex: 1;
}

.banner-icon-box {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.banner-text h3 {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 4px;
}

.banner-text p {
  font-size: 12px;
  opacity: 0.9;
  line-height: 1.6;
}

.provider-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.provider-card {
  background: var(--workspace-card);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-lg);
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  transition: all var(--transition-fast);
}

.provider-card:hover {
  border-color: var(--lumi-primary);
  box-shadow: 0 2px 12px var(--lumi-primary-glow);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.vendor-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  font-size: 13px;
  font-weight: 600;
}

.card-actions {
  display: flex;
  gap: 4px;
}

.action-btn {
  width: 30px;
  height: 30px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.action-btn:hover {
  background: var(--workspace-hover);
  color: var(--text-secondary);
}

.action-btn.danger:hover {
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
}

.card-fields {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.field-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.field-item label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.field-input-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-sm);
  padding: 0 10px;
  transition: all var(--transition-fast);
}

.field-input-wrap:focus-within {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

.field-input {
  flex: 1;
  padding: 8px 0;
  font-size: 13px;
  color: var(--text-primary);
  background: transparent;
}

.field-action {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.field-action:hover {
  background: var(--workspace-hover);
  color: var(--lumi-primary);
}

.field-select-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.add-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 200px;
  border: 2px dashed var(--workspace-border);
  border-radius: var(--radius-lg);
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 500;
  transition: all var(--transition-fast);
}

.add-card:hover {
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
  background: var(--lumi-primary-light);
}

.config-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 560px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.form-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.form-value {
  font-size: 13px;
  font-weight: 600;
  color: var(--lumi-primary);
  font-variant-numeric: tabular-nums;
}

.form-select-wrap {
  position: relative;
  display: flex;
  align-items: center;
}

.form-select {
  width: 100%;
  padding: 10px 36px 10px 14px;
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-primary);
  cursor: pointer;
  appearance: none;
  transition: all var(--transition-fast);
}

.form-select:focus {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

.select-icon {
  position: absolute;
  right: 12px;
  color: var(--text-muted);
  pointer-events: none;
  transform: rotate(90deg);
}

.form-input {
  width: 100%;
  padding: 10px 14px;
  background: var(--workspace-panel);
  border: 1px solid var(--workspace-border);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-primary);
  transition: all var(--transition-fast);
}

.form-input:focus {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px var(--lumi-primary-glow);
}

.form-input::placeholder {
  color: var(--text-muted);
}

.form-slider {
  width: 100%;
  height: 6px;
  appearance: none;
  background: var(--workspace-border);
  border-radius: 3px;
  outline: none;
  cursor: pointer;
}

.form-slider::-webkit-slider-thumb {
  appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--lumi-primary);
  cursor: pointer;
  box-shadow: 0 2px 6px rgba(13, 148, 136, 0.3);
  transition: transform var(--transition-fast);
}

.form-slider::-webkit-slider-thumb:hover {
  transform: scale(1.15);
}

.slider-labels {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}

.toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.toggle-switch {
  width: 44px;
  height: 24px;
  border-radius: 12px;
  background: var(--workspace-border);
  position: relative;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.toggle-switch.active {
  background: var(--lumi-primary);
}

.toggle-thumb {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: white;
  transition: transform var(--transition-fast);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}

.toggle-switch.active .toggle-thumb {
  transform: translateX(20px);
}

.form-hint {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: -4px;
}
</style>

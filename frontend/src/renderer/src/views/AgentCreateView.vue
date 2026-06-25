<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  X, ChevronRight, ChevronLeft, Upload, Sparkles,
  FileText, Brain, Terminal, Presentation,
  FileSpreadsheet, FileCode, Plus, CircleDot
} from 'lucide-vue-next'
import { useAgentStore } from '../stores/agent'
import LumiButton from '../components/common/LumiButton.vue'
import LumiInput from '../components/common/LumiInput.vue'
import LumiCard from '../components/common/LumiCard.vue'

const router = useRouter()
const agentStore = useAgentStore()

const currentStep = ref(0)
const totalSteps = 4

const stepTitles = ['身份与模型', '技能配置', '高级设置', '确认创建']
const stepSubtitles = ['定义智能体基础信息', '选择并配置能力模块', '调整行为参数', '预览并完成创建']

interface AvatarOption {
  id: string
  emoji: string
  color: string
}

const avatarCategories = [
  { id: 'classic', label: '经典' },
  { id: 'cute', label: '萌系' },
  { id: 'tech', label: '科技' },
  { id: 'artistic', label: '艺术' }
]

const avatarOptions: Record<string, AvatarOption[]> = {
  classic: [
    { id: 'c1', emoji: '\u{1F9D4}', color: 'var(--lumi-brand)' },
    { id: 'c2', emoji: '\u{1F9D3}', color: 'var(--lumi-info)' },
    { id: 'c3', emoji: '\u{1F9D1}\u200D\u{1F52C}', color: 'var(--task-purple)' }
  ],
  cute: [
    { id: 'cu1', emoji: '\u{1F978}', color: 'var(--lumi-success)' },
    { id: 'cu2', emoji: '\u{1F4A1}', color: 'var(--lumi-warning)' },
    { id: 'cu3', emoji: '\u{1F389}', color: 'var(--lumi-accent)' }
  ],
  tech: [
    { id: 't1', emoji: '\u{1F916}', color: 'var(--lumi-sky)' },
    { id: 't2', emoji: '\u{1F6E0}\uFE0F', color: 'var(--lumi-indigo)' },
    { id: 't3', emoji: '\u{26A1}', color: 'var(--lumi-amber)' }
  ],
  artistic: [
    { id: 'a1', emoji: '\u{1F3A8}', color: 'var(--task-pink)' },
    { id: 'a2', emoji: '\u{1F3B8}', color: 'var(--task-purple)' },
    { id: 'a3', emoji: '\u{2728}', color: 'var(--lumi-brand-soft)' }
  ]
}

const activeAvatarCategory = ref('classic')

const styleTags = [
  { id: 'professional', label: '专业' },
  { id: 'friendly', label: '友好' },
  { id: 'creative', label: '创意' },
  { id: 'concise', label: '简洁' },
  { id: 'casual', label: '随意' },
  { id: 'expert', label: '专家' }
]

const modelOptions = [
  { id: 'auto', label: '自动' },
  { id: 'gpt4o', label: 'GPT-4o' },
  { id: 'claude', label: 'Claude' },
  { id: 'gemini', label: 'Gemini' }
]

const skillItems = [
  {
    id: 'skill-search',
    name: '技能查找器',
    desc: '通过关键词搜索内置目录库，快速定位所需能力模块',
    icon: FileText,
    defaultEnabled: true
  },
  {
    id: 'skill-builder',
    name: '技能创建器',
    desc: '创建、修改、评估和优化智能体技能，支持结构化的 SKILL.md 编写',
    icon: FileCode,
    defaultEnabled: true
  },
  {
    id: 'self-learning',
    name: '智能体自我学习',
    desc: '将学习成果、错误和反思记录到每日日志中，持续提升推理与决策能力',
    icon: Brain,
    defaultEnabled: true
  },
  {
    id: 'mcp-tools',
    name: 'MCP 工具 (CLI)',
    desc: '通过 accio-mcp-cli 命令行发现和调用 MCP 工具（Notion、Square、Apify 等）',
    icon: Terminal,
    defaultEnabled: true
  },
  {
    id: 'powerpoint',
    name: 'PowerPoint',
    desc: '为供应商评审、数据汇总和战略提案生成 PowerPoint 演示文稿',
    icon: Presentation,
    defaultEnabled: false
  },
  {
    id: 'pdf',
    name: 'PDF',
    desc: '生成或解析 PDF 文档，从合同中提取关键条款及商业合规分析',
    icon: FileText,
    defaultEnabled: false
  },
  {
    id: 'word',
    name: 'Word 文档',
    desc: '创建和编辑 Word 文档，包括询价函（RFQ）、SOP 及合同模板',
    icon: FileText,
    defaultEnabled: false
  },
  {
    id: 'xlsx',
    name: 'Excel 表格',
    desc: '创建、编辑、分析和可视化 Excel 电子表格，支持公式与图表',
    icon: FileSpreadsheet,
    defaultEnabled: false
  }
]

const formData = reactive({
  name: '',
  description: '',
  selectedAvatarId: 'c1',
  selectedStyle: 'professional',
  selectedModel: 'auto',
  skills: {} as Record<string, boolean>,
  temperature: 0.7,
  maxTokens: 4096,
  systemPrompt: ''
})

skillItems.forEach(skill => {
  formData.skills[skill.id] = skill.defaultEnabled
})

const selectedAvatar = computed(() => {
  const allAvatars = Object.values(avatarOptions).flat()
  return allAvatars.find(a => a.id === formData.selectedAvatarId) || allAvatars[0]
})

const currentAvatars = computed(() => avatarOptions[activeAvatarCategory.value] || [])

const canGoNext = computed(() => {
  switch (currentStep.value) {
    case 0: return formData.name.trim().length > 0
    case 1: return true
    case 2: return true
    case 3: return true
    default: return false
  }
})

const goNext = () => {
  if (currentStep.value < totalSteps - 1) {
    currentStep.value++
  } else {
    handleCreateAgent()
  }
}

const goPrev = () => {
  if (currentStep.value > 0) {
    currentStep.value--
  }
}

const selectAvatar = (avatarId: string) => {
  formData.selectedAvatarId = avatarId
}

const toggleStyle = (styleId: string) => {
  formData.selectedStyle = styleId
}

const toggleSkill = (skillId: string) => {
  formData.skills[skillId] = !formData.skills[skillId]
}

const enabledSkillsCount = computed(() => {
  return Object.values(formData.skills).filter(v => v).length
})

const handleClose = () => {
  router.push('/workspace')
}

const errorMessage = ref('')

const handleCreateAgent = async () => {
  errorMessage.value = ''
  try {
    const capabilities = Object.entries(formData.skills)
      .filter(([, enabled]) => enabled)
      .map(([id]) => id)

    await agentStore.createAgent({
      name: formData.name,
      description: formData.description,
      systemPrompt: formData.systemPrompt,
      model: formData.selectedModel === 'auto' ? undefined : formData.selectedModel,
      color: selectedAvatar.value.color,
      capabilities: capabilities.length > 0 ? capabilities : ['chat']
    })
    router.push('/workspace')
  } catch (err: any) {
    console.error('Failed to create agent:', err)
    errorMessage.value = err.response?.data?.detail || err.message || '创建失败'
  }
}
</script>

<template>
  <div class="wizard-overlay" @click.self="handleClose">
    <div class="wizard-container animate-scale-in">
      <div class="wizard-header">
        <div class="header-left">
          <div class="header-icon-wrap">
            <Sparkles :size="20" />
          </div>
          <div class="header-titles">
            <h2 class="wizard-title">{{ stepTitles[currentStep] }}</h2>
            <p class="wizard-subtitle">第 {{ currentStep + 1 }} 步 > {{ stepSubtitles[currentStep] }}</p>
          </div>
        </div>
        <LumiButton
          variant="ghost"
          size="sm"
          icon-only
          aria-label="关闭"
          @click="handleClose"
        >
          <template #icon><X :size="18" /></template>
        </LumiButton>
      </div>

      <div class="wizard-body">
        <Transition name="step-fade" mode="out-in">
          <!-- Step 1: Identity & Model -->
          <div v-if="currentStep === 0" key="step-1" class="step-content step-layout-split">
            <div class="form-area">
              <div class="form-group">
                <label class="form-label">名称<span class="required">*</span></label>
                <LumiInput
                  v-model="formData.name"
                  type="text"
                  placeholder="给你的智能体起个名字..."
                />
              </div>

              <div class="form-group">
                <label class="form-label">智能体头像</label>
                <div class="avatar-section">
                  <div class="avatar-categories">
                    <button
                      v-for="cat in avatarCategories"
                      :key="cat.id"
                      :class="['cat-tab', { active: activeAvatarCategory === cat.id }]"
                      @click="activeAvatarCategory = cat.id"
                    >
                      {{ cat.label }}
                    </button>
                  </div>
                  <div class="avatar-grid">
                    <button
                      v-for="avatar in currentAvatars"
                      :key="avatar.id"
                      :class="['avatar-item', { selected: formData.selectedAvatarId === avatar.id }]"
                      :style="{ '--avatar-color': avatar.color }"
                      @click="selectAvatar(avatar.id)"
                    >
                      <span class="avatar-emoji">{{ avatar.emoji }}</span>
                    </button>
                    <button class="avatar-item upload-avatar" title="上传自定义头像">
                      <Upload :size="18" />
                    </button>
                  </div>
                </div>
              </div>

              <div class="form-group">
                <label class="form-label">描述</label>
                <textarea
                  v-model="formData.description"
                  class="lumi-textarea"
                  rows="3"
                  placeholder="简要描述这个智能体的定位和能力..."
                ></textarea>
              </div>

              <div class="form-group">
                <label class="form-label">风格</label>
                <div class="tag-list">
                  <button
                    v-for="tag in styleTags"
                    :key="tag.id"
                    :class="['style-tag', { active: formData.selectedStyle === tag.id }]"
                    @click="toggleStyle(tag.id)"
                  >
                    {{ tag.label }}
                  </button>
                </div>
              </div>

              <div class="form-group">
                <label class="form-label">模型偏好</label>
                <div class="model-list">
                  <button
                    v-for="model in modelOptions"
                    :key="model.id"
                    :class="['model-chip', { active: formData.selectedModel === model.id }]"
                    @click="formData.selectedModel = model.id"
                  >
                    {{ model.label }}
                  </button>
                </div>
              </div>
            </div>

            <div class="preview-area">
              <div class="preview-header">
                <CircleDot :size="14" />
                <span>智能体预览</span>
              </div>
              <p class="preview-hint">实时预览智能体效果</p>

              <LumiCard class="preview-card" padding="md">
                <div
                  class="preview-avatar-ring"
                  :style="{ '--avatar-color': selectedAvatar.color }"
                >
                  <span class="preview-avatar-emoji">{{ selectedAvatar.emoji }}</span>
                </div>
                <h3 class="preview-name">{{ formData.name || '未命名智能体' }}</h3>
                <p class="preview-badge">{{ styleTags.find(t => t.id === formData.selectedStyle)?.label || '风格' }} · 已验证</p>
                <p class="preview-desc">{{ formData.description || '暂无描述信息。添加描述可帮助理解智能体的定位与用途。' }}</p>
                <div class="preview-meta">
                  <span>模型：{{ modelOptions.find(m => m.id === formData.selectedModel)?.label }}</span>
                </div>
              </LumiCard>

              <div class="step-indicator">
                简览步骤 • 第 {{ currentStep + 1 }} / {{ totalSteps }} 步
              </div>
            </div>
          </div>

          <!-- Step 2: Skills -->
          <div v-else-if="currentStep === 1" key="step-2" class="step-content step-layout-full">
            <div class="skills-intro">
              <p>基于智能体定位推荐的能力模块，创建时全量启用。可用开关控制是否启能。</p>
            </div>
            <div class="skills-list">
              <div
                v-for="skill in skillItems"
                :key="skill.id"
                class="skill-item"
              >
                <div class="skill-icon-wrap">
                  <component :is="skill.icon" :size="18" />
                </div>
                <div class="skill-info">
                  <h4 class="skill-name">{{ skill.name }}</h4>
                  <p class="skill-desc">{{ skill.desc }}</p>
                </div>
                <button
                  :class="['lumi-toggle', { 'is-active': formData.skills[skill.id] }]"
                  @click="toggleSkill(skill.id)"
                  :aria-label="formData.skills[skill.id] ? '关闭' : '开启'"
                ></button>
              </div>
            </div>
            <button class="add-skill-pack-btn">
              <Plus :size="16" />
              <span>从推荐技能包添加</span>
            </button>
          </div>

          <!-- Step 3: Advanced Settings -->
          <div v-else-if="currentStep === 2" key="step-3" class="step-content step-layout-full">
            <div class="settings-grid">
              <LumiCard class="settings-card" padding="md">
                <h3 class="card-title">模型参数</h3>
                <div class="form-group">
                  <label class="form-label">Temperature ({{ formData.temperature.toFixed(1) }})</label>
                  <input
                    v-model.number="formData.temperature"
                    type="range"
                    min="0"
                    max="2"
                    step="0.1"
                    class="range-slider"
                  />
                  <div class="range-labels">
                    <span>精确</span>
                    <span>创意</span>
                  </div>
                </div>
                <div class="form-group">
                  <label class="form-label">最大 Token 数</label>
                  <LumiInput
                    v-model.number="formData.maxTokens"
                    type="number"
                    min="256"
                    max="128000"
                  />
                </div>
              </LumiCard>

              <LumiCard class="settings-card" padding="md">
                <h3 class="card-title">系统提示词</h3>
                <div class="form-group">
                  <textarea
                    v-model="formData.systemPrompt"
                    class="lumi-textarea system-prompt-area"
                    rows="10"
                    placeholder="定义智能体的角色、行为准则和约束条件...&#10;&#10;例如：你是一个专业的编程助手，专注于提供高质量的代码解决方案。"
                  ></textarea>
                </div>
              </LumiCard>
            </div>
          </div>

          <!-- Step 4: Confirm -->
          <div v-else-if="currentStep === 3" key="step-4" class="step-content step-layout-full">
            <Transition name="toast-slide">
              <div v-if="errorMessage" class="error-notification">
                <div class="notification-icon error">
                  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="15" y1="9" x2="9" y2="15"/>
                    <line x1="9" y1="9" x2="15" y2="15"/>
                  </svg>
                </div>
                <span class="notification-message">{{ errorMessage }}</span>
                <button class="notification-close" @click="errorMessage = ''">
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>
              </div>
            </Transition>
            <div class="confirm-grid">
              <LumiCard class="confirm-card main-confirm" padding="md">
                <div class="confirm-header-row">
                  <div
                    class="confirm-avatar-lg"
                    :style="{ '--avatar-color': selectedAvatar.color }"
                  >
                    <span class="confirm-avatar-emoji">{{ selectedAvatar.emoji }}</span>
                  </div>
                  <div>
                    <h2 class="confirm-name">{{ formData.name }}</h2>
                    <p class="confirm-style">{{ styleTags.find(t => t.id === formData.selectedStyle)?.label }} 风格</p>
                  </div>
                </div>
                <div class="confirm-divider"></div>
                <div class="confirm-details">
                  <div class="detail-row">
                    <span class="detail-label">描述</span>
                    <span class="detail-value">{{ formData.description || '未设置' }}</span>
                  </div>
                  <div class="detail-row">
                    <span class="detail-label">模型</span>
                    <span class="detail-value">{{ modelOptions.find(m => m.id === formData.selectedModel)?.label }}</span>
                  </div>
                  <div class="detail-row">
                    <span class="detail-label">已选技能</span>
                    <span class="detail-value">{{ enabledSkillsCount }} 项</span>
                  </div>
                  <div class="detail-row">
                    <span class="detail-label">Temperature</span>
                    <span class="detail-value">{{ formData.temperature }}</span>
                  </div>
                  <div class="detail-row">
                    <span class="detail-label">Max Tokens</span>
                    <span class="detail-value">{{ formData.maxTokens }}</span>
                  </div>
                </div>
              </LumiCard>

              <LumiCard class="confirm-card side-confirm" padding="md">
                <h4 class="side-title">已启用技能</h4>
                <div class="enabled-skills-list">
                  <div
                    v-for="skill in skillItems.filter(s => formData.skills[s.id])"
                    :key="skill.id"
                    class="enabled-skill-tag"
                  >
                    <component :is="skill.icon" :size="14" />
                    <span>{{ skill.name }}</span>
                  </div>
                  <p v-if="enabledSkillsCount === 0" class="no-skills">暂无启用技能</p>
                </div>
              </LumiCard>
            </div>
          </div>
        </Transition>
      </div>

      <div class="wizard-footer">
        <LumiButton
          variant="secondary"
          size="md"
          :disabled="currentStep === 0"
          @click="goPrev"
        >
          <ChevronLeft :size="16" />
          <span>上一步</span>
        </LumiButton>
        <LumiButton
          variant="primary"
          size="md"
          :disabled="!canGoNext"
          @click="goNext"
        >
          <span>{{ currentStep === totalSteps - 1 ? '创建 Agent' : `下一步: ${currentStep === 0 ? '技能' : currentStep === 1 ? '设置' : '确认'}` }}</span>
          <ChevronRight :size="16" />
        </LumiButton>
      </div>
    </div>
  </div>
</template>

<style scoped>
.wizard-overlay {
  background: var(--overlay-bg);
  backdrop-filter: blur(var(--space-2));
  -webkit-backdrop-filter: blur(var(--space-2));
  padding: var(--space-6);
}

.wizard-container {
  width: 100%;
  max-width: 900px;
  max-height: 88vh;
  border-radius: var(--radius-xl);
  background: var(--surface);
  box-shadow: var(--shadow-xl);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--border-light);
}

.wizard-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-5) var(--space-7) var(--space-4);
  flex-shrink: 0;
  border-bottom: 1px solid var(--border-light);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.header-icon-wrap {
  width: 38px;
  height: 38px;
  border-radius: var(--radius-md);
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
  display: flex;
  align-items: center;
  justify-content: center;
}

.header-titles {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.wizard-title {
  font-size: var(--text-lg);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  line-height: 1.3;
}

.wizard-subtitle {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.wizard-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-6) var(--space-7);
  min-height: 0;
}

.step-content {
  min-height: 100%;
}

.step-layout-split {
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: var(--space-8);
  align-items: start;
}

.step-layout-full {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

/* Form styles */
.form-group {
  margin-bottom: var(--space-5);
}

.form-label {
  display: block;
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}

.required {
  color: var(--lumi-accent);
  margin-left: 2px;
}

/* Avatar section */
.avatar-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.avatar-categories {
  display: flex;
  gap: var(--space-1);
  flex-wrap: wrap;
}

.cat-tab {
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-full);
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--text-secondary);
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  transition: all var(--transition-fast);
}

.cat-tab.active {
  background: var(--surface);
  color: var(--text-primary);
  border-color: var(--text-primary);
  box-shadow: var(--shadow-xs);
}

.cat-tab:hover:not(.active) {
  border-color: var(--text-muted);
}

.avatar-grid {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.avatar-item {
  width: 52px;
  height: 52px;
  border-radius: var(--radius-full);
  border: 2px solid transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-3xl);
  cursor: pointer;
  transition: all var(--transition-normal);
  background: var(--bg-secondary);
}

.avatar-item:hover {
  transform: scale(1.08);
}

.avatar-item.selected {
  border-color: var(--avatar-color, var(--lumi-brand));
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--avatar-color, var(--lumi-brand)) 20%, transparent);
}

.upload-avatar {
  color: var(--text-muted);
  border-style: dashed;
  border-color: var(--border);
}

.upload-avatar:hover {
  border-color: var(--lumi-brand);
  color: var(--lumi-brand);
  background: var(--lumi-brand-light);
}

/* Style tags */
.tag-list {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.style-tag {
  padding: 7px var(--space-4);
  border-radius: var(--radius-full);
  font-size: var(--text-base);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  transition: all var(--transition-fast);
}

.style-tag:hover:not(.active) {
  border-color: var(--text-muted);
}

.style-tag.active {
  background: var(--text-primary);
  color: var(--text-inverse);
  border-color: transparent;
}

/* Model chips */
.model-list {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.model-chip {
  padding: 7px var(--space-4);
  border-radius: var(--radius-full);
  font-size: var(--text-base);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  transition: all var(--transition-fast);
}

.model-chip:hover:not(.active) {
  border-color: var(--text-muted);
}

.model-chip.active {
  background: var(--text-primary);
  color: var(--text-inverse);
  border-color: transparent;
}

/* Preview area */
.preview-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
}

.preview-header {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  color: var(--text-secondary);
  width: 100%;
}

.preview-header svg {
  color: var(--lumi-brand);
}

.preview-hint {
  font-size: var(--text-sm);
  color: var(--text-muted);
  width: 100%;
}

.preview-card {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  text-align: center;
}

.preview-card :deep(.lumi-card__body) {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  text-align: center;
}

.preview-avatar-ring {
  width: var(--space-10);
  height: var(--space-10);
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--avatar-color, var(--lumi-brand)), color-mix(in srgb, var(--avatar-color, var(--lumi-brand)) 60%, transparent));
  box-shadow: var(--shadow-md);
}

.preview-avatar-emoji {
  font-size: var(--text-4xl);
}

.preview-name {
  font-size: var(--text-xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
}

.preview-badge {
  font-size: var(--text-xs);
  color: var(--text-muted);
  padding: 3px var(--space-2);
  border-radius: var(--radius-full);
  background: var(--surface);
  border: 1px solid var(--border-light);
}

.preview-desc {
  font-size: var(--text-sm);
  color: var(--text-muted);
  line-height: var(--leading-relaxed);
  text-align: left;
  width: 100%;
}

.preview-meta {
  font-size: var(--text-xs);
  color: var(--text-muted);
  width: 100%;
  text-align: left;
  padding-top: var(--space-2);
  border-top: 1px solid var(--border-light);
}

.step-indicator {
  font-size: var(--text-sm);
  color: var(--text-muted);
  width: 100%;
  text-align: right;
  padding-top: var(--space-1);
}

/* Skills section */
.skills-intro {
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  background: var(--lumi-brand-light);
  color: var(--text-secondary);
  font-size: var(--text-base);
  line-height: var(--leading-relaxed);
  border: 1px solid color-mix(in srgb, var(--lumi-brand) 10%, transparent);
}

.skills-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.skill-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  background: var(--surface);
  border: 1px solid var(--border-light);
  transition: all var(--transition-fast);
}

.skill-item:hover {
  border-color: var(--border);
  box-shadow: var(--shadow-xs);
}

.skill-icon-wrap {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  background: var(--lumi-brand-light);
  color: var(--lumi-brand);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.skill-info {
  flex: 1;
  min-width: 0;
}

.skill-name {
  font-size: var(--text-md);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin-bottom: 2px;
}

.skill-desc {
  font-size: var(--text-sm);
  color: var(--text-muted);
  line-height: 1.5;
}

.add-skill-pack-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-3);
  border-radius: var(--radius-md);
  border: 1px dashed var(--lumi-brand);
  color: var(--lumi-brand);
  font-size: var(--text-base);
  font-weight: var(--font-medium);
  background: transparent;
  cursor: pointer;
  transition: all var(--transition-fast);
  margin-top: var(--space-2);
}

.add-skill-pack-btn:hover {
  background: var(--lumi-brand-light);
}

/* Settings grid */
.settings-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-5);
}

.settings-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.settings-card :deep(.lumi-card__body) {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.card-title {
  font-size: var(--text-lg);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  margin-bottom: var(--space-3);
}

.range-slider {
  width: 100%;
  height: 6px;
  border-radius: var(--radius-xs);
  appearance: none;
  background: var(--border);
  outline: none;
  cursor: pointer;
}

.range-slider::-webkit-slider-thumb {
  appearance: none;
  width: 18px;
  height: 18px;
  border-radius: var(--radius-full);
  background: var(--lumi-brand);
  cursor: pointer;
  box-shadow: var(--shadow-sm);
  transition: transform var(--transition-fast);
}

.range-slider::-webkit-slider-thumb:hover {
  transform: scale(1.15);
}

.range-labels {
  display: flex;
  justify-content: space-between;
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-top: var(--space-1);
}

.system-prompt-area {
  min-height: 200px;
  font-family: inherit;
}

/* Confirm section */
.confirm-grid {
  display: grid;
  grid-template-columns: 1.2fr 0.8fr;
  gap: var(--space-5);
}

.confirm-card {
  display: flex;
  flex-direction: column;
}

.confirm-card :deep(.lumi-card__body) {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.main-confirm {
  gap: var(--space-3);
}

.confirm-header-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.confirm-avatar-lg {
  width: 56px;
  height: 56px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: linear-gradient(135deg, var(--avatar-color, var(--lumi-brand)), color-mix(in srgb, var(--avatar-color, var(--lumi-brand)) 60%, transparent));
  box-shadow: var(--shadow-md);
}

.confirm-avatar-emoji {
  font-size: var(--text-4xl);
}

.confirm-name {
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
}

.confirm-style {
  font-size: var(--text-base);
  color: var(--text-muted);
}

.confirm-divider {
  height: 1px;
  background: var(--divider-soft);
}

.confirm-details {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.detail-label {
  font-size: var(--text-base);
  color: var(--text-muted);
  font-weight: var(--font-medium);
}

.detail-value {
  font-size: var(--text-base);
  color: var(--text-primary);
  font-weight: var(--font-semibold);
}

.side-title {
  font-size: var(--text-md);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  margin-bottom: var(--space-2);
}

.enabled-skills-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.enabled-skill-tag {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--surface);
  font-size: var(--text-sm);
  color: var(--text-secondary);
  font-weight: var(--font-medium);
}

.enabled-skill-tag svg {
  color: var(--lumi-brand);
  flex-shrink: 0;
}

.no-skills {
  font-size: var(--text-base);
  color: var(--text-muted);
  text-align: center;
  padding: var(--space-4);
}

/* Footer */
.wizard-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-7);
  border-top: 1px solid var(--border-light);
  flex-shrink: 0;
}

/* Transitions */
.step-fade-enter-active {
  transition: all var(--duration-slow) var(--ease-in-out);
}

.step-fade-leave-active {
  transition: all var(--duration-normal) var(--ease-in-out);
}

.step-fade-enter-from {
  opacity: 0;
  transform: translateX(20px);
}

.step-fade-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

@media (max-width: 768px) {
  .step-layout-split {
    grid-template-columns: 1fr;
  }

  .preview-area {
    order: -1;
  }

  .settings-grid {
    grid-template-columns: 1fr;
  }

  .confirm-grid {
    grid-template-columns: 1fr;
  }

  .wizard-container {
    max-height: 92vh;
  }
}

.error-notification {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  background: var(--task-red-soft);
  border: 1px solid var(--task-red-border);
  border-radius: var(--radius-lg);
  color: var(--lumi-danger);
  font-size: var(--text-md);
  font-weight: var(--font-medium);
  margin-bottom: var(--space-5);
  box-shadow: var(--shadow-sm);
}

.notification-icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.notification-icon.error {
  color: var(--lumi-danger);
}

.notification-message {
  flex: 1;
  line-height: 1.4;
}

.notification-close {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--space-6);
  height: var(--space-6);
  border: none;
  background: var(--lumi-danger-light);
  border-radius: var(--radius-xs);
  color: var(--lumi-danger);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.notification-close:hover {
  background: color-mix(in srgb, var(--lumi-danger) 18%, transparent);
  transform: rotate(90deg);
}

.toast-slide-enter-active {
  transition: all var(--duration-normal) var(--ease-out-expo);
}

.toast-slide-leave-active {
  transition: all var(--duration-leave) var(--ease-in-out);
}

.toast-slide-enter-from {
  opacity: 0;
  transform: translateY(-10px);
}

.toast-slide-leave-to {
  opacity: 0;
  transform: translateY(-10px) scale(0.95);
}

</style>

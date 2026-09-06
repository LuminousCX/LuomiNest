<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { FileText, Save, ShieldCheck, AlertCircle, Loader2 } from 'lucide-vue-next'
import LumiModal from '../common/LumiModal.vue'
import LumiButton from '../common/LumiButton.vue'
import LumiInput from '../common/LumiInput.vue'
import { usePluginsStore } from '../../stores/plugins'
import type { CxSkillValidateResult } from '../../plugins/types'

const props = defineProps<{
  visible: boolean
  /** 传入 null 表示新建；传入 skillId 表示编辑现有技能 */
  skillId: string | null
  /** 新建时的默认内容模板 */
  defaultContent?: string
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  saved: []
}>()

const store = usePluginsStore()

const skillIdInput = ref('')
const content = ref('')
const validating = ref(false)
const saving = ref(false)
const loadingRaw = ref(false)
const validateResult = ref<CxSkillValidateResult | null>(null)
const errorMessage = ref('')

const isCreate = computed(() => props.skillId === null)

const DEFAULT_TEMPLATE = `---
id: my-skill
name: 我的技能
description: 在这里描述技能的用途和适用场景
version: 0.1.0
author: LuminousCX
license: MIT
tags: []
category: tool
icon: brain
trigger_keywords:
  - 关键词1
  - 关键词2
  - 关键词3
---

# 技能标题

## 触发条件
描述什么情况下应该使用此技能。

## 使用流程
1. 步骤一
2. 步骤二
3. 步骤三

## 注意事项
- 注意点一
- 注意点二
`

const resolveSkillId = () => (isCreate.value ? skillIdInput.value.trim() : props.skillId ?? '')

/**
 * 规范化 SKILL.md 内容：补齐 frontmatter 缺失的标准字段（id/name/version/description/trigger_keywords）。
 *
 * 目的：兼容从外部复制的旧格式技能（如 SKILL.md 只有 name/description/license），
 * 使其能通过后端校验（validate_skill_md_content 要求 id 与目录名一致、name 非空、
 * description 非空、trigger_keywords >= 3 个）。只追加缺失字段，不修改已有内容与 body。
 */
const normalizeSkillContent = (raw: string, skillId: string): string => {
  const trimmed = raw.replace(/^\uFEFF/, '').trimStart()
  // 无 YAML frontmatter 时无法安全注入，原样返回（后端会给出校验提示）
  if (!trimmed.startsWith('---')) return raw

  const fmEnd = trimmed.indexOf('\n---', 3)
  if (fmEnd === -1) return raw

  const fmRaw = trimmed.slice(3, fmEnd).replace(/\r\n/g, '\n')
  const body = trimmed.slice(fmEnd + 4).trimStart()

  // 解析已有 key（保留原样，仅用于判断缺失字段）
  const existingKeys = new Set<string>()
  for (const line of fmRaw.split('\n')) {
    const m = line.match(/^([a-zA-Z_][a-zA-Z0-9_]*)\s*:/)
    if (m) existingKeys.add(m[1])
  }

  const extra: string[] = []
  if (!existingKeys.has('id')) extra.push(`id: ${skillId}`)
  if (!existingKeys.has('name')) extra.push(`name: ${skillId}`)
  if (!existingKeys.has('version')) extra.push(`version: 1.0.0`)
  if (!existingKeys.has('author')) extra.push(`author: LuminousCX`)
  if (!existingKeys.has('license')) extra.push(`license: MIT`)

  // description 缺失时补一句占位描述（后端要求非空）
  if (!existingKeys.has('description')) {
    extra.push(`description: ${skillId} 技能：按照 SKILL.md 指令完成相关任务`)
  }

  // trigger_keywords 缺失或不足时，从 name/description 提取关键词补齐
  if (!existingKeys.has('trigger_keywords')) {
    const nameMatch = fmRaw.match(/^name\s*:\s*(.+)$/m)
    const descMatch = fmRaw.match(/^description\s*:\s*(.+)$/m)
    const candidates: string[] = [
      ...(nameMatch ? [nameMatch[1].trim().replace(/["']/g, '')] : [skillId]),
      ...(descMatch
        ? descMatch[1].replace(/["']/g, '').split(/[,，。.\s]+/).filter((w) => w.length >= 2).slice(0, 4)
        : []),
    ]
    const kws = [...new Set(candidates)].filter(Boolean).slice(0, 5)
    while (kws.length < 3) kws.push(skillId)
    extra.push('trigger_keywords:')
    for (const kw of kws) extra.push(`  - ${kw}`)
  }

  if (extra.length === 0) return raw
  return `---\n${fmRaw.trim()}\n${extra.join('\n')}\n---\n\n${body}`
}

const loadRaw = async () => {
  if (isCreate.value || !props.skillId) return
  loadingRaw.value = true
  errorMessage.value = ''
  try {
    const raw = await store.getSkillRaw(props.skillId)
    if (raw !== null) {
      content.value = raw
    } else {
      errorMessage.value = '无法读取技能原文'
    }
  } finally {
    loadingRaw.value = false
  }
}

const handleValidate = async () => {
  const id = resolveSkillId()
  if (!id) {
    errorMessage.value = '请填写技能 ID（kebab-case）'
    return
  }
  if (!content.value.trim()) {
    errorMessage.value = '内容不能为空'
    return
  }
  validating.value = true
  errorMessage.value = ''
  validateResult.value = null
  try {
    // 校验前先规范化补齐缺失的 frontmatter 字段，兼容旧格式技能
    const result = await store.validateSkill(id, normalizeSkillContent(content.value, id))
    validateResult.value = result
    if (result && !result.valid) {
      errorMessage.value = result.errors.join('；') || '校验未通过'
    }
  } finally {
    validating.value = false
  }
}

const handleSave = async () => {
  const id = resolveSkillId()
  if (!id) {
    errorMessage.value = '请填写技能 ID（kebab-case）'
    return
  }
  if (!/^[a-z0-9][a-z0-9-]{0,63}$/.test(id)) {
    errorMessage.value = '技能 ID 必须为 kebab-case（小写字母/数字/连字符，1-64 字符）'
    return
  }
  if (!content.value.trim()) {
    errorMessage.value = '内容不能为空'
    return
  }

  saving.value = true
  errorMessage.value = ''
  try {
    // 保存前规范化补齐缺失的 frontmatter 字段，兼容旧格式技能
    const result = await store.writeSkill(id, normalizeSkillContent(content.value, id), true)
    if (result) {
      emit('saved')
      emit('update:visible', false)
    } else {
      errorMessage.value = '保存失败，请查看错误提示'
    }
  } finally {
    saving.value = false
  }
}

const handleClose = () => {
  emit('update:visible', false)
}

watch(
  () => props.visible,
  (visible) => {
    if (!visible) return
    errorMessage.value = ''
    validateResult.value = null
    if (isCreate.value) {
      skillIdInput.value = ''
      content.value = props.defaultContent ?? DEFAULT_TEMPLATE
    } else {
      skillIdInput.value = props.skillId ?? ''
      content.value = ''
      loadRaw()
    }
  },
)
</script>

<template>
  <LumiModal
    :visible="visible"
    :title="isCreate ? '新建技能' : `编辑技能：${skillId}`"
    size="lg"
    @close="handleClose"
    @update:visible="emit('update:visible', $event)"
  >
    <div class="skill-edit-dialog">
      <!-- 技能 ID 输入（仅新建模式可编辑） -->
      <div class="form-row">
        <label class="form-label">
          <FileText :size="14" />
          <span>技能 ID</span>
        </label>
        <LumiInput
          v-model="skillIdInput"
          :placeholder="'kebab-case，例如：travel-planner'"
          :disabled="!isCreate"
          :error="errorMessage && isCreate ? errorMessage : false"
        />
        <p class="form-hint">小写字母 / 数字 / 连字符，1-64 字符，全局唯一</p>
      </div>

      <!-- SKILL.md 内容编辑区 -->
      <div class="form-row">
        <label class="form-label">
          <FileText :size="14" />
          <span>SKILL.md 内容</span>
        </label>
        <div v-if="loadingRaw" class="loading-state">
          <Loader2 :size="16" class="spinning" />
          <span>加载技能原文...</span>
        </div>
        <textarea
          v-else
          v-model="content"
          class="skill-textarea"
          spellcheck="false"
          placeholder="编辑 SKILL.md 内容，需包含 YAML frontmatter 与 Markdown 正文"
        />
      </div>

      <!-- 校验结果 -->
      <div v-if="validateResult" class="validate-result">
        <div :class="['validate-badge', validateResult.valid ? 'valid' : 'invalid']">
          <component :is="validateResult.valid ? ShieldCheck : AlertCircle" :size="13" />
          <span>{{ validateResult.valid ? '校验通过' : '校验未通过' }}</span>
        </div>
        <ul v-if="validateResult.errors.length" class="error-list">
          <li v-for="(err, idx) in validateResult.errors" :key="idx">{{ err }}</li>
        </ul>
      </div>

      <!-- 错误提示 -->
      <div v-if="errorMessage && !validateResult" class="error-message">
        <AlertCircle :size="13" />
        <span>{{ errorMessage }}</span>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <LumiButton variant="ghost" size="sm" @click="handleClose">取消</LumiButton>
        <LumiButton
          variant="outline"
          size="sm"
          :disabled="validating || saving || loadingRaw"
          :loading="validating"
          @click="handleValidate"
        >
          <ShieldCheck :size="13" />
          <span>校验</span>
        </LumiButton>
        <LumiButton
          variant="primary"
          size="sm"
          :disabled="validating || saving || loadingRaw"
          :loading="saving"
          @click="handleSave"
        >
          <Save :size="13" />
          <span>保存</span>
        </LumiButton>
      </div>
    </template>
  </LumiModal>
</template>

<style scoped>
.skill-edit-dialog {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.form-row {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.form-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.form-hint {
  font-size: var(--text-2xs);
  color: var(--text-muted);
  margin: 0;
}

.loading-state {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-4);
  color: var(--text-muted);
  font-size: var(--text-sm);
  background: var(--surface-hover);
  border-radius: var(--radius-sm);
}

.skill-textarea {
  width: 100%;
  min-height: 320px;
  padding: var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--workspace-card);
  color: var(--text-primary);
  font-family: var(--font-mono, 'Cascadia Mono', Consolas, monospace);
  font-size: var(--text-xs);
  line-height: 1.6;
  resize: vertical;
  outline: none;
  transition: border-color var(--transition-fast);
}

.skill-textarea:focus {
  border-color: var(--lumi-primary);
}

.validate-result {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--surface-hover);
}

.validate-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--text-xs);
  font-weight: var(--font-semibold);
}

.validate-badge.valid {
  color: var(--lumi-success-hover, rgb(22, 163, 74));
}

.validate-badge.invalid {
  color: var(--lumi-danger-hover, rgb(220, 38, 38));
}

.error-list {
  margin: 0;
  padding-left: var(--space-4);
  font-size: var(--text-xs);
  color: var(--lumi-danger-hover, rgb(220, 38, 38));
}

.error-message {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  background: var(--lumi-danger-light, rgba(239, 68, 68, 0.08));
  color: var(--lumi-danger-hover, rgb(220, 38, 38));
  font-size: var(--text-xs);
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}

.spinning {
  animation: spin 0.8s linear infinite;
}


</style>

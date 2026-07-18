<script setup lang="ts">
import { computed } from 'vue'
import { Bot, AlertTriangle } from 'lucide-vue-next'
import type { AgentProfile, AgentRoleDefinition } from '../../types'
import type { PresetAvatar } from '../../composables/useWorkspaceAgentDialogs'

const props = defineProps<{
  showCreateDialog: boolean
  showEditDialog: boolean
  showConfirmDialog: boolean
  showCreateGroupDialog: boolean
  showAddAgentDialog: boolean
  createForm: { name: string; description: string; systemPrompt: string; color: string; avatarMode: string; avatarUrl: string }
  editForm: { name: string; description: string; systemPrompt: string; color: string; avatarMode: string; avatarUrl: string }
  createError: string
  confirmMessage: string
  confirmIsDanger: boolean
  newGroupName: string
  newGroupDesc: string
  addAgentId: string
  addAgentRole: string
  availableAgentsForGroup: AgentProfile[]
  agentColors: string[]
  presetAvatars: PresetAvatar[]
  agentRoles: AgentRoleDefinition[]
}>()

const emit = defineEmits<{
  'update:showCreateDialog': [value: boolean]
  'update:createForm': [value: typeof props.createForm]
  'update:createError': [value: string]
  'create-agent': []
  'update:showEditDialog': [value: boolean]
  'update:editForm': [value: typeof props.editForm]
  'update-agent': []
  'delete-agent': []
  'confirm': []
  'cancel': []
  'update:showCreateGroupDialog': [value: boolean]
  'update:newGroupName': [value: string]
  'update:newGroupDesc': [value: string]
  'create-group': []
  'update:showAddAgentDialog': [value: boolean]
  'update:addAgentId': [value: string]
  'update:addAgentRole': [value: string]
  'add-agent-to-group': []
}>()

const createName = computed({
  get: () => props.createForm.name,
  set: (v) => emit('update:createForm', { ...props.createForm, name: v }),
})

const createDescription = computed({
  get: () => props.createForm.description,
  set: (v) => emit('update:createForm', { ...props.createForm, description: v }),
})

const createSystemPrompt = computed({
  get: () => props.createForm.systemPrompt,
  set: (v) => emit('update:createForm', { ...props.createForm, systemPrompt: v }),
})

const createColor = computed({
  get: () => props.createForm.color,
  set: (v) => emit('update:createForm', { ...props.createForm, color: v }),
})

const createAvatarMode = computed({
  get: () => props.createForm.avatarMode as 'color' | 'preset',
  set: (v) => emit('update:createForm', { ...props.createForm, avatarMode: v }),
})

const createAvatarUrl = computed({
  get: () => props.createForm.avatarUrl,
  set: (v) => emit('update:createForm', { ...props.createForm, avatarUrl: v }),
})

const editName = computed({
  get: () => props.editForm.name,
  set: (v) => emit('update:editForm', { ...props.editForm, name: v }),
})

const editDescription = computed({
  get: () => props.editForm.description,
  set: (v) => emit('update:editForm', { ...props.editForm, description: v }),
})

const editSystemPrompt = computed({
  get: () => props.editForm.systemPrompt,
  set: (v) => emit('update:editForm', { ...props.editForm, systemPrompt: v }),
})

const editColor = computed({
  get: () => props.editForm.color,
  set: (v) => emit('update:editForm', { ...props.editForm, color: v }),
})

const editAvatarMode = computed({
  get: () => props.editForm.avatarMode as 'color' | 'preset',
  set: (v) => emit('update:editForm', { ...props.editForm, avatarMode: v }),
})

const editAvatarUrl = computed({
  get: () => props.editForm.avatarUrl,
  set: (v) => emit('update:editForm', { ...props.editForm, avatarUrl: v }),
})

const newGroupNameModel = computed({
  get: () => props.newGroupName,
  set: (v) => emit('update:newGroupName', v),
})

const newGroupDescModel = computed({
  get: () => props.newGroupDesc,
  set: (v) => emit('update:newGroupDesc', v),
})

const addAgentIdModel = computed({
  get: () => props.addAgentId,
  set: (v) => emit('update:addAgentId', v),
})

const addAgentRoleModel = computed({
  get: () => props.addAgentRole,
  set: (v) => emit('update:addAgentRole', v),
})
</script>

<template>
  <Transition name="dialog-fade">
    <div v-if="showCreateDialog" class="create-dialog-overlay" @click.self="emit('update:showCreateDialog', false)">
      <div class="create-dialog">
        <h3>创建自定义 Agent</h3>
        <Transition name="toast-slide">
          <div v-if="createError" class="dialog-error">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"/>
              <line x1="15" y1="9" x2="9" y2="15"/>
              <line x1="9" y1="9" x2="15" y2="15"/>
            </svg>
            <span>{{ createError }}</span>
            <button class="error-close" @click="emit('update:createError', '')">
              <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
        </Transition>
        <div class="form-group">
          <label class="form-label">
            名称
            <span class="required-mark">*</span>
          </label>
          <input v-model="createName" type="text" class="form-input" placeholder="如: 小助手" />
        </div>
        <div class="form-group">
          <label class="form-label">描述</label>
          <input v-model="createDescription" type="text" class="form-input" placeholder="如: 通用对话助手" />
        </div>
        <div class="form-group">
          <label class="form-label">系统提示词</label>
          <textarea
            v-model="createSystemPrompt"
            class="form-input form-textarea"
            placeholder="定义 Agent 的角色和行为..."
            rows="4"
          ></textarea>
        </div>
        <div class="form-group">
          <label class="form-label">头像</label>
          <div class="avatar-mode-toggle">
            <button
              :class="['mode-btn', { active: createAvatarMode === 'color' }]"
              @click="createAvatarMode = 'color'"
            >颜色</button>
            <button
              :class="['mode-btn', { active: createAvatarMode === 'preset' }]"
              @click="createAvatarMode = 'preset'"
            >预设头像</button>
          </div>
          <div v-if="createAvatarMode === 'color'" class="color-picker">
            <button
              v-for="color in agentColors"
              :key="color"
              :class="['color-dot', { active: createColor === color }]"
              :style="{ background: color }"
              @click="createColor = color"
            ></button>
          </div>
          <div v-else class="preset-avatar-grid">
            <button
              v-for="avatar in presetAvatars"
              :key="avatar.id"
              :class="['preset-avatar-item', { selected: createAvatarUrl === avatar.url }]"
              :title="avatar.name"
              @click="createAvatarUrl = avatar.url"
            >
              <img :src="avatar.url" :alt="avatar.name" class="preset-avatar-img" />
            </button>
          </div>
        </div>
        <div class="dialog-actions">
          <button class="dialog-btn cancel" @click="emit('update:showCreateDialog', false)">取消</button>
          <button
            :class="['dialog-btn confirm', { disabled: !createName.trim() }]"
            :disabled="!createName.trim()"
            @click="emit('create-agent')"
          >
            创建
          </button>
        </div>
      </div>
    </div>
  </Transition>

  <Transition name="dialog-fade">
    <div v-if="showEditDialog" class="create-dialog-overlay" @click.self="emit('update:showEditDialog', false)">
      <div class="create-dialog">
        <h3>编辑 Agent</h3>
        <div class="form-group">
          <label class="form-label">
            名称
            <span class="required-mark">*</span>
          </label>
          <input v-model="editName" type="text" class="form-input" placeholder="如: 小助手" />
        </div>
        <div class="form-group">
          <label class="form-label">描述</label>
          <input v-model="editDescription" type="text" class="form-input" placeholder="如: 通用对话助手" />
        </div>
        <div class="form-group">
          <label class="form-label">系统提示词</label>
          <textarea
            v-model="editSystemPrompt"
            class="form-input form-textarea"
            placeholder="定义 Agent 的角色和行为..."
            rows="4"
          ></textarea>
        </div>
        <div class="form-group">
          <label class="form-label">头像</label>
          <div class="avatar-mode-toggle">
            <button
              :class="['mode-btn', { active: editAvatarMode === 'color' }]"
              @click="editAvatarMode = 'color'"
            >颜色</button>
            <button
              :class="['mode-btn', { active: editAvatarMode === 'preset' }]"
              @click="editAvatarMode = 'preset'"
            >预设头像</button>
          </div>
          <div v-if="editAvatarMode === 'color'" class="color-picker">
            <button
              v-for="color in agentColors"
              :key="color"
              :class="['color-dot', { active: editColor === color }]"
              :style="{ background: color }"
              @click="editColor = color"
            ></button>
          </div>
          <div v-else class="preset-avatar-grid">
            <button
              v-for="avatar in presetAvatars"
              :key="avatar.id"
              :class="['preset-avatar-item', { selected: editAvatarUrl === avatar.url }]"
              :title="avatar.name"
              @click="editAvatarUrl = avatar.url"
            >
              <img :src="avatar.url" :alt="avatar.name" class="preset-avatar-img" />
            </button>
          </div>
        </div>
        <div class="dialog-actions">
          <button class="dialog-btn delete" @click="emit('delete-agent')">
            删除
          </button>
          <div class="flex-1"></div>
          <button class="dialog-btn cancel" @click="emit('update:showEditDialog', false)">取消</button>
          <button
            :class="['dialog-btn confirm', { disabled: !editName.trim() }]"
            :disabled="!editName.trim()"
            @click="emit('update-agent')"
          >
            保存
          </button>
        </div>
      </div>
    </div>
  </Transition>

  <Transition name="dialog-fade">
    <div v-if="showConfirmDialog" class="confirm-dialog-overlay" @click.self="emit('cancel')">
      <div class="confirm-dialog">
        <div class="confirm-dialog-icon">
          <AlertTriangle :size="24" />
        </div>
        <p class="confirm-dialog-message">{{ confirmMessage }}</p>
        <div class="confirm-dialog-actions">
          <button class="dialog-btn confirm" @click="emit('confirm')">
            确定
          </button>
          <button class="dialog-btn cancel" @click="emit('cancel')">取消</button>
        </div>
      </div>
    </div>
  </Transition>

  <Transition name="dialog-fade">
    <div v-if="showCreateGroupDialog" class="create-dialog-overlay" @click.self="emit('update:showCreateGroupDialog', false)">
      <div class="create-dialog">
        <h3>创建群组</h3>
        <div class="form-group">
          <label class="form-label">
            群组名称
            <span class="required-mark">*</span>
          </label>
          <input v-model="newGroupNameModel" type="text" class="form-input" placeholder="如: 项目讨论组" />
        </div>
        <div class="form-group">
          <label class="form-label">描述</label>
          <input v-model="newGroupDescModel" type="text" class="form-input" placeholder="群组用途描述" />
        </div>
        <div class="dialog-actions">
          <button class="dialog-btn cancel" @click="emit('update:showCreateGroupDialog', false)">取消</button>
          <button
            :class="['dialog-btn confirm', { disabled: !newGroupNameModel.trim() }]"
            :disabled="!newGroupNameModel.trim()"
            @click="emit('create-group')"
          >
            创建
          </button>
        </div>
      </div>
    </div>
  </Transition>

  <Transition name="dialog-fade">
    <div v-if="showAddAgentDialog" class="create-dialog-overlay" @click.self="emit('update:showAddAgentDialog', false)">
      <div class="create-dialog">
        <h3>添加 Agent 到群组</h3>
        <div v-if="availableAgentsForGroup.length === 0" class="dialog-empty">
          <Bot :size="24" />
          <p>所有 Agent 都已在群组中，或暂无可用 Agent</p>
        </div>
        <div v-else class="agent-select-list">
          <div
            v-for="agent in availableAgentsForGroup"
            :key="agent.id"
            :class="['agent-select-item', { selected: addAgentIdModel === agent.id }]"
            @click="addAgentIdModel = agent.id"
          >
            <div class="agent-select-avatar" :style="{ background: `color-mix(in srgb, ${agent.color} 8%, transparent)`, color: agent.color }">
              <img v-if="agent.avatar" :src="agent.avatar" class="agent-select-avatar-img" :alt="agent.name" />
              <Bot v-else :size="18" />
            </div>
            <div class="agent-select-info">
              <span class="agent-select-name">{{ agent.name }}</span>
              <span class="agent-select-desc">{{ agent.description || '暂无描述' }}</span>
            </div>
          </div>
        </div>
        <div v-if="addAgentIdModel" class="form-group">
          <label class="form-label">角色定位</label>
          <input v-model="addAgentRoleModel" type="text" class="form-input" placeholder="如: 调度员、数据专员、计算专员、审核专员" />
          <div class="role-suggestions" v-if="agentRoles.length > 0">
            <button
              v-for="role in agentRoles"
              :key="role.roleId"
              class="role-suggestion-chip"
              :style="{ background: `color-mix(in srgb, ${role.color} 8%, transparent)`, color: role.color }"
              @click="addAgentRoleModel = role.name"
            >
              {{ role.name }}
            </button>
          </div>
        </div>
        <div class="dialog-actions">
          <button class="dialog-btn cancel" @click="emit('update:showAddAgentDialog', false)">取消</button>
          <button
            :class="['dialog-btn confirm', { disabled: !addAgentIdModel }]"
            :disabled="!addAgentIdModel"
            @click="emit('add-agent-to-group')"
          >
            添加
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.create-dialog-overlay,
.confirm-dialog-overlay {
  background: var(--overlay-bg);
  backdrop-filter: blur(4px);
  padding: var(--space-4);
}

.create-dialog {
  width: 100%;
  max-width: 460px;
  max-height: 90vh;
  overflow-y: auto;
  background: var(--surface);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xl);
  padding: var(--space-6);
}

.create-dialog h3 {
  font-size: var(--text-xl);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--space-5);
}

.form-group {
  margin-bottom: var(--space-4);
}

.form-label {
  display: block;
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}

.required-mark {
  color: var(--lumi-danger);
  margin-left: 2px;
}

.form-input {
  width: 100%;
  padding: 10px var(--space-3);
  border-radius: var(--radius-md);
  border: 1px solid var(--workspace-border);
  background: var(--workspace-panel);
  color: var(--text-primary);
  font-size: var(--text-base);
  outline: none;
  transition: all var(--transition-fast);
}

.form-input:focus {
  border-color: var(--lumi-brand-border);
  background: var(--surface);
  box-shadow: 0 0 0 3px var(--lumi-brand-glow);
}

.form-textarea {
  resize: vertical;
  min-height: 100px;
  font-family: inherit;
  line-height: 1.5;
}

.color-picker {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.color-dot.active {
  border-color: var(--text-primary);
  transform: scale(1.1);
}

.avatar-mode-toggle {
  display: flex;
  gap: var(--space-1);
  margin-bottom: var(--space-3);
  background: var(--workspace-panel);
  border-radius: var(--radius-md);
  padding: 3px;
}

.mode-btn {
  flex: 1;
  padding: 7px var(--space-3);
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--text-secondary);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.mode-btn.active {
  background: var(--surface);
  color: var(--text-primary);
  box-shadow: var(--shadow-xs);
}

.preset-avatar-grid {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.preset-avatar-item {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-full);
  border: 2px solid transparent;
  padding: 0;
  cursor: pointer;
  transition: all var(--transition-normal);
  background: var(--bg-secondary);
  overflow: hidden;
}

.preset-avatar-item:hover {
  transform: scale(1.08);
}

.preset-avatar-item.selected {
  border-color: var(--lumi-brand);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--lumi-brand) 20%, transparent);
}

.preset-avatar-img {
  width: 100%;
  height: 100%;
  border-radius: inherit;
  object-fit: cover;
}

.dialog-btn {
  padding: 10px var(--space-5);
  border-radius: var(--radius-md);
  font-size: var(--text-base);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
  border: none;
}

.dialog-btn.cancel {
  color: var(--text-secondary);
  background: var(--workspace-panel);
}

.dialog-btn.cancel:hover {
  background: var(--workspace-hover);
}

.dialog-btn.confirm:hover:not(.disabled) {
  background: var(--lumi-brand-hover);
}

.dialog-btn.delete:hover {
  background: var(--task-red-soft);
}

.confirm-dialog {
  width: 100%;
  max-width: 380px;
  background: var(--surface);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xl);
  padding: var(--space-6);
  text-align: center;
}

.confirm-dialog-icon {
  width: 56px;
  height: 56px;
  border-radius: var(--radius-full);
  background: var(--lumi-accent-light);
  color: var(--lumi-accent);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto var(--space-4);
}

.confirm-dialog-message {
  font-size: var(--text-base);
  color: var(--text-primary);
  margin: 0 0 var(--space-5);
  line-height: 1.5;
}

.confirm-dialog-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
}

.dialog-empty {
  padding: var(--space-6) var(--space-4);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-muted);
}

.dialog-empty p {
  font-size: var(--text-sm);
  margin: 0;
  text-align: center;
}

.agent-select-list {
  max-height: 240px;
  overflow-y: auto;
  margin: 0 calc(-1 * var(--space-1)) var(--space-2);
  padding: 0 var(--space-1);
}

.agent-select-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: var(--space-2) 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.agent-select-item:hover {
  background: var(--workspace-hover);
}

.agent-select-item.selected {
  background: var(--lumi-brand-light);
}

.agent-select-avatar {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  overflow: hidden;
}

.agent-select-avatar-img {
  width: 100%;
  height: 100%;
  border-radius: inherit;
  object-fit: cover;
}

.agent-select-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.agent-select-name {
  font-size: var(--text-base);
  font-weight: 500;
  color: var(--text-primary);
}

.agent-select-desc {
  font-size: var(--text-xs);
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.role-suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
  margin-top: 6px;
}

.role-suggestion-chip {
  font-size: var(--text-xs);
  padding: 3px var(--space-2);
  border-radius: 10px;
  border: none;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.role-suggestion-chip:hover {
  transform: translateY(-1px);
}

.dialog-error {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: var(--space-3) 14px;
  background: var(--task-red-soft);
  border: 1px solid var(--task-red-border);
  border-radius: var(--radius-md);
  color: var(--lumi-danger);
  font-size: var(--text-base);
  font-weight: 500;
  margin-bottom: var(--space-4);
  box-shadow: 0 4px 12px var(--overlay-subtle);
}

.dialog-error svg {
  flex-shrink: 0;
}

.error-close {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--space-5);
  height: var(--space-5);
  border: none;
  background: var(--lumi-danger-light);
  border-radius: 4px;
  color: var(--lumi-danger);
  cursor: pointer;
  transition: all var(--duration-leave) var(--ease-default);
  margin-left: auto;
}

.error-close:hover {
  background: color-mix(in srgb, var(--lumi-danger), transparent 80%);
  transform: rotate(90deg);
}

.dialog-fade-enter-active,
.dialog-fade-leave-active {
  transition: all var(--duration-normal) var(--ease-default);
}

.dialog-fade-enter-from,
.dialog-fade-leave-to {
  opacity: 0;
}

.toast-slide-enter-active {
  transition: all var(--duration-normal) var(--ease-out-expo);
}

.toast-slide-leave-active {
  transition: all var(--duration-leave) ease-in;
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

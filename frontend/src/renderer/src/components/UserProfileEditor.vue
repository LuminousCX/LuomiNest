<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { User, Save, RotateCcw, Plus, X, Sparkles } from 'lucide-vue-next'
import { useApi } from '../composables/useApi'
import type { UserProfile } from '../types'

const { apiGet, apiPut, apiDelete } = useApi()

const profile = ref<UserProfile>({
  name: '',
  nickname: '',
  age: '',
  gender: '',
  occupation: '',
  location: '',
  timezone: '',
  language: '',
  interests: [],
  hobbies: [],
  preferences: {},
  notes: '',
  updated_at: ''
})

const loading = ref(false)
const saving = ref(false)
const newInterest = ref('')
const newHobby = ref('')
const newPrefKey = ref('')
const newPrefValue = ref('')

const hasProfile = computed(() => {
  return profile.value.name || profile.value.nickname || profile.value.occupation ||
    profile.value.location || profile.value.interests.length > 0 || profile.value.hobbies.length > 0
})

const loadProfile = async () => {
  loading.value = true
  try {
    const resp = await apiGet<{ profile: UserProfile }>('/memory/profile')
    if (resp.profile) {
      profile.value = {
        ...resp.profile,
        interests: resp.profile.interests || [],
        hobbies: resp.profile.hobbies || [],
        preferences: resp.profile.preferences || {}
      }
    }
  } catch (e) {
    console.error('Failed to load profile:', e)
  } finally {
    loading.value = false
  }
}

const saveProfile = async () => {
  saving.value = true
  try {
    await apiPut('/memory/profile', profile.value)
  } catch (e) {
    console.error('Failed to save profile:', e)
  } finally {
    saving.value = false
  }
}

const clearProfile = async () => {
  if (!confirm('确定要清空所有个人信息吗？')) return
  try {
    await apiDelete('/memory/profile')
    profile.value = {
      name: '',
      nickname: '',
      age: '',
      gender: '',
      occupation: '',
      location: '',
      timezone: '',
      language: '',
      interests: [],
      hobbies: [],
      preferences: {},
      notes: '',
      updated_at: ''
    }
  } catch (e) {
    console.error('Failed to clear profile:', e)
  }
}

const addInterest = () => {
  if (newInterest.value.trim()) {
    profile.value.interests.push(newInterest.value.trim())
    newInterest.value = ''
  }
}

const removeInterest = (index: number) => {
  profile.value.interests.splice(index, 1)
}

const addHobby = () => {
  if (newHobby.value.trim()) {
    profile.value.hobbies.push(newHobby.value.trim())
    newHobby.value = ''
  }
}

const removeHobby = (index: number) => {
  profile.value.hobbies.splice(index, 1)
}

const addPreference = () => {
  if (newPrefKey.value.trim() && newPrefValue.value.trim()) {
    profile.value.preferences[newPrefKey.value.trim()] = newPrefValue.value.trim()
    newPrefKey.value = ''
    newPrefValue.value = ''
  }
}

const removePreference = (key: string) => {
  delete profile.value.preferences[key]
}

onMounted(() => {
  loadProfile()
})
</script>

<template>
  <div class="profile-editor">
    <div class="profile-header">
      <div class="header-title">
        <User :size="18" />
        <span>个人信息</span>
        <span v-if="hasProfile" class="profile-badge">
          <Sparkles :size="12" />
          已设置
        </span>
      </div>
      <div class="header-actions">
        <button class="btn-clear" @click="clearProfile" :disabled="!hasProfile">
          <RotateCcw :size="14" />
          清空
        </button>
        <button class="btn-save" @click="saveProfile" :disabled="saving">
          <Save :size="14" />
          {{ saving ? '保存中...' : '保存' }}
        </button>
      </div>
    </div>

    <div class="profile-body" v-if="!loading">
      <div class="form-grid">
        <div class="form-group">
          <label>姓名</label>
          <input v-model="profile.name" type="text" placeholder="您的真实姓名" />
        </div>
        <div class="form-group">
          <label>昵称</label>
          <input v-model="profile.nickname" type="text" placeholder="您希望被称呼的名字" />
        </div>
        <div class="form-group">
          <label>年龄</label>
          <input v-model="profile.age" type="text" placeholder="年龄或年龄段" />
        </div>
        <div class="form-group">
          <label>性别</label>
          <select v-model="profile.gender">
            <option value="">请选择</option>
            <option value="男">男</option>
            <option value="女">女</option>
            <option value="其他">其他</option>
          </select>
        </div>
        <div class="form-group">
          <label>职业</label>
          <input v-model="profile.occupation" type="text" placeholder="您的职业" />
        </div>
        <div class="form-group">
          <label>所在地</label>
          <input v-model="profile.location" type="text" placeholder="城市或地区" />
        </div>
        <div class="form-group">
          <label>时区</label>
          <input v-model="profile.timezone" type="text" placeholder="如: UTC+8" />
        </div>
        <div class="form-group">
          <label>语言</label>
          <input v-model="profile.language" type="text" placeholder="常用语言" />
        </div>
      </div>

      <div class="form-section">
        <label>兴趣爱好</label>
        <div class="tag-input">
          <div class="tags">
            <span v-for="(interest, idx) in profile.interests" :key="idx" class="tag">
              {{ interest }}
              <button @click="removeInterest(idx)" class="tag-remove">
                <X :size="12" />
              </button>
            </span>
          </div>
          <div class="tag-add">
            <input
              v-model="newInterest"
              type="text"
              placeholder="添加兴趣..."
              @keydown.enter="addInterest"
            />
            <button @click="addInterest" :disabled="!newInterest.trim()">
              <Plus :size="14" />
            </button>
          </div>
        </div>
      </div>

      <div class="form-section">
        <label>爱好</label>
        <div class="tag-input">
          <div class="tags">
            <span v-for="(hobby, idx) in profile.hobbies" :key="idx" class="tag">
              {{ hobby }}
              <button @click="removeHobby(idx)" class="tag-remove">
                <X :size="12" />
              </button>
            </span>
          </div>
          <div class="tag-add">
            <input
              v-model="newHobby"
              type="text"
              placeholder="添加爱好..."
              @keydown.enter="addHobby"
            />
            <button @click="addHobby" :disabled="!newHobby.trim()">
              <Plus :size="14" />
            </button>
          </div>
        </div>
      </div>

      <div class="form-section">
        <label>偏好设置</label>
        <div class="pref-list">
          <div v-for="(value, key) in profile.preferences" :key="key" class="pref-item">
            <span class="pref-key">{{ key }}</span>
            <span class="pref-value">{{ value }}</span>
            <button @click="removePreference(key)" class="pref-remove">
              <X :size="12" />
            </button>
          </div>
        </div>
        <div class="pref-add">
          <input v-model="newPrefKey" type="text" placeholder="偏好名称" />
          <input v-model="newPrefValue" type="text" placeholder="偏好值" />
          <button @click="addPreference" :disabled="!newPrefKey.trim() || !newPrefValue.trim()">
            <Plus :size="14" />
            添加
          </button>
        </div>
      </div>

      <div class="form-section">
        <label>备注</label>
        <textarea
          v-model="profile.notes"
          placeholder="其他想让 AI 了解的信息..."
          rows="3"
        ></textarea>
      </div>
    </div>

    <div class="profile-loading" v-else>
      <div class="loading-spinner"></div>
      <span>加载中...</span>
    </div>
  </div>
</template>

<style scoped>
.profile-editor {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  overflow: hidden;
  max-height: 400px;
  display: flex;
  flex-direction: column;
}

.profile-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border);
  background: linear-gradient(135deg, rgba(13, 148, 136, 0.06), rgba(139, 92, 246, 0.04));
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}

.header-title svg {
  color: var(--lumi-primary);
}

.profile-badge {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  background: rgba(13, 148, 136, 0.1);
  color: var(--lumi-primary);
  font-weight: 500;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.btn-clear, .btn-save {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 12px;
  cursor: pointer;
  transition: all 200ms ease;
}

.btn-clear {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-muted);
}

.btn-clear:hover:not(:disabled) {
  background: var(--surface-hover);
  color: var(--text);
}

.btn-save {
  background: var(--lumi-primary);
  border: none;
  color: white;
}

.btn-save:hover:not(:disabled) {
  background: var(--lumi-primary-hover);
}

.btn-clear:disabled, .btn-save:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.profile-body {
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  overflow-y: auto;
  flex: 1;
  min-height: 0;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-group label {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 500;
}

.form-group input,
.form-group select {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  font-size: 13px;
  transition: all 200ms ease;
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px rgba(13, 148, 136, 0.1);
}

.form-group input::placeholder {
  color: var(--text-muted);
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.form-section > label {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 500;
}

.tag-input {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border-radius: 20px;
  background: rgba(139, 92, 246, 0.1);
  color: #a78bfa;
  font-size: 12px;
}

.tag-remove {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: transparent;
  border: none;
  color: inherit;
  cursor: pointer;
  transition: background 200ms ease;
}

.tag-remove:hover {
  background: rgba(139, 92, 246, 0.2);
}

.tag-add {
  display: flex;
  gap: 8px;
}

.tag-add input {
  flex: 1;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  font-size: 13px;
}

.tag-add input:focus {
  outline: none;
  border-color: var(--lumi-primary);
}

.tag-add button {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: var(--lumi-primary);
  border: none;
  color: white;
  cursor: pointer;
  transition: background 200ms ease;
}

.tag-add button:hover:not(:disabled) {
  background: var(--lumi-primary-hover);
}

.tag-add button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.pref-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.pref-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--bg);
  border: 1px solid var(--border);
}

.pref-key {
  font-size: 12px;
  color: var(--lumi-primary);
  font-weight: 500;
  min-width: 80px;
}

.pref-value {
  flex: 1;
  font-size: 13px;
  color: var(--text);
}

.pref-remove {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 200ms ease;
}

.pref-remove:hover {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.pref-add {
  display: flex;
  gap: 8px;
}

.pref-add input {
  flex: 1;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  font-size: 13px;
}

.pref-add input:focus {
  outline: none;
  border-color: var(--lumi-primary);
}

.pref-add button {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 14px;
  border-radius: 8px;
  background: var(--surface-hover);
  border: 1px solid var(--border);
  color: var(--text);
  font-size: 12px;
  cursor: pointer;
  transition: all 200ms ease;
}

.pref-add button:hover:not(:disabled) {
  background: var(--lumi-primary);
  border-color: var(--lumi-primary);
  color: white;
}

.pref-add button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.form-section textarea {
  padding: 12px;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  font-size: 13px;
  resize: vertical;
  min-height: 80px;
}

.form-section textarea:focus {
  outline: none;
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 3px rgba(13, 148, 136, 0.1);
}

.form-section textarea::placeholder {
  color: var(--text-muted);
}

.profile-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 40px;
  color: var(--text-muted);
}

.loading-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--border);
  border-top-color: var(--lumi-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>

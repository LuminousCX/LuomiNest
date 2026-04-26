<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { User, Save, RotateCcw, Plus, X, Sparkles, UserCircle, Heart, Briefcase, MapPin, Globe, Clock, FileText, Check } from 'lucide-vue-next'
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
      profile.value.name = resp.profile.name || ''
      profile.value.nickname = resp.profile.nickname || ''
      profile.value.age = resp.profile.age || ''
      profile.value.gender = resp.profile.gender || ''
      profile.value.occupation = resp.profile.occupation || ''
      profile.value.location = resp.profile.location || ''
      profile.value.timezone = resp.profile.timezone || ''
      profile.value.language = resp.profile.language || ''
      profile.value.interests = resp.profile.interests || []
      profile.value.hobbies = resp.profile.hobbies || []
      profile.value.preferences = resp.profile.preferences || {}
      profile.value.notes = resp.profile.notes || ''
      profile.value.updated_at = resp.profile.updated_at || ''
    }
  } catch (e) {
    console.error('Failed to load profile:', e)
  } finally {
    loading.value = false
  }
}

const saveSuccess = ref(false)

const saveProfile = async () => {
  saving.value = true
  saveSuccess.value = false
  try {
    await apiPut('/memory/profile', profile.value)
    saveSuccess.value = true
    setTimeout(() => saveSuccess.value = false, 2000)
  } catch (e) {
    console.error('Failed to save profile:', e)
    alert('保存失败，请检查网络连接')
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
  <div class="profile-view">
    <div class="profile-header">
      <div class="header-left">
        <UserCircle :size="22" />
        <h2>个人信息</h2>
        <span v-if="hasProfile" class="header-badge">
          <Sparkles :size="12" />
          已设置
        </span>
      </div>
      <div class="header-actions">
        <button class="btn-clear" @click="clearProfile" :disabled="!hasProfile">
          <RotateCcw :size="14" />
          清空
        </button>
        <button class="btn-save" @click="saveProfile" :disabled="saving" :class="{ 'btn-success': saveSuccess }">
          <Check v-if="saveSuccess" :size="14" />
          <Save v-else :size="14" />
          {{ saveSuccess ? '已保存' : (saving ? '保存中...' : '保存') }}
        </button>
      </div>
    </div>

    <div class="profile-content" v-if="!loading">
      <div class="profile-card">
        <div class="card-header">
          <User :size="16" />
          <span>基本信息</span>
        </div>
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
        </div>
      </div>

      <div class="profile-card">
        <div class="card-header">
          <Briefcase :size="16" />
          <span>工作与生活</span>
        </div>
        <div class="form-grid">
          <div class="form-group">
            <label>职业</label>
            <input v-model="profile.occupation" type="text" placeholder="您的职业" />
          </div>
          <div class="form-group">
            <label>所在地</label>
            <div class="input-with-icon">
              <MapPin :size="14" />
              <input v-model="profile.location" type="text" placeholder="城市或地区" />
            </div>
          </div>
          <div class="form-group">
            <label>时区</label>
            <div class="input-with-icon">
              <Clock :size="14" />
              <input v-model="profile.timezone" type="text" placeholder="如: UTC+8" />
            </div>
          </div>
          <div class="form-group">
            <label>语言</label>
            <div class="input-with-icon">
              <Globe :size="14" />
              <input v-model="profile.language" type="text" placeholder="常用语言" />
            </div>
          </div>
        </div>
      </div>

      <div class="profile-card">
        <div class="card-header">
          <Heart :size="16" />
          <span>兴趣爱好</span>
        </div>
        <div class="form-section">
          <label>兴趣</label>
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
              <input v-model="newInterest" type="text" placeholder="添加兴趣..." @keydown.enter="addInterest" />
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
              <input v-model="newHobby" type="text" placeholder="添加爱好..." @keydown.enter="addHobby" />
              <button @click="addHobby" :disabled="!newHobby.trim()">
                <Plus :size="14" />
              </button>
            </div>
          </div>
        </div>
      </div>

      <div class="profile-card">
        <div class="card-header">
          <FileText :size="16" />
          <span>偏好与备注</span>
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
          <textarea v-model="profile.notes" placeholder="其他想让 AI 了解的信息..." rows="4"></textarea>
        </div>
      </div>
    </div>

    <div class="profile-loading" v-else>
      <div class="loading-spinner"></div>
      <span>加载中...</span>
    </div>
  </div>
</template>

<style scoped>
.profile-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg);
  color: var(--text);
  overflow: hidden;
}

.profile-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  background: var(--surface);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-left h2 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text);
}

.header-left svg {
  color: var(--lumi-primary);
}

.header-badge {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 20px;
  background: rgba(13, 148, 136, 0.1);
  color: var(--lumi-primary);
  font-weight: 500;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.btn-clear, .btn-save {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 10px;
  font-size: 13px;
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

.btn-save.btn-success {
  background: #22c55e;
}

.btn-save.btn-success:hover {
  background: #16a34a;
}

.profile-content {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 800px;
}

.profile-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
}

.card-header svg {
  color: var(--lumi-primary);
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
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

.input-with-icon {
  position: relative;
  display: flex;
  align-items: center;
}

.input-with-icon svg {
  position: absolute;
  left: 12px;
  color: var(--text-muted);
  pointer-events: none;
}

.input-with-icon input {
  width: 100%;
  padding-left: 34px;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 16px;
}

.form-section:first-of-type {
  margin-top: 0;
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
  padding: 60px;
  color: var(--text-muted);
}

.loading-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--border);
  border-top-color: var(--lumi-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>

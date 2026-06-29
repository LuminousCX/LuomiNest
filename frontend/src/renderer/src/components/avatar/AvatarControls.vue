<script setup lang="ts">
import {
  Heart,
  Volume2,
  Send,
  Square,
  MessageCircle
} from 'lucide-vue-next'
import LumiButton from '../common/LumiButton.vue'
import LumiCard from '../common/LumiCard.vue'
import type { AvatarEmotion, AvatarMode, IdleAnimation } from './types'

const props = defineProps<{
  currentMode: string
  avatarModes: AvatarMode[]
  chatText: string
  isChatStreaming: boolean
  isChatSynthesizing: boolean
  isChatSpeaking: boolean
  chatCurrentEmotion: string | null
  ttsText: string
  isAvatarSpeaking: boolean
  isAvatarSynthesizing: boolean
  emotions: AvatarEmotion[]
  currentEmotionLocal: AvatarEmotion
  expressionValue: number
  idleAnimations: IdleAnimation[]
}>()

const emit = defineEmits<{
  'select-mode': [modeId: string]
  'update:chat-text': [value: string]
  'chat-send': []
  'chat-keydown': [event: KeyboardEvent]
  'update:tts-text': [value: string]
  'tts-send': []
  'tts-keydown': [event: KeyboardEvent]
  'select-emotion': [emotion: AvatarEmotion]
}>()
</script>

<template>
  <div class="stage-controls">
    <div class="controls-top-row">
      <div class="mode-switcher">
        <button
          v-for="mode in props.avatarModes"
          :key="mode.id"
          :class="['mode-btn', { active: props.currentMode === mode.id }]"
          @click="emit('select-mode', mode.id)"
        >
          <span class="mode-name">{{ mode.label }}</span>
          <span class="mode-desc">{{ mode.desc }}</span>
        </button>
      </div>

      <div class="tts-inline">
        <div class="chat-input-row">
          <textarea
            :value="props.chatText"
            class="chat-input"
            placeholder="Chat with avatar... (Enter to send)"
            rows="1"
            :disabled="props.isChatSynthesizing"
            @input="emit('update:chat-text', ($event.target as HTMLTextAreaElement).value)"
            @keydown="emit('chat-keydown', $event)"
          ></textarea>
          <LumiButton
            :variant="props.isChatStreaming ? 'danger' : 'primary'"
            size="sm"
            icon-only
            :loading="props.isChatSynthesizing"
            :disabled="props.isChatSynthesizing || (!props.chatText.trim() && !props.isChatStreaming)"
            :aria-label="props.isChatStreaming ? 'Stop' : 'Send'"
            @click="emit('chat-send')"
          >
            <template #icon>
              <Square v-if="props.isChatStreaming" :size="14" />
              <MessageCircle v-else :size="14" />
            </template>
          </LumiButton>
        </div>
        <div class="tts-status-row">
          <MessageCircle :size="11" />
          <span v-if="props.isChatStreaming" class="tts-status-text synthesizing">Streaming</span>
          <span v-else-if="props.isChatSpeaking" class="tts-status-text speaking">Speaking</span>
          <span v-else-if="props.isChatSynthesizing" class="tts-status-text synthesizing">Synthesizing</span>
          <span v-else class="tts-status-text">Avatar Chat</span>
          <span v-if="props.chatCurrentEmotion" class="tts-emotion-tag">{{ props.chatCurrentEmotion }}</span>
        </div>
        <div class="tts-input-row">
          <textarea
            :value="props.ttsText"
            class="tts-input"
            placeholder="Or type text to speak directly..."
            rows="1"
            :disabled="props.isAvatarSynthesizing"
            @input="emit('update:tts-text', ($event.target as HTMLTextAreaElement).value)"
            @keydown="emit('tts-keydown', $event)"
          ></textarea>
          <LumiButton
            :variant="props.isAvatarSpeaking ? 'danger' : 'primary'"
            size="sm"
            icon-only
            :loading="props.isAvatarSynthesizing"
            :disabled="props.isAvatarSynthesizing || (!props.ttsText.trim() && !props.isAvatarSpeaking)"
            :aria-label="props.isAvatarSpeaking ? 'Stop' : 'Speak'"
            @click="emit('tts-send')"
          >
            <template #icon>
              <Square v-if="props.isAvatarSpeaking" :size="14" />
              <Send v-else :size="14" />
            </template>
          </LumiButton>
        </div>
      </div>
    </div>

    <div class="controls-panels-row">
      <LumiCard class="emotion-panel" padding="md">
        <div class="panel-title">
          <Heart :size="14" />
          <span>Emotion</span>
          <span class="expression-value">PAD: {{ props.expressionValue > 0 ? '+' : '' }}{{ props.expressionValue.toFixed(1) }}</span>
        </div>
        <div class="emotion-grid">
          <button
            v-for="emo in props.emotions"
            :key="emo.id"
            :class="['emo-btn', { active: props.currentEmotionLocal.id === emo.id }]"
            :style="{ '--emo-color': emo.color }"
            @click="emit('select-emotion', emo)"
          >
            <component :is="emo.icon" :size="18" />
            <span>{{ emo.label }}</span>
          </button>
        </div>
      </LumiCard>

      <LumiCard class="idle-panel" padding="md">
        <div class="panel-title">
          <Volume2 :size="14" />
          <span>Idle Animation</span>
        </div>
        <div class="idle-list">
          <div
            v-for="(anim, idx) in props.idleAnimations"
            :key="idx"
            class="idle-item"
          >
            <div class="idle-info">
              <span class="idle-name">{{ anim.name }}</span>
              <span :class="['idle-status', anim.status]">{{ anim.status === 'running' ? 'Running' : 'Paused' }}</span>
            </div>
            <div class="idle-bar">
              <div
                class="idle-fill"
                :class="anim.status"
                :style="{ width: anim.progress + '%' }"
              ></div>
            </div>
          </div>
        </div>
      </LumiCard>
    </div>
  </div>
</template>

<style scoped>
.stage-controls {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5);
  flex-shrink: 0;
  position: relative;
}

.stage-controls::before {
  content: '';
  position: absolute;
  top: 0;
  left: var(--space-5);
  right: var(--space-5);
  height: 1px;
  background: var(--divider-soft);
}

.controls-top-row {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.controls-panels-row {
  display: flex;
  gap: var(--space-3);
  flex-wrap: wrap;
  align-items: flex-start;
}

.mode-switcher {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.mode-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
  padding: var(--space-2) 14px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-light);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-in-out);
  white-space: nowrap;
}

.mode-btn:hover {
  background: var(--surface-hover);
  color: var(--text);
}

.mode-btn.active {
  background: var(--lumi-primary-light);
  border-color: var(--lumi-primary);
  color: var(--lumi-primary);
}

.mode-name {
  font-size: var(--text-base);
  font-weight: 600;
}

.mode-desc {
  font-size: var(--text-xs);
  opacity: 0.55;
}

.emotion-panel,
.idle-panel {
  flex: 1;
  min-width: 180px;
}

.tts-inline {
  flex: 1;
  min-width: 240px;
  max-width: 420px;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.tts-inline .tts-input-row {
  display: flex;
  gap: 6px;
  align-items: flex-end;
}

.tts-inline .chat-input-row {
  display: flex;
  gap: 6px;
  align-items: flex-end;
  margin-bottom: var(--space-1);
}

.tts-inline .chat-input {
  flex: 1;
  min-height: var(--space-7);
  max-height: var(--space-10);
  padding: 6px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--lumi-primary-border);
  background: var(--surface);
  color: var(--text);
  font-size: var(--text-sm);
  font-family: var(--font-sans);
  line-height: 1.4;
  resize: none;
  transition: border-color var(--duration-normal) var(--ease-in-out);
  outline: none;
}

.tts-inline .chat-input::placeholder {
  color: var(--text-muted);
  opacity: 0.6;
}

.tts-inline .chat-input:focus {
  border-color: var(--lumi-primary);
  box-shadow: 0 0 0 var(--space-1) var(--lumi-primary-subtle);
}

.tts-inline .chat-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.tts-inline .chat-send-btn {
  width: var(--space-7);
  height: var(--space-7);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--lumi-primary);
  color: var(--text-inverse);
  cursor: pointer;
  flex-shrink: 0;
  transition: all var(--duration-normal) var(--ease-in-out);
}

.tts-inline .chat-send-btn:hover:not(:disabled) {
  background: var(--lumi-primary-hover);
  transform: translateY(-1px);
  box-shadow: 0 2px 8px var(--lumi-primary-border);
}

.tts-inline .chat-send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.tts-inline .chat-send-btn.streaming {
  background: var(--lumi-accent);
}

.tts-inline .chat-send-btn.streaming:hover:not(:disabled) {
  background: var(--lumi-danger-hover);
}

.tts-emotion-tag {
  margin-left: auto;
  font-size: var(--text-2xs);
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  background: var(--lumi-primary-subtle);
  color: var(--lumi-primary);
  font-weight: 500;
  text-transform: capitalize;
}

.tts-inline .tts-input {
  flex: 1;
  min-height: var(--space-7);
  max-height: var(--space-10);
  padding: 6px 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
  background: var(--surface);
  color: var(--text);
  font-size: var(--text-sm);
  font-family: var(--font-sans);
  line-height: 1.4;
  resize: none;
  transition: border-color var(--duration-normal) var(--ease-in-out);
  outline: none;
}

.tts-inline .tts-input::placeholder {
  color: var(--text-muted);
  opacity: 0.6;
}

.tts-inline .tts-input:focus {
  border-color: var(--lumi-primary-border);
  box-shadow: 0 0 0 var(--space-1) var(--lumi-primary-subtle);
}

.tts-inline .tts-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.tts-inline .tts-send-btn {
  width: var(--space-7);
  height: var(--space-7);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--lumi-primary);
  color: var(--text-inverse);
  cursor: pointer;
  flex-shrink: 0;
  transition: all var(--duration-normal) var(--ease-in-out);
}

.tts-inline .tts-send-btn:hover:not(:disabled) {
  background: var(--lumi-primary-hover);
  transform: translateY(-1px);
  box-shadow: 0 2px 8px var(--lumi-primary-border);
}

.tts-inline .tts-send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.tts-inline .tts-send-btn.speaking {
  background: var(--lumi-accent);
}

.tts-inline .tts-send-btn.speaking:hover:not(:disabled) {
  background: var(--lumi-danger-hover);
}

.tts-inline .tts-send-btn.loading {
  background: var(--lumi-primary-soft);
}

.tts-loading-spin {
  animation: spin 1s linear infinite;
}

.tts-status-row {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-xs);
  color: var(--text-muted);
  padding: 0 2px;
}

.tts-status-text {
  font-weight: 500;
}

.tts-status-text.speaking {
  color: var(--lumi-success);
}

.tts-status-text.synthesizing {
  color: var(--lumi-amber-dark);
}

.tts-inline .tts-error {
  font-size: var(--text-2xs);
  color: var(--lumi-accent);
  padding: 0 2px;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: var(--space-2);
}

.expression-value {
  margin-left: auto;
  font-family: monospace;
  font-size: var(--text-sm);
  color: var(--lumi-primary);
  opacity: 0.7;
}

.emotion-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.emo-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: var(--space-2) 10px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-in-out);
  font-size: var(--text-xs);
}

.emo-btn:hover {
  background: color-mix(in srgb, var(--emo-color, var(--text-muted)) 8%, transparent);
  color: var(--text);
  transform: translateY(-2px);
}

.emo-btn.active {
  background: color-mix(in srgb, var(--emo-color, var(--text-muted)) 14%, transparent);
  border-color: var(--emo-color, var(--lumi-primary));
  color: var(--emo-color, var(--lumi-primary));
  box-shadow: 0 2px 12px color-mix(in srgb, var(--emo-color, var(--text-muted)) 18%, transparent);
}

.idle-list {
  display: flex;
  flex-direction: column;
}

.idle-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-1) 0;
}

.idle-info {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: var(--space-4);
}

.idle-name {
  font-size: var(--text-xs);
  color: var(--text);
  line-height: 1.2;
}

.idle-status {
  font-size: var(--text-2xs);
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  line-height: 1.4;
}

.idle-status.running {
  background: var(--task-green-soft);
  color: var(--lumi-success);
}

.idle-status.paused {
  background: var(--overlay-subtle);
  color: var(--text-muted);
}

.idle-bar {
  height: 3px;
  background: var(--border);
  border-radius: var(--radius-xs);
  overflow: hidden;
}

.idle-fill {
  height: 100%;
  border-radius: var(--radius-xs);
  transition: width 1000ms ease-in-out;
}

.idle-fill.running {
  background: linear-gradient(90deg, var(--lumi-primary), var(--lumi-success));
  animation: bar-pulse 2s ease-in-out infinite;
}

@keyframes bar-pulse {
  0%, 100% { opacity: 0.7; }
  50% { opacity: 1; }
}
</style>

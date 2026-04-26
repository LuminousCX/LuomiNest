import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface AvatarEmotion {
  id: string
  label: string
  intensity: number
}

export interface AvatarPadVector {
  pleasure: number
  arousal: number
  dominance: number
}

export const AVATAR_EMOTIONS = [
  { id: 'happy', label: 'Happy', color: '#f59e0b' },
  { id: 'sad', label: 'Sad', color: '#6366f1' },
  { id: 'neutral', label: 'Neutral', color: '#8b5cf6' },
  { id: 'love', label: 'Love', color: '#ec4899' },
  { id: 'surprise', label: 'Surprise', color: '#22c55e' },
  { id: 'angry', label: 'Angry', color: '#ef4444' },
  { id: 'think', label: 'Think', color: '#3b82f6' },
  { id: 'awkward', label: 'Awkward', color: '#f97316' },
  { id: 'curious', label: 'Curious', color: '#06b6d4' }
] as const

export const AVATAR_LIP_SYNC_PARAMS = {
  mouthOpenY: 'ParamMouthOpenY',
  mouthForm: 'ParamMouthForm'
} as const

export const AVATAR_FACE_PARAMS = {
  angleX: 'ParamAngleX',
  angleY: 'ParamAngleY',
  angleZ: 'ParamAngleZ',
  eyeLOpen: 'ParamEyeLOpen',
  eyeROpen: 'ParamEyeROpen',
  eyeBallX: 'ParamEyeBallX',
  eyeBallY: 'ParamEyeBallY',
  browLY: 'ParamBrowLY',
  browRY: 'ParamBrowRY',
  browLAngle: 'ParamBrowLAngle',
  browRAngle: 'ParamBrowRAngle',
  browLForm: 'ParamBrowLForm',
  browRForm: 'ParamBrowRForm',
  mouthOpenY: 'ParamMouthOpenY',
  mouthForm: 'ParamMouthForm',
  cheek: 'ParamCheek',
  breath: 'ParamBreath'
} as const

export const AVATAR_BODY_PARAMS = {
  bodyAngleX: 'ParamBodyAngleX',
  bodyAngleY: 'ParamBodyAngleY',
  bodyAngleZ: 'ParamBodyAngleZ'
} as const

export const useAvatarControlStore = defineStore('avatarControl', () => {
  const currentEmotion = ref<AvatarEmotion>({ id: 'neutral', label: 'Neutral', intensity: 0 })
  const padVector = ref<AvatarPadVector>({ pleasure: 0, arousal: 0, dominance: 0 })
  const isDesktopPetRunning = ref(false)
  const currentModelName = ref('')
  const availableMotions = ref<string[]>([])
  const availableExpressions = ref<string[]>([])
  const lipSyncValue = ref(0)

  const emotionLabel = computed(() => {
    const found = AVATAR_EMOTIONS.find(e => e.id === currentEmotion.value.id)
    return found?.label ?? 'Neutral'
  })

  const triggerMotion = async (group: string, index: number = 0): Promise<boolean> => {
    try {
      if (isDesktopPetRunning.value) {
        return await window.api.desktopPet.triggerMotion(group, index)
      }
      return false
    } catch {
      return false
    }
  }

  const triggerExpression = async (name: string): Promise<boolean> => {
    try {
      currentEmotion.value = { id: name, label: name, intensity: 0.5 }
      if (isDesktopPetRunning.value) {
        return await window.api.desktopPet.triggerExpression(name)
      }
      return false
    } catch {
      return false
    }
  }

  const driveEmotion = async (emotionId: string, intensity: number = 0.5): Promise<boolean> => {
    currentEmotion.value = { id: emotionId, label: emotionId, intensity }
    return triggerExpression(emotionId)
  }

  const drivePadEmotion = async (pleasure: number, arousal: number, dominance: number): Promise<boolean> => {
    padVector.value = { pleasure, arousal, dominance }
    try {
      if (isDesktopPetRunning.value) {
        return await (window.api as any).desktopPet.drivePadEmotion(pleasure, arousal, dominance)
      }
      return false
    } catch {
      return false
    }
  }

  const driveLipSync = async (value: number): Promise<boolean> => {
    lipSyncValue.value = Math.max(0, Math.min(1, value))
    try {
      if (isDesktopPetRunning.value) {
        return await (window.api as any).desktopPet.driveLipSync(lipSyncValue.value)
      }
      return false
    } catch {
      return false
    }
  }

  const setCoreParam = async (paramId: string, value: number): Promise<boolean> => {
    try {
      if (isDesktopPetRunning.value) {
        return await (window.api as any).desktopPet.setCoreParam(paramId, value)
      }
      return false
    } catch {
      return false
    }
  }

  const setModelPosition = async (x: number, y: number): Promise<boolean> => {
    try {
      if (isDesktopPetRunning.value) {
        return await (window.api as any).desktopPet.setPosition(x, y)
      }
      return false
    } catch {
      return false
    }
  }

  const setModelScale = async (scale: number): Promise<boolean> => {
    try {
      if (isDesktopPetRunning.value) {
        return await (window.api as any).desktopPet.setScale(scale)
      }
      return false
    } catch {
      return false
    }
  }

  const openDesktopPet = async (modelInfo?: any): Promise<boolean> => {
    try {
      await window.api.desktopPet.open(modelInfo)
      isDesktopPetRunning.value = true
      return true
    } catch {
      return false
    }
  }

  const closeDesktopPet = async (): Promise<boolean> => {
    try {
      await window.api.desktopPet.close()
      isDesktopPetRunning.value = false
      return true
    } catch {
      return false
    }
  }

  const checkDesktopPetStatus = async () => {
    try {
      isDesktopPetRunning.value = await window.api.desktopPet.isRunning()
    } catch {
      isDesktopPetRunning.value = false
    }
  }

  const getModelCapabilities = async () => {
    try {
      if (isDesktopPetRunning.value) {
        const caps = await (window.api as any).desktopPet.getModelCapabilities()
        if (caps) {
          availableMotions.value = caps.motions || []
          availableExpressions.value = caps.expressions || []
          currentModelName.value = caps.modelName || ''
        }
      }
    } catch {
    }
  }

  return {
    currentEmotion,
    padVector,
    isDesktopPetRunning,
    currentModelName,
    availableMotions,
    availableExpressions,
    lipSyncValue,
    emotionLabel,
    triggerMotion,
    triggerExpression,
    driveEmotion,
    drivePadEmotion,
    driveLipSync,
    setCoreParam,
    setModelPosition,
    setModelScale,
    openDesktopPet,
    closeDesktopPet,
    checkDesktopPetStatus,
    getModelCapabilities
  }
})

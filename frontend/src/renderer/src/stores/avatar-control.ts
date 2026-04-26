import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export type AvatarCoreParamId =
  | 'ParamAngleX' | 'ParamAngleY' | 'ParamAngleZ'
  | 'ParamEyeLOpen' | 'ParamEyeROpen'
  | 'ParamEyeBallX' | 'ParamEyeBallY'
  | 'ParamBrowLY' | 'ParamBrowRY'
  | 'ParamBrowLAngle' | 'ParamBrowRAngle'
  | 'ParamBrowLForm' | 'ParamBrowRForm'
  | 'ParamMouthOpenY' | 'ParamMouthForm'
  | 'ParamCheek' | 'ParamBreath'
  | 'ParamBodyAngleX' | 'ParamBodyAngleY' | 'ParamBodyAngleZ'

const AVATAR_CORE_PARAM_WHITELIST = new Set<string>([
  'ParamAngleX', 'ParamAngleY', 'ParamAngleZ',
  'ParamEyeLOpen', 'ParamEyeROpen',
  'ParamEyeBallX', 'ParamEyeBallY',
  'ParamBrowLY', 'ParamBrowRY',
  'ParamBrowLAngle', 'ParamBrowRAngle',
  'ParamBrowLForm', 'ParamBrowRForm',
  'ParamMouthOpenY', 'ParamMouthForm',
  'ParamCheek', 'ParamBreath',
  'ParamBodyAngleX', 'ParamBodyAngleY', 'ParamBodyAngleZ'
])

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

export interface PetModelInfo {
  id: string
  name: string
  url: string
  scale: number
  type: string
  tags: string[]
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
        const result = await window.api.desktopPet.triggerMotion(group, index)
        return result?.success === true
      }
      return false
    } catch (error: unknown) {
      console.error('[LuomiNestAvatarControl] triggerMotion failed', { group, index, error })
      return false
    }
  }

  const triggerExpression = async (name: string, intensity: number = 0.5): Promise<boolean> => {
    try {
      if (isDesktopPetRunning.value) {
        const result = await window.api.desktopPet.triggerExpression(name)
        if (result?.success === true) {
          currentEmotion.value = { id: name, label: name, intensity }
          return true
        }
        return false
      }
      return false
    } catch (error: unknown) {
      console.error('[LuomiNestAvatarControl] triggerExpression failed', { name, intensity, error })
      return false
    }
  }

  const driveEmotion = async (emotionId: string, intensity: number = 0.5): Promise<boolean> => {
    const result = await triggerExpression(emotionId, intensity)
    if (result) {
      currentEmotion.value = { id: emotionId, label: emotionId, intensity }
    }
    return result
  }

  const drivePadEmotion = async (pleasure: number, arousal: number, dominance: number): Promise<boolean> => {
    try {
      if (isDesktopPetRunning.value) {
        const result = await window.api.desktopPet.drivePadEmotion(pleasure, arousal, dominance)
        if (result?.success === true) {
          padVector.value = { pleasure, arousal, dominance }
          return true
        }
        return false
      }
      return false
    } catch (error: unknown) {
      console.error('[LuomiNestAvatarControl] drivePadEmotion failed', { pleasure, arousal, dominance, error })
      return false
    }
  }

  const driveLipSync = async (value: number): Promise<boolean> => {
    const clampedValue = Math.max(0, Math.min(1, value))
    try {
      if (isDesktopPetRunning.value) {
        const result = await window.api.desktopPet.driveLipSync(clampedValue)
        if (result?.success === true) {
          lipSyncValue.value = clampedValue
          return true
        }
        return false
      }
      return false
    } catch (error: unknown) {
      console.error('[LuomiNestAvatarControl] driveLipSync failed', { value, error })
      return false
    }
  }

  const setCoreParam = async (paramId: AvatarCoreParamId | string, value: number): Promise<boolean> => {
    if (!AVATAR_CORE_PARAM_WHITELIST.has(paramId)) {
      console.warn('[LuomiNestAvatarControl] setCoreParam rejected: param not in whitelist', { paramId })
      return false
    }
    try {
      if (isDesktopPetRunning.value) {
        const result = await window.api.desktopPet.setCoreParam(paramId, value)
        return result?.success === true
      }
      return false
    } catch (error: unknown) {
      console.error('[LuomiNestAvatarControl] setCoreParam failed', { paramId, value, error })
      return false
    }
  }

  const setModelPosition = async (x: number, y: number): Promise<boolean> => {
    try {
      if (isDesktopPetRunning.value) {
        const result = await window.api.desktopPet.setPosition(x, y)
        return result?.success === true
      }
      return false
    } catch (error: unknown) {
      console.error('[LuomiNestAvatarControl] setModelPosition failed', { x, y, error })
      return false
    }
  }

  const setModelScale = async (scale: number): Promise<boolean> => {
    try {
      if (isDesktopPetRunning.value) {
        const result = await window.api.desktopPet.setScale(scale)
        return result?.success === true
      }
      return false
    } catch (error: unknown) {
      console.error('[LuomiNestAvatarControl] setModelScale failed', { scale, error })
      return false
    }
  }

  const openDesktopPet = async (modelInfo?: PetModelInfo): Promise<boolean> => {
    try {
      const res = await window.api.desktopPet.open(modelInfo)
      if (res.success) {
        isDesktopPetRunning.value = await window.api.desktopPet.isRunning()
      }
      return res.success
    } catch (error: unknown) {
      console.error('[LuomiNestAvatarControl] openDesktopPet failed', { modelInfo, error })
      isDesktopPetRunning.value = false
      return false
    }
  }

  const closeDesktopPet = async (): Promise<boolean> => {
    try {
      const res = await window.api.desktopPet.close()
      if (res.success) {
        isDesktopPetRunning.value = await window.api.desktopPet.isRunning()
      }
      return res.success
    } catch (error: unknown) {
      console.error('[LuomiNestAvatarControl] closeDesktopPet failed', error)
      isDesktopPetRunning.value = false
      return false
    }
  }

  const checkDesktopPetStatus = async () => {
    try {
      isDesktopPetRunning.value = await window.api.desktopPet.isRunning()
    } catch (error: unknown) {
      console.error('[LuomiNestAvatarControl] checkDesktopPetStatus failed', error)
      isDesktopPetRunning.value = false
    }
  }

  const getModelCapabilities = async () => {
    try {
      if (isDesktopPetRunning.value) {
        const caps = await window.api.desktopPet.getModelCapabilities()
        if (caps) {
          availableMotions.value = caps.motions || []
          availableExpressions.value = caps.expressions || []
          currentModelName.value = caps.modelName || ''
        }
      }
    } catch (error: unknown) {
      console.error('[LuomiNestAvatarControl] getModelCapabilities failed', error)
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

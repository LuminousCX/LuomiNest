/**
 * usePngTuber - PNG Tuber 渲染器
 *
 * 基于 PixiJS AnimatedSprite 实现 PNG Tuber 模型渲染。
 *
 * 设计原则：
 * - 参照 OpenAI Codex Pet 的 spritesheet 格式（1536×1872 / 8列×9行 / 每帧 192×208）
 * - 通过 luominest-avatar:// 协议加载 manifest.json + spritesheet.png
 * - 9 状态机：idle / running-right / running-left / waving / jumping / failed / waiting / running / review
 * - 复用现有 PixiJS 基础设施（与 Live2D / Pixel 共享 PIXI.Application）
 * - 不支持的能力（focusTracking / padEmotion / viseme）静默忽略
 * - 颜色不硬编码：spritesheet 中的颜色由素材决定，渲染器只做帧切换
 *
 * Manifest 格式（由 generate-png-tuber-spritesheet.mjs 生成）：
 * ```json
 * {
 *   "schema_version": "1.0",
 *   "name": "codex-pet",
 *   "type": "png",
 *   "format": "spritesheet",
 *   "sheet": {
 *     "image": "spritesheet.png",
 *     "width": 1536, "height": 1872,
 *     "frame_width": 192, "frame_height": 208,
 *     "cols": 8, "rows": 9
 *   },
 *   "states": [
 *     { "name": "idle", "row": 0, "frames": 8, "fps": 4, "loop": true, "next": null },
 *     ...
 *   ],
 *   "emotion_map": { "happy": "waving", "sad": "failed", ... },
 *   "default_state": "idle"
 * }
 * ```
 *
 * 模型加载流程：
 * 1. fetch manifest.json（luominest-avatar://png/{model}/manifest.json）
 * 2. 解析 spritesheet 相对路径，拼接成完整 URL
 * 3. PIXI.BaseTexture.from 加载 spritesheet
 * 4. 按状态切割帧（每状态一行，COLS 帧）
 * 5. 创建 AnimatedSprite，按状态切换 textures
 */
import { ref, type Ref } from 'vue'
import { Application, AnimatedSprite, BaseTexture, Rectangle, Texture } from 'pixi.js'
import { createLuomiNestRendererLogger } from '@/utils/logger'
import type { AvatarCapability, AvatarRendererType } from '@/types/avatar'
import type { IAvatarRenderer } from './IAvatarRenderer'

const logger = createLuomiNestRendererLogger('PngTuber')

// ---------------------------------------------------------------------------
// 默认配置（与 Codex Pet 规格一致）
// ---------------------------------------------------------------------------

const DEFAULT_FRAME_WIDTH = 192
const DEFAULT_FRAME_HEIGHT = 208
const DEFAULT_COLS = 8
const DEFAULT_CANVAS_SIZE = 256  // 渲染画布大小（ spritesheet 帧会缩放到此尺寸）

// ---------------------------------------------------------------------------
// Manifest 类型定义
// ---------------------------------------------------------------------------

interface PngTuberManifestSheet {
  image: string
  width: number
  height: number
  frame_width: number
  frame_height: number
  cols: number
  rows: number
}

interface PngTuberManifestState {
  name: string
  row: number
  frames: number
  fps: number
  loop: boolean
  next: string | null
}

interface PngTuberManifest {
  schema_version: string
  name: string
  display_name?: string
  type: 'png'
  format: 'spritesheet'
  sheet: PngTuberManifestSheet
  states: PngTuberManifestState[]
  emotion_map: Record<string, string>
  default_state: string
  colors?: Record<string, string>
}

// ---------------------------------------------------------------------------
// 渲染器状态
// ---------------------------------------------------------------------------

export interface PngTuberState {
  isReady: boolean
  isLoading: boolean
  error: string | null
  currentState: string
  availableStates: string[]
  modelName: string
}

// ---------------------------------------------------------------------------
// URL 解析工具
// ---------------------------------------------------------------------------

/**
 * 将 manifest 中的相对路径解析为绝对 URL
 *
 * 例如：
 *   manifestUrl = 'luominest-avatar://png/codex-pet/manifest.json'
 *   relativePath = 'spritesheet.png'
 *   → 'luominest-avatar://png/codex-pet/spritesheet.png'
 */
function resolveRelativeUrl(manifestUrl: string, relativePath: string): string {
  // 如果已经是绝对 URL（带协议），直接返回
  if (/^[a-z]+:\/\//i.test(relativePath)) {
    return relativePath
  }
  // 取 manifest URL 的 base 部分，拼接相对路径
  const lastSlash = manifestUrl.lastIndexOf('/')
  if (lastSlash < 0) return relativePath
  return manifestUrl.slice(0, lastSlash + 1) + relativePath
}

// ---------------------------------------------------------------------------
// 渲染器实现
// ---------------------------------------------------------------------------

export function usePngTuber(
  canvasRef: Ref<HTMLCanvasElement | null>,
  modelId: string = 'builtin-png-codex',
): IAvatarRenderer & { state: PngTuberState } {
  const type: AvatarRendererType = 'png'

  const isReady = ref(false)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const currentState = ref<string>('idle')
  const availableStates = ref<string[]>([])
  const modelName = ref<string>('')

  let pixiApp: Application | null = null
  let currentSprite: AnimatedSprite | null = null
  let baseTexture: BaseTexture | null = null
  let stateTextures: Map<string, Texture[]> = new Map()
  let stateConfig: Map<string, PngTuberManifestState> = new Map()
  let emotionMap: Record<string, string> = {}
  let defaultState = 'idle'

  // ------------------------------------------------------------------
  // 生命周期
  // ------------------------------------------------------------------

  const loadModel = async (url: string, _opts?: { scale?: number }): Promise<void> => {
    isLoading.value = true
    error.value = null
    isReady.value = false

    try {
      // 1. fetch manifest
      logger.info(`Loading PNG Tuber manifest: ${url}`)
      const response = await fetch(url)
      if (!response.ok) {
        throw new Error(`Failed to fetch manifest: ${response.status} ${response.statusText}`)
      }
      const manifest: PngTuberManifest = await response.json()
      modelName.value = manifest.display_name ?? manifest.name
      logger.info(`Manifest loaded: ${manifest.name}, ${manifest.states.length} states`)

      // 2. 解析 spritesheet URL
      const sheetUrl = resolveRelativeUrl(url, manifest.sheet.image)
      logger.info(`Loading spritesheet: ${sheetUrl}`)

      // 3. 初始化 PixiJS Application
      if (!pixiApp) {
        pixiApp = new Application({
          view: canvasRef.value ?? undefined,
          backgroundAlpha: 0,
          antialias: true,
          width: DEFAULT_CANVAS_SIZE,
          height: DEFAULT_CANVAS_SIZE,
        })
      }

      // 4. 加载 spritesheet BaseTexture
      baseTexture = BaseTexture.from(sheetUrl)
      await new Promise<void>((resolve, reject) => {
        if (baseTexture!.valid) {
          resolve()
        } else {
          baseTexture!.once('loaded', () => resolve())
          baseTexture!.once('error', (e: unknown) => reject(e))
        }
      })

      // 5. 按状态切割帧
      stateTextures.clear()
      stateConfig.clear()
      emotionMap = manifest.emotion_map ?? {}
      defaultState = manifest.default_state ?? 'idle'

      const sheet = manifest.sheet
      const frameW = sheet.frame_width || DEFAULT_FRAME_WIDTH
      const frameH = sheet.frame_height || DEFAULT_FRAME_HEIGHT
      const cols = sheet.cols || DEFAULT_COLS

      for (const state of manifest.states) {
        const textures: Texture[] = []
        const row = state.row
        const frames = Math.min(state.frames, cols)

        for (let col = 0; col < frames; col++) {
          const frame = new Rectangle(
            col * frameW,
            row * frameH,
            frameW,
            frameH,
          )
          const texture = new Texture(baseTexture!, frame)
          textures.push(texture)
        }

        stateTextures.set(state.name, textures)
        stateConfig.set(state.name, state)
      }
      availableStates.value = Array.from(stateTextures.keys())

      // 6. 初始状态
      setState(defaultState)

      isReady.value = true
      logger.info(`PNG Tuber model loaded: ${manifest.name}`)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load PNG Tuber'
      error.value = message
      logger.error('Load error:', message)
    } finally {
      isLoading.value = false
    }
  }

  const destroy = (): void => {
    if (currentSprite) {
      pixiApp?.stage.removeChild(currentSprite)
      currentSprite.destroy()
      currentSprite = null
    }
    // 注意：Texture 由 baseTexture 派生，销毁 baseTexture 会自动销毁所有派生 Texture
    if (baseTexture) {
      baseTexture.destroy()
      baseTexture = null
    }
    stateTextures.clear()
    stateConfig.clear()
    if (pixiApp) {
      pixiApp.destroy(true)
      pixiApp = null
    }
    isReady.value = false
    logger.debug('PNG Tuber destroyed')
  }

  // ------------------------------------------------------------------
  // 状态机
  // ------------------------------------------------------------------

  const setState = (state: string): void => {
    if (!pixiApp) return
    const config = stateConfig.get(state)
    if (!config) {
      logger.warn(`Unknown state: ${state}`)
      return
    }
    const textures = stateTextures.get(state)
    if (!textures || textures.length === 0) {
      logger.warn(`No textures for state: ${state}`)
      return
    }

    // 销毁旧 sprite
    if (currentSprite) {
      pixiApp.stage.removeChild(currentSprite)
      currentSprite.destroy()
    }

    // 创建新 sprite
    currentSprite = new AnimatedSprite(textures)
    currentSprite.animationSpeed = config.fps / 60
    currentSprite.loop = config.loop
    currentSprite.anchor.set(0.5, 0.5)
    currentSprite.x = DEFAULT_CANVAS_SIZE / 2
    currentSprite.y = DEFAULT_CANVAS_SIZE / 2

    // 缩放：将 spritesheet 帧（192×208）缩放到画布大小（256×256）
    const scaleX = DEFAULT_CANVAS_SIZE / (config.frames > 0 ? textures[0].frame.width : DEFAULT_FRAME_WIDTH)
    const scaleY = DEFAULT_CANVAS_SIZE / (config.frames > 0 ? textures[0].frame.height : DEFAULT_FRAME_HEIGHT)
    const scale = Math.min(scaleX, scaleY) * 0.9  // 留 10% 边距
    currentSprite.scale.set(scale)

    // 非循环动画播放完毕后切换到 next 状态
    if (!config.loop && config.next) {
      currentSprite.onComplete = () => {
        setState(config.next!)
      }
    }

    currentSprite.play()
    pixiApp.stage.addChild(currentSprite)
    currentState.value = state

    logger.debug(`State changed: ${state}`)
  }

  // ------------------------------------------------------------------
  // 驱动接口
  // ------------------------------------------------------------------

  const triggerMotion = async (group: string, _index: number = 0): Promise<void> => {
    // PNG Tuber：动作名直接作为状态名
    if (stateConfig.has(group)) {
      setState(group)
    }
  }

  const triggerExpression = async (name: string): Promise<void> => {
    // 表情名直接作为状态名（不经 emotion_map 转换）
    if (stateConfig.has(name)) {
      setState(name)
    }
  }

  const driveEmotion = async (emotionId: string): Promise<void> => {
    const state = emotionMap[emotionId] ?? defaultState
    setState(state)
  }

  const drivePadEmotion = (_p: number, _a: number, _d: number): void => {
    // PNG Tuber 不支持 PAD 连续驱动（静态图片无参数化能力）
    // 静默忽略
  }

  const syncLipParam = (value: number): void => {
    // PNG Tuber 口型同步：音量 > 0.3 切到 waving（说话状），否则回 idle
    // 注：Codex 9 状态无 talk 状态，借用 waving 作为"说话"近似
    if (value > 0.3 && currentState.value === 'idle') {
      setState('waving')
    } else if (value <= 0.1 && currentState.value === 'waving') {
      setState('idle')
    }
  }

  const syncLipVowel = (_vowel: string): void => {
    // PNG Tuber 不支持 viseme，静默忽略
  }

  const setCoreParam = (_paramId: string, _value: number): void => {
    // PNG Tuber 不支持直设参数，静默忽略
  }

  const resetPose = async (): Promise<void> => {
    setState(defaultState)
  }

  // ------------------------------------------------------------------
  // 状态查询
  // ------------------------------------------------------------------

  const getCapabilities = (): AvatarCapability => ({
    expressions: [],
    motions: [],
    states: Array.from(stateConfig.keys()),
    visemes: null,
    lip_sync: false,
    focus_tracking: false,
    pad_emotion: false,
    custom_params: null,
  })

  const isReadyFn = (): boolean => isReady.value

  // 响应式状态对象（供上层 ref 访问）
  const state: PngTuberState = {
    get isReady() { return isReady.value },
    get isLoading() { return isLoading.value },
    get error() { return error.value },
    get currentState() { return currentState.value },
    get availableStates() { return availableStates.value },
    get modelName() { return modelName.value },
  }

  return {
    type,
    modelId,
    state,
    loadModel,
    destroy,
    triggerMotion,
    triggerExpression,
    driveEmotion,
    drivePadEmotion,
    syncLipParam,
    syncLipVowel,
    setCoreParam,
    resetPose,
    getCapabilities,
    isReady: isReadyFn,
  }
}

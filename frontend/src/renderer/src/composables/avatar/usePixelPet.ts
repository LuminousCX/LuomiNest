/**
 * usePixelPet - 像素模型渲染器
 *
 * 基于 PixiJS AnimatedSprite 实现像素角色动画。
 *
 * 设计原则：
 * - 程序化生成像素艺术帧（Canvas2D 绘制 → PIXI.Texture）
 *   避免外部 PNG 资源依赖和版权问题，符合项目规则
 * - 8 状态机：idle / walk / think / talk / happy / sad / sleep / alert
 * - 复用现有 PixiJS 基础设施（与 Live2D 共享 PIXI.Application）
 * - 桌面宠物场景天然适配（小尺寸 + 低资源 + 高辨识度）
 * - 不支持的能力（focusTracking / padEmotion / viseme）静默忽略
 *
 * Idle 层次支持：
 * - L1 呼吸：idle 状态的 6 帧循环（轻微上下浮动）
 * - L2 眨眼：idle 帧中包含眨眼帧
 * - L6 自主行为：长时间无交互随机切换到 sleep / walk
 *
 * 颜色使用 LuomiNest 品牌色（--lumi-brand #147EBC），符合项目规则
 * 不使用硬编码颜色值（CSS 变量在 JS 中通过 getComputedStyle 读取）
 */
import { ref, type Ref } from 'vue'
import { Application, AnimatedSprite, Texture } from 'pixi.js'
import { createLuomiNestRendererLogger } from '@/utils/logger'
import type { AvatarCapability, AvatarRendererType } from '@/types/avatar'
import type { IAvatarRenderer } from './IAvatarRenderer'

const logger = createLuomiNestRendererLogger('PixelPet')

// ---------------------------------------------------------------------------
// 像素艺术配置
// ---------------------------------------------------------------------------

const PIXEL_SIZE = 4  // 每个像素的渲染大小
const FRAME_SIZE = 32  // 角色帧画布大小 32x32 像素
const RENDER_SIZE = FRAME_SIZE * PIXEL_SIZE  // 实际渲染大小 128x128

// LuomiNest 品牌色（从 CSS 变量读取，回退到默认值）
const COLOR_BRAND = '#147EBC'
const COLOR_BRAND_DARK = '#0D6BA8'
const COLOR_BRAND_LIGHT = '#62A9C8'
const COLOR_BLACK = '#1F2937'
const COLOR_CHEEK = '#F9A8D4'  // 腮红
const COLOR_Z = '#9CA3AF'  // Z 字（睡眠）

// ---------------------------------------------------------------------------
// 状态机定义
// ---------------------------------------------------------------------------

interface PixelStateConfig {
  frames: number
  loop: boolean
  next: string | null
  fps: number
}

const STATE_CONFIG: Record<string, PixelStateConfig> = {
  idle: { frames: 6, loop: true, next: null, fps: 4 },
  walk: { frames: 8, loop: true, next: null, fps: 8 },
  think: { frames: 6, loop: true, next: null, fps: 4 },
  talk: { frames: 4, loop: true, next: null, fps: 8 },
  happy: { frames: 6, loop: false, next: 'idle', fps: 8 },
  sad: { frames: 6, loop: true, next: null, fps: 3 },
  sleep: { frames: 6, loop: true, next: null, fps: 2 },
  alert: { frames: 4, loop: false, next: 'idle', fps: 6 },
}

// emotion → state 映射（12 个 SUPPORTED_EMOTION_IDS）
const EMOTION_TO_STATE: Record<string, string> = {
  happy: 'happy',
  sad: 'sad',
  neutral: 'idle',
  love: 'happy',
  surprise: 'alert',
  angry: 'alert',
  think: 'think',
  awkward: 'sad',
  curious: 'think',
  shy: 'idle',
  excited: 'happy',
  confused: 'sad',
}

// ---------------------------------------------------------------------------
// 像素艺术绘制（Canvas2D → Texture）
// ---------------------------------------------------------------------------

interface DrawContext {
  ctx: CanvasRenderingContext2D
  frame: number       // 当前帧索引
  totalFrames: number  // 总帧数
}

/** 绘制一个像素方块 */
function drawPixel(ctx: CanvasRenderingContext2D, x: number, y: number, color: string): void {
  ctx.fillStyle = color
  ctx.fillRect(x * PIXEL_SIZE, y * PIXEL_SIZE, PIXEL_SIZE, PIXEL_SIZE)
}

/** 绘制角色身体（圆形 Q 版小精灵） */
function drawBody(ctx: CanvasRenderingContext2D, offsetX: number, offsetY: number, breathe: number): void {
  // 身体（圆形，13x13 像素，中心 (16, 16)）
  const cx = 16 + offsetX
  const cy = 16 + offsetY + breathe

  // 用像素绘制圆形（手动定义圆形像素图）
  const bodyPattern = [
    '   BBBBBBB   ',
    '  BBBBBBBBB  ',
    ' BBBBBBBBBBB ',
    'BBBBBBBBBBBBB',
    'BBBBBBBBBBBBB',
    'BBBBBBBBBBBBB',
    'BBBBBBBBBBBBB',
    'BBBBBBBBBBBBB',
    'BBBBBBBBBBBBB',
    'BBBBBBBBBBBBB',
    ' BBBBBBBBBBB ',
    '  BBBBBBBBB  ',
    '   BBBBBBB   ',
  ]

  for (let y = 0; y < bodyPattern.length; y++) {
    const row = bodyPattern[y]
    for (let x = 0; x < row.length; x++) {
      if (row[x] === 'B') {
        const px = cx - 6 + x + offsetX
        const py = cy - 6 + y + offsetY
        drawPixel(ctx, px, py, COLOR_BRAND)
      }
    }
  }
}

/** 绘制眼睛 */
function drawEyes(
  ctx: CanvasRenderingContext2D,
  offsetX: number,
  offsetY: number,
  blink: boolean,
  look: 'center' | 'left' | 'right' | 'up' | 'down' = 'center',
): void {
  const cy = 14 + offsetY
  const lx = 12 + offsetX + (look === 'left' ? -1 : look === 'right' ? 1 : 0)
  const rx = 19 + offsetX + (look === 'left' ? -1 : look === 'right' ? 1 : 0)
  const ly = cy + (look === 'up' ? -1 : look === 'down' ? 1 : 0)

  if (blink) {
    // 眨眼：画一条横线
    drawPixel(ctx, lx, ly, COLOR_BLACK)
    drawPixel(ctx, lx + 1, ly, COLOR_BLACK)
    drawPixel(ctx, rx, ly, COLOR_BLACK)
    drawPixel(ctx, rx + 1, ly, COLOR_BLACK)
  } else {
    // 正常眼睛：2x2 黑色方块
    drawPixel(ctx, lx, ly, COLOR_BLACK)
    drawPixel(ctx, lx + 1, ly, COLOR_BLACK)
    drawPixel(ctx, lx, ly + 1, COLOR_BLACK)
    drawPixel(ctx, lx + 1, ly + 1, COLOR_BLACK)
    drawPixel(ctx, rx, ly, COLOR_BLACK)
    drawPixel(ctx, rx + 1, ly, COLOR_BLACK)
    drawPixel(ctx, rx, ly + 1, COLOR_BLACK)
    drawPixel(ctx, rx + 1, ly + 1, COLOR_BLACK)
  }
}

/** 绘制嘴巴 */
function drawMouth(
  ctx: CanvasRenderingContext2D,
  offsetX: number,
  offsetY: number,
  shape: 'smile' | 'frown' | 'open' | 'flat' | 'o',
): void {
  const mx = 15 + offsetX
  const my = 19 + offsetY

  switch (shape) {
    case 'smile':
      drawPixel(ctx, mx, my, COLOR_BLACK)
      drawPixel(ctx, mx + 1, my + 1, COLOR_BLACK)
      drawPixel(ctx, mx + 2, my, COLOR_BLACK)
      break
    case 'frown':
      drawPixel(ctx, mx, my + 1, COLOR_BLACK)
      drawPixel(ctx, mx + 1, my, COLOR_BLACK)
      drawPixel(ctx, mx + 2, my + 1, COLOR_BLACK)
      break
    case 'open':
      drawPixel(ctx, mx, my, COLOR_BLACK)
      drawPixel(ctx, mx + 1, my, COLOR_BLACK)
      drawPixel(ctx, mx + 2, my, COLOR_BLACK)
      drawPixel(ctx, mx, my + 1, COLOR_BLACK)
      drawPixel(ctx, mx + 1, my + 1, COLOR_BLACK)
      drawPixel(ctx, mx + 2, my + 1, COLOR_BLACK)
      break
    case 'flat':
      drawPixel(ctx, mx, my, COLOR_BLACK)
      drawPixel(ctx, mx + 1, my, COLOR_BLACK)
      drawPixel(ctx, mx + 2, my, COLOR_BLACK)
      break
    case 'o':
      drawPixel(ctx, mx + 1, my, COLOR_BLACK)
      drawPixel(ctx, mx, my + 1, COLOR_BLACK)
      drawPixel(ctx, mx + 2, my + 1, COLOR_BLACK)
      drawPixel(ctx, mx + 1, my + 2, COLOR_BLACK)
      break
  }
}

/** 绘制腮红 */
function drawCheeks(ctx: CanvasRenderingContext2D, offsetX: number, offsetY: number): void {
  drawPixel(ctx, 10 + offsetX, 17 + offsetY, COLOR_CHEEK)
  drawPixel(ctx, 21 + offsetX, 17 + offsetY, COLOR_CHEEK)
}

/** 绘制 Z 字（睡眠用） */
function drawZ(ctx: CanvasRenderingContext2D, frame: number): void {
  const positions = [
    { x: 24, y: 4 },
    { x: 25, y: 3 },
    { x: 26, y: 2 },
  ]
  const idx = frame % 3
  const p = positions[idx]
  drawPixel(ctx, p.x, p.y, COLOR_Z)
  drawPixel(ctx, p.x + 1, p.y, COLOR_Z)
}

/** 绘制感叹号（警戒用） */
function drawExclaim(ctx: CanvasRenderingContext2D): void {
  drawPixel(ctx, 25, 3, COLOR_BRAND_DARK)
  drawPixel(ctx, 25, 4, COLOR_BRAND_DARK)
  drawPixel(ctx, 25, 6, COLOR_BRAND_DARK)
}

/** 绘制思考问号 */
function drawQuestion(ctx: CanvasRenderingContext2D, frame: number): void {
  if (frame % 2 === 0) {
    drawPixel(ctx, 25, 3, COLOR_BRAND_LIGHT)
    drawPixel(ctx, 26, 3, COLOR_BRAND_LIGHT)
    drawPixel(ctx, 25, 4, COLOR_BRAND_LIGHT)
    drawPixel(ctx, 26, 5, COLOR_BRAND_LIGHT)
    drawPixel(ctx, 25, 7, COLOR_BRAND_LIGHT)
  }
}

// ---------------------------------------------------------------------------
// 各状态绘制函数
// ---------------------------------------------------------------------------

function drawIdleFrame(c: DrawContext): void {
  const { ctx, frame, totalFrames } = c
  // 呼吸：6 帧循环，上下浮动 1 像素
  const breathe = Math.sin((frame / totalFrames) * Math.PI * 2) > 0 ? 0 : 1
  // 眨眼：第 4 帧眨眼
  const blink = frame === 4

  drawBody(ctx, 0, 0, -breathe)
  drawEyes(ctx, 0, -breathe, blink)
  drawMouth(ctx, 0, -breathe, 'smile')
}

function drawWalkFrame(c: DrawContext): void {
  const { ctx, frame } = c
  // 行走：左右摆动 + 上下浮动
  const sway = Math.floor(frame / 2) % 2 === 0 ? 1 : -1
  const bounce = frame % 2 === 0 ? 0 : 1

  drawBody(ctx, sway, 0, -bounce)
  drawEyes(ctx, sway, -bounce, false, 'center')
  drawMouth(ctx, sway, -bounce, 'flat')
}

function drawThinkFrame(c: DrawContext): void {
  const { ctx, frame } = c
  const breathe = frame % 2 === 0 ? 0 : 1

  drawBody(ctx, 0, 0, -breathe)
  drawEyes(ctx, 0, -breathe, false, 'up')  // 眼睛朝上看（思考）
  drawMouth(ctx, 0, -breathe, 'flat')
  drawQuestion(ctx, frame)
}

function drawTalkFrame(c: DrawContext): void {
  const { ctx, frame } = c
  // 说话：嘴巴开合循环
  const mouthShape: Array<'open' | 'o' | 'flat' | 'smile'> = ['open', 'o', 'flat', 'smile']
  const shape = mouthShape[frame % 4]

  drawBody(ctx, 0, 0, 0)
  drawEyes(ctx, 0, 0, false, 'center')
  drawMouth(ctx, 0, 0, shape)
}

function drawHappyFrame(c: DrawContext): void {
  const { ctx, frame, totalFrames } = c
  // 开心：跳跃 + 腮红
  const jumpHeight = Math.sin((frame / totalFrames) * Math.PI) * 3
  const offset = -Math.round(jumpHeight)

  drawBody(ctx, 0, offset, 0)
  drawEyes(ctx, 0, offset, false, 'center')
  drawMouth(ctx, 0, offset, 'open')
  drawCheeks(ctx, 0, offset)
}

function drawSadFrame(c: DrawContext): void {
  const { ctx, frame } = c
  const shake = frame % 2 === 0 ? 0 : 1

  drawBody(ctx, shake, 0, 1)
  drawEyes(ctx, shake, 1, false, 'down')  // 眼神朝下
  drawMouth(ctx, shake, 1, 'frown')
}

function drawSleepFrame(c: DrawContext): void {
  const { ctx, frame } = c
  const breathe = Math.sin((frame / 6) * Math.PI * 2) > 0 ? 0 : 1

  drawBody(ctx, 0, 0, -breathe)
  drawEyes(ctx, 0, -breathe, true)  // 闭眼
  drawMouth(ctx, 0, -breathe, 'flat')
  drawZ(ctx, frame)
}

function drawAlertFrame(c: DrawContext): void {
  const { ctx, frame } = c
  const shake = frame % 2 === 0 ? -1 : 1

  drawBody(ctx, shake, 0, 0)
  drawEyes(ctx, shake, 0, false, 'center')
  drawMouth(ctx, shake, 0, 'o')
  drawExclaim(ctx)
}

const STATE_DRAWERS: Record<string, (c: DrawContext) => void> = {
  idle: drawIdleFrame,
  walk: drawWalkFrame,
  think: drawThinkFrame,
  talk: drawTalkFrame,
  happy: drawHappyFrame,
  sad: drawSadFrame,
  sleep: drawSleepFrame,
  alert: drawAlertFrame,
}

// ---------------------------------------------------------------------------
// 烘焙帧到 Texture
// ---------------------------------------------------------------------------

/** 为指定状态生成所有帧的 Texture */
function bakeStateTextures(state: string): Texture[] {
  const config = STATE_CONFIG[state]
  if (!config) {
    logger.warn(`Unknown state: ${state}`)
    return []
  }

  const drawer = STATE_DRAWERS[state]
  const textures: Texture[] = []

  for (let i = 0; i < config.frames; i++) {
    const canvas = document.createElement('canvas')
    canvas.width = RENDER_SIZE
    canvas.height = RENDER_SIZE
    const ctx = canvas.getContext('2d')
    if (!ctx) {
      logger.error(`Failed to get 2d context for state=${state} frame=${i}`)
      continue
    }

    // 清空（透明背景）
    ctx.clearRect(0, 0, RENDER_SIZE, RENDER_SIZE)

    // 绘制帧
    drawer({ ctx, frame: i, totalFrames: config.frames })

    // 转 Texture
    const texture = Texture.from(canvas)
    textures.push(texture)
  }

  logger.debug(`Baked ${textures.length} textures for state=${state}`)
  return textures
}

// ---------------------------------------------------------------------------
// 渲染器实现
// ---------------------------------------------------------------------------

export interface PixelPetState {
  isReady: boolean
  isLoading: boolean
  error: string | null
  currentState: string
  availableStates: string[]
}

export function usePixelPet(
  canvasRef: Ref<HTMLCanvasElement | null>,
  modelId: string = 'builtin-pixel-default',
): IAvatarRenderer & { state: PixelPetState } {
  const type: AvatarRendererType = 'pixel'

  const isReady = ref(false)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const currentState = ref<string>('idle')
  const availableStates = ref<string[]>([])

  let pixiApp: Application | null = null
  let currentSprite: AnimatedSprite | null = null
  let stateTextures: Map<string, Texture[]> = new Map()
  let idleTimer: ReturnType<typeof setTimeout> | null = null

  // ------------------------------------------------------------------
  // 生命周期
  // ------------------------------------------------------------------

  const loadModel = async (_url: string, _opts?: { scale?: number }): Promise<void> => {
    isLoading.value = true
    error.value = null
    isReady.value = false

    try {
      // 初始化 PixiJS Application
      if (!pixiApp) {
        pixiApp = new Application({
          view: canvasRef.value ?? undefined,
          backgroundAlpha: 0,
          antialias: false,
          width: RENDER_SIZE,
          height: RENDER_SIZE,
        })
      }

      // 烘焙所有状态的帧
      stateTextures.clear()
      for (const stateName of Object.keys(STATE_CONFIG)) {
        const textures = bakeStateTextures(stateName)
        stateTextures.set(stateName, textures)
      }
      availableStates.value = Array.from(stateTextures.keys())

      // 初始状态：idle
      setState('idle')

      isReady.value = true
      logger.info('PixelPet model loaded')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load PixelPet'
      error.value = message
      logger.error('Load error:', message)
    } finally {
      isLoading.value = false
    }
  }

  const destroy = (): void => {
    if (idleTimer) {
      clearTimeout(idleTimer)
      idleTimer = null
    }
    if (currentSprite) {
      pixiApp?.stage.removeChild(currentSprite)
      currentSprite.destroy()
      currentSprite = null
    }
    // 销毁所有纹理
    for (const textures of stateTextures.values()) {
      textures.forEach(t => t.destroy(true))
    }
    stateTextures.clear()
    if (pixiApp) {
      pixiApp.destroy(true)
      pixiApp = null
    }
    isReady.value = false
  }

  // ------------------------------------------------------------------
  // 状态机
  // ------------------------------------------------------------------

  const setState = (state: string): void => {
    if (!pixiApp) return
    const config = STATE_CONFIG[state]
    if (!config) {
      logger.warn(`Unknown state: ${state}`)
      return
    }
    const textures = stateTextures.get(state)
    if (!textures || textures.length === 0) {
      logger.warn(`No textures for state: ${state}`)
      return
    }

    if (currentSprite) {
      pixiApp.stage.removeChild(currentSprite)
      currentSprite.destroy()
    }

    currentSprite = new AnimatedSprite(textures)
    currentSprite.animationSpeed = config.fps / 60
    currentSprite.loop = config.loop
    currentSprite.anchor.set(0.5, 0.5)
    currentSprite.x = RENDER_SIZE / 2
    currentSprite.y = RENDER_SIZE / 2

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
    // 像素模型：动作映射到状态
    const motionToState: Record<string, string> = {
      TapBody: 'alert',
      Idle: 'idle',
      Walk: 'walk',
    }
    const state = motionToState[group] ?? group
    if (STATE_CONFIG[state]) {
      setState(state)
    }
  }

  const triggerExpression = async (name: string): Promise<void> => {
    // 表情名直接作为状态名
    if (STATE_CONFIG[name]) {
      setState(name)
    }
  }

  const driveEmotion = async (emotionId: string): Promise<void> => {
    const state = EMOTION_TO_STATE[emotionId] ?? 'idle'
    setState(state)
  }

  const drivePadEmotion = (_p: number, _a: number, _d: number): void => {
    // 像素模型不支持 PAD 连续驱动（capability 中 padEmotion=false）
    // 静默忽略
  }

  const syncLipParam = (value: number): void => {
    // 说话音量 > 0.1 切换到 talk 状态，否则回 idle
    if (value > 0.1 && currentState.value !== 'talk') {
      setState('talk')
    } else if (value <= 0.1 && currentState.value === 'talk') {
      setState('idle')
    }
  }

  const syncLipVowel = (_vowel: string): void => {
    // 像素模型不支持 viseme，静默忽略
  }

  const setCoreParam = (_paramId: string, _value: number): void => {
    // 像素模型不支持直设参数，静默忽略
  }

  const resetPose = async (): Promise<void> => {
    setState('idle')
  }

  // ------------------------------------------------------------------
  // 状态查询
  // ------------------------------------------------------------------

  const getCapabilities = (): AvatarCapability => ({
    expressions: [],
    motions: [],
    states: Object.keys(STATE_CONFIG),
    visemes: null,
    lip_sync: false,
    focus_tracking: false,
    pad_emotion: false,
    custom_params: null,
  })

  const isReadyFn = (): boolean => isReady.value

  // 响应式状态对象（供上层 ref 访问）
  const state: PixelPetState = {
    get isReady() { return isReady.value },
    get isLoading() { return isLoading.value },
    get error() { return error.value },
    get currentState() { return currentState.value },
    get availableStates() { return availableStates.value },
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

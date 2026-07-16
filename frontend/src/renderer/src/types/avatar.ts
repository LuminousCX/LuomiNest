/**
 * LuomiNest Avatar 多模型驱动协议类型定义
 *
 * 与后端 backend/app/schemas/avatar.py 镜像，保持前后端类型一致。
 *
 * 重要：字段命名与后端 Pydantic model_dump() 输出一致（snake_case），
 * 不做 camelCase 转换，避免运行时类型不匹配。
 *
 * 设计原则：
 * - 与现有 ChatStreamChunk.emotion 字段解耦：emotion_drive 是更高层的封装
 * - chat stream emotion 仍只承载 LLM 输出的离散表情 ID
 * - emotion_drive 协议是可选的实时驱动通道（摄像头/语音情感/AI 自主行为）
 */

// ---------------------------------------------------------------------------
// 模型类型与来源
// ---------------------------------------------------------------------------

export type AvatarRendererType = 'live2d' | 'vrm' | 'pixel' | 'spine' | 'png'
export type AvatarSource = 'builtin' | 'imported'

// ---------------------------------------------------------------------------
// 模型能力声明（字段名与后端 AvatarCapability 一致：snake_case）
// ---------------------------------------------------------------------------

export interface AvatarCapability {
  expressions: string[]
  motions: string[]
  states?: string[] | null
  visemes?: string[] | null
  lip_sync: boolean
  focus_tracking: boolean
  pad_emotion: boolean
  custom_params?: string[] | null
}

// ---------------------------------------------------------------------------
// 模型绑定（字段名与后端 AvatarBinding 一致：snake_case）
// ---------------------------------------------------------------------------

export interface AvatarBinding {
  voice: string
  voice_lang: string
  expression_map: Record<string, string>
  default_expression: string
}

// ---------------------------------------------------------------------------
// 模型清单条目（字段名与后端 AvatarManifestModel 一致：snake_case）
// ---------------------------------------------------------------------------

export interface AvatarManifestModel {
  id: string
  name: string
  type: AvatarRendererType
  version: string
  source: AvatarSource
  path: string
  thumbnail?: string | null
  tags: string[]
  capabilities: AvatarCapability
  binding?: AvatarBinding | null
}

export interface AvatarManifest {
  schema_version: string
  models: AvatarManifestModel[]
}

// ---------------------------------------------------------------------------
// 统一驱动协议
// ---------------------------------------------------------------------------

export interface PadEmotion {
  p: number  // [-1, 1] Pleasure
  a: number  // [-1, 1] Arousal
  d: number  // [-1, 1] Dominance
}

export interface AvatarDriveData {
  emotion?: string | null
  pad?: PadEmotion | null
  action?: string | null
  lip_sync?: number | null  // [0, 1]
  viseme?: string | null
  params?: Record<string, number> | null
}

export interface AvatarDrivePacket {
  type: 'emotion_drive'
  timestamp: number  // ms
  data: AvatarDriveData
}

// ---------------------------------------------------------------------------
// WebSocket 控制消息
// ---------------------------------------------------------------------------

export interface AvatarDriveSubscribe {
  type: 'subscribe'
  model_id: string
}

export interface AvatarDriveUnsubscribe {
  type: 'unsubscribe'
}

export type AvatarDriveClientMessage =
  | AvatarDriveSubscribe
  | AvatarDriveUnsubscribe
  | AvatarDrivePacket

/** 服务端 → 客户端的订阅确认 */
export interface AvatarDriveSubscribedAck {
  type: 'subscribed'
  model_id: string
  timestamp: number
}

export interface AvatarDriveUnsubscribedAck {
  type: 'unsubscribed'
  timestamp: number
}

export type AvatarDriveServerMessage =
  | AvatarDriveSubscribedAck
  | AvatarDriveUnsubscribedAck
  | AvatarDrivePacket

// ---------------------------------------------------------------------------
// 后端 API 响应
// ---------------------------------------------------------------------------

export interface ApiResult<T = unknown> {
  code: number  // 0 = 成功
  message: string
  data: T | null
}

/** 更新绑定的请求体（与后端 AvatarBindingUpdate 一致） */
export interface AvatarBindingUpdate {
  voice?: string
  voice_lang?: string
  expression_map?: Record<string, string>
  default_expression?: string
}

// ---------------------------------------------------------------------------
// 渲染器状态
// ---------------------------------------------------------------------------

export interface AvatarRendererState {
  isReady: boolean
  isLoading: boolean
  error: string | null
  currentModelName: string
  currentModelUrl: string
  availableMotions: string[]
  availableExpressions: string[]
  idleActive: boolean
}

// ===========================================================================
// 皮套工坊（Avatar Workshop）专用类型
// ===========================================================================

/**
 * 显示模式：内嵌画布 or 桌面宠物窗口
 *
 * 与 AvatarRendererType 正交：
 * - AvatarRendererType 回答「渲染什么模型」（Live2D/VRM/Pixel/...）
 * - WorkshopDisplayMode 回答「在哪里渲染」（页面内嵌 canvas or 独立桌宠窗口）
 */
export type WorkshopDisplayMode = 'inline' | 'desktop'

/**
 * 模型类型元信息（用于 UI 展示与切换器）
 */
export interface ModelTypeInfo {
  type: AvatarRendererType
  label: string
  desc: string
  /** 是否已实现（未实现的类型在 UI 上禁用切换） */
  implemented: boolean
}

/**
 * 所有支持的模型类型清单（与 createAvatarRenderer 工厂一致）
 *
 * implemented 字段必须与 createAvatarRenderer.ts 中的 case 分支保持同步：
 * - live2d: true（Live2DRendererAdapter 已实现）
 * - pixel: true（usePixelPet 已实现）
 * - vrm: false（P1 阶段）
 * - spine: false（P2 阶段）
 * - png: false（P2 阶段）
 */
export const AVATAR_MODEL_TYPES: ModelTypeInfo[] = [
  { type: 'live2d', label: 'Live2D', desc: 'Cubism 4/5', implemented: true },
  { type: 'pixel', label: 'PixelPet', desc: 'Q-version Pet', implemented: true },
  { type: 'vrm', label: 'VRM', desc: '3D Model', implemented: false },
  { type: 'spine', label: 'Spine', desc: 'Skeletal Anim', implemented: false },
  { type: 'png', label: 'PNG Tuber', desc: 'Static Image', implemented: false },
]

/**
 * 工坊整体状态快照（用于调试或 Pinia 持久化）
 */
export interface WorkshopState {
  currentMode: AvatarRendererType
  currentModelId: string
  displayMode: WorkshopDisplayMode
  manifestLoaded: boolean
  modelCount: number
}

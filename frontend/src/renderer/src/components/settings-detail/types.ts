/** 设置项可承载的值类型 */
export type SectionValue = boolean | string | number

/** 设置项公共字段 */
interface SectionItemBase {
  /** 唯一标识，用于 change/select 事件回传与持久化 */
  key: string
  label: string
  desc: string
}

/** 开关项 */
export interface SectionToggleItem extends SectionItemBase {
  type: 'toggle'
  value: boolean
}

/** 下拉选择项 */
export interface SectionSelectItem extends SectionItemBase {
  type: 'select'
  value: string
  options: Array<{ label: string; value: string }>
}

/** 文本 / 密码输入项 */
export interface SectionInputItem extends SectionItemBase {
  type: 'input' | 'password'
  value: string
  placeholder?: string
}

/** 滑块项 */
export interface SectionSliderItem extends SectionItemBase {
  type: 'slider'
  value: number
  min: number
  max: number
  step?: number
  unit?: string
}

/** 时间段项，value 格式 "HH:mm-HH:mm"（允许为空） */
export interface SectionTimeRangeItem extends SectionItemBase {
  type: 'time'
  value: string
}

/** 动作行：无绑定值，点击整行触发 select 事件（导航或功能入口） */
export interface SectionActionItem extends SectionItemBase {
  type: 'list' | 'button' | 'connect' | 'action'
  /** 右侧动作文案，缺省按 type 推断 */
  actionText?: string
}

export type SectionItem =
  | SectionToggleItem
  | SectionSelectItem
  | SectionInputItem
  | SectionSliderItem
  | SectionTimeRangeItem
  | SectionActionItem

export interface TtsEngineInfo {
  id: string
  name: string
  online: boolean
  available: boolean
  category?: string
  needs_api_key?: boolean
  default_voices?: Record<string, string>
  voices?: Array<{ id: string; name: string; lang: string }>
  lang_map?: Record<string, string>
}

export interface TtsDeviceInfo {
  type: string
  name: string
  vendor?: string
  gpu_count?: number
  cuda_available: boolean
  cuda_version?: string
  torch_available?: boolean
  note?: string
}

export interface TtsBindingInfo {
  model_id: string
  voice: string
  voice_lang: string
  default_expression: string
}

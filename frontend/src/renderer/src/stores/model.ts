import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ModelProvider, ModelInfo, ModelConfig, ProviderTemplate, TTSConfig, STTConfig, STTEngine } from '../types'
import { useApi } from '../composables/useApi'
import { PROVIDER_LOGOS } from '../config/provider-logos'
import { getItem, setItem } from '../utils/storage'

const unwrapData = <T>(result: T | { data: T }): T => {
  if (typeof result === 'object' && result !== null && 'data' in result) {
    return (result as { data: T }).data
  }
  return result as T
}

const LOCAL_TEMPLATES: ProviderTemplate[] = [
  {
    id: 'openai',
    name: 'OpenAI',
    vendor: 'openai_compatible',
    baseUrl: 'https://api.openai.com/v1',
    defaultModel: 'gpt-4o-mini',
    description: 'GPT-4o / o3 等旗舰模型',
    category: 'cloud',
    color: PROVIDER_LOGOS.openai.color,
    initials: PROVIDER_LOGOS.openai.initials,
    svgIcon: PROVIDER_LOGOS.openai.svgIcon,
    defaultModels: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo', 'o3-mini'],
  },
  {
    id: 'anthropic',
    name: 'Anthropic',
    vendor: 'openai_compatible',
    baseUrl: 'https://api.anthropic.com/v1',
    defaultModel: 'claude-sonnet-4-20250514',
    description: 'Claude Opus / Sonnet 系列',
    category: 'cloud',
    color: PROVIDER_LOGOS.anthropic.color,
    initials: PROVIDER_LOGOS.anthropic.initials,
    svgIcon: PROVIDER_LOGOS.anthropic.svgIcon,
    defaultModels: ['claude-sonnet-4-20250514', 'claude-opus-4-20250514', 'claude-3.5-sonnet-20241022', 'claude-3-haiku-20240307'],
  },
  {
    id: 'deepseek',
    name: 'DeepSeek',
    vendor: 'openai_compatible',
    baseUrl: 'https://api.deepseek.com',
    defaultModel: 'deepseek-chat',
    description: 'DeepSeek V3 / R1 推理模型',
    category: 'cloud',
    color: PROVIDER_LOGOS.deepseek.color,
    initials: PROVIDER_LOGOS.deepseek.initials,
    svgIcon: PROVIDER_LOGOS.deepseek.svgIcon,
    defaultModels: ['deepseek-chat', 'deepseek-reasoner'],
  },
  {
    id: 'google',
    name: 'Google Gemini',
    vendor: 'openai_compatible',
    baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai',
    defaultModel: 'gemini-2.0-flash',
    description: 'Gemini 2.0 Flash / Pro',
    category: 'cloud',
    color: PROVIDER_LOGOS.google.color,
    initials: PROVIDER_LOGOS.google.initials,
    svgIcon: PROVIDER_LOGOS.google.svgIcon,
    defaultModels: ['gemini-2.0-flash', 'gemini-2.0-flash-lite', 'gemini-1.5-pro', 'gemini-1.5-flash'],
  },
  {
    id: 'mistral',
    name: 'Mistral AI',
    vendor: 'openai_compatible',
    baseUrl: 'https://api.mistral.ai/v1',
    defaultModel: 'mistral-small-latest',
    description: 'Mistral / Codestral 系列',
    category: 'cloud',
    color: PROVIDER_LOGOS.mistral.color,
    initials: PROVIDER_LOGOS.mistral.initials,
    svgIcon: PROVIDER_LOGOS.mistral.svgIcon,
    defaultModels: ['mistral-large-latest', 'mistral-small-latest', 'codestral-latest'],
  },
  {
    id: 'groq',
    name: 'Groq',
    vendor: 'openai_compatible',
    baseUrl: 'https://api.groq.com/openai/v1',
    defaultModel: 'llama-3.3-70b-versatile',
    description: 'LPU 超高速推理',
    category: 'cloud',
    color: PROVIDER_LOGOS.groq.color,
    initials: PROVIDER_LOGOS.groq.initials,
    svgIcon: PROVIDER_LOGOS.groq.svgIcon,
    defaultModels: ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant', 'mixtral-8x7b-32768'],
  },
  {
    id: 'xai',
    name: 'xAI',
    vendor: 'openai_compatible',
    baseUrl: 'https://api.x.ai/v1',
    defaultModel: 'grok-3-mini-beta',
    description: 'Grok 系列模型',
    category: 'cloud',
    color: PROVIDER_LOGOS.xai.color,
    initials: PROVIDER_LOGOS.xai.initials,
    svgIcon: PROVIDER_LOGOS.xai.svgIcon,
    defaultModels: ['grok-3-mini-beta', 'grok-2'],
  },
  {
    id: 'moonshot',
    name: 'Moonshot (Kimi)',
    vendor: 'openai_compatible',
    baseUrl: 'https://api.moonshot.cn/v1',
    defaultModel: 'moonshot-v1-8k',
    description: '月之暗面 Kimi 长上下文',
    category: 'cloud',
    color: PROVIDER_LOGOS.moonshot.color,
    initials: PROVIDER_LOGOS.moonshot.initials,
    svgIcon: PROVIDER_LOGOS.moonshot.svgIcon,
    defaultModels: ['moonshot-v1-8k', 'moonshot-v1-32k', 'moonshot-v1-128k'],
  },
  {
    id: 'zhipu',
    name: 'ZhiPu (智谱)',
    vendor: 'openai_compatible',
    baseUrl: 'https://open.bigmodel.cn/api/paas/v4',
    defaultModel: 'glm-4-flash',
    description: 'GLM-4 系列',
    category: 'cloud',
    color: PROVIDER_LOGOS.zhipu.color,
    initials: PROVIDER_LOGOS.zhipu.initials,
    svgIcon: PROVIDER_LOGOS.zhipu.svgIcon,
    defaultModels: ['glm-4-flash', 'glm-4-plus', 'glm-4-long'],
  },
  {
    id: 'dashscope',
    name: 'DashScope (百炼)',
    vendor: 'openai_compatible',
    baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    defaultModel: 'qwen-plus',
    description: '阿里云通义千问系列',
    category: 'cloud',
    color: PROVIDER_LOGOS.dashscope.color,
    initials: PROVIDER_LOGOS.dashscope.initials,
    svgIcon: PROVIDER_LOGOS.dashscope.svgIcon,
    defaultModels: ['qwen-plus', 'qwen-turbo', 'qwen-max', 'qwen-long'],
  },
  {
    id: 'siliconflow',
    name: 'SiliconFlow',
    vendor: 'openai_compatible',
    baseUrl: 'https://api.siliconflow.cn/v1',
    defaultModel: 'Qwen/Qwen2.5-7B-Instruct',
    description: '硅基流动多模型平台',
    category: 'aggregator',
    color: PROVIDER_LOGOS.siliconflow.color,
    initials: PROVIDER_LOGOS.siliconflow.initials,
    svgIcon: PROVIDER_LOGOS.siliconflow.svgIcon,
    defaultModels: ['Qwen/Qwen2.5-7B-Instruct', 'deepseek-ai/DeepSeek-V3', 'meta-llama/Llama-3.3-70B-Instruct'],
  },
  {
    id: 'openrouter',
    name: 'OpenRouter',
    vendor: 'openai_compatible',
    baseUrl: 'https://openrouter.ai/api/v1',
    defaultModel: 'openai/gpt-4o-mini',
    description: '聚合 200+ 模型网关',
    category: 'aggregator',
    color: PROVIDER_LOGOS.openrouter.color,
    initials: PROVIDER_LOGOS.openrouter.initials,
    svgIcon: PROVIDER_LOGOS.openrouter.svgIcon,
    defaultModels: ['openai/gpt-4o-mini', 'anthropic/claude-3.5-sonnet', 'google/gemini-2.0-flash-exp'],
  },
  {
    id: 'together',
    name: 'Together AI',
    vendor: 'openai_compatible',
    baseUrl: 'https://api.together.xyz/v1',
    defaultModel: 'meta-llama/Llama-3.3-70B-Instruct-Turbo',
    description: '开源模型云端推理',
    category: 'aggregator',
    color: PROVIDER_LOGOS.together.color,
    initials: PROVIDER_LOGOS.together.initials,
    defaultModels: ['meta-llama/Llama-3.3-70B-Instruct-Turbo', 'mistralai/Mixtral-8x7B-Instruct-v0.1'],
  },
  {
    id: 'fireworks',
    name: 'Fireworks AI',
    vendor: 'openai_compatible',
    baseUrl: 'https://api.fireworks.ai/inference/v1',
    defaultModel: 'accounts/fireworks/models/llama-v3p3-70b-instruct',
    description: '高速开源模型推理',
    category: 'aggregator',
    color: PROVIDER_LOGOS.fireworks.color,
    initials: PROVIDER_LOGOS.fireworks.initials,
    defaultModels: ['accounts/fireworks/models/llama-v3p3-70b-instruct', 'accounts/fireworks/models/llama-v3-70b-instruct'],
  },
  {
    id: 'ollama',
    name: 'Ollama',
    vendor: 'ollama',
    baseUrl: 'http://localhost:11434/v1',
    defaultModel: 'qwen2.5:7b',
    description: '本地 Ollama 推理引擎',
    category: 'local',
    color: PROVIDER_LOGOS.ollama.color,
    initials: PROVIDER_LOGOS.ollama.initials,
    svgIcon: PROVIDER_LOGOS.ollama.svgIcon,
    defaultModels: ['qwen2.5:7b', 'llama3.1:8b', 'mistral:7b', 'deepseek-r1:7b', 'gemma2:9b'],
  },
  {
    id: 'lmstudio',
    name: 'LM Studio',
    vendor: 'openai_compatible',
    baseUrl: 'http://localhost:1234/v1',
    defaultModel: '',
    description: '本地 LM Studio 推理',
    category: 'local',
    color: PROVIDER_LOGOS.lmstudio.color,
    initials: PROVIDER_LOGOS.lmstudio.initials,
    svgIcon: PROVIDER_LOGOS.lmstudio.svgIcon,
    defaultModels: [],
  },
  {
    id: 'vllm',
    name: 'vLLM',
    vendor: 'openai_compatible',
    baseUrl: 'http://localhost:8000/v1',
    defaultModel: '',
    description: '本地 vLLM 高性能推理',
    category: 'local',
    color: PROVIDER_LOGOS.vllm.color,
    initials: PROVIDER_LOGOS.vllm.initials,
    svgIcon: PROVIDER_LOGOS.vllm.svgIcon,
    defaultModels: [],
  },
  {
    id: 'nous',
    name: 'Nous Research',
    vendor: 'openai_compatible',
    baseUrl: 'https://inference-api.nousresearch.com/v1',
    defaultModel: 'deephermes-3-llama-3-8b-preview:free',
    description: 'Nous Research Hermes 系列模型',
    category: 'cloud',
    color: PROVIDER_LOGOS.nous.color,
    initials: PROVIDER_LOGOS.nous.initials,
    defaultModels: ['deephermes-3-llama-3-8b-preview:free', 'hermes-3-llama-3.1-405b'],
  },
  {
    id: 'nvidia',
    name: 'NVIDIA NIM',
    vendor: 'openai_compatible',
    baseUrl: 'https://integrate.api.nvidia.com/v1',
    defaultModel: 'meta/llama-3.1-70b-instruct',
    description: 'NVIDIA NIM 云端推理',
    category: 'cloud',
    color: PROVIDER_LOGOS.nvidia.color,
    initials: PROVIDER_LOGOS.nvidia.initials,
    svgIcon: PROVIDER_LOGOS.nvidia.svgIcon,
    defaultModels: ['meta/llama-3.1-70b-instruct', 'meta/llama-3.1-405b-instruct', 'nvidia/llama-3.1-nemotron-70b-instruct'],
  },
  {
    id: 'stepfun',
    name: 'StepFun',
    vendor: 'openai_compatible',
    baseUrl: 'https://api.stepfun.ai/v1',
    defaultModel: 'step-2-16k',
    description: '阶跃星辰 Step 系列模型',
    category: 'cloud',
    color: PROVIDER_LOGOS.stepfun.color,
    initials: PROVIDER_LOGOS.stepfun.initials,
    svgIcon: PROVIDER_LOGOS.stepfun.svgIcon,
    defaultModels: ['step-2-16k', 'step-1v-32k', 'step-1-flash'],
  },
  {
    id: 'huggingface',
    name: 'HuggingFace',
    vendor: 'openai_compatible',
    baseUrl: 'https://api-inference.huggingface.co/v1',
    defaultModel: 'meta-llama/Llama-3.3-70B-Instruct',
    description: 'HuggingFace 推理 API 聚合',
    category: 'aggregator',
    color: PROVIDER_LOGOS.huggingface.color,
    initials: PROVIDER_LOGOS.huggingface.initials,
    defaultModels: ['meta-llama/Llama-3.3-70B-Instruct', 'mistralai/Mistral-7B-Instruct-v0.3'],
  },
  {
    id: 'arcee',
    name: 'Arcee AI',
    vendor: 'openai_compatible',
    baseUrl: 'https://api.arcee.ai/api/v1',
    defaultModel: 'arcee-blitz',
    description: 'Arcee AI 模型融合平台',
    category: 'cloud',
    color: PROVIDER_LOGOS.arcee.color,
    initials: PROVIDER_LOGOS.arcee.initials,
    defaultModels: ['arcee-blitz', 'arcee-coder', 'arcee-super'],
  },
  {
    id: 'gmi',
    name: 'GMI',
    vendor: 'openai_compatible',
    baseUrl: 'https://api.gmi-serving.com/v1',
    defaultModel: 'gmi-cloud-1',
    description: 'GMI 云端推理服务',
    category: 'cloud',
    color: PROVIDER_LOGOS.gmi.color,
    initials: PROVIDER_LOGOS.gmi.initials,
    defaultModels: ['gmi-cloud-1', 'gmi-cloud-2'],
  },
  {
    id: 'minimax',
    name: 'MiniMax',
    vendor: 'openai_compatible',
    baseUrl: 'https://api.minimax.chat/v1',
    defaultModel: 'MiniMax-Text-01',
    description: 'MiniMax 文本模型',
    category: 'cloud',
    color: PROVIDER_LOGOS.minimax.color,
    initials: PROVIDER_LOGOS.minimax.initials,
    svgIcon: PROVIDER_LOGOS.minimax.svgIcon,
    defaultModels: ['MiniMax-Text-01', 'abab6.5s-chat'],
  },
  {
    id: 'vercel',
    name: 'Vercel AI',
    vendor: 'openai_compatible',
    baseUrl: 'https://sdk.vercel.ai/api/v1',
    defaultModel: 'openai/gpt-4o-mini',
    description: 'Vercel AI 网关聚合',
    category: 'aggregator',
    color: PROVIDER_LOGOS.vercel.color,
    initials: PROVIDER_LOGOS.vercel.initials,
    defaultModels: ['openai/gpt-4o-mini', 'anthropic/claude-3.5-sonnet', 'google/gemini-2.0-flash'],
  },
  {
    id: 'volcengine',
    name: 'Volcengine (火山引擎)',
    vendor: 'openai_compatible',
    baseUrl: 'https://ark.cn-beijing.volces.com/api/v3',
    defaultModel: 'doubao-pro-32k',
    description: '火山引擎豆包大模型',
    category: 'cloud',
    color: PROVIDER_LOGOS.volcengine.color,
    initials: PROVIDER_LOGOS.volcengine.initials,
    svgIcon: PROVIDER_LOGOS.volcengine.svgIcon,
    defaultModels: ['doubao-pro-32k', 'doubao-lite-32k', 'doubao-pro-128k'],
  },
  {
    id: 'aihubmix',
    name: 'AiHubMix',
    vendor: 'openai_compatible',
    baseUrl: 'https://aihubmix.com/v1',
    defaultModel: 'gpt-4o-mini',
    description: 'AiHubMix 多模型聚合网关',
    category: 'aggregator',
    color: PROVIDER_LOGOS.aihubmix.color,
    initials: PROVIDER_LOGOS.aihubmix.initials,
    svgIcon: PROVIDER_LOGOS.aihubmix.svgIcon,
    defaultModels: ['gpt-4o-mini', 'claude-3.5-sonnet', 'gemini-2.0-flash'],
  },
  {
    id: 'qianfan',
    name: 'Qianfan (千帆)',
    vendor: 'openai_compatible',
    baseUrl: 'https://qianfan.baidubce.com/v2',
    defaultModel: 'ernie-4.0-turbo-8k',
    description: '百度千帆文心大模型',
    category: 'cloud',
    color: PROVIDER_LOGOS.qianfan.color,
    initials: PROVIDER_LOGOS.qianfan.initials,
    svgIcon: PROVIDER_LOGOS.qianfan.svgIcon,
    defaultModels: ['ernie-4.0-turbo-8k', 'ernie-3.5-8k', 'ernie-speed-128k'],
  },
  {
    id: 'xiaomimimo',
    name: 'XiaomiMiMo',
    vendor: 'openai_compatible',
    baseUrl: 'https://api.xiaomimimo.com/v1',
    defaultModel: 'mimo-v2-flash',
    description: '小米 MiMo 系列模型',
    category: 'cloud',
    color: PROVIDER_LOGOS.xiaomimimo.color,
    initials: PROVIDER_LOGOS.xiaomimimo.initials,
    svgIcon: PROVIDER_LOGOS.xiaomimimo.svgIcon,
    defaultModels: ['mimo-v2-flash'],
  },
  {
    id: 'azure',
    name: 'Azure OpenAI',
    vendor: 'openai_compatible',
    baseUrl: 'https://YOUR_RESOURCE.openai.azure.com/openai/deployments',
    defaultModel: 'gpt-4o',
    description: 'Azure OpenAI 服务',
    category: 'cloud',
    color: PROVIDER_LOGOS.azure.color,
    initials: PROVIDER_LOGOS.azure.initials,
    svgIcon: PROVIDER_LOGOS.azure.svgIcon,
    defaultModels: ['gpt-4o', 'gpt-4o-mini', 'gpt-4'],
  },
  {
    id: 'custom',
    name: 'Custom',
    vendor: 'openai_compatible',
    baseUrl: '',
    defaultModel: '',
    description: '自定义 OpenAI 兼容端点',
    category: 'aggregator',
    color: '#6b7280',
    initials: 'CU',
    defaultModels: [],
  },
]

interface RawProvider {
  id: string
  name: string
  type?: string
  vendor?: string
  baseUrl?: string
  base_url?: string
  apiKeySet?: boolean
  api_key_set?: boolean
  apiKeyPrefix?: string
  api_key_prefix?: string
  defaultModel?: string
  default_model?: string
  isDefault?: boolean
  is_default?: boolean
  selectedModels?: string[]
  selected_models?: string[]
  models?: unknown[]
}

interface RawTemplate {
  id: string
  name: string
  vendor?: string
  baseUrl?: string
  base_url?: string
  defaultModel?: string
  default_model?: string
  description?: string
}

interface RawModelConfig {
  defaultProvider?: string
  default_provider?: string
  defaultModel?: string
  default_model?: string
  defaultTemperature?: number
  default_temperature?: number
  defaultMaxTokens?: number
  default_max_tokens?: number
  defaultTopP?: number
  default_top_p?: number
  reasonerProvider?: string
  reasoner_provider?: string
  reasonerModel?: string
  reasoner_model?: string
  reasonerTemperature?: number
  reasoner_temperature?: number
  reasonerMaxTokens?: number
  reasoner_max_tokens?: number
  reasonerEffort?: string
  reasoner_effort?: string
  ttsProvider?: string
  tts_provider?: string
  ttsModel?: string
  tts_model?: string
  ttsVoice?: string
  tts_voice?: string
  ttsSpeed?: number
  tts_speed?: number
  sttProvider?: string
  stt_provider?: string
  sttModel?: string
  stt_model?: string
  sttLanguage?: string
  stt_language?: string
  sttAutoSend?: boolean
  stt_auto_send?: boolean
  sttAutoSendDelay?: number
  stt_auto_send_delay?: number
  sttEngine?: string
  stt_engine?: string
  contextWindowSize?: number
  context_window_size?: number
  compressionThreshold?: number
  compression_threshold?: number
  llmCompressEnabled?: boolean
  llm_compress_enabled?: boolean
  summaryModel?: string
  summary_model?: string
  summaryProvider?: string
  summary_provider?: string
}

const TTS_VOICES = [
  { value: 'zh-CN-XiaoxiaoNeural', label: '晓晓（女·温柔）' },
  { value: 'zh-CN-YunxiNeural', label: '云希（男·阳光）' },
  { value: 'zh-CN-YunjianNeural', label: '云健（男·沉稳）' },
  { value: 'zh-CN-XiaoyiNeural', label: '晓艺（女·活泼）' },
  { value: 'en-US-JennyNeural', label: 'Jenny（EN·Female）' },
  { value: 'en-US-GuyNeural', label: 'Guy（EN·Male）' },
  { value: 'ja-JP-NanamiNeural', label: '七海（JA·Female）' },
  { value: 'ja-JP-KeitaNeural', label: '圭太（JA·Male）' },
] as const

/** TTS 引擎选项（与后端 engine_meta 对应） */
const TTS_ENGINE_OPTIONS = [
  { value: 'auto', label: '自动（按降级链选择）', category: 'auto', needsApiKey: false },
  { value: 'edge-tts', label: 'Edge TTS（在线·免费）', category: 'cloud-free', needsApiKey: false },
  { value: 'gemini', label: 'Gemini TTS（Google·免费层）', category: 'cloud-paid', needsApiKey: true },
  { value: 'minimax', label: 'MiniMax TTS（高质量）', category: 'cloud-paid', needsApiKey: true },
  { value: 'siliconflow', label: 'SiliconFlow TTS（CosyVoice2 云端）', category: 'cloud-paid', needsApiKey: true },
  { value: 'fish-audio', label: 'Fish Audio TTS（多语言）', category: 'cloud-paid', needsApiKey: true },
  { value: 'sherpa-onnx', label: 'Sherpa-ONNX TTS（离线神经网络）', category: 'local', needsApiKey: false },
  { value: 'local', label: '本地 TTS（pyttsx3·CPU）', category: 'local', needsApiKey: false },
] as const

/** 各引擎音色列表 */
const TTS_ENGINE_VOICES: Record<string, Array<{ value: string; label: string }>> = {
  'edge-tts': [...TTS_VOICES],
  'gemini': [
    { value: 'Leda', label: 'Leda' },
    { value: 'Puck', label: 'Puck' },
    { value: 'Charon', label: 'Charon' },
    { value: 'Aoede', label: 'Aoede' },
    { value: 'Fenrir', label: 'Fenrir' },
    { value: 'Kore', label: 'Kore' },
    { value: 'Orus', label: 'Orus' },
    { value: 'Zephyr', label: 'Zephyr' },
    { value: 'Sulochan', label: 'Sulochan' },
    { value: 'Algenib', label: 'Algenib' },
    { value: 'Achernar', label: 'Achernar' },
    { value: 'Aldebaran', label: 'Aldebaran' },
    { value: 'Bellatrix', label: 'Bellatrix' },
    { value: 'Castor', label: 'Castor' },
    { value: 'Pollux', label: 'Pollux' },
  ],
  'minimax': [
    { value: 'English_Graceful_Lady', label: 'English Graceful Lady（英文优雅女声）' },
    { value: 'English_Trustworth_Man', label: 'English Trustworth Man（英文可靠男声）' },
    { value: 'Chinese_Gentle_Lady', label: 'Chinese Gentle Lady（中文温柔女声）' },
    { value: 'Chinese_Serene_Man', label: 'Chinese Serene Man（中文沉稳男声）' },
    { value: 'Chinese_Expressive_Girl', label: 'Chinese Expressive Girl（中文活泼女孩）' },
    { value: 'Chinese_Fresh_Girl', label: 'Chinese Fresh Girl（中文清新女声）' },
    { value: 'Japanese_Calm_Woman', label: 'Japanese Calm Woman（日文冷静女声）' },
  ],
  'siliconflow': [
    { value: 'FunAudioLLM/CosyVoice2-0.5B:alex', label: 'Alex（英文男声）' },
    { value: 'FunAudioLLM/CosyVoice2-0.5B:benjamin', label: 'Benjamin（英文男声）' },
    { value: 'FunAudioLLM/CosyVoice2-0.5B:bella', label: 'Bella（英文女声）' },
    { value: 'FunAudioLLM/CosyVoice2-0.5B:claire', label: 'Claire（英文女声）' },
    { value: 'FunAudioLLM/CosyVoice2-0.5B:david', label: 'David（英文男声）' },
    { value: 'FunAudioLLM/CosyVoice2-0.5B:diana', label: 'Diana（英文女声）' },
    { value: 'FunAudioLLM/CosyVoice2-0.5B:emily', label: 'Emily（英文女声）' },
    { value: 'FunAudioLLM/CosyVoice2-0.5B:grace', label: 'Grace（英文女声）' },
  ],
  'fish-audio': [
    { value: '', label: '请输入 reference_id 或角色名称' },
  ],
  'sherpa-onnx': [
    { value: 'zh-female', label: '中文女声' },
    { value: 'en-female', label: '英文女声' },
  ],
  'local': [],
  'auto': [],
}

/** 各引擎默认模型 */
const TTS_ENGINE_DEFAULT_MODEL: Record<string, string> = {
  'gemini': 'gemini-2.5-flash-preview-tts',
  'minimax': 'speech-2.8-hd',
  'siliconflow': 'FunAudioLLM/CosyVoice2-0.5B',
}
const STT_LANGUAGES = [
  { value: 'zh-CN', label: '中文（简体）' },
  { value: 'zh-TW', label: '中文（繁体）' },
  { value: 'en-US', label: 'English' },
  { value: 'ja-JP', label: '日本語' },
  { value: 'ko-KR', label: '한국어' },
  { value: 'fr-FR', label: 'Français' },
  { value: 'de-DE', label: 'Deutsch' },
  { value: 'es-ES', label: 'Español' },
] as const

export const useModelStore = defineStore('model', () => {
  const { apiGet, apiPost, apiDelete, apiPatch } = useApi()

  const providers = ref<ModelProvider[]>([])
  const templates = ref<ProviderTemplate[]>([])
  const modelConfig = ref<ModelConfig>({
    defaultProvider: '',
    defaultModel: '',
    defaultTemperature: 0.7,
    defaultMaxTokens: 4096,
    defaultTopP: 0.9,
    reasonerProvider: '',
    reasonerModel: '',
    reasonerTemperature: undefined,
    reasonerMaxTokens: undefined,
    reasonerEffort: '',
  })
  const ttsConfig = ref<TTSConfig>({
    provider: '',
    model: 'tts-1',
    voice: 'zh-CN-XiaoxiaoNeural',
    speed: 1.0,
    baseUrl: '',
    apiKeySet: false,
    engine: 'auto',
  })
  const sttConfig = ref<STTConfig>({
    provider: '',
    model: 'whisper-1',
    language: 'zh-CN',
    autoSend: false,
    autoSendDelay: 2000,
    baseUrl: '',
    apiKeySet: false,
    engine: 'auto',
  })
  const loading = ref(false)
  const saveStatus = ref<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const sttEngines = ref<STTEngine[]>([])

  const defaultProvider = computed(() =>
    providers.value.find(p => p.isDefault)
  )

  const allModels = computed(() => {
    const models: (ModelInfo & { providerId: string })[] = []
    for (const provider of providers.value) {
      for (const model of provider.models) {
        models.push({ ...model, providerId: provider.id })
      }
    }
    return models
  })

  const allTemplates = computed(() => {
    const backendIds = new Set(templates.value.map(t => t.id))
    const unique = LOCAL_TEMPLATES.filter(t => !backendIds.has(t.id))
    return [...templates.value, ...unique]
  })

  const templatesByCategory = computed(() => {
    const cats: Record<string, ProviderTemplate[]> = { cloud: [], local: [], aggregator: [] }
    for (const t of allTemplates.value) {
      const key = t.category || 'cloud'
      if (!cats[key]) cats[key] = []
      cats[key].push(t)
    }
    return cats
  })

  const getProviderModels = (providerId: string): ModelInfo[] => {
    const provider = providers.value.find(p => p.id === providerId)
    return provider?.models || []
  }

  const resolveModel = computed(() => {
    const mainProvider = modelConfig.value.defaultProvider
    const mainModel = modelConfig.value.defaultModel
    const reasonerProvider = modelConfig.value.reasonerProvider
    const reasonerModel = modelConfig.value.reasonerModel

    if (mainProvider && mainModel) {
      return { provider: mainProvider, model: mainModel, type: 'main' as const }
    }
    if (reasonerProvider && reasonerModel) {
      return { provider: reasonerProvider, model: reasonerModel, type: 'reasoner' as const }
    }
    const first = providers.value[0]
    if (first) {
      return { provider: first.id, model: first.defaultModel, type: 'fallback' as const }
    }
    return null
  })

  const resolveReasonerModel = computed(() => {
    const rp = modelConfig.value.reasonerProvider
    const rm = modelConfig.value.reasonerModel
    if (rp && rm) {
      return { provider: rp, model: rm }
    }
    const mp = modelConfig.value.defaultProvider
    const mm = modelConfig.value.defaultModel
    if (mp && mm) {
      return { provider: mp, model: mm }
    }
    return null
  })

  const fetchProviders = async () => {
    loading.value = true
    try {
      const result = await apiGet<RawProvider[]>('/models/providers')
      const raw = Array.isArray(result) ? result : []
      providers.value = raw.map(p => {
        const prefix = p.apiKeyPrefix || p.api_key_prefix || ''
        return {
          id: p.id,
          name: p.name,
          type: p.type || p.vendor || 'openai_compatible',
          vendor: p.vendor || '',
          baseUrl: p.baseUrl || p.base_url || '',
          apiKeyPrefix: prefix,
          apiKeySet: Boolean(prefix) || p.apiKeySet || p.api_key_set || false,
          defaultModel: p.defaultModel || p.default_model || '',
          isDefault: p.isDefault || p.is_default || false,
          selectedModels: p.selectedModels || p.selected_models || [],
          models: (p.models || []) as { id: string; name: string }[],
        }
      })

      for (const provider of providers.value) {
        if (provider.id && provider.models.length === 0) {
          fetchProviderModels(provider.id).catch(() => {})
        }
      }
    } catch {
      providers.value = []
    } finally {
      loading.value = false
    }
  }

  const fetchTemplates = async () => {
    try {
      const result = await apiGet<RawTemplate[]>('/models/providers/templates')
      const raw = Array.isArray(result) ? result : []
      templates.value = raw.map(t => {
        const local = LOCAL_TEMPLATES.find(lt => lt.id === t.id)
        return {
          id: t.id,
          name: t.name,
          vendor: t.vendor || '',
          baseUrl: t.baseUrl || t.base_url || '',
          defaultModel: t.defaultModel || t.default_model || '',
          description: t.description || '',
          category: local?.category || 'cloud' as const,
          color: local?.color || '#6b7280',
          initials: local?.initials || t.name.slice(0, 2).toUpperCase(),
          svgIcon: local?.svgIcon,
          defaultModels: local?.defaultModels,
        }
      })
    } catch {
      templates.value = []
    }
  }

  const addProvider = async (provider: {
    id: string
    name: string
    vendor: string
    baseUrl: string
    apiKey: string
    defaultModel: string
    isDefault: boolean
    selectedModels?: string[]
  }) => {
    const result = await apiPost<ModelProvider>('/models/providers', {
      id: provider.id,
      name: provider.name,
      vendor: provider.vendor,
      baseUrl: provider.baseUrl,
      apiKey: provider.apiKey,
      defaultModel: provider.defaultModel,
      isDefault: provider.isDefault,
      selectedModels: provider.selectedModels || [],
    })
    await fetchProviders()
    return result
  }

  const updateProvider = async (providerId: string, updates: {
    name?: string
    vendor?: string
    baseUrl?: string
    apiKey?: string
    defaultModel?: string
    isDefault?: boolean
    selectedModels?: string[]
  }) => {
    const result = await apiPatch<ModelProvider>(`/models/providers/${providerId}`, {
      name: updates.name,
      vendor: updates.vendor,
      baseUrl: updates.baseUrl,
      apiKey: updates.apiKey,
      defaultModel: updates.defaultModel,
      isDefault: updates.isDefault,
      selectedModels: updates.selectedModels,
    })
    await fetchProviders()
    return result
  }

  const removeProvider = async (providerId: string) => {
    await apiDelete(`/models/providers/${providerId}`)
    providers.value = providers.value.filter(p => p.id !== providerId)
  }

  const testProvider = async (payload: {
    vendor: string
    baseUrl: string
    apiKey: string
    defaultModel?: string
  }): Promise<{ success: boolean; models: ModelInfo[]; error: string | null }> => {
    const result = await apiPost<{ success: boolean; models: ModelInfo[]; error: string | null } | { data: { success: boolean; models: ModelInfo[]; error: string | null } }>('/models/providers/test', {
      vendor: payload.vendor,
      baseUrl: payload.baseUrl,
      apiKey: payload.apiKey,
      defaultModel: payload.defaultModel || '',
    })
    const data = unwrapData<{ success: boolean; models: ModelInfo[]; error: string | null }>(result)
    return data
  }

  const fetchProviderModels = async (providerId: string) => {
    const result = await apiGet<ModelInfo[] | { data: ModelInfo[] }>(`/models/providers/${providerId}/models`)
    const models = unwrapData<ModelInfo[]>(result)
    const provider = providers.value.find(p => p.id === providerId)
    if (provider) {
      provider.models = models
    }
    return models
  }

  const fetchModelConfig = async () => {
    try {
      const result = await apiGet<RawModelConfig>('/models/config')
      const config = unwrapData<RawModelConfig>(result)
      if (config) {
        modelConfig.value = {
          defaultProvider: config.defaultProvider || config.default_provider || '',
          defaultModel: config.defaultModel || config.default_model || '',
          defaultTemperature: config.defaultTemperature ?? config.default_temperature ?? 0.7,
          defaultMaxTokens: config.defaultMaxTokens ?? config.default_max_tokens ?? 4096,
          defaultTopP: config.defaultTopP ?? config.default_top_p ?? 0.9,
          reasonerProvider: config.reasonerProvider || config.reasoner_provider,
          reasonerModel: config.reasonerModel || config.reasoner_model,
          reasonerTemperature: config.reasonerTemperature ?? config.reasoner_temperature,
          reasonerMaxTokens: config.reasonerMaxTokens ?? config.reasoner_max_tokens,
          reasonerEffort: config.reasonerEffort || config.reasoner_effort,
          ttsProvider: config.ttsProvider || config.tts_provider,
          ttsModel: config.ttsModel || config.tts_model || 'tts-1',
          ttsVoice: config.ttsVoice || config.tts_voice || 'zh-CN-XiaoxiaoNeural',
          ttsSpeed: config.ttsSpeed ?? config.tts_speed ?? 1.0,
          sttProvider: config.sttProvider || config.stt_provider,
          sttModel: config.sttModel || config.stt_model || 'whisper-1',
          sttLanguage: config.sttLanguage || config.stt_language || 'zh-CN',
          sttAutoSend: config.sttAutoSend ?? config.stt_auto_send ?? false,
          sttAutoSendDelay: config.sttAutoSendDelay ?? config.stt_auto_send_delay ?? 2000,
          sttEngine: config.sttEngine || config.stt_engine || 'auto',
          contextWindowSize: config.contextWindowSize ?? config.context_window_size ?? 0,
          compressionThreshold: config.compressionThreshold ?? config.compression_threshold ?? 0.70,
          llmCompressEnabled: config.llmCompressEnabled ?? config.llm_compress_enabled ?? false,
          summaryModel: config.summaryModel || config.summary_model || '',
          summaryProvider: config.summaryProvider || config.summary_provider || '',
        }
      }
    } catch {
      // use defaults
    }

    loadTTSConfigFromLocal()
    loadSTTConfigFromLocal()
  }

  const updateModelConfig = async (config: Partial<ModelConfig>) => {
    saveStatus.value = 'saving'
    try {
      const body: Record<string, unknown> = {}
      if (config.defaultProvider !== undefined) body.provider = config.defaultProvider
      if (config.defaultModel !== undefined) body.model = config.defaultModel
      if (config.defaultTemperature !== undefined) body.temperature = config.defaultTemperature
      if (config.defaultMaxTokens !== undefined) body.maxTokens = config.defaultMaxTokens
      if (config.defaultTopP !== undefined) body.topP = config.defaultTopP
      if (config.reasonerProvider !== undefined) body.reasonerProvider = config.reasonerProvider
      if (config.reasonerModel !== undefined) body.reasonerModel = config.reasonerModel
      if (config.reasonerTemperature !== undefined) body.reasonerTemperature = config.reasonerTemperature
      if (config.reasonerMaxTokens !== undefined) body.reasonerMaxTokens = config.reasonerMaxTokens
      if (config.reasonerEffort !== undefined) body.reasonerEffort = config.reasonerEffort
      if (config.ttsProvider !== undefined) body.ttsProvider = config.ttsProvider
      if (config.ttsModel !== undefined) body.ttsModel = config.ttsModel
      if (config.ttsVoice !== undefined) body.ttsVoice = config.ttsVoice
      if (config.ttsSpeed !== undefined) body.ttsSpeed = config.ttsSpeed
      if (config.sttProvider !== undefined) body.sttProvider = config.sttProvider
      if (config.sttModel !== undefined) body.sttModel = config.sttModel
      if (config.sttLanguage !== undefined) body.sttLanguage = config.sttLanguage
      if (config.sttAutoSend !== undefined) body.sttAutoSend = config.sttAutoSend
      if (config.sttAutoSendDelay !== undefined) body.sttAutoSendDelay = config.sttAutoSendDelay
      if (config.sttEngine !== undefined) body.sttEngine = config.sttEngine
      if (config.contextWindowSize !== undefined) body.contextWindowSize = config.contextWindowSize
      if (config.compressionThreshold !== undefined) body.compressionThreshold = config.compressionThreshold
      if (config.llmCompressEnabled !== undefined) body.llmCompressEnabled = config.llmCompressEnabled
      if (config.summaryModel !== undefined) body.summaryModel = config.summaryModel
      if (config.summaryProvider !== undefined) body.summaryProvider = config.summaryProvider

      try {
        await apiPatch('/models/config', body)
        await fetchModelConfig()
      } catch {
        modelConfig.value = { ...modelConfig.value, ...config }
      }
      saveStatus.value = 'saved'
      setTimeout(() => { saveStatus.value = 'idle' }, 2000)
    } catch {
      saveStatus.value = 'error'
      setTimeout(() => { saveStatus.value = 'idle' }, 3000)
    }
  }

  const saveTTSConfigToLocal = () => {
    const cfg = ttsConfig.value
    const data = {
      provider: cfg.provider,
      model: cfg.model,
      voice: cfg.voice,
      speed: cfg.speed,
      baseUrl: cfg.baseUrl,
      engine: cfg.engine,
    }
    setItem('luominest-tts-config', data)
    window.api?.config?.setTTS(data).catch(() => {})
  }

  const loadTTSConfigFromLocal = () => {
    const saved = getItem<Partial<TTSConfig> | null>('luominest-tts-config', null)
    if (saved) {
      ttsConfig.value = {
        provider: saved.provider || modelConfig.value.ttsProvider || '',
        model: saved.model || modelConfig.value.ttsModel || 'tts-1',
        voice: saved.voice || modelConfig.value.ttsVoice || 'zh-CN-XiaoxiaoNeural',
        speed: saved.speed ?? modelConfig.value.ttsSpeed ?? 1.0,
        baseUrl: saved.baseUrl || '',
        apiKeySet: false,
        engine: saved.engine || saved.provider || 'auto',
      }
    } else {
      ttsConfig.value = {
        provider: modelConfig.value.ttsProvider || '',
        model: modelConfig.value.ttsModel || 'tts-1',
        voice: modelConfig.value.ttsVoice || 'zh-CN-XiaoxiaoNeural',
        speed: modelConfig.value.ttsSpeed ?? 1.0,
        baseUrl: '',
        apiKeySet: false,
        engine: modelConfig.value.ttsProvider || 'auto',
      }
    }
  }

  const saveSTTConfigToLocal = () => {
    const cfg = sttConfig.value
    const data = {
      provider: cfg.provider,
      model: cfg.model,
      language: cfg.language,
      autoSend: cfg.autoSend,
      autoSendDelay: cfg.autoSendDelay,
      baseUrl: cfg.baseUrl,
      engine: cfg.engine,
    }
    setItem('luominest-stt-config', data)
    window.api?.config?.setSTT(data).catch(() => {})
  }

  const loadSTTConfigFromLocal = () => {
    const saved = getItem<Partial<STTConfig> | null>('luominest-stt-config', null)
    if (saved) {
      sttConfig.value = {
        provider: saved.provider || modelConfig.value.sttProvider || '',
        model: saved.model || modelConfig.value.sttModel || 'whisper-1',
        language: saved.language || modelConfig.value.sttLanguage || 'zh-CN',
        autoSend: saved.autoSend ?? modelConfig.value.sttAutoSend ?? false,
        autoSendDelay: saved.autoSendDelay ?? modelConfig.value.sttAutoSendDelay ?? 2000,
        baseUrl: saved.baseUrl || '',
        apiKeySet: false,
        engine: saved.engine || 'auto',
      }
    } else {
      sttConfig.value = {
        provider: modelConfig.value.sttProvider || '',
        model: modelConfig.value.sttModel || 'whisper-1',
        language: modelConfig.value.sttLanguage || 'zh-CN',
        autoSend: modelConfig.value.sttAutoSend ?? false,
        autoSendDelay: modelConfig.value.sttAutoSendDelay ?? 2000,
        baseUrl: '',
        apiKeySet: false,
        engine: 'auto',
      }
    }
  }

  const updateTTSConfig = async (updates: Partial<TTSConfig>) => {
    ttsConfig.value = { ...ttsConfig.value, ...updates }
    saveTTSConfigToLocal()

    const configUpdates: Partial<ModelConfig> = {}
    // engine 与 provider 同义，统一写入 ttsProvider
    const engineId = updates.engine ?? updates.provider
    if (engineId !== undefined) configUpdates.ttsProvider = engineId
    if (updates.provider !== undefined) configUpdates.ttsProvider = updates.provider
    if (updates.model !== undefined) configUpdates.ttsModel = updates.model
    if (updates.voice !== undefined) configUpdates.ttsVoice = updates.voice
    if (updates.speed !== undefined) configUpdates.ttsSpeed = updates.speed

    try {
      await updateModelConfig(configUpdates)
    } catch {
      // local save already done
    }
  }

  const updateSTTConfig = async (updates: Partial<STTConfig>) => {
    sttConfig.value = { ...sttConfig.value, ...updates }
    saveSTTConfigToLocal()

    const configUpdates: Partial<ModelConfig> = {}
    if (updates.provider !== undefined) configUpdates.sttProvider = updates.provider
    if (updates.model !== undefined) configUpdates.sttModel = updates.model
    if (updates.language !== undefined) configUpdates.sttLanguage = updates.language
    if (updates.autoSend !== undefined) configUpdates.sttAutoSend = updates.autoSend
    if (updates.autoSendDelay !== undefined) configUpdates.sttAutoSendDelay = updates.autoSendDelay
    if (updates.engine !== undefined) configUpdates.sttEngine = updates.engine

    try {
      await updateModelConfig(configUpdates)
    } catch {
      // local save already done
    }
  }

  const fetchSTTEngines = async () => {
    try {
      const result = await apiGet<{ engines: STTEngine[] } | STTEngine[]>('/chat/stt/engines')
      const data = unwrapData<{ engines: STTEngine[] } | STTEngine[]>(result)
      if (Array.isArray(data)) {
        sttEngines.value = data
      } else if (data?.engines) {
        sttEngines.value = data.engines
      }
    } catch {
      sttEngines.value = []
    }
  }

  return {
    providers,
    templates,
    modelConfig,
    ttsConfig,
    sttConfig,
    sttEngines,
    loading,
    saveStatus,
    defaultProvider,
    allModels,
    allTemplates,
    templatesByCategory,
    resolveModel,
    resolveReasonerModel,
    getProviderModels,
    fetchProviders,
    fetchTemplates,
    addProvider,
    updateProvider,
    removeProvider,
    testProvider,
    fetchProviderModels,
    fetchModelConfig,
    updateModelConfig,
    updateTTSConfig,
    updateSTTConfig,
    fetchSTTEngines,
    TTS_VOICES,
    TTS_ENGINE_OPTIONS,
    TTS_ENGINE_VOICES,
    TTS_ENGINE_DEFAULT_MODEL,
    STT_LANGUAGES,
  }
})

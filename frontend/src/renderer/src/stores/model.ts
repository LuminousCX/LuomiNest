import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ModelProvider, ModelInfo, ModelConfig, ProviderTemplate, TTSConfig, STTConfig } from '../types'
import { useApi } from '../composables/useApi'

const unwrapData = <T>(result: any): T => {
  if (result && typeof result === 'object' && 'data' in result) {
    return result.data as T
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
    color: '#10a37f',
    initials: 'OA',
    svgIcon: '<svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M21.55 10.004a5.416 5.416 0 00-.478-4.501c-1.217-2.09-3.662-3.166-6.05-2.66A5.59 5.59 0 0010.831 1C8.39.995 6.224 2.546 5.473 4.838A5.553 5.553 0 001.76 7.496a5.487 5.487 0 00.691 6.5 5.416 5.416 0 00.477 4.502c1.217 2.09 3.662 3.165 6.05 2.66A5.586 5.586 0 0013.168 23c2.443.006 4.61-1.546 5.361-3.84a5.553 5.553 0 003.715-2.66 5.488 5.488 0 00-.693-6.497v.001zm-8.381 11.558a4.199 4.199 0 01-2.675-.954c.034-.018.093-.05.132-.074l4.44-2.53a.71.71 0 00.364-.623v-6.176l1.877 1.069c.02.01.033.029.036.05v5.115c-.003 2.274-1.87 4.118-4.174 4.123zM4.192 17.78a4.059 4.059 0 01-.498-2.763c.032.02.09.055.131.078l4.44 2.53c.225.13.504.13.73 0l5.42-3.088v2.138a.068.068 0 01-.027.057L9.9 19.288c-1.999 1.136-4.552.46-5.707-1.51h-.001zM3.023 8.216A4.15 4.15 0 015.198 6.41l-.002.151v5.06a.711.711 0 00.364.624l5.42 3.087-1.876 1.07a.067.067 0 01-.063.005l-4.489-2.559c-1.995-1.14-2.679-3.658-1.53-5.63h.001zm15.417 3.54l-5.42-3.088L14.896 7.6a.067.067 0 01.063-.006l4.489 2.557c1.998 1.14 2.683 3.662 1.529 5.633a4.163 4.163 0 01-2.174 1.807V12.38a.71.71 0 00-.363-.623zm1.867-2.773a6.04 6.04 0 00-.132-.078l-4.44-2.53a.731.731 0 00-.729 0l-5.42 3.088V7.325a.068.068 0 01.027-.057L14.1 4.713c2-1.137 4.555-.46 5.707 1.513.487.833.664 1.809.499 2.757h.001zm-11.741 3.81l-1.877-1.068a.065.065 0 01-.036-.051V6.559c.001-2.277 1.873-4.122 4.181-4.12.976 0 1.92.338 2.671.954-.034.018-.092.05-.131.073l-4.44 2.53a.71.71 0 00-.365.623l-.003 6.173v.002zm1.02-2.168L12 9.25l2.414 1.375v2.75L12 14.75l-2.415-1.375v-2.75z"/></svg>',
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
    color: '#d4a574',
    initials: 'AN',
    svgIcon: '<svg viewBox="0 0 24 24" width="24" height="24"><path d="M4.709 15.955l4.72-2.647.08-.23-.08-.128H9.2l-.79-.048-2.698-.073-2.339-.097-2.266-.122-.571-.121L0 11.784l.055-.352.48-.321.686.06 1.52.103 2.278.158 1.652.097 2.449.255h.389l.055-.157-.134-.098-.103-.097-2.358-1.596-2.552-1.688-1.336-.972-.724-.491-.364-.462-.158-1.008.656-.722.881.06.225.061.893.686 1.908 1.476 2.491 1.833.365.304.145-.103.019-.073-.164-.274-1.355-2.446-1.446-2.49-.644-1.032-.17-.619a2.97 2.97 0 01-.104-.729L6.283.134 6.696 0l.996.134.42.364.62 1.414 1.002 2.229 1.555 3.03.456.898.243.832.091.255h.158V9.01l.128-1.706.237-2.095.23-2.695.08-.76.376-.91.747-.492.584.28.48.685-.067.444-.286 1.851-.559 2.903-.364 1.942h.212l.243-.242.985-1.306 1.652-2.064.73-.82.85-.904.547-.431h1.033l.76 1.129-.34 1.166-1.064 1.347-.881 1.142-1.264 1.7-.79 1.36.073.11.188-.02 2.856-.606 1.543-.28 1.841-.315.833.388.091.395-.328.807-1.969.486-2.309.462-3.439.813-.042.03.049.061 1.549.146.662.036h1.622l3.02.225.79.522.474.638-.079.485-1.215.62-1.64-.389-3.829-.91-1.312-.329h-.182v.11l1.093 1.068 2.006 1.81 2.509 2.33.127.578-.322.455-.34-.049-2.205-1.657-.851-.747-1.926-1.62h-.128v.17l.444.649 2.345 3.521.122 1.08-.17.353-.608.213-.668-.122-1.374-1.925-1.415-2.167-1.143-1.943-.14.08-.674 7.254-.316.37-.729.28-.607-.461-.322-.747.322-1.476.389-1.924.315-1.53.286-1.9.17-.632-.012-.042-.14.018-1.434 1.967-2.18 2.945-1.726 1.845-.414.164-.717-.37.067-.662.401-.589 2.388-3.036 1.44-1.882.93-1.086-.006-.158h-.055L4.132 18.56l-1.13.146-.487-.456.061-.746.231-.243 1.908-1.312-.006.006z" fill="#D97757"/></svg>',
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
    color: '#4d6bfe',
    initials: 'DS',
    svgIcon: '<svg viewBox="0 0 24 24" width="24" height="24"><path d="M23.748 4.482c-.254-.124-.364.113-.512.234-.051.039-.094.09-.137.136-.372.397-.806.657-1.373.626-.829-.046-1.537.214-2.163.848-.133-.782-.575-1.248-1.247-1.548-.352-.156-.708-.311-.955-.65-.172-.241-.219-.51-.305-.774-.055-.16-.11-.323-.293-.35-.2-.031-.278.136-.356.276-.313.572-.434 1.202-.422 1.84.027 1.436.633 2.58 1.838 3.393.137.093.172.187.129.323-.082.28-.18.552-.266.833-.055.179-.137.217-.329.14a5.526 5.526 0 01-1.736-1.18c-.857-.828-1.631-1.742-2.597-2.458a11.365 11.365 0 00-.689-.471c-.985-.957.13-1.743.388-1.836.27-.098.093-.432-.779-.428-.872.004-1.67.295-2.687.684a3.055 3.055 0 01-.465.137 9.597 9.597 0 00-2.883-.102c-1.885.21-3.39 1.102-4.497 2.623C.082 8.606-.231 10.684.152 12.85c.403 2.284 1.569 4.175 3.36 5.653 1.858 1.533 3.997 2.284 6.438 2.14 1.482-.085 3.133-.284 4.994-1.86.47.234.962.327 1.78.397.63.059 1.236-.03 1.705-.128.735-.156.684-.837.419-.961-2.155-1.004-1.682-.595-2.113-.926 1.096-1.296 2.746-2.642 3.392-7.003.05-.347.007-.565 0-.845-.004-.17.035-.237.23-.256a4.173 4.173 0 001.545-.475c1.396-.763 1.96-2.015 2.093-3.517.02-.23-.004-.467-.247-.588zM11.581 18c-2.089-1.642-3.102-2.183-3.52-2.16-.392.024-.321.471-.235.763.09.288.207.486.371.739.114.167.192.416-.113.603-.673.416-1.842-.14-1.897-.167-1.361-.802-2.5-1.86-3.301-3.307-.774-1.393-1.224-2.887-1.298-4.482-.02-.386.093-.522.477-.592a4.696 4.696 0 011.529-.039c2.132.312 3.946 1.265 5.468 2.774.868.86 1.525 1.887 2.202 2.891.72 1.066 1.494 2.082 2.48 2.914.348.292.625.514.891.677-.802.09-2.14.11-3.054-.614zm1-6.44a.306.306 0 01.415-.287.302.302 0 01.2.288.306.306 0 01-.31.307.303.303 0 01-.304-.308zm3.11 1.596c-.2.081-.399.151-.59.16a1.245 1.245 0 01-.798-.254c-.274-.23-.47-.358-.552-.758a1.73 1.73 0 01.016-.588c.07-.327-.008-.537-.239-.727-.187-.156-.426-.199-.688-.199a.559.559 0 01-.254-.078c-.11-.054-.2-.19-.114-.358.028-.054.16-.186.192-.21.356-.202.767-.136 1.146.016.352.144.618.403.825.726.447.698.486 1.493.103 2.227z" fill="#4d6bfe"/></svg>',
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
    color: '#4285f4',
    initials: 'GG',
    svgIcon: '<svg viewBox="0 0 24 24" width="24" height="24"><defs><linearGradient id="gm-fill" x1="0%" x2="68.73%" y1="100%" y2="30.395%"><stop offset="0%" stop-color="#1C7DFF"/><stop offset="52.021%" stop-color="#1C69FF"/><stop offset="100%" stop-color="#F0DCD6"/></linearGradient></defs><path d="M12 24A14.304 14.304 0 000 12 14.304 14.304 0 0012 0a14.305 14.305 0 0012 12 14.305 14.305 0 00-12 12" fill="url(#gm-fill)"/></svg>',
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
    color: '#ff7000',
    initials: 'MI',
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
    color: '#f55036',
    initials: 'GQ',
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
    color: '#1d1d1d',
    initials: 'XA',
    svgIcon: '<svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M6.469 8.776L16.512 23h-4.464L2.005 8.776H6.47zm-.004 7.9l2.233 3.164L6.467 23H2l4.465-6.324zM22 2.582V23h-3.659V7.764L22 2.582zM22 1l-9.952 14.095-2.233-3.163L17.533 1H22z"/></svg>',
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
    color: '#6c5ce7',
    initials: 'MK',
    svgIcon: '<svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>',
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
    color: '#3b5cff',
    initials: 'ZP',
    svgIcon: '<svg viewBox="0 0 24 24" width="24" height="24"><defs><linearGradient id="qw-fill" x1="0%" x2="100%" y1="0%" y2="0%"><stop offset="0%" stop-color="#00055F" stop-opacity=".84"/><stop offset="100%" stop-color="#6F69F7" stop-opacity=".84"/></linearGradient></defs><path d="M12.604 1.34c.393.69.784 1.382 1.174 2.075a.18.18 0 00.157.091h5.552c.174 0 .322.11.446.327l1.454 2.57c.19.337.24.478.024.837-.26.43-.513.864-.76 1.3l-.367.658c-.106.196-.223.28-.04.512l2.652 4.637c.172.301.111.494-.043.77-.437.785-.882 1.564-1.335 2.34-.159.272-.352.375-.68.37-.777-.016-1.552-.01-2.327.016a.099.099 0 00-.081.05 575.097 575.097 0 01-2.705 4.74c-.169.293-.38.363-.725.364-.997.003-2.002.004-3.017.002a.537.537 0 01-.465-.271l-1.335-2.323a.09.09 0 00-.083-.049H4.982c-.285.03-.553-.001-.805-.092l-1.603-2.77a.543.543 0 01-.002-.54l1.207-2.12a.198.198 0 000-.197 550.951 550.951 0 01-1.875-3.272l-.79-1.395c-.16-.31-.173-.496.095-.965.465-.813.927-1.625 1.387-2.436.132-.234.304-.334.584-.335a338.3 338.3 0 012.589-.001.124.124 0 00.107-.063l2.806-4.895a.488.488 0 01.422-.246c.524-.001 1.053 0 1.583-.006L11.704 1c.341-.003.724.032.9.34zm-3.432.403a.06.06 0 00-.052.03L6.254 6.788a.157.157 0 01-.135.078H3.253c-.056 0-.07.025-.041.074l5.81 10.156c.025.042.013.062-.034.063l-2.795.015a.218.218 0 00-.2.116l-1.32 2.31c-.044.078-.021.118.068.118l5.716.008c.046 0 .08.02.104.061l1.403 2.454c.046.081.092.082.139 0l5.006-8.76.783-1.382a.055.055 0 01.096 0l1.424 2.53a.122.122 0 00.107.062l2.763-.02a.04.04 0 00.035-.02.041.041 0 000-.04l-2.9-5.086a.108.108 0 010-.113l.293-.507 1.12-1.977c.024-.041.012-.062-.035-.062H9.2c-.059 0-.073-.026-.043-.077l1.434-2.505a.107.107 0 000-.114L9.225 1.774a.06.06 0 00-.053-.031zm6.29 8.02c.046 0 .058.02.034.06l-.832 1.465-2.613 4.585a.056.056 0 01-.05.029.058.058 0 01-.05-.029L8.498 9.841c-.02-.034-.01-.052.028-.054l.216-.012 6.722-.012z" fill="url(#qw-fill)"/></svg>',
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
    color: '#ff6a00',
    initials: 'DQ',
    svgIcon: '<svg viewBox="0 0 24 24" width="24" height="24"><path d="M19.44 10.153l-2.936 11.586a.215.215 0 00.214.261h5.87a.215.215 0 00.214-.261l-2.95-11.586a.214.214 0 00-.412 0zM3.28 12.778l-2.275 8.96A.214.214 0 001.22 22h4.532a.212.212 0 00.214-.165.214.214 0 000-.097l-2.276-8.96a.214.214 0 00-.41 0z" fill="#00E5E5"/><path d="M7.29 5.359L3.148 21.738a.215.215 0 00.203.261h8.29a.214.214 0 00.215-.261L7.7 5.358a.214.214 0 00-.41 0z" fill="#006EFF"/><path d="M14.44.15a.214.214 0 00-.41 0L8.366 21.739a.214.214 0 00.214.261H19.9a.216.216 0 00.171-.078.214.214 0 00.044-.183L14.439.15z" fill="#006EFF"/><path d="M10.278 7.741L6.685 21.736a.214.214 0 00.214.264h7.17a.215.215 0 00.214-.264L10.688 7.741a.214.214 0 00-.41 0z" fill="#00E5E5"/></svg>',
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
    color: '#7c3aed',
    initials: 'SF',
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
    color: '#6d28d9',
    initials: 'OR',
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
    color: '#3b82f6',
    initials: 'TA',
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
    color: '#ef4444',
    initials: 'FW',
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
    color: '#0d0d0d',
    initials: 'OL',
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
    color: '#1e40af',
    initials: 'LM',
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
    color: '#059669',
    initials: 'VL',
    defaultModels: [],
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

const TTS_VOICES = ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer'] as const
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
  })
  const ttsConfig = ref<TTSConfig>({
    provider: '',
    model: 'tts-1',
    voice: 'alloy',
    speed: 1.0,
    baseUrl: '',
    apiKeySet: false,
  })
  const sttConfig = ref<STTConfig>({
    provider: '',
    model: 'whisper-1',
    language: 'zh-CN',
    autoSend: false,
    autoSendDelay: 2000,
    baseUrl: '',
    apiKeySet: false,
  })
  const loading = ref(false)
  const saveStatus = ref<'idle' | 'saving' | 'saved' | 'error'>('idle')

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
      const result = await apiGet<any[]>('/models/providers')
      const raw = Array.isArray(result) ? result : []
      providers.value = raw.map(p => ({
        id: p.id,
        name: p.name,
        vendor: p.vendor,
        baseUrl: p.baseUrl || p.base_url || '',
        apiKeySet: p.apiKeySet || p.api_key_set || false,
        defaultModel: p.defaultModel || p.default_model || '',
        isDefault: p.isDefault || p.is_default || false,
        models: p.models || [],
      }))

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
      const result = await apiGet<any[]>('/models/providers/templates')
      const raw = Array.isArray(result) ? result : []
      templates.value = raw.map(t => {
        const local = LOCAL_TEMPLATES.find(lt => lt.id === t.id)
        return {
          id: t.id,
          name: t.name,
          vendor: t.vendor,
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
  }) => {
    const result = await apiPost<ModelProvider>('/models/providers', {
      id: provider.id,
      name: provider.name,
      vendor: provider.vendor,
      baseUrl: provider.baseUrl,
      apiKey: provider.apiKey,
      defaultModel: provider.defaultModel,
      isDefault: provider.isDefault,
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
  }) => {
    const result = await apiPatch<ModelProvider>(`/models/providers/${providerId}`, {
      name: updates.name,
      vendor: updates.vendor,
      baseUrl: updates.baseUrl,
      apiKey: updates.apiKey,
      defaultModel: updates.defaultModel,
      isDefault: updates.isDefault,
    })
    await fetchProviders()
    return result
  }

  const removeProvider = async (providerId: string) => {
    await apiDelete(`/models/providers/${providerId}`)
    providers.value = providers.value.filter(p => p.id !== providerId)
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
      const result = await apiGet<any>('/models/config')
      const config = unwrapData<any>(result)
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
          ttsVoice: config.ttsVoice || config.tts_voice || 'alloy',
          ttsSpeed: config.ttsSpeed ?? config.tts_speed ?? 1.0,
          sttProvider: config.sttProvider || config.stt_provider,
          sttModel: config.sttModel || config.stt_model || 'whisper-1',
          sttLanguage: config.sttLanguage || config.stt_language || 'zh-CN',
          sttAutoSend: config.sttAutoSend ?? config.stt_auto_send ?? false,
          sttAutoSendDelay: config.sttAutoSendDelay ?? config.stt_auto_send_delay ?? 2000,
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
      const body: any = {}
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
    }
    localStorage.setItem('luominest-tts-config', JSON.stringify(data))
    window.api?.config?.setTTS(data).catch(() => {})
  }

  const loadTTSConfigFromLocal = () => {
    try {
      const raw = localStorage.getItem('luominest-tts-config')
      if (raw) {
        const saved = JSON.parse(raw)
        ttsConfig.value = {
          provider: saved.provider || modelConfig.value.ttsProvider || '',
          model: saved.model || modelConfig.value.ttsModel || 'tts-1',
          voice: saved.voice || modelConfig.value.ttsVoice || 'alloy',
          speed: saved.speed ?? modelConfig.value.ttsSpeed ?? 1.0,
          baseUrl: saved.baseUrl || '',
          apiKeySet: false,
        }
      } else {
        ttsConfig.value = {
          provider: modelConfig.value.ttsProvider || '',
          model: modelConfig.value.ttsModel || 'tts-1',
          voice: modelConfig.value.ttsVoice || 'alloy',
          speed: modelConfig.value.ttsSpeed ?? 1.0,
          baseUrl: '',
          apiKeySet: false,
        }
      }
    } catch {
      // use defaults
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
    }
    localStorage.setItem('luominest-stt-config', JSON.stringify(data))
    window.api?.config?.setSTT(data).catch(() => {})
  }

  const loadSTTConfigFromLocal = () => {
    try {
      const raw = localStorage.getItem('luominest-stt-config')
      if (raw) {
        const saved = JSON.parse(raw)
        sttConfig.value = {
          provider: saved.provider || modelConfig.value.sttProvider || '',
          model: saved.model || modelConfig.value.sttModel || 'whisper-1',
          language: saved.language || modelConfig.value.sttLanguage || 'zh-CN',
          autoSend: saved.autoSend ?? modelConfig.value.sttAutoSend ?? false,
          autoSendDelay: saved.autoSendDelay ?? modelConfig.value.sttAutoSendDelay ?? 2000,
          baseUrl: saved.baseUrl || '',
          apiKeySet: false,
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
        }
      }
    } catch {
      // use defaults
    }
  }

  const updateTTSConfig = async (updates: Partial<TTSConfig>) => {
    ttsConfig.value = { ...ttsConfig.value, ...updates }
    saveTTSConfigToLocal()

    const configUpdates: Partial<ModelConfig> = {}
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

    try {
      await updateModelConfig(configUpdates)
    } catch {
      // local save already done
    }
  }

  return {
    providers,
    templates,
    modelConfig,
    ttsConfig,
    sttConfig,
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
    fetchProviderModels,
    fetchModelConfig,
    updateModelConfig,
    updateTTSConfig,
    updateSTTConfig,
    TTS_VOICES,
    STT_LANGUAGES,
  }
})

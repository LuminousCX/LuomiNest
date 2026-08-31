<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ref, onMounted } from 'vue'
import { ArrowLeft, ExternalLink, AlertTriangle, Scale, Heart } from 'lucide-vue-next'
import LicenseSectionHeader from '../../components/settings-detail/LicenseSectionHeader.vue'
import LumiSettingsBackground from '../../components/settings-detail/LumiSettingsBackground.vue'
import '../../styles/views/settings-independent-bg.css'
// 打包进前端的默认头像：缓存未就绪或网络失败时兜底显示
import avatarLuminousChenXi from '../../assets/images/avatars/luminous-ChenXi.png'
import avatarKipbbsjsjs from '../../assets/images/avatars/kipbbsjsjs.png'
import avatarNoobL696 from '../../assets/images/avatars/NoobL696.jpg'

const router = useRouter()

const frontendLicenses = [
  {
    name: 'Vue 3',
    version: '3.5',
    author: 'Evan You',
    license: 'MIT',
    description: '渐进式 JavaScript 框架，用于构建用户界面。',
    url: 'https://github.com/vuejs/core'
  },
  {
    name: 'Electron',
    version: '41.0',
    author: 'OpenJS Foundation',
    license: 'MIT',
    description: '使用 JavaScript、HTML 和 CSS 构建跨平台桌面应用程序。',
    url: 'https://github.com/electron/electron'
  },
  {
    name: 'TypeScript',
    version: '6.0',
    author: 'Microsoft',
    license: 'Apache-2.0',
    description: 'JavaScript 的超集，添加了可选的静态类型和基于类的面向对象编程。',
    url: 'https://github.com/microsoft/TypeScript'
  },
  {
    name: 'Pinia',
    version: '3.0',
    author: 'Eduardo San Martin Morote',
    license: 'MIT',
    description: 'Vue 的直觉式、类型安全、灵活且轻量的状态管理库。',
    url: 'https://github.com/vuejs/pinia'
  },
  {
    name: 'Vue Router',
    version: '5.0',
    author: 'Evan You',
    license: 'MIT',
    description: 'Vue.js 的官方路由管理器。',
    url: 'https://github.com/vuejs/router'
  },
  {
    name: 'Vite',
    version: '6.2',
    author: 'Yuxi (Evan) You',
    license: 'MIT',
    description: '下一代前端构建工具，提供极速的开发体验和优化的生产构建。',
    url: 'https://github.com/vitejs/vite'
  },
  {
    name: 'PixiJS',
    version: '7.4',
    author: 'PixiJS Contributors',
    license: 'MIT',
    description: '快速轻量的 2D WebGL 渲染引擎。',
    url: 'https://github.com/pixijs/pixijs'
  },
  {
    name: 'lucide-vue-next',
    version: '0.577.0',
    author: 'Lucide Contributors',
    license: 'ISC',
    description: '简洁美观的开源图标库，为 Lucide 的 Vue 3 实现。',
    url: 'https://github.com/lucide-icons/lucide'
  },
  {
    name: 'Marked',
    version: '18.0',
    author: 'MarkedJS Contributors',
    license: 'MIT',
    description: '低级编译器，用于将 Markdown 解析为 HTML，无需长时间缓存或阻塞。',
    url: 'https://github.com/markedjs/marked'
  },
  {
    name: 'DOMPurify',
    version: '3.4',
    author: 'Cure53',
    license: '(Apache-2.0 OR MPL-2.0)',
    description: '仅清理 HTML 代码并防止 XSS 攻击的 DOM-only 超快速、高容忍度 sanitizer。',
    url: 'https://github.com/cure53/DOMPurify'
  },
  {
    name: '@pixi/unsafe-eval',
    version: '7.4',
    author: 'PixiJS Contributors',
    license: 'MIT',
    description: 'PixiJS 插件，允许在不支持 eval 的环境中运行 PixiJS。',
    url: 'https://github.com/pixijs/pixijs'
  },
  {
    name: 'pixi-live2d-display-mulmotion',
    version: '0.5.0',
    author: 'guansss',
    license: 'MIT',
    description: '基于 PixiJS 的 Live2D 模型渲染器，支持多动作切换的社区维护版本。',
    url: 'https://github.com/guansss/pixi-live2d-display'
  }
]

const backendLicenses = [
  {
    name: 'FastAPI',
    version: '0.115',
    author: 'Sebastián Ramírez',
    license: 'MIT',
    description: '现代、高性能的 Python Web 框架，基于标准 Python 类型提示。',
    url: 'https://github.com/fastapi/fastapi'
  },
  {
    name: 'Uvicorn',
    version: '0.34',
    author: 'Encode',
    license: 'BSD-3-Clause',
    description: '极速 ASGI 服务器，使用 uvloop 和 httptools 构建。',
    url: 'https://github.com/encode/uvicorn'
  },
  {
    name: 'Pydantic',
    version: '2.10',
    author: 'Samuel Colvin',
    license: 'MIT',
    description: 'Python 数据验证与序列化库，使用 Python 类型提示。',
    url: 'https://github.com/pydantic/pydantic'
  },
  {
    name: 'SQLAlchemy',
    version: '2.0',
    author: 'Mike Bayer',
    license: 'MIT',
    description: 'Python SQL 工具包和对象关系映射（ORM）库。',
    url: 'https://github.com/sqlalchemy/sqlalchemy'
  },
  {
    name: 'Alembic',
    version: '1.14',
    author: 'Mike Bayer',
    license: 'MIT',
    description: 'SQLAlchemy 的数据库迁移工具。',
    url: 'https://github.com/sqlalchemy/alembic'
  },
  {
    name: 'PostgreSQL (asyncpg)',
    version: '0.30',
    author: 'MagicStack',
    license: 'PostgreSQL',
    description: 'Python 异步 PostgreSQL 驱动，专为高性能设计。',
    url: 'https://github.com/MagicStack/asyncpg'
  },
  {
    name: 'Redis (redis-py)',
    version: '5.2',
    author: 'Redis Inc.',
    license: 'MIT',
    description: 'Python Redis 客户端，支持 Redis 的所有数据结构和功能。',
    url: 'https://github.com/redis/redis-py'
  },
  {
    name: 'LiteLLM',
    version: '1.55',
    author: 'BerriAI',
    license: 'MIT',
    description: '统一调用 100+ LLM 的 Python SDK，提供 OpenAI 兼容接口。',
    url: 'https://github.com/BerriAI/litellm'
  },
  {
    name: 'OpenAI Python',
    version: '1.58',
    author: 'OpenAI',
    license: 'Apache-2.0',
    description: 'OpenAI 官方 Python SDK，用于访问 GPT 系列模型。',
    url: 'https://github.com/openai/openai-python'
  },
  {
    name: 'Anthropic Python',
    version: '0.42',
    author: 'Anthropic',
    license: 'MIT',
    description: 'Anthropic 官方 Python SDK，用于访问 Claude 系列模型。',
    url: 'https://github.com/anthropics/anthropic-sdk-python'
  },
  {
    name: 'httpx',
    version: '0.28',
    author: 'Encode',
    license: 'BSD-3-Clause',
    description: 'Python 新一代 HTTP 客户端，支持同步和异步请求。',
    url: 'https://github.com/encode/httpx'
  },
  {
    name: 'NumPy',
    version: '2.2',
    author: 'NumPy Developers',
    license: 'BSD-3-Clause',
    description: 'Python 科学计算的基础库，提供多维数组和数学函数。',
    url: 'https://github.com/numpy/numpy'
  },
  {
    name: 'Pydantic Settings',
    version: '2.7',
    author: 'Samuel Colvin',
    license: 'MIT',
    description: 'Pydantic 的配置管理扩展，支持环境变量、文件等来源的配置加载与验证。',
    url: 'https://github.com/pydantic/pydantic-settings'
  },
  {
    name: 'python-multipart',
    version: '0.0.18',
    author: 'Andrew Svetlov',
    license: 'Apache-2.0',
    description: 'Python 的 multipart/form-data 解析库，用于 FastAPI 文件上传和表单数据处理。',
    url: 'https://github.com/andrew-svetlov/python-multipart'
  },
  {
    name: 'aiofiles',
    version: '24.1',
    author: 'Tin Tvrtković',
    license: 'Apache-2.0',
    description: 'Python 异步文件操作库，提供 async/await 风格的文件 I/O 接口。',
    url: 'https://github.com/Tinche/aiofiles'
  },
  {
    name: 'aiosqlite',
    version: '0.20',
    author: 'Amjith Ramanujam',
    license: 'MIT',
    description: 'Python 异步 SQLite 数据库驱动，支持 async/await 异步数据库操作。',
    url: 'https://github.com/omnilib/aiosqlite'
  },
  {
    name: 'aiohttp',
    version: '3.9',
    author: 'Nikolay Kim',
    license: 'Apache-2.0',
    description: 'Python 异步 HTTP 客户端/服务端框架，支持高效的并发网络请求。',
    url: 'https://github.com/aio-libs/aiohttp'
  },
  {
    name: 'websockets',
    version: '14.0',
    author: 'Aymeric Augustin',
    license: 'BSD-3-Clause',
    description: 'Python WebSocket 协议实现库，支持实时双向通信。',
    url: 'https://github.com/python-websockets/websockets'
  },
  {
    name: 'paho-mqtt',
    version: '2.1',
    author: 'Eclipse Foundation',
    license: 'EPL-2.0 OR BSD-3-Clause',
    description: 'Eclipse Paho MQTT 客户端库，支持 MQTT v3.1/v3.1.1/v5.0 物联网通信协议。',
    url: 'https://github.com/eclipse/paho.mqtt.python'
  },
  {
    name: 'pgvector',
    version: '0.3.6',
    author: 'Andrew Kane',
    license: 'MIT',
    description: 'PostgreSQL 向量相似度检索扩展库，支持向量嵌入存储与 ANN 搜索。',
    url: 'https://github.com/pgvector/pgvector-python'
  },
  {
    name: 'python-jose',
    version: '3.3',
    author: 'Michael Davis',
    license: 'MIT',
    description: 'JOSE（JSON 对象签名与加密）标准实现库，支持 JWT 令牌的编解码与验证。',
    url: 'https://github.com/mpdavis/python-jose'
  },
  {
    name: 'passlib',
    version: '1.7.4',
    author: 'Eli Collins',
    license: 'BSD-3-Clause',
    description: 'Python 密码哈希库，支持 bcrypt 等多种密码哈希算法。',
    url: 'https://github.com/glic3rinu/passlib'
  },
  {
    name: 'cryptography',
    version: '44.0',
    author: 'Python Cryptographic Authority',
    license: 'Apache-2.0 OR BSD-3-Clause',
    description: 'Python 加密库，提供对称/非对称加密、数字签名、密钥交换等密码学原语。',
    url: 'https://github.com/pyca/cryptography'
  },
  {
    name: 'Loguru',
    version: '0.7.3',
    author: 'Delgan',
    license: 'MIT',
    description: 'Python 日志库，提供简洁美观的 API、自动旋转、结构化日志等高级特性。',
    url: 'https://github.com/Delgan/loguru'
  },
  {
    name: 'APScheduler',
    version: '3.10',
    author: 'Alex Grönholm',
    license: 'MIT',
    description: 'Python 高级任务调度库，支持 Cron 表达式、固定间隔和一次性定时任务。',
    url: 'https://github.com/agronholm/apscheduler'
  },
  {
    name: 'Tenacity',
    version: '9.0',
    author: 'Kenneth Reitz',
    license: 'Apache-2.0',
    description: 'Python 通用重试库，支持指数退避、自定义异常判断和异步重试。',
    url: 'https://github.com/jd/tenacity'
  },
  {
    name: 'Pillow',
    version: '11.0',
    author: 'Alex Clark',
    license: 'Historical',
    description: 'Python 图像处理库，支持图像打开、操作和保存等多种格式。',
    url: 'https://github.com/python-pillow/Pillow'
  },
  {
    name: 'orjson',
    version: '3.10',
    author: 'ijl',
    license: 'MIT',
    description: 'Python 高性能 JSON 序列化库，比标准 json 模块快 3-10 倍。',
    url: 'https://github.com/ijl/orjson'
  },
  {
    name: 'PyMuPDF',
    version: '1.24',
    author: 'Artifex Software',
    license: 'AGPL-3.0',
    description: 'Python PDF 文档解析库，支持提取文本、图像、表格等结构化内容。',
    url: 'https://github.com/pymupdf/PyMuPDF'
  },
  {
    name: 'python-docx',
    version: '1.1',
    author: 'Steve Canny',
    license: 'MIT',
    description: 'Python Word 文档 (.docx) 创建与解析库，支持读写 Microsoft Word 文件。',
    url: 'https://github.com/python-openxml/python-docx'
  },
  {
    name: 'edge-tts',
    version: '6.1.18',
    author: 'Rany',
    license: 'GPL-3.0',
    description: 'Python 微软 Edge 文本转语音库，利用 Edge 浏览器免费 TTS 服务生成自然语音。',
    url: 'https://github.com/rany2/edge-tts'
  },
  {
    name: 'MCP',
    version: '1.0',
    author: 'Anthropic',
    license: 'MIT',
    description: 'Model Context Protocol Python SDK，用于构建 AI Agent 工具与服务。',
    url: 'https://github.com/modelcontextprotocol/python-sdk'
  },
  {
    name: 'python-magic',
    version: '0.4.27',
    author: 'Adam Hupp',
    license: 'MIT',
    description: 'Python 文件类型检测库，基于 libmagic 识别文件的 MIME 类型。',
    url: 'https://github.com/ahupp/python-magic'
  },
  {
    name: 'tzdata',
    version: '2024.1',
    author: 'Paul Ganssle',
    license: 'Apache-2.0',
    description: 'Python IANA 时区数据库包，提供最新的时区信息支持。',
    url: 'https://github.com/python/tzdata'
  }
]

const referenceProjects = [
  {
    name: 'DeerFlow',
    version: '1.0',
    author: 'Bytedance',
    license: 'MIT',
    description: '字节跳动开源的深度研究框架，用于构建 AI 驱动的多步骤研究工作流。',
    url: 'https://github.com/bytedance/deer-flow'
  },
  {
    name: 'Hermes Agent',
    version: '1.0',
    author: 'Nous Research',
    license: 'MIT',
    description: 'Nous Research 开源的 AI Agent 框架，支持工具调用与多模态交互。',
    url: 'https://github.com/NousResearch/hermes-agent'
  },
  {
    name: 'Mindcraft',
    version: '1.0',
    author: 'Kolby Nottingham',
    license: 'MIT',
    description: '基于 LLM 与 Mineflayer 的 Minecraft AI Agent 框架，为游戏世界构建具备自主行为的智能体。',
    url: 'https://github.com/mindcraft-bots/mindcraft'
  },
  {
    name: 'TencentDB Agent Memory',
    version: '0.3',
    author: 'Tencent',
    license: 'MIT',
    description: '腾讯开源的四层本地记忆系统插件，通过本地 LLM 与 SQLite 向量检索实现对话知识的自动捕获与结构化。',
    url: 'https://github.com/tencentdb-agent-memory/memory-tencentdb'
  },
  {
    name: 'CubeSandbox',
    version: '1.0',
    author: 'Tencent',
    license: 'Apache-2.0',
    description: '腾讯开源的面向 AI Agent 的即时、并发、安全且轻量的沙箱服务，提供隔离的代码执行环境。',
    url: 'https://github.com/tencentcloud/CubeSandbox'
  },
  {
    name: 'EverOS',
    version: '1.1.0',
    author: 'EverMind AI',
    license: 'Apache-2.0',
    description: '企业级 AI 长期记忆系统，支持多类型记忆提取、Agentic 检索与多租户架构。',
    url: 'https://github.com/EverMind-AI/EverMemOS'
  },
  {
    name: 'MSA',
    version: '1.0',
    author: 'EverMind AI',
    license: 'MIT',
    description: 'Memory Sparse Attention，端到端可训练的稀疏记忆框架，实现 100M token 超长上下文处理。',
    url: 'https://github.com/EverMind-AI/MSA'
  },
  {
    name: 'Fabric',
    version: '1.0',
    author: 'Daniel Miessler',
    license: 'MIT',
    description: 'AI Prompt 模式化编排框架，通过 170+ Pattern 增强 AI 任务效率，支持多供应商集成。',
    url: 'https://github.com/danielmiessler/fabric'
  },
  {
    name: 'Hyperledger Fabric',
    version: '3.1.4',
    author: 'Linux Foundation',
    license: 'Apache-2.0',
    description: '企业级许可型区块链平台，采用 Execute-Order-Validate 架构，支持可插拔共识与通道隐私隔离。',
    url: 'https://github.com/hyperledger/fabric'
  },
  {
    name: 'Stagehand',
    version: '3.2.1',
    author: 'Browserbase',
    license: 'MIT',
    description: 'AI 驱动的浏览器自动化框架，支持自然语言控制浏览器、结构化数据提取与多模式 AI Agent。',
    url: 'https://github.com/browserbase/stagehand'
  },
  {
    name: 'LoliMeow',
    version: '13.12',
    author: '专收爆米花',
    license: 'GPL-2.0+',
    description: 'WordPress 博客主题，本页面背景装饰与卡片视觉风格受其启发。',
    url: 'https://www.boxmoe.com'
  }
]

const specialLicenses = [
  {
    name: 'Live2D Cubism SDK',
    version: '5-r.5',
    author: 'Live2D Inc.',
    license: 'Live2D Open Software License',
    coreLicense: 'Live2D Proprietary Software License',
    description: 'Live2D Cubism SDK，用于创建和渲染 Live2D 模型。本项目使用了 Cubism Core（专有许可）和 Cubism Components（开放源代码许可）。',
    note: '年营收超过 1000 万日元（约 50 万人民币）的企业需要额外获得发布许可。',
    url: 'https://www.live2d.com/en/develop/download/'
  }
]

const collaborators = [
  {
    name: 'Luminous辰汐',
    key: 'luminous-ChenXi',
    role: '项目创始人 · 项目总负责人 · 全栈开发 · 架构设计 / 软件安全',
    url: 'https://github.com/luminous-ChenXi'
  },
  {
    name: 'kipbbsjsjs',
    key: 'kipbbsjsjs',
    role: '核心记忆模块开发 · 本地用户数据管理 · 功能贡献',
    url: 'https://github.com/kipbbsjsjs'
  },
  {
    name: 'NoobL696',
    key: 'NoobL696',
    role: '测试与反馈 · 建议贡献',
    url: 'https://github.com/NoobL696'
  }
]

const bundledAvatarByKey: Record<string, string> = {
  'luminous-ChenXi': avatarLuminousChenXi,
  'kipbbsjsjs': avatarKipbbsjsjs,
  'NoobL696': avatarNoobL696
}

/**
 * 当前生效的头像 URL：优先使用主进程缓存的协议 URL（luominest-avatar://cached/），
 * 未命中时回退到打包进前端的静态资源，保证离线也能正常显示。
 */
const avatarUrls = ref<Record<string, string>>({})

const resolveAvatars = async (): Promise<void> => {
  try {
    const entries = await Promise.all(
      collaborators.map(async (person) => {
        const result = await window.api.avatar.getCollaboratorAvatar(person.key)
        return [person.name, result.url ?? bundledAvatarByKey[person.key]] as const
      })
    )
    avatarUrls.value = Object.fromEntries(entries)
  } catch {
    // IPC 异常时保持默认打包资源
  }
}

onMounted(() => {
  void resolveAvatars()
  // 触发一次更新：成功后刷新显示，失败则保持现有缓存/打包资源
  window.api.avatar
    .updateCollaboratorAvatars()
    .then(() => resolveAvatars())
    .catch(() => {})
})

const onAvatarError = (key: string, event: Event): void => {
  const img = event.target as HTMLImageElement
  img.src = bundledAvatarByKey[key] ?? ''
}
</script>

<template>
  <div class="lumi-settings-page license-view">
    <LumiSettingsBackground />
    <header class="lumi-settings-page__header lumi-settings-animate-fade">
      <button class="lumi-settings-page__back" @click="router.push('/settings')">
        <ArrowLeft :size="18" />
      </button>
      <div>
        <h1 class="lumi-settings-page__title">项目参考</h1>
        <p class="lumi-settings-page__subtitle">LuomiNest 依赖的开源项目及其许可证</p>
      </div>
    </header>

    <main class="lumi-settings-page__body">
      <div class="lumi-settings-page__content">
        <section class="license-hero lumi-settings-animate-slide">
          <div class="license-hero__content">
            <Scale :size="28" class="license-hero__icon" />
            <h2 class="license-hero__title">AGPL-3.0</h2>
            <p class="license-hero__desc">
              LuomiNest 基于 <strong>GNU Affero General Public License v3.0</strong> 开源。
              你可以自由使用、修改和分发本软件的源代码。
            </p>
            <div class="license-hero__stats">
              <div class="license-hero__stat">
                <span class="license-hero__stat-value">{{ frontendLicenses.length }}</span>
                <span class="license-hero__stat-label">前端依赖</span>
              </div>
              <div class="license-hero__divider" />
              <div class="license-hero__stat">
                <span class="license-hero__stat-value">{{ backendLicenses.length }}</span>
                <span class="license-hero__stat-label">后端依赖</span>
              </div>
              <div class="license-hero__divider" />
              <div class="license-hero__stat">
                <span class="license-hero__stat-value">{{ specialLicenses.length }}</span>
                <span class="license-hero__stat-label">特殊许可</span>
              </div>
              <div class="license-hero__divider" />
              <div class="license-hero__stat">
                <span class="license-hero__stat-value">{{ collaborators.length }}</span>
                <span class="license-hero__stat-label">前期合作者</span>
              </div>
            </div>
          </div>
        </section>

        <section class="license-section lumi-settings-animate-slide">
          <LicenseSectionHeader
            :icon="ExternalLink"
            title="前端依赖"
            desc="Electron 桌面客户端直接依赖的主要开源库"
          />
          <div class="license-grid">
            <a
              v-for="(lib, index) in frontendLicenses"
              :key="lib.name"
              :href="lib.url"
              target="_blank"
              rel="noopener noreferrer"
              class="license-card"
              :style="{ animationDelay: `${index * 40}ms` }"
            >
              <div class="license-card__shine" />
              <div class="license-card__top">
                <div class="license-card__name-row">
                  <span class="license-card__name">{{ lib.name }}</span>
                  <ExternalLink :size="12" class="license-card__link-icon" />
                </div>
                <span class="license-card__version">v{{ lib.version }}</span>
              </div>
              <p class="license-card__desc">{{ lib.description }}</p>
              <div class="license-card__footer">
                <span class="license-badge">{{ lib.license }}</span>
                <span class="license-card__author">{{ lib.author }}</span>
              </div>
            </a>
          </div>
        </section>

        <section class="license-section lumi-settings-animate-slide">
          <LicenseSectionHeader
            :icon="ExternalLink"
            title="后端依赖"
            desc="Python 后端服务直接依赖的主要开源库"
          />
          <div class="license-grid">
            <a
              v-for="(lib, index) in backendLicenses"
              :key="lib.name"
              :href="lib.url"
              target="_blank"
              rel="noopener noreferrer"
              class="license-card"
              :style="{ animationDelay: `${index * 40}ms` }"
            >
              <div class="license-card__shine" />
              <div class="license-card__top">
                <div class="license-card__name-row">
                  <span class="license-card__name">{{ lib.name }}</span>
                  <ExternalLink :size="12" class="license-card__link-icon" />
                </div>
                <span class="license-card__version">v{{ lib.version }}</span>
              </div>
              <p class="license-card__desc">{{ lib.description }}</p>
              <div class="license-card__footer">
                <span class="license-badge">{{ lib.license }}</span>
                <span class="license-card__author">{{ lib.author }}</span>
              </div>
            </a>
          </div>
        </section>

        <section class="license-section lumi-settings-animate-slide">
          <LicenseSectionHeader
            :icon="ExternalLink"
            title="参考项目"
            desc="在项目研发过程中参考和学习的优秀开源项目"
          />
          <div class="license-grid">
            <a
              v-for="(lib, index) in referenceProjects"
              :key="lib.name"
              :href="lib.url"
              target="_blank"
              rel="noopener noreferrer"
              class="license-card"
              :style="{ animationDelay: `${index * 40}ms` }"
            >
              <div class="license-card__shine" />
              <div class="license-card__top">
                <div class="license-card__name-row">
                  <span class="license-card__name">{{ lib.name }}</span>
                  <ExternalLink :size="12" class="license-card__link-icon" />
                </div>
                <span class="license-card__version">v{{ lib.version }}</span>
              </div>
              <p class="license-card__desc">{{ lib.description }}</p>
              <div class="license-card__footer">
                <span class="license-badge">{{ lib.license }}</span>
                <span class="license-card__author">{{ lib.author }}</span>
              </div>
            </a>
          </div>
        </section>

        <section class="license-section lumi-settings-animate-slide">
          <LicenseSectionHeader
            :icon="AlertTriangle"
            title="特殊许可证"
            desc="包含专有组件或商业使用限制的非标准开源许可"
            theme="warning"
          />
          <div class="license-special-list">
            <div
              v-for="(lib, index) in specialLicenses"
              :key="lib.name"
              class="license-special-card"
              :style="{ animationDelay: `${index * 80}ms` }"
            >
              <div class="license-special-card__header">
                <div class="license-special-card__title">
                  <a
                    :href="lib.url"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="license-special-card__name"
                  >
                    {{ lib.name }}
                    <ExternalLink :size="14" />
                  </a>
                  <span class="license-special-card__version">v{{ lib.version }}</span>
                </div>
                <span class="license-special-card__author">{{ lib.author }}</span>
              </div>

              <p class="license-special-card__desc">{{ lib.description }}</p>

              <div class="license-special-card__tags">
                <div class="license-special-tag">
                  <span class="license-special-tag__label">组件</span>
                  <span class="license-special-tag__value">{{ lib.license }}</span>
                </div>
                <div class="license-special-tag license-special-tag--proprietary">
                  <span class="license-special-tag__label">核心库</span>
                  <span class="license-special-tag__value">{{ lib.coreLicense }}</span>
                </div>
              </div>

              <div class="license-special-alert">
                <AlertTriangle :size="14" />
                <span>{{ lib.note }}</span>
              </div>
            </div>
          </div>
        </section>

        <section class="license-section lumi-settings-animate-slide">
          <LicenseSectionHeader
            :icon="Scale"
            title="AGPL-3.0 协议概要"
            desc="LuomiNest 所采用的开源许可证核心条款"
          />
          <div class="license-agpl-card">
            <ul class="license-agpl-list">
              <li>你可以自由使用、修改和分发本软件的源代码。</li>
              <li>任何对本软件的修改版本必须以相同的 AGPL-3.0 许可证发布。</li>
              <li>如果你通过网络向用户提供本软件的服务（例如 SaaS），你必须向用户提供该软件完整源代码的获取途径。</li>
              <li>分发时必须保留原始版权声明和许可证声明。</li>
            </ul>
            <a
              href="https://www.gnu.org/licenses/agpl-3.0.html"
              target="_blank"
              rel="noopener noreferrer"
              class="license-agpl-link"
            >
              阅读完整协议文本
              <ExternalLink :size="12" />
            </a>
          </div>
        </section>

        <section class="license-section lumi-settings-animate-slide">
          <LicenseSectionHeader
            :icon="Heart"
            title="前期合作者"
            desc="为 LuomiNest 做出贡献的伙伴们"
            theme="accent"
          />
          <div class="license-collab-grid">
            <a
              v-for="(person, index) in collaborators"
              :key="person.name"
              :href="person.url"
              target="_blank"
              rel="noopener noreferrer"
              class="license-collab-card"
              :style="{ animationDelay: `${index * 80}ms` }"
            >
              <img
                :src="avatarUrls[person.name] ?? bundledAvatarByKey[person.key]"
                :alt="person.name"
                class="license-collab-card__avatar"
                loading="lazy"
                @error="onAvatarError(person.key, $event)"
              />
              <div class="license-collab-card__info">
                <span class="license-collab-card__name">{{ person.name }}</span>
                <span class="license-collab-card__role">{{ person.role }}</span>
              </div>
            </a>
          </div>
        </section>

        <footer class="license-footer">
          <p>Made with LuomiNest · 感谢所有开源贡献者</p>
        </footer>
      </div>
    </main>
  </div>
</template>

<style scoped src="../../styles/views/license-view.css"></style>

<style scoped>
/* 背景由 settings-independent-bg.css 独立控制 */
</style>

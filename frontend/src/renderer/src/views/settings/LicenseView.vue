<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ArrowLeft, ExternalLink, AlertTriangle, Scale, Heart } from 'lucide-vue-next'
import LicenseSectionHeader from '../../components/settings-detail/LicenseSectionHeader.vue'
import LumiSettingsBackground from '../../components/settings-detail/LumiSettingsBackground.vue'
import '../../styles/views/settings-independent-bg.css'
// 打包进前端的默认头像：缓存未就绪或网络失败时兜底显示
import avatarLuminousChenXi from '../../assets/images/avatars/luminous-ChenXi.png'
import avatarKipbbsjsjs from '../../assets/images/avatars/kipbbsjsjs.png'
import avatarNoobL696 from '../../assets/images/avatars/NoobL696.jpg'

const router = useRouter()
const { t } = useI18n()

const frontendLicenses = [
  {
    name: 'Vue 3',
    key: 'vue3',
    version: '3.5',
    author: 'Evan You',
    license: 'MIT',
    url: 'https://github.com/vuejs/core'
  },
  {
    name: 'Electron',
    key: 'electron',
    version: '41.0',
    author: 'OpenJS Foundation',
    license: 'MIT',
    url: 'https://github.com/electron/electron'
  },
  {
    name: 'TypeScript',
    key: 'typescript',
    version: '6.0',
    author: 'Microsoft',
    license: 'Apache-2.0',
    url: 'https://github.com/microsoft/TypeScript'
  },
  {
    name: 'Pinia',
    key: 'pinia',
    version: '3.0',
    author: 'Eduardo San Martin Morote',
    license: 'MIT',
    url: 'https://github.com/vuejs/pinia'
  },
  {
    name: 'Vue Router',
    key: 'vueRouter',
    version: '5.0',
    author: 'Evan You',
    license: 'MIT',
    url: 'https://github.com/vuejs/router'
  },
  {
    name: 'Vite',
    key: 'vite',
    version: '6.2',
    author: 'Yuxi (Evan) You',
    license: 'MIT',
    url: 'https://github.com/vitejs/vite'
  },
  {
    name: 'PixiJS',
    key: 'pixijs',
    version: '7.4',
    author: 'PixiJS Contributors',
    license: 'MIT',
    url: 'https://github.com/pixijs/pixijs'
  },
  {
    name: 'lucide-vue-next',
    key: 'lucide',
    version: '0.577.0',
    author: 'Lucide Contributors',
    license: 'ISC',
    url: 'https://github.com/lucide-icons/lucide'
  },
  {
    name: 'Marked',
    key: 'marked',
    version: '18.0',
    author: 'MarkedJS Contributors',
    license: 'MIT',
    url: 'https://github.com/markedjs/marked'
  },
  {
    name: 'DOMPurify',
    key: 'dompurify',
    version: '3.4',
    author: 'Cure53',
    license: '(Apache-2.0 OR MPL-2.0)',
    url: 'https://github.com/cure53/DOMPurify'
  },
  {
    name: '@pixi/unsafe-eval',
    key: 'pixiUnsafeEval',
    version: '7.4',
    author: 'PixiJS Contributors',
    license: 'MIT',
    url: 'https://github.com/pixijs/pixijs'
  },
  {
    name: 'pixi-live2d-display-mulmotion',
    key: 'pixiLive2d',
    version: '0.5.0',
    author: 'guansss',
    license: 'MIT',
    url: 'https://github.com/guansss/pixi-live2d-display'
  }
]

const backendLicenses = [
  {
    name: 'FastAPI',
    key: 'fastapi',
    version: '0.115',
    author: 'Sebastián Ramírez',
    license: 'MIT',
    url: 'https://github.com/fastapi/fastapi'
  },
  {
    name: 'Uvicorn',
    key: 'uvicorn',
    version: '0.34',
    author: 'Encode',
    license: 'BSD-3-Clause',
    url: 'https://github.com/encode/uvicorn'
  },
  {
    name: 'Pydantic',
    key: 'pydantic',
    version: '2.10',
    author: 'Samuel Colvin',
    license: 'MIT',
    url: 'https://github.com/pydantic/pydantic'
  },
  {
    name: 'SQLAlchemy',
    key: 'sqlalchemy',
    version: '2.0',
    author: 'Mike Bayer',
    license: 'MIT',
    url: 'https://github.com/sqlalchemy/sqlalchemy'
  },
  {
    name: 'Alembic',
    key: 'alembic',
    version: '1.14',
    author: 'Mike Bayer',
    license: 'MIT',
    url: 'https://github.com/sqlalchemy/alembic'
  },
  {
    name: 'PostgreSQL (asyncpg)',
    key: 'asyncpg',
    version: '0.30',
    author: 'MagicStack',
    license: 'PostgreSQL',
    url: 'https://github.com/MagicStack/asyncpg'
  },
  {
    name: 'Redis (redis-py)',
    key: 'redis',
    version: '5.2',
    author: 'Redis Inc.',
    license: 'MIT',
    url: 'https://github.com/redis/redis-py'
  },
  {
    name: 'LiteLLM',
    key: 'litellm',
    version: '1.55',
    author: 'BerriAI',
    license: 'MIT',
    url: 'https://github.com/BerriAI/litellm'
  },
  {
    name: 'OpenAI Python',
    key: 'openai',
    version: '1.58',
    author: 'OpenAI',
    license: 'Apache-2.0',
    url: 'https://github.com/openai/openai-python'
  },
  {
    name: 'Anthropic Python',
    key: 'anthropic',
    version: '0.42',
    author: 'Anthropic',
    license: 'MIT',
    url: 'https://github.com/anthropics/anthropic-sdk-python'
  },
  {
    name: 'httpx',
    key: 'httpx',
    version: '0.28',
    author: 'Encode',
    license: 'BSD-3-Clause',
    url: 'https://github.com/encode/httpx'
  },
  {
    name: 'NumPy',
    key: 'numpy',
    version: '2.2',
    author: 'NumPy Developers',
    license: 'BSD-3-Clause',
    url: 'https://github.com/numpy/numpy'
  },
  {
    name: 'Pydantic Settings',
    key: 'pydanticSettings',
    version: '2.7',
    author: 'Samuel Colvin',
    license: 'MIT',
    url: 'https://github.com/pydantic/pydantic-settings'
  },
  {
    name: 'python-multipart',
    key: 'pythonMultipart',
    version: '0.0.18',
    author: 'Andrew Svetlov',
    license: 'Apache-2.0',
    url: 'https://github.com/andrew-svetlov/python-multipart'
  },
  {
    name: 'aiofiles',
    key: 'aiofiles',
    version: '24.1',
    author: 'Tin Tvrtković',
    license: 'Apache-2.0',
    url: 'https://github.com/Tinche/aiofiles'
  },
  {
    name: 'aiosqlite',
    key: 'aiosqlite',
    version: '0.20',
    author: 'Amjith Ramanujam',
    license: 'MIT',
    url: 'https://github.com/omnilib/aiosqlite'
  },
  {
    name: 'aiohttp',
    key: 'aiohttp',
    version: '3.9',
    author: 'Nikolay Kim',
    license: 'Apache-2.0',
    url: 'https://github.com/aio-libs/aiohttp'
  },
  {
    name: 'websockets',
    key: 'websockets',
    version: '14.0',
    author: 'Aymeric Augustin',
    license: 'BSD-3-Clause',
    url: 'https://github.com/python-websockets/websockets'
  },
  {
    name: 'paho-mqtt',
    key: 'pahoMqtt',
    version: '2.1',
    author: 'Eclipse Foundation',
    license: 'EPL-2.0 OR BSD-3-Clause',
    url: 'https://github.com/eclipse/paho.mqtt.python'
  },
  {
    name: 'pgvector',
    key: 'pgvector',
    version: '0.3.6',
    author: 'Andrew Kane',
    license: 'MIT',
    url: 'https://github.com/pgvector/pgvector-python'
  },
  {
    name: 'python-jose',
    key: 'pythonJose',
    version: '3.3',
    author: 'Michael Davis',
    license: 'MIT',
    url: 'https://github.com/mpdavis/python-jose'
  },
  {
    name: 'passlib',
    key: 'passlib',
    version: '1.7.4',
    author: 'Eli Collins',
    license: 'BSD-3-Clause',
    url: 'https://github.com/glic3rinu/passlib'
  },
  {
    name: 'cryptography',
    key: 'cryptography',
    version: '44.0',
    author: 'Python Cryptographic Authority',
    license: 'Apache-2.0 OR BSD-3-Clause',
    url: 'https://github.com/pyca/cryptography'
  },
  {
    name: 'Loguru',
    key: 'loguru',
    version: '0.7.3',
    author: 'Delgan',
    license: 'MIT',
    url: 'https://github.com/Delgan/loguru'
  },
  {
    name: 'APScheduler',
    key: 'apscheduler',
    version: '3.10',
    author: 'Alex Grönholm',
    license: 'MIT',
    url: 'https://github.com/agronholm/apscheduler'
  },
  {
    name: 'Tenacity',
    key: 'tenacity',
    version: '9.0',
    author: 'Kenneth Reitz',
    license: 'Apache-2.0',
    url: 'https://github.com/jd/tenacity'
  },
  {
    name: 'Pillow',
    key: 'pillow',
    version: '11.0',
    author: 'Alex Clark',
    license: 'Historical',
    url: 'https://github.com/python-pillow/Pillow'
  },
  {
    name: 'orjson',
    key: 'orjson',
    version: '3.10',
    author: 'ijl',
    license: 'MIT',
    url: 'https://github.com/ijl/orjson'
  },
  {
    name: 'PyMuPDF',
    key: 'pymupdf',
    version: '1.24',
    author: 'Artifex Software',
    license: 'AGPL-3.0',
    url: 'https://github.com/pymupdf/PyMuPDF'
  },
  {
    name: 'python-docx',
    key: 'pythonDocx',
    version: '1.1',
    author: 'Steve Canny',
    license: 'MIT',
    url: 'https://github.com/python-openxml/python-docx'
  },
  {
    name: 'edge-tts',
    key: 'edgeTts',
    version: '6.1.18',
    author: 'Rany',
    license: 'GPL-3.0',
    url: 'https://github.com/rany2/edge-tts'
  },
  {
    name: 'MCP',
    key: 'mcp',
    version: '1.0',
    author: 'Anthropic',
    license: 'MIT',
    url: 'https://github.com/modelcontextprotocol/python-sdk'
  },
  {
    name: 'python-magic',
    key: 'pythonMagic',
    version: '0.4.27',
    author: 'Adam Hupp',
    license: 'MIT',
    url: 'https://github.com/ahupp/python-magic'
  },
  {
    name: 'tzdata',
    key: 'tzdata',
    version: '2024.1',
    author: 'Paul Ganssle',
    license: 'Apache-2.0',
    url: 'https://github.com/python/tzdata'
  }
]

const referenceProjects = [
  {
    name: 'DeerFlow',
    key: 'deerflow',
    version: '1.0',
    author: 'Bytedance',
    license: 'MIT',
    url: 'https://github.com/bytedance/deer-flow'
  },
  {
    name: 'Hermes Agent',
    key: 'hermesAgent',
    version: '1.0',
    author: 'Nous Research',
    license: 'MIT',
    url: 'https://github.com/NousResearch/hermes-agent'
  },
  {
    name: 'Mindcraft',
    key: 'mindcraft',
    version: '1.0',
    author: 'Kolby Nottingham',
    license: 'MIT',
    url: 'https://github.com/mindcraft-bots/mindcraft'
  },
  {
    name: 'TencentDB Agent Memory',
    key: 'tencentdbMemory',
    version: '0.3',
    author: 'Tencent',
    license: 'MIT',
    url: 'https://github.com/tencentdb-agent-memory/memory-tencentdb'
  },
  {
    name: 'CubeSandbox',
    key: 'cubeSandbox',
    version: '1.0',
    author: 'Tencent',
    license: 'Apache-2.0',
    url: 'https://github.com/tencentcloud/CubeSandbox'
  },
  {
    name: 'EverOS',
    key: 'everos',
    version: '1.1.0',
    author: 'EverMind AI',
    license: 'Apache-2.0',
    url: 'https://github.com/EverMind-AI/EverMemOS'
  },
  {
    name: 'MSA',
    key: 'msa',
    version: '1.0',
    author: 'EverMind AI',
    license: 'MIT',
    url: 'https://github.com/EverMind-AI/MSA'
  },
  {
    name: 'Fabric',
    key: 'fabric',
    version: '1.0',
    author: 'Daniel Miessler',
    license: 'MIT',
    url: 'https://github.com/danielmiessler/fabric'
  },
  {
    name: 'Hyperledger Fabric',
    key: 'hyperledgerFabric',
    version: '3.1.4',
    author: 'Linux Foundation',
    license: 'Apache-2.0',
    url: 'https://github.com/hyperledger/fabric'
  },
  {
    name: 'Stagehand',
    key: 'stagehand',
    version: '3.2.1',
    author: 'Browserbase',
    license: 'MIT',
    url: 'https://github.com/browserbase/stagehand'
  },
  {
    name: 'LoliMeow',
    key: 'loliMeow',
    version: '13.12',
    author: '专收爆米花',
    license: 'GPL-2.0+',
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
    url: 'https://www.live2d.com/en/develop/download/'
  }
]

const collaborators = [
  {
    name: 'Luminous辰汐',
    key: 'luminous-ChenXi',
    roleKey: 'luminousChenXi',
    url: 'https://github.com/luminous-ChenXi'
  },
  {
    name: 'kipbbsjsjs',
    key: 'kipbbsjsjs',
    roleKey: 'kipbbsjsjs',
    url: 'https://github.com/kipbbsjsjs'
  },
  {
    name: 'NoobL696',
    key: 'NoobL696',
    roleKey: 'noobL696',
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
        <h1 class="lumi-settings-page__title">{{ t('license.title') }}</h1>
        <p class="lumi-settings-page__subtitle">{{ t('license.subtitle') }}</p>
      </div>
    </header>

    <main class="lumi-settings-page__body">
      <div class="lumi-settings-page__content">
        <section class="license-hero lumi-settings-animate-slide">
          <div class="license-hero__content">
            <Scale :size="28" class="license-hero__icon" />
            <h2 class="license-hero__title">AGPL-3.0</h2>
            <p class="license-hero__desc">
              {{ t('license.hero.descBefore') }}<strong>GNU Affero General Public License v3.0</strong>{{ t('license.hero.descAfter') }}
            </p>
            <div class="license-hero__stats">
              <div class="license-hero__stat">
                <span class="license-hero__stat-value">{{ frontendLicenses.length }}</span>
                <span class="license-hero__stat-label">{{ t('license.stats.frontend') }}</span>
              </div>
              <div class="license-hero__divider" />
              <div class="license-hero__stat">
                <span class="license-hero__stat-value">{{ backendLicenses.length }}</span>
                <span class="license-hero__stat-label">{{ t('license.stats.backend') }}</span>
              </div>
              <div class="license-hero__divider" />
              <div class="license-hero__stat">
                <span class="license-hero__stat-value">{{ specialLicenses.length }}</span>
                <span class="license-hero__stat-label">{{ t('license.stats.special') }}</span>
              </div>
              <div class="license-hero__divider" />
              <div class="license-hero__stat">
                <span class="license-hero__stat-value">{{ collaborators.length }}</span>
                <span class="license-hero__stat-label">{{ t('license.stats.collaborators') }}</span>
              </div>
            </div>
          </div>
        </section>

        <section class="license-section lumi-settings-animate-slide">
          <LicenseSectionHeader
            :icon="ExternalLink"
            :title="t('license.sections.frontend.title')"
            :desc="t('license.sections.frontend.desc')"
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
              <p class="license-card__desc">{{ t('license.libs.frontend.' + lib.key) }}</p>
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
            :title="t('license.sections.backend.title')"
            :desc="t('license.sections.backend.desc')"
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
              <p class="license-card__desc">{{ t('license.libs.backend.' + lib.key) }}</p>
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
            :title="t('license.sections.reference.title')"
            :desc="t('license.sections.reference.desc')"
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
              <p class="license-card__desc">{{ t('license.libs.reference.' + lib.key) }}</p>
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
            :title="t('license.sections.special.title')"
            :desc="t('license.sections.special.desc')"
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

              <p class="license-special-card__desc">{{ t('license.libs.special.description') }}</p>

              <div class="license-special-card__tags">
                <div class="license-special-tag">
                  <span class="license-special-tag__label">{{ t('license.special.componentLabel') }}</span>
                  <span class="license-special-tag__value">{{ lib.license }}</span>
                </div>
                <div class="license-special-tag license-special-tag--proprietary">
                  <span class="license-special-tag__label">{{ t('license.special.coreLabel') }}</span>
                  <span class="license-special-tag__value">{{ lib.coreLicense }}</span>
                </div>
              </div>

              <div class="license-special-alert">
                <AlertTriangle :size="14" />
                <span>{{ t('license.libs.special.note') }}</span>
              </div>
            </div>
          </div>
        </section>

        <section class="license-section lumi-settings-animate-slide">
          <LicenseSectionHeader
            :icon="Scale"
            :title="t('license.sections.agpl.title')"
            :desc="t('license.sections.agpl.desc')"
          />
          <div class="license-agpl-card">
            <ul class="license-agpl-list">
              <li>{{ t('license.agpl.item1') }}</li>
              <li>{{ t('license.agpl.item2') }}</li>
              <li>{{ t('license.agpl.item3') }}</li>
              <li>{{ t('license.agpl.item4') }}</li>
            </ul>
            <a
              href="https://www.gnu.org/licenses/agpl-3.0.html"
              target="_blank"
              rel="noopener noreferrer"
              class="license-agpl-link"
            >
              {{ t('license.agpl.readFull') }}
              <ExternalLink :size="12" />
            </a>
          </div>
        </section>

        <section class="license-section lumi-settings-animate-slide">
          <LicenseSectionHeader
            :icon="Heart"
            :title="t('license.sections.collaborators.title')"
            :desc="t('license.sections.collaborators.desc')"
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
                <span class="license-collab-card__role">{{ t('license.roles.' + person.roleKey) }}</span>
              </div>
            </a>
          </div>
        </section>

        <footer class="license-footer">
          <p>{{ t('license.footer') }}</p>
        </footer>
      </div>
    </main>
  </div>
</template>

<style scoped src="../../styles/views/license-view.css"></style>

<style scoped>
/* 背景由 settings-independent-bg.css 独立控制 */
</style>

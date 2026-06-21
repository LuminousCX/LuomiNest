<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ArrowLeft, Users, ExternalLink } from 'lucide-vue-next'

const router = useRouter()

const licenses = [
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
    name: 'lucide-vue-next',
    version: '0.577.0',
    author: 'Lucide Contributors',
    license: 'ISC',
    description: '简洁美观的开源图标库，为 Lucide 的 Vue 3 实现。',
    url: 'https://github.com/lucide-icons/lucide'
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
  }
]

const collaborators = [
  {
    name: 'Luminous辰汐',
    role: '项目创始人 · 全栈开发 · 前端架构 / 后端 / 安全',
    url: 'https://github.com/luminous-ChenXi',
    avatar: 'https://github.com/luminous-ChenXi.png'
  },
  {
    name: 'kipbbsjsjs',
    role: '记忆模块开发 · 功能贡献',
    url: 'https://github.com/kipbbsjsjs',
    avatar: 'https://github.com/kipbbsjsjs.png'
  },
  {
    name: 'NoobL696',
    role: '测试与反馈 · Fork 维护',
    url: 'https://github.com/NoobL696',
    avatar: 'https://github.com/NoobL696.png'
  }
]
</script>

<template>
  <div class="license-view">
    <div class="license-header animate-fade-in">
      <button class="back-btn" @click="router.push('/settings')">
        <ArrowLeft :size="18" />
      </button>
      <div>
        <h1 class="page-title">开源协议</h1>
        <p class="page-subtitle">LuomiNest 依赖的开源项目及其许可证</p>
      </div>
    </div>

    <div class="license-body">
      <!-- 协议介绍 -->
      <div class="sketch-card sketch-intro animate-slide-up">
        <div class="sketch-dots"></div>
        <p>
          LuomiNest 基于 <strong>GNU Affero General Public License v3.0 (AGPL-3.0)</strong> 开源。
          以下列出了本项目直接依赖的主要开源库及其许可证信息。
        </p>
      </div>

      <!-- 依赖列表 -->
      <div class="license-grid animate-slide-up" style="animation-delay: 60ms;">
        <div
          v-for="lib in licenses"
          :key="lib.name"
          class="sketch-card sketch-item"
        >
          <div class="sketch-dots"></div>
          <div class="item-top">
            <div class="item-name-row">
              <a
                :href="lib.url"
                target="_blank"
                rel="noopener noreferrer"
                class="item-name"
              >
                {{ lib.name }}
                <ExternalLink :size="11" />
              </a>
              <span class="item-version">v{{ lib.version }}</span>
            </div>
            <span class="item-badge">{{ lib.license }}</span>
          </div>
          <p class="item-desc">{{ lib.description }}</p>
          <span class="item-author">{{ lib.author }}</span>
        </div>
      </div>

      <!-- AGPL 协议概要 -->
      <div class="sketch-card sketch-agpl animate-slide-up" style="animation-delay: 120ms;">
        <div class="sketch-dots"></div>
        <h3 class="sketch-title">AGPL-3.0 协议概要</h3>
        <div class="agpl-content">
          <p>GNU Affero General Public License v3.0 是一个自由软件许可证，其核心条款包括：</p>
          <ul>
            <li>你可以自由使用、修改和分发本软件的源代码。</li>
            <li>任何对本软件的修改版本必须以相同的 AGPL-3.0 许可证发布。</li>
            <li>如果你通过网络向用户提供本软件的服务（例如 SaaS），你必须向用户提供该软件完整源代码的获取途径。</li>
            <li>分发时必须保留原始版权声明和许可证声明。</li>
          </ul>
          <p>完整协议文本请访问
            <a href="https://www.gnu.org/licenses/agpl-3.0.html" target="_blank" rel="noopener noreferrer">
              GNU 官方网站
            </a>
          </p>
        </div>
      </div>

      <!-- 前期合作者 -->
      <div class="sketch-card sketch-collab animate-slide-up" style="animation-delay: 180ms;">
        <div class="sketch-dots"></div>
        <h3 class="sketch-title">
          <Users :size="15" />
          前期合作者
        </h3>
        <div class="collab-grid">
          <a
            v-for="person in collaborators"
            :key="person.name"
            :href="person.url"
            target="_blank"
            rel="noopener noreferrer"
            class="collab-card"
          >
            <img :src="person.avatar" :alt="person.name" class="collab-avatar" />
            <div class="collab-info">
              <span class="collab-name">{{ person.name }}</span>
              <span class="collab-role">{{ person.role }}</span>
            </div>
          </a>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.license-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--workspace-bg);
  overflow: hidden;
}

.license-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 28px;
  border-bottom: 1px solid var(--workspace-border);
  flex-shrink: 0;
}

.back-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.back-btn:hover {
  background: var(--workspace-hover);
  color: var(--lumi-primary);
}

.page-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}

.page-subtitle {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 1px;
}

.license-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px 28px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ── Sketch card base (hand-drawn feel) ── */

.sketch-card {
  position: relative;
  background: var(--workspace-card);
  border: 2px dashed var(--divider-soft);
  border-radius: 20px 18px 22px 20px;
  padding: 18px 20px;
  overflow: hidden;
  transition: all 0.3s ease-in-out;
}

.sketch-card:hover {
  border-color: var(--border-light);
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
}

/* Subtle dot pattern overlay */
.sketch-dots {
  position: absolute;
  inset: 0;
  background: radial-gradient(circle, var(--divider-soft) 1px, transparent 1px);
  background-size: 16px 16px;
  opacity: 0.25;
  pointer-events: none;
}

/* ── Intro card ── */

.sketch-intro p {
  position: relative;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.7;
}

.sketch-intro strong {
  color: var(--text-primary);
  font-weight: 600;
}

/* ── License grid ── */

.license-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.sketch-item {
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.item-top {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.item-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.item-name {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  font-weight: 600;
  color: var(--lumi-primary);
  text-decoration: none;
  transition: color var(--transition-fast);
}

.item-name:hover {
  color: var(--lumi-primary-hover);
  text-decoration: underline;
}

.item-version {
  font-size: 11px;
  color: var(--text-muted);
  font-family: monospace;
}

.item-badge {
  position: relative;
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--lumi-primary-light);
  color: var(--lumi-primary);
  white-space: nowrap;
}

.item-desc {
  position: relative;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.item-author {
  position: relative;
  font-size: 11px;
  color: var(--text-muted);
}

/* ── AGPL section ── */

.sketch-title {
  position: relative;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.agpl-content {
  position: relative;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.7;
}

.agpl-content p {
  margin-bottom: 12px;
}

.agpl-content ul {
  padding-left: 20px;
  margin-bottom: 12px;
}

.agpl-content li {
  margin-bottom: 6px;
}

.agpl-content a {
  color: var(--lumi-primary);
  text-decoration: none;
  transition: color var(--transition-fast);
}

.agpl-content a:hover {
  color: var(--lumi-primary-hover);
  text-decoration: underline;
}

/* ── Collaborators ── */

.sketch-collab {
  border-color: var(--lumi-primary);
  border-color: color-mix(in srgb, var(--lumi-primary) 30%, transparent);
}

.collab-grid {
  position: relative;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.collab-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: var(--workspace-bg);
  border: 1.5px dashed var(--divider-soft);
  border-radius: 16px;
  text-decoration: none;
  transition: all 0.25s ease-in-out;
}

.collab-card:hover {
  border-color: var(--lumi-primary);
  border-style: solid;
  transform: translateY(-2px);
  box-shadow: 0 3px 12px rgba(0, 0, 0, 0.1);
}

.collab-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid var(--divider-soft);
  transition: border-color var(--transition-fast);
}

.collab-card:hover .collab-avatar {
  border-color: var(--lumi-primary);
}

.collab-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.collab-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.collab-role {
  font-size: 11px;
  color: var(--text-muted);
}
</style>

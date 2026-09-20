<div align="center">

<img src="frontend/resources/icon.svg" alt="LuomiNest Logo" width="120" height="120" />

# LuomiNest

**分布式多用户关系型 AI 智能体平台**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.8.1-green.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Vue](https://img.shields.io/badge/Vue-3-4FC08D.svg?logo=vuedotjs&logoColor=white)](https://vuejs.org/)
[![Electron](https://img.shields.io/badge/Electron-44-47848F.svg?logo=electron&logoColor=white)](https://www.electronjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![CodeRabbit](https://img.shields.io/endpoint?url=https://coderabbit.ai/api/badges/LuminousCX/LuomiNest&label=CodeRabbit)](https://coderabbit.ai)
[![GitHub Stars](https://img.shields.io/github/stars/LuminousCX/LuomiNest?style=social)](https://github.com/LuminousCX/LuomiNest/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/LuminousCX/LuomiNest?style=social)](https://github.com/LuminousCX/LuomiNest/network/members)
[![GitHub Issues](https://img.shields.io/github/issues/LuminousCX/LuomiNest)](https://github.com/LuminousCX/LuomiNest/issues)
[![GitHub Last Commit](https://img.shields.io/github/last-commit/LuminousCX/LuomiNest)](https://github.com/LuminousCX/LuomiNest/commits/master)
[![Code Size](https://img.shields.io/github/languages/code-size/LuminousCX/LuomiNest)](https://github.com/LuminousCX/LuomiNest)

[English](README.md) | [简体中文](README_zh.md) | [日本語](README_ja.md)

</div>

---

<a id="luominest"></a>

## 简介

LuomiNest 是一个开源的**分布式多用户关系型 AI 智能体平台**，以“关系驱动”为核心设计理念。它通过主/从双层记忆架构，在群聊中自动提取每位用户的独立画像（从记忆），私聊时自动加载该用户的记忆（主记忆联动），实现真正个性化的多用户对话；同时支持人、AI、AI 与 AI 跨平台群聊协作。它可运行于桌面电脑、嵌入式终端（ESP32）、智能家居设备之上，覆盖自然语言对话、语音交互、Live2D 虚拟形象、工作流自动化与浏览器操作等能力，提供懂每一个人的长期智能体服务。

核心设计理念：**一台普通电脑即可运行，数据 100% 本地闭环。**

产品主打三件事：**记得住你（记忆性）、像一个生命（陪伴性）、装得上任何能力（扩展性）**。工具与 MCP 是基石级基础设施，不是卖点本身。

## 核心特性

- **双轨记忆系统** — 主人记忆 / 平台用户记忆行级隔离，群聊群友独立画像轨（跨群共享），自动事实抽取、蒸馏沉淀与画像知识库，向量检索全量落 SQLite
- **Live2D 虚拟形象** — Cubism 5 引擎驱动，口型同步、表情驱动、情感映射，支持 PngTuber 像素化头像与桌面宠物（VRM 规划中）
- **插件与技能系统** — CxPlugin 插件热加载 + CxSkill 轻技能双轨扩展，内置扩展市场与多 CDN 发布源
- **沉浸式对话** — 多轮自然语言对话，支持多 LLM Provider（OpenAI 兼容 32 模板 / Anthropic 原生 / DeepSeek / Ollama 等），SSE 流式响应
- **多平台接入** — QQ（OneBot / 官方）、微信（公众号 / 企业微信）、Telegram、Discord、Minecraft、米家、Home Assistant 等 13 种适配器
- **语音交互** — SherpaOnnx / FunASR / Faster-Whisper 语音识别（ASR）+ Edge TTS / SherpaOnnx / 本地 TTS 等 7 引擎合成，能力声明与语言感知回退
- **MCP 工具协议** — 标准 MCP 协议支持，工具注册与调用，内置 CLI、文件操作、子 Agent 委派等 20+ 工具
- **多 Agent 协作** — 任务分析 → 子任务调度 → 并行执行 → 结果综合，支持 A2A 协议 AI-AI 自主对话
- **工作流引擎** — 可视化节点编排、模板库、定时任务调度（APScheduler）、工具调用记录与持久化
- **安全内嵌浏览器** — 精简为只读安全浏览模式（网址导航 + 自动截图与历史预览），提供收敛的 AI 工具（`browser_visit` / `browser_screenshot`），杜绝外部 DOM 注入风险
- **统一日志中心** — 前端、主进程、后端、平台适配器四路日志一体化，支持近千条实时查看、级别与来源筛选、搜索与脱敏诊断上传
- **IoT 智能控制** — MQTT 设备通信，ESP32-P4 硬件终端，Home Assistant（12 类设备域）与米家统一设备/场景视图
- **桌面客户端** — Electron 桌面应用，内置桌面宠物、Live2D 皮套工坊、控制台终端与自适应主题
- **合规与安全体系** — 首启用户协议与隐私政策门禁（支持 PIPL / CCPA 等多法域）、JWT/Token 双模式认证、本地沙箱、命令守卫、速率限制、24h 自动备份
- **隐私优先** — 对话与记忆数据全部本地存储（单 SQLite 库，WAL 模式），敏感配置 AES 加密，非必要不上传云端

## 技术栈

| 层级 | 技术选型 |
|------|---------|
| **前端** | Electron 44 + Vue 3 + TypeScript + Pinia + PixiJS (Live2D) |
| **后端** | Python 3.12+ + FastAPI + Uvicorn + SQLAlchemy 2 (async) + APScheduler |
| **存储** | SQLite (SQLAlchemy ORM, WAL 单库) + JSON 缓存；PostgreSQL / Redis 为云端化预留 |
| **通信** | WebSocket + MQTT + HTTP/REST + SSE 流式响应 |
| **AI/LLM** | OpenAI / Anthropic / DeepSeek / Ollama，多厂商适配器 + 中间件管道 |
| **语音** | SherpaOnnx / FunASR / Faster-Whisper (ASR) + Edge TTS / SherpaOnnx / 本地 TTS / Gemini / MiniMax / SiliconFlow / Fish Audio |
| **硬件** | ESP-IDF (ESP32-P4) |
| **部署** | Docker Compose + PyInstaller + Electron Builder + Inno Setup |

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 22+
- pnpm (推荐 10.x+)

### 一键启动（Make）

```bash
# 克隆仓库
git clone https://github.com/LuminousCX/LuomiNest.git
cd LuomiNest

# 安装全部依赖（前端 + 后端）
make install

# 配置环境变量
make config

# 启动后端（端口 18000）
make dev-backend

# 新终端，启动前端客户端
make dev-frontend
```

### 手动启动

<details>
<summary><strong>后端启动步骤</strong></summary>

```bash
cd backend

# 创建并激活虚拟环境
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

# 安装依赖
pip install -e ".[dev]"

# 配置环境变量
cp config/.env.example config/.env
# 编辑 config/.env，填入你的 API Key 等基础配置

# 启动后端服务
python main.py
```

后端默认运行在 `http://127.0.0.1:18000`，交互式 API 文档位于 `http://127.0.0.1:18000/docs`。

</details>

<details>
<summary><strong>前端启动步骤</strong></summary>

```bash
cd frontend

# 安装依赖
pnpm install

# 启动开发服务器与 Electron
pnpm dev

# 构建生产版本产物
pnpm build
```

</details>

<details>
<summary><strong>Docker 部署</strong></summary>

```bash
cd docker

# 开发环境（backend + PostgreSQL + Redis + MQTT；后端当前使用 SQLite，pg/redis 为预留）
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# 生产环境
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

</details>

## 项目结构

```
LuomiNest/
├── backend/                     # Python 后端服务
│   ├── app/
│   │   ├── api/v1/endpoints/    # REST API 端点（24 个模块）
│   │   ├── api/ws/              # WebSocket（浏览器自动化、Avatar 驱动）
│   │   ├── core/                # 配置、容器、上下文管理、工作流引擎、Agent 编排、调度器
│   │   ├── domains/             # 领域逻辑（社交、群聊、AI-AI 对话）
│   │   ├── engines/             # 引擎（双轨记忆、语音）
│   │   ├── infrastructure/      # 基础设施（数据库 28 表、备份、MQTT、同步、平台适配）
│   │   ├── runtime/             # 运行时（平台适配器 ×13、插件、技能、Provider）
│   │   ├── security/            # 安全体系（JWT、内部鉴权、RBAC、沙箱、审计、速率限制）
│   │   └── services/            # 业务服务层
│   ├── config/                  # 环境配置模板
│   ├── plugins/                 # 内置插件（4 个）
│   ├── skills/                  # 内置技能（21 个）
│   └── tests/                   # 自动化测试套件
│
├── frontend/                    # Electron + Vue 3 桌面客户端
│   ├── src/
│   │   ├── main/                # Electron 主进程（IPC、后端托管、窗口管理）
│   │   ├── preload/             # 预加载脚本
│   │   └── renderer/            # Vue 渲染进程（24 个功能页面）
│   └── resources/               # 静态资源（图标、Live2D 模型）
│
├── firmware/                    # ESP32 嵌入式固件
│   └── embedded/esp32-p4/       # ESP32-P4 主控（组件化：app / bsp / drivers）
│
├── templates/                   # 插件与扩展开发模板
└── docker/                      # Docker 部署与环境编排
```

## 文档

项目维护着一套完整的中文文档体系（概览 / 架构 / 接口 / 数据模型 / 功能实现 / 部署 / 开发指南 / 路线图），**仅随本地工作区提供，不随本仓库分发**。您可以在本地工作区的 `文档/` 目录中查阅。

### 打包与发布

桌面客户端的本地打包、跨平台产物与发布流程见 **[frontend/BUILD.md](frontend/BUILD.md)**：
- 本地一键打包脚本（`build-all.ps1`）
- GitHub Actions 全平台发布工作流（推 `v*` 标签发布正式 Release，master 分支版本变更发布 dev 预发布）
- 各平台产物形态（Windows 安装包/便携版、Linux AppImage/deb、macOS dmg/zip）与排障指南

## 贡献

我们热烈欢迎社区贡献！在提交代码前，请先阅读：
- [贡献指南 (Contributing Guide)](CONTRIBUTING_zh.md)（[English](CONTRIBUTING.md) / [日本語](CONTRIBUTING_ja.md)）
- [行为准则 (Code of Conduct)](CODE_OF_CONDUCT_zh.md)（[English](CODE_OF_CONDUCT.md) / [日本語](CODE_OF_CONDUCT_ja.md)）

快速贡献步骤：
1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/amazing-feature`
3. 提交更改：`git commit -m "feat(scope): add amazing feature"`
4. 推送分支：`git push origin feature/amazing-feature`
5. 创建 Pull Request

- 报告 Bug：[提交 Bug 报告](https://github.com/LuminousCX/LuomiNest/issues/new?template=bug_report.yaml)
- 功能建议：[提交功能请求](https://github.com/LuminousCX/LuomiNest/issues/new?template=feature_request.yaml)
- 社区讨论：[GitHub Discussions](https://github.com/LuminousCX/LuomiNest/discussions)

## 安全策略

如发现安全漏洞，请**切勿**在公开 Issue 中披露。请通过邮件私下联系核心团队：

- 邮箱：`luminouschenxi@outlook.com`
- 主题：`LuomiNest Security Report`

详见 [安全策略 (SECURITY.md)](SECURITY_zh.md)（[English](SECURITY.md) / [日本語](SECURITY_ja.md)）。

## 许可证

本项目基于 [GNU Affero General Public License v3.0](LICENSE) 开源。

---

<div align="center">

**LuomiNest** by [LuminousCX R&D Team](https://github.com/LuminousCX)

</div>

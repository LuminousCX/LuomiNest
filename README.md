<div align="center">

<img src="frontend/resources/icon.svg" alt="LuomiNest Logo" width="120" height="120" />

# LuomiNest

**分布式多用户关系型 AI 智能体平台**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.7.7-green.svg)](CHANGELOG.md)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Vue](https://img.shields.io/badge/Vue-3-4FC08D.svg?logo=vuedotjs&logoColor=white)](https://vuejs.org/)
[![Electron](https://img.shields.io/badge/Electron-41-47848F.svg?logo=electron&logoColor=white)](https://www.electronjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![CodeRabbit](https://img.shields.io/endpoint?url=https://coderabbit.ai/api/badges/LuminousCX/LuomiNest&label=CodeRabbit)](https://coderabbit.ai)
[![GitHub Stars](https://img.shields.io/github/stars/LuminousCX/LuomiNest?style=social)](https://github.com/LuminousCX/LuomiNest/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/LuminousCX/LuomiNest?style=social)](https://github.com/LuminousCX/LuomiNest/network/members)
[![GitHub Issues](https://img.shields.io/github/issues/LuminousCX/LuomiNest)](https://github.com/LuminousCX/LuomiNest/issues)
[![GitHub Last Commit](https://img.shields.io/github/last-commit/LuminousCX/LuomiNest)](https://github.com/LuminousCX/LuomiNest/commits/master)
[![Code Size](https://img.shields.io/github/languages/code-size/LuminousCX/LuomiNest)](https://github.com/LuminousCX/LuomiNest)

[English](#english) | [中文](#luominest)

</div>

---

<a id="luominest"></a>

## 简介

LuomiNest 是一个开源的**分布式多用户关系型 AI 智能体平台**，以"关系驱动"为核心设计理念。它通过主/从双层记忆架构，在群聊中自动提取每位用户的独立画像（从记忆），私聊时自动加载该用户的记忆（主记忆联动），实现真正个性化的多用户对话；同时支持人、AI、AI 与 AI 跨平台群聊协作。它可运行于桌面电脑、嵌入式终端（ESP32）、智能家居设备之上，覆盖自然语言对话、语音交互、Live2D 虚拟形象、工作流自动化与浏览器操作等能力，提供懂每一个人的长期智能体服务。

核心设计理念：**一台普通电脑即可运行，数据 100% 本地闭环。**

## 核心特性

- **沉浸式对话** — 多轮自然语言对话，支持多 LLM Provider（OpenAI / Anthropic / DeepSeek / Ollama 等），流式响应
- **Live2D 虚拟形象** — Cubism 5 引擎驱动，口型同步、表情驱动、情感映射，支持 VRM 模型与 PngTuber 像素化头像
- **三层记忆系统** — 工作记忆 + 情景记忆 + 语义记忆，自动提取事实、构建用户画像、知识图谱
- **语音交互** — Whisper / FunASR 语音识别（ASR）+ Edge TTS / 本地 TTS 等多引擎合成，支持多语言
- **多平台接入** — QQ（OneBot / 官方）、微信（公众号 / 企业微信）、Telegram、Discord、Minecraft 等 13 种适配器
- **MCP 工具协议** — 标准 MCP 协议支持，工具注册与调用，内置 CLI、文件操作、子 Agent 委派等工具
- **多 Agent 协作** — 任务分析 → 子任务调度 → 并行执行 → 结果综合，支持 A2A 协议 AI-AI 自主对话
- **工作流引擎** — 可视化节点编排、定时任务调度（APScheduler）、工具调用记录与持久化
- **浏览器自动化** — Luminous Human 模拟交互（鼠标 / 键盘 / 滚动），标签页管理、隐身预加载与搜索
- **主题皮肤系统** — 预设主题 + 自定义皮肤编辑器，注册表源管理与扩展市场
- **IoT 智能控制** — MQTT 设备通信，ESP32-P4 硬件终端，支持状态上报、音频流和位置信息
- **插件与技能系统** — Star 插件热加载 + Skills 轻技能双轨扩展，内置扩展市场
- **桌面客户端** — Electron 桌面应用，内置浏览器、桌面宠物、Live2D 皮套工坊、控制台终端
- **安全体系** — JWT 认证、RBAC 权限控制、本地沙箱、命令守卫、速率限制、安全审计日志
- **隐私优先** — 全部数据本地存储，零外网传输，AES-256 加密

## 技术栈

| 层级 | 技术选型 |
|------|---------|
| **前端** | Electron 41 + Vue 3 + TypeScript + Pinia + PixiJS (Live2D) |
| **后端** | Python 3.12+ + FastAPI + Uvicorn + SQLAlchemy 2 (async) + APScheduler |
| **存储** | SQLite (SQLAlchemy ORM) + JSON 文件 + PostgreSQL (PGVector) + Redis |
| **通信** | WebSocket + MQTT + HTTP/REST + SSE 流式响应 |
| **AI/LLM** | OpenAI / Anthropic / DeepSeek / Ollama，多厂商适配器 + 中间件管道 |
| **语音** | Whisper / FunASR (ASR) + Edge TTS / SherpaOnnx / 多引擎 TTS |
| **硬件** | ESP-IDF (ESP32-P4) |
| **部署** | Docker Compose + PyInstaller + Electron Builder + Inno Setup |

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 22+
- pnpm

### 一键启动（Make）

```bash
# 克隆仓库
git clone https://github.com/LuminousCX/LuomiNest.git
cd LuomiNest

# 安装全部依赖（前端 + 后端）
make install

# 配置环境变量
make config

# 启动后端
make dev-backend

# 新终端，启动前端
make dev-frontend
```

### 手动启动

<details>
<summary><strong>后端</strong></summary>

```bash
cd backend

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

# 安装依赖
pip install -e ".[dev]"

# 配置环境变量
cp config/.env.example config/.env
# 编辑 config/.env，填入 API Key

# 启动
python main.py
```

后端默认运行在 `http://127.0.0.1:18000`，API 文档访问 `http://127.0.0.1:18000/docs`。

</details>

<details>
<summary><strong>前端</strong></summary>

```bash
cd frontend

# 安装依赖
pnpm install

# 开发模式
pnpm dev

# 构建生产版本
pnpm build
```

</details>

<details>
<summary><strong>Docker 部署</strong></summary>

```bash
cd docker

# 开发环境（含 PostgreSQL + Redis + MQTT）
docker compose -f docker-compose.dev.yml up -d

# 生产环境
docker compose -f docker-compose.prod.yml up -d
```

</details>

## 项目结构

```
LuomiNest/
├── backend/                     # Python 后端服务
│   ├── app/
│   │   ├── api/v1/endpoints/    # REST API 端点（21 个模块）
│   │   ├── api/ws/              # WebSocket（认证、Avatar 驱动、连接管理）
│   │   ├── core/                # 配置、容器、工作流引擎、Agent 编排、调度器
│   │   ├── domains/             # 领域逻辑（社交、群聊、AI-AI 对话）
│   │   ├── engines/             # 引擎（记忆、渲染、定位）
│   │   ├── infrastructure/      # 基础设施（数据库、Redis、MQTT、安装、同步）
│   │   ├── runtime/             # 运行时（平台适配器、插件、Provider）
│   │   ├── security/            # 安全（JWT、OAuth、RBAC、沙箱、审计、速率限制）
│   │   └── services/            # 业务服务
│   ├── config/                  # 环境配置
│   ├── plugins/                 # 插件目录
│   ├── skills/                  # 技能目录
│   └── tests/                   # 测试
│
├── frontend/                    # Electron + Vue 3 桌面客户端
│   ├── src/
│   │   ├── main/                # Electron 主进程（IPC、浏览器自动化、后端托管）
│   │   ├── preload/             # 预加载脚本
│   │   └── renderer/            # Vue 渲染进程（26 个页面）
│   └── resources/               # 静态资源（图标、Live2D 模型）
│
├── firmware/                    # ESP32 嵌入式固件
│   └── embedded/esp32-p4/       # ESP32-P4 主控（组件化：app / bsp / drivers）
│
├── docker/                      # Docker 部署配置
├── docs/                        # VitePress 文档站
└── 文档/                        # 项目设计文档
```

## 文档

| 文档 | 说明 |
|------|------|
| [需求规格说明书](文档/SRS-需求规格说明书.md) | 系统功能边界、验收标准、技术约束（IEEE 830） |
| [核心架构文档](文档/ARC-核心架构文档.md) | 架构设计、技术选型、ADR 决策记录 |
| [接口规格说明书](文档/API-接口规格说明书.md) | REST / WebSocket / MQTT 接口契约 |
| [数据模型设计说明书](文档/DBS-数据模型设计说明书.md) | 数据实体、表结构、缓存策略 |
| [技术实现手册](文档/IMP-技术实现手册.md) | 代码实现、部署配置、开发指南 |
| [安全与隐私专项设计](文档/SEC-安全与隐私专项设计.md) | 安全合规、加密方案、审计机制 |
| [需求追溯矩阵](文档/RTM-需求追溯矩阵.md) | 需求全生命周期追踪 |
| [开放通信协议](文档/NEST-开放通信协议与自动化执行架构.md) | NestProtocol 协议栈设计 |

## 贡献

我们欢迎社区贡献！请先阅读 [贡献指南](CONTRIBUTING.md)。

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/amazing-feature`
3. 提交更改：`git commit -m "feat(scope): add amazing feature"`
4. 推送分支：`git push origin feature/amazing-feature`
5. 提交 Pull Request

报告 Bug：[提交 Bug 报告](https://github.com/LuminousCX/LuomiNest/issues/new?template=bug_report.yaml)
功能建议：[提交功能请求](https://github.com/LuminousCX/LuomiNest/issues/new?template=feature_request.yaml)

## 安全

如发现安全漏洞，请**不要**在公开 Issue 中提交。请通过邮件私下报告：

- 邮箱：`luminouschenxi@outlook.com`
- 主题：`LuomiNest Security Report`

详见 [安全策略](SECURITY.md)。

## 许可证

本项目基于 [GNU Affero General Public License v3.0](LICENSE) 开源。

---

<a id="english"></a>

## Introduction

LuomiNest is an open-source distributed multi-user relational AI agent platform built on a relationship-driven design. Its dual-layer memory architecture (primary memory pool + per-user persona memory) automatically extracts each user's profile during group chats and loads it back in private conversations, enabling truly personalized multi-user dialogue. It supports human, AI, and AI-to-AI collaboration across platforms (QQ / WeChat / Telegram / Discord, etc.). It runs on desktop computers, embedded terminals (ESP32), and smart home devices, delivering natural language dialogue, voice interaction, Live2D virtual avatars, workflow automation, and browser operations for a long-term agent experience that knows every single user.

Core design principle: **Runs on a single ordinary computer with 100% local data retention.**

## Key Features

- **Immersive Dialogue** — Multi-turn natural language conversations with multiple LLM providers (OpenAI / Anthropic / DeepSeek / Ollama), streaming responses
- **Live2D Avatar** — Cubism 5 engine with lip sync, expression drive, emotion mapping; VRM model and PngTuber support
- **Three-Layer Memory** — Working + episodic + semantic memory with automatic fact extraction, user profiling, and knowledge graphs
- **Voice Interaction** — Whisper / FunASR ASR + Edge TTS / local TTS synthesis, multi-language support
- **Multi-Platform Access** — 13 adapter types: QQ (OneBot / Official), WeChat (MP / Work), Telegram, Discord, Minecraft, and more
- **MCP Tool Protocol** — Standard MCP protocol support with tool registration and invocation; built-in CLI, file ops, sub-agent delegation
- **Multi-Agent Collaboration** — Task analysis → sub-task scheduling → parallel execution → result synthesis; A2A AI-to-AI autonomous dialogue
- **Workflow Engine** — Visual node orchestration, scheduled tasks (APScheduler), tool-call recording and persistence
- **Browser Automation** — Luminous Human simulated interaction (mouse / keyboard / scroll), tab management, incognito preload and search
- **Theme System** — Preset skins + custom skin editor, registry source management and marketplace
- **IoT Smart Control** — MQTT device communication, ESP32-P4 hardware terminals, status reporting, audio streaming, and location tracking
- **Plugin & Skill System** — Star plugin hot-reload + Skills lightweight extension dual-track architecture with built-in marketplace
- **Desktop Client** — Electron app with built-in browser, desktop pet, Live2D avatar workshop, and console terminal
- **Security** — JWT authentication, RBAC, local sandbox, command guard, rate limiting, and security audit logs
- **Privacy First** — All data stored locally, zero external transmission, AES-256 encryption

## Quick Start

```bash
git clone https://github.com/LuminousCX/LuomiNest.git
cd LuomiNest
make install    # Install all dependencies
make config     # Setup environment variables
make dev-backend   # Start backend (port 18000)
make dev-frontend  # Start frontend (new terminal)
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE).

---

<div align="center">

**LuomiNest** by [LuminousCX R&D Team](https://github.com/LuminousCX)

</div>

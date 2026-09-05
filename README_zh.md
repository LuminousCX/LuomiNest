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

</div>

---

## 简介

LuomiNest 是一个开源的**分布式多用户关系型 AI 智能体平台**，以"关系驱动"为核心设计理念。它通过主/从双层记忆架构，在群聊中自动提取每位用户的独立画像（从记忆），私聊时自动加载该用户的记忆（主记忆联动），实现真正个性化的多用户对话；同时支持人、AI、AI 与 AI 跨平台群聊协作。它可运行于桌面电脑、嵌入式终端（ESP32）、智能家居设备之上，覆盖自然语言对话、语音交互、Live2D 虚拟形象、工作流自动化与浏览器操作等能力，提供懂每一个人的长期智能体服务。

核心设计理念：**一台普通电脑即可运行，数据 100% 本地闭环。**

产品主打三件事：**记得住你（记忆性）、像一个生命（陪伴性）、装得上任何能力（扩展性）**。工具与 MCP 是基石级基础设施，不是卖点本身。

## 核心特性

- **双轨记忆系统** — 主人记忆 / 平台用户记忆行级隔离，自动事实抽取、蒸馏沉淀、画像与知识库，向量检索全量落 SQLite
- **Live2D 虚拟形象** — Cubism 5 引擎驱动，口型同步、表情驱动、情感映射，支持 PngTuber 像素化头像与桌面宠物（VRM 规划中）
- **插件与技能系统** — CxPlugin 插件热加载 + CxSkill 轻技能双轨扩展，内置扩展市场与多 CDN 发布源
- **沉浸式对话** — 多轮自然语言对话，支持多 LLM Provider（OpenAI 兼容 32 模板 / Anthropic 原生 / DeepSeek / Ollama 等），SSE 流式响应
- **多平台接入** — QQ（OneBot / 官方）、微信（公众号 / 企业微信）、Telegram、Discord、Minecraft、米家、Home Assistant 等 13 种适配器
- **语音交互** — SherpaOnnx / FunASR / Faster-Whisper 语音识别（ASR）+ Edge TTS / SherpaOnnx / 本地 TTS 等 7 引擎合成，能力声明与语言感知回退
- **MCP 工具协议** — 标准 MCP 协议支持，工具注册与调用，内置 CLI、文件操作、子 Agent 委派等 40+ 工具
- **多 Agent 协作** — 任务分析 → 子任务调度 → 并行执行 → 结果综合，支持 A2A 协议 AI-AI 自主对话
- **工作流引擎** — 可视化节点编排、模板库、定时任务调度（APScheduler）、工具调用记录与持久化
- **浏览器自动化** — Luminous Human 模拟交互（鼠标 / 键盘 / 滚动），标签页管理、隐身预加载与搜索
- **主题系统** — 预设主题与外观设置，注册表源管理与扩展市场（插件 / 技能安装）
- **IoT 智能控制** — MQTT 设备通信，ESP32-P4 硬件终端，设备 / 场景 / 房间 / 自动化统一视图
- **桌面客户端** — Electron 桌面应用，内置浏览器、桌面宠物、Live2D 皮套工坊、控制台终端
- **安全体系** — JWT / Token 双模式认证、RBAC（定义中）、本地沙箱、命令守卫、速率限制、安全审计日志、24h 自动备份
- **隐私优先** — 对话与记忆数据全部本地存储（单 SQLite 库），敏感配置 AES 加密

## 技术栈

| 层级 | 技术选型 |
|------|---------|
| **前端** | Electron 41 + Vue 3 + TypeScript + Pinia + PixiJS (Live2D) |
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

# 开发环境（backend + PostgreSQL + Redis + MQTT；后端当前使用 SQLite，pg/redis 为预留）
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
│   │   ├── api/v1/endpoints/    # REST API 端点（23 个模块）
│   │   ├── api/ws/              # WebSocket（浏览器自动化、Avatar 驱动）
│   │   ├── core/                # 配置、容器、端口、工具、工作流引擎、Agent 编排、调度器
│   │   ├── domains/             # 领域逻辑（社交、群聊、AI-AI 对话）
│   │   ├── engines/             # 引擎（记忆）
│   │   ├── infrastructure/      # 基础设施（数据库 27 表、备份、MQTT、同步、适配器）
│   │   ├── runtime/             # 运行时（平台适配器 ×13、插件、技能、Provider）
│   │   ├── security/            # 安全（JWT、内部鉴权、RBAC、沙箱、审计、速率限制）
│   │   └── services/            # 业务服务
│   ├── config/                  # 环境配置
│   ├── plugins/                 # 内置插件（4 个）
│   ├── skills/                  # 内置技能（21 个）
│   └── tests/                   # 测试
│
├── frontend/                    # Electron + Vue 3 桌面客户端
│   ├── src/
│   │   ├── main/                # Electron 主进程（IPC、浏览器自动化、后端托管）
│   │   ├── preload/             # 预加载脚本
│   │   └── renderer/            # Vue 渲染进程（24 个页面）
│   └── resources/               # 静态资源（图标、Live2D 模型）
│
├── firmware/                    # ESP32 嵌入式固件
│   └── embedded/esp32-p4/       # ESP32-P4 主控（组件化：app / bsp / drivers）
│
├── luominest-cloud/             # Java 云端服务（认证 + LLM 目录/配额，其余规划中）
├── templates/                   # 插件开发模板
└── docker/                      # Docker 部署配置
```

## 文档

## 文档

项目维护着一套完整的中文文档体系（概览 / 架构 / 接口 / 数据模型 / 功能实现 / 部署 / 开发指南 / 路线图），**仅随本地工作区提供，不随本仓库分发**。

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

<div align="center">

**LuomiNest** by [LuminousCX R&D Team](https://github.com/LuminousCX)

</div>

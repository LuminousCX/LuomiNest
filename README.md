<div align="center">

<img src="frontend/resources/icon.svg" alt="LuomiNest Logo" width="120" height="120" />

# LuomiNest

**Distributed Multi-User Relational AI Agent Platform**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.8.2-green.svg)](CHANGELOG.md)
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

## Introduction

LuomiNest is an open-source, **distributed multi-user relational AI agent platform** architected around a relationship-driven paradigm. Through its primary/secondary dual-layer memory system, LuomiNest automatically extracts independent profiles for individual participants in group chats (secondary memory) and seamlessly activates the user's specific context during direct conversations (primary memory linking). This powers authentic, tailored multi-user interactions while facilitating cross-platform group collaboration among humans, AI, and autonomous AI-to-AI networks.

Designed to operate seamlessly on standard desktop PCs, embedded edge devices (ESP32), and smart home hardware, LuomiNest integrates multi-turn natural language dialogue, real-time voice synthesis and recognition, Cubism 5 Live2D avatar drivers, visual workflow automation, and browser interactions into a durable, private AI companion that understands every user.

Core design tenet: **Runs smoothly on a single consumer PC with 100% local data sovereignty.**

The product centers on three pillars: **Memory (remembers who you are), Companionship (feels genuinely alive), and Extensibility (effortlessly integrates any capability)**. Tools and MCP form the bedrock infrastructure, serving the companion rather than complicating it.

## Key Features

- **Dual-Track Memory System** — Row-level isolation between owner memory and platform user profiles; experimental per-member group chat persona tracks (cross-group sharing); automatic fact extraction, distillation, user profiling, and full SQLite vector retrieval.
- **Live2D Virtual Avatars** — Powered by Cubism 5 runtime with real-time lip synchronization, expression drivers, and emotional mapping; supports pixel avatars (PngTuber), desktop pet modes, and upcoming VRM support.
- **Extensible Plugin & Skill Ecosystem** — Dual-track extensibility combining dynamic `CxPlugin` hot-reloading with lightweight `CxSkill` extensions; built-in extension marketplace supporting multi-CDN registries.
- **Immersive Multi-Provider Dialogue** — Robust multi-turn conversations supporting OpenAI-compatible APIs (32 provider templates), native Anthropic, DeepSeek, local Ollama, and full SSE streaming.
- **Omnichannel Platform Adapters** — Out-of-the-box adapters for 13 platforms: QQ (OneBot / Official API), WeChat (Official Accounts / Enterprise WeCom), Telegram, Discord, Minecraft, Xiaomi IoT, Home Assistant, and more.
- **Multi-Engine Voice Interaction** — High-accuracy speech recognition via SherpaOnnx, FunASR, and Faster-Whisper; speech synthesis across 7 engines (Edge TTS, SherpaOnnx, local offline TTS, Gemini, MiniMax, SiliconFlow, Fish Audio) with capability negotiation and language-aware fallback.
- **Model Context Protocol (MCP)** — Native implementation of the MCP protocol with dynamic tool registration and execution; 20+ built-in system tools covering CLI execution, file manipulation, and sub-agent delegation.
- **Multi-Agent Orchestration & A2A** — Structured task decomposition: problem analysis → sub-task scheduling → concurrent execution → result synthesis; supports native AI-to-AI autonomous dialogue via the A2A protocol.
- **Visual Workflow Engine** — Drag-and-drop node orchestration, workflow template library, cron and interval scheduling (APScheduler), with persistent tool call audits.
- **Secure Embedded Browser** — Hardened read-only navigation mode with automated page snapshots, thumbnail previews, and constrained AI tools (`browser_visit` / `browser_screenshot`) to eliminate external DOM injection hazards.
- **Unified Log Center** — Unified log pipeline aggregating renderer, main process, backend, and platform adapters; supports recent log search, severity filtering, live tailing, and privacy-redacted diagnostic uploads.
- **IoT & Smart Home Automation** — MQTT protocol communication, hardware integration with ESP32-P4, Home Assistant integration (12 device domains with read-only sensors), and unified scene/device status views.
- **Electron Desktop Client** — Polished desktop environment featuring floating desktop pets, Avatar Workshop, interactive terminal, and adaptable theme styling.
- **Enterprise Security & Compliance** — Multi-jurisdiction onboarding gate for Terms of Service and Privacy Policy (PIPL, CCPA/CPRA, etc.); JWT/Token dual authentication; command sandbox; rate limiting; AES-256 encrypted configurations; and 24-hour scheduled backups.
- **Privacy First** — Dialogue and memory databases reside entirely on your local machine (single SQLite WAL file); sensitive credentials stay secure and are never uploaded without explicit consent.

## Technology Stack

| Layer | Technologies |
|-------|--------------|
| **Frontend** | Electron 44 + Vue 3 + TypeScript + Pinia + PixiJS (Live2D Cubism 5) |
| **Backend** | Python 3.12+ + FastAPI + Uvicorn + SQLAlchemy 2 (async) + APScheduler |
| **Storage** | SQLite (SQLAlchemy ORM, WAL mode single DB) + JSON caching; PostgreSQL / Redis reserved for cloud scaling |
| **Communication** | WebSocket + MQTT + HTTP/REST + SSE (Server-Sent Events) |
| **AI / LLM** | OpenAI / Anthropic / DeepSeek / Ollama, multi-vendor adapters + middleware pipeline |
| **Speech** | SherpaOnnx / FunASR / Faster-Whisper (ASR) + Edge TTS / SherpaOnnx / Local / Cloud TTS engines |
| **Hardware** | ESP-IDF (ESP32-P4) |
| **Distribution** | Docker Compose + PyInstaller + Electron Builder + NSIS |

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 22+
- pnpm (recommended 10.x+)

### Quick Launch with Make

```bash
# Clone the repository
git clone https://github.com/LuminousCX/LuomiNest.git
cd LuomiNest

# Install all dependencies (Frontend + Backend)
make install

# Configure environment variables
make config

# Start backend service (port 18000)
make dev-backend

# In a new terminal, launch the desktop client
make dev-frontend
```

### Manual Setup

<details>
<summary><strong>Backend Setup</strong></summary>

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

# Install development dependencies
pip install -e ".[dev]"

# Configure environment
cp config/.env.example config/.env
# Edit config/.env and configure your LLM API keys

# Start backend server
python main.py
```

The backend server will run at `http://127.0.0.1:18000`. Interactive API documentation is available at `http://127.0.0.1:18000/docs`.

</details>

<details>
<summary><strong>Frontend Setup</strong></summary>

```bash
cd frontend

# Install dependencies
pnpm install

# Launch Vite development server with Electron
pnpm dev

# Build production artifacts
pnpm build
```

</details>

<details>
<summary><strong>Docker Deployment</strong></summary>

```bash
cd docker

# Development environment (backend + PostgreSQL + Redis + MQTT; backend currently uses SQLite, pg/redis reserved)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Production environment
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

</details>

## Project Structure

```
LuomiNest/
├── backend/                     # Python backend service
│   ├── app/
│   │   ├── api/v1/endpoints/    # REST API endpoints (24 modules)
│   │   ├── api/ws/              # WebSocket endpoints (browser automation, avatar driver)
│   │   ├── core/                # Configuration, container, context, workflow, agent orchestration
│   │   ├── domains/             # Domain logic (social, group chat, AI-to-AI interaction)
│   │   ├── engines/             # Engine subsystems (dual-track memory, voice)
│   │   ├── infrastructure/      # Infrastructure (28 database tables, backup, MQTT, adapters)
│   │   ├── runtime/             # Runtimes (13 platform adapters, plugins, skills, providers)
│   │   ├── security/            # Security (JWT, internal auth, RBAC, sandbox, audit, rate limits)
│   │   └── services/            # Application business services
│   ├── config/                  # Environment configuration templates
│   ├── plugins/                 # Built-in plugins (4 plugins)
│   ├── skills/                  # Built-in lightweight skills (21 skills)
│   └── tests/                   # Automated test suite
│
├── frontend/                    # Electron + Vue 3 desktop application
│   ├── src/
│   │   ├── main/                # Electron main process (IPC, backend management, window state)
│   │   ├── preload/             # Electron preload scripts
│   │   └── renderer/            # Vue 3 renderer application (24 functional views)
│   └── resources/               # Static assets (application icons, Live2D models)
│
├── firmware/                    # ESP32 embedded firmware
│   └── embedded/esp32-p4/       # ESP32-P4 controller (modular: app / bsp / drivers)
│
├── templates/                   # Plugin and skill development templates
└── docker/                      # Docker deployment configurations
```

## Documentation

The project maintains a comprehensive technical documentation suite (architecture, API specs, data models, deployment guides, and roadmaps). **This documentation is maintained in the local workspace directory (`文档/`) and is not distributed through the public git repository.** Please consult the `文档/` directory in your local checkout.

### Packaging & Release

For details on packaging and multi-platform distribution, please see **[frontend/BUILD.md](frontend/BUILD.md)**:
- One-click local builds (`build-all.ps1`)
- GitHub Actions CI/CD workflows (`v*` tags trigger production releases; changes to `master` trigger dev pre-releases)
- Platform distribution formats (Windows NSIS/portable, Linux AppImage/deb, macOS dmg/zip) and troubleshooting.

## Contributing

We warmly welcome community contributions! Please review our guides before getting started:
- [Contributing Guidelines](CONTRIBUTING.md) ([中文版](CONTRIBUTING_zh.md) / [日本語](CONTRIBUTING_ja.md))
- [Code of Conduct](CODE_OF_CONDUCT.md) ([中文版](CODE_OF_CONDUCT_zh.md) / [日本語](CODE_OF_CONDUCT_ja.md))

Quick contribution steps:
1. Fork the repository
2. Create your feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m "feat(scope): add amazing feature"`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

- Report a Bug: [Submit Bug Report](https://github.com/LuminousCX/LuomiNest/issues/new?template=bug_report.yaml)
- Request a Feature: [Submit Feature Request](https://github.com/LuminousCX/LuomiNest/issues/new?template=feature_request.yaml)
- Community Discussions: [GitHub Discussions](https://github.com/LuminousCX/LuomiNest/discussions)

## Security Policy

If you discover a security vulnerability, please **do not** create a public issue. Report it confidentially to:

- Email: `luminouschenxi@outlook.com`
- Subject: `LuomiNest Security Report`

For complete disclosure policies, see [SECURITY.md](SECURITY.md) ([中文版](SECURITY_zh.md) / [日本語](SECURITY_ja.md)).

## License

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE).

---

<div align="center">

**LuomiNest** by [LuminousCX R&D Team](https://github.com/LuminousCX)

</div>

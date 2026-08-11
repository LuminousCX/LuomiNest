# Changelog

All notable changes to LuomiNest will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Deprecated

### Removed

### Fixed

### Security

---

## [0.7.7] - 2026-08-11

> 本版本合并了 v0.7.4 之后的所有开发工作（含未打标签的 0.7.5 / 0.7.6 开发版本），是自
> v0.7.4 起的首个正式发布版本。

### Added

- **主题系统与扩展市场增强** (#62)
  - 主题皮肤编辑器：自定义皮肤创建、背景图片上传与预览
  - 预设主题管理与皮肤选择器
  - 注册表源（Registry Source）管理：自定义 CDN 源、GitHub 同步与市场目录增强
- **认证与安全基础设施**
  - JWT 认证端点重构与本地令牌签发/校验
  - WebSocket 连接认证（WS Auth）
  - 命令守卫（Command Guard）与命令安全策略
  - 速率限制（Rate Limiter）
  - 提示词安全过滤（Prompt Security）
  - 沙箱体系：本地沙箱、文件路径策略、环境变量策略
- **依赖注入容器**（DI Container）与平台信息模块
- **MCP 协议集成**：工具注册与调用、MCP 端点
- **Avatar 驱动系统**：PngTuber 像素化头像、像素宠物与 WebSocket 实时驱动
- **工作流引擎增强**：定时任务调度（APScheduler）、工具调用记录与持久化
- **浏览器自动化**：Luminous Human 模拟交互（鼠标 / 键盘 / 滚动）、标签页管理与隐身预加载
- **数据库层**：SQLAlchemy ORM 模型与仓储层、JSON → SQLite 迁移器、Provider 凭据管理
- **设置页面**：关于开发者、隐私与合规、项目参考（依赖许可证清单）页面
- **固件**：ESP32-P4 组件化重构（app / bsp / drivers 分层），以太网、SPI 帧接收与 JPEG 解码

### Changed

- 插件与技能系统重构：CxPlugin 框架统一平台适配器升级 (#61)
- 聊天基础设施重构：平台会话管理与对话持久化增强 (#60)
- 硬件抽象层、语音引擎迁移与前端架构优化 (#58)
- 固件重构：移除多余嵌入式工程，重组 ESP32-P4 架构 (#59)
- 数据库层重构：SQLAlchemy ORM 迁移，移除已废弃的 Facade 层 (#55)
- Provider 系统重构：多厂商 LLM 适配器、凭据管理、中间件管道
- 前端架构优化：大型视图拆分（Composable 化）、共享 IPC 类型、作用域日志基础设施
- 语音引擎统一：STT / TTS Provider 接口（Edge TTS、SherpaOnnx、Faster-Whisper、FunASR、Fish-Audio、Gemini、MiniMax、SiliconFlow）

### Deprecated

### Removed

- 移除已废弃的数据库 Facade 层
- 移除旧版固件工程结构（esp32-s3 / esp32-c6-coordinator / 预渲染服务器）
- 清理项目中的临时脚本与调试文件

### Fixed

- 修复 WebSocket 认证与依赖解析问题
- 修复工作流工具注册与浏览器组件问题
- 修复记忆引擎关闭时的并发问题
- 修复扩展市场安全漏洞与安装流程缺陷

### Security

- 认证中间件强化：WS 认证、命令守卫与速率限制
- 提示词安全过滤与沙箱增强
- 安全审计日志与依赖审计

---

## [0.7.4] - 2026-06-30

### Added

- 数据库层重构：SQLAlchemy ORM 模型、仓储层与迁移器
- 扩展市场 UI 增强与统计排行榜 (#54)

### Changed

- 存储层从 JSON 平滑迁移至 SQLite（保留 JSON 兼容层）
- Provider 系统增强

### Fixed

- 修复市场安全漏洞与功能缺陷

---

## [0.7.0] - 2026-06-20

### Added

- 登录页与启动页（Splash）
- TTS 文本过滤器与语音合成优化
- 扩展市场统计与安装系统、注册表源管理
- 建议问题组件

### Changed

- v0.7.0 大版本更新：侧边栏与聊天模块重构
- Live2D 与 Provider 系统优化
- 构建脚本与安装程序配置优化

### Fixed

- 修复市场安全漏洞和功能缺陷 (#48)

---

## [v0.4.0] - 2026-04-23

### Added

- 插件市场与 Skill 市场模块
- Agent 隔离的对话状态管理
- 多 Agent 编排系统与任务管理 (#16 / #18)
- 技能 / 工具调用、RAG 搜索、多 Agent 对话、群聊与本地持久化
- 桌面宠物模式与 Live2D 模型导入、持久化支持

### Changed

- 构建系统优化与 CI/CD 工作流增强 (#13)

### Fixed

- 修复 HTML 嵌套错误与 CSP 配置
- 修复后端启动崩溃问题

---

## [v0.3.0] - 2026-04-14

### Added

- Live2D 头像系统：模型导入、表情控制、桌面宠物模式
- 浏览器增强：标签页缓存、休眠模式、错误处理与 IPC 通信
- Inno Setup 安装程序与依赖升级

### Changed

- 前端目录结构重构
- CSS 变量统一与深色模式支持

---

## [v0.2.0-alpha] - 2026-04-13

### Added

- 初始桌面客户端架构（Electron + Vue 3）
- Avatar、Memory、Social 视图页面
- Python 后端服务与 Live2D 模型
- 自动化构建与发布工作流（GitHub Actions）

---

## [0.1.0] - 2026-01-15

### Added

- 项目初始化
- 基于 FastAPI 的基础后端结构
- 聊天与 Agent 交互核心 API
- 初始 Electron 前端应用
- 基础 Live2D 模型集成
- 简单记忆存储实现
- MQTT 客户端用于 IoT 通信

---

## Version History

| Version | Date | Description |
|---------|------|-------------|
| 0.1.0 | 2026-01-15 | Initial release with core functionality |
| v0.2.0-alpha | 2026-04-13 | Alpha release: desktop client + backend service |
| v0.3.0 | 2026-04-14 | Live2D avatar, desktop pet, enhanced browser |
| v0.4.0 | 2026-04-23 | Marketplace, agent isolation chat, multi-agent collaboration |
| 0.7.0 | 2026-06-20 | Major update: login/splash, sidebar & chat refactor, marketplace |
| 0.7.4 | 2026-06-30 | Database layer refactor (SQLAlchemy ORM), marketplace enhancement |
| 0.7.5 | dev | Browser automation, settings pages, hardware abstraction, firmware restructure |
| 0.7.6 | dev | Chat infrastructure, plugin/skill refactor, MCP integration, PngTuber |
| 0.7.7 | 2026-08-11 | Theme system & marketplace enhancement, auth & security hardening |

---

[Unreleased]: https://github.com/LuminousCX/LuomiNest/compare/v0.7.7...HEAD
[0.7.7]: https://github.com/LuminousCX/LuomiNest/releases/tag/v0.7.7
[0.7.4]: https://github.com/LuminousCX/LuomiNest/releases/tag/v0.7.4
[0.7.0]: https://github.com/LuminousCX/LuomiNest/releases/tag/0.7.0
[v0.4.0]: https://github.com/LuminousCX/LuomiNest/releases/tag/v0.4.0
[v0.3.0]: https://github.com/LuminousCX/LuomiNest/releases/tag/v0.3.0
[v0.2.0-alpha]: https://github.com/LuminousCX/LuomiNest/releases/tag/v0.2.0-alpha
[0.1.0]: https://github.com/LuminousCX/LuomiNest/releases/tag/v0.1.0

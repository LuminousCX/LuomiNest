# Changelog

All notable changes to LuomiNest will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- 工具检索（S1b）：`ToolRegistry` / `InternalToolRegistry` 新增 `search()` 轻量召回；workflow 工具注入改为「核心+召回全 schema、长尾仅名称、`tool.read` 按需取定义」；普通模式白名单并入召回结果与 meta 工具
- workflow 路径超长工具输出（>2000 字符）统一落盘 `tool_call_records` 并替换占位符，与 function calling 中间件同阈值
- `tool_call_records` 表新增 `scope` / `tool_type` 列（工具分层审计）
- 浏览器开发者面板新增「源码」tab（读取当前页 HTML）；统一搜索框组件 `SearchInput`
- 工坊模型管理：内置模型支持「隐藏/恢复」（localStorage 本地偏好，仅影响工坊列表，桌宠与 `luominest-avatar://` 协议加载不受影响）；导入模型支持删除（二次点击确认，连本地文件一并删除，此前删除逻辑无 UI 入口）；类型切换与工坊初始化自动跳过已隐藏模型
- CONTRIBUTING 新增「模型资产分发政策」：内置皮套/语音模型目录仅官方维护、不接受资产类 PR；用户导入模型存应用数据目录（userData），结构上不进 git 仓库
- 后端工具函数收口：`core/utils.parse_llm_json`（LLM 围栏 JSON 解析 4 份实现合一，含截断修复超集）、`AsyncKeyLocks`（按 key 双检锁 4 份合一）、`extract_llm_text` 超集化（支持 choices 嵌套解析）
- 后端公共件下沉：`runtime/provider/model_paths`（4 份模型目录解析合一）、`model_downloader`（sherpa STT/TTS 下载器合一）、STT 公共基类 `BaseSTTProvider`（音频解码/重采样/16k 采样率收口）、TTS `tts/_http.post_json_for_audio`（4 家云 TTS HTTP 模板合一）、平台侧 `AppTokenMixin`（QQ 官方/公众号/企微三份 token 管理合一）与共享 `parse_target`
- LLM 双协议适配器抽 `adapters/common.py`：可重试状态码/错误分类/推理清洗/工具调用合并/客户端生命周期 mixin，消除 chat_completions 与 anthropic_messages 间已分叉的 6 组重复
- `BaseRepository` 新增通用 `upsert_async` / `delete_by_provider_async`：5 份手写 upsert、2 份逐字重复的删除方法收口；conversation 门面 22 个 `*_async` 直连 repository 去掉双层 to_thread 包装
- Settings 新增 `MODEL_DOWNLOAD_TIMEOUT`(=600)、`PLATFORM_HTTP_TIMEOUT`(=15)，替换平台适配器散落的硬编码超时
- 大文件拆分（对外导出与行为不变）：`core/context/__init__`（789 行 5 类 → 5 模块）与 `core/workflow/register_tools.py`（2024 行 → tool_domains/ 7 个域模块 + 入口）

### Changed

- 对话模式收敛为 普通/专业 双模式；存量 ultra 会话启动时自动归一为 standard，workflow 入参 ultra 自动归一
- 会话搜索提速：SQL 层 `instr()` 定位命中位置 + `LIMIT 50`，替换全字段 LIKE 扫描与 Python 逐行切片；前端防抖后才进入 loading 态并支持 AbortController 取消过期请求
- 搜索结果高亮逻辑收敛到 `utils/highlight.ts`；工作台搜索结果点击后滚动并高亮命中消息
- 后端全库时间戳统一 `core.utils.utc_now/utc_now_dt`；记忆目录/owner 前缀收口到 `engines/memory/store.py`（`agents_root`/`agent_memory_dir`/`OWNER_PREFIX` 等，替换 7 处手拼路径与 9 处 "owner:" 字面量）；默认音色常量 `DEFAULT_EDGE_VOICE` 收口到 `core/constants/voice.py`
- TTS 注册表更名 `LuminousChenXiTTSRegistry` → `LuomiNestTTSRegistry`（旧名保留别名兼容）；文档 03-接口规格修正 system/models/platforms 三处前缀失配与"约 49 处 HTTPException"过时描述，02-系统架构同步 services/Depends 工厂计数
- 依赖全量刷新（2026-09-06，venv 删除重建逐包验证）：`pyproject.toml` 下限同步为验证过的最新稳定版（fastapi 0.141.1 / pydantic 2.13.5 / sqlalchemy 2.0.52 / numpy 2.5.2 / mcp 2.1.1 等），extras/dev 同步；前端 pnpm 10.33.0→10.34.5、vue-tsc 3.2.6→3.3.11，node_modules 与 pnpm-lock.yaml 删除重装（npm/pip/maven 全程走内网 Nexus 镜像）
- `runtime/platform/infrastructure/retry.py` 重试调度改由 tenacity 承担（该依赖此前已声明但全库零使用）：对外 `RetryConfig` / `async_retry` / `RetryCallback` 接口、延迟公式与日志格式不变，异步 `on_retry` 经自定义 sleep 钩子保持"回调→睡眠"顺序，替换前 7 项行为用例全过
- `domains/social/agent_orchestrator._extract_json_plan` 收口到 `core/utils.parse_llm_json`（LLM JSON 提取第 5 处合一，顺带获得截断修复能力）
- 测试目录归位：tests/ 内 15 个 Phase 期独立自验脚本（模块级 `sys.exit` / `asyncio.run`，pytest 收集即 INTERNALERROR，且写死旧项目绝对路径）移至 `backend/scripts/selfcheck/` 并修复路径；`tests/` 仅保留 pytest 套件

### Fixed

- 鉴权兼容性：passlib 1.7.4（已停更）与 bcrypt 5.x 不兼容，`hash()` 直接抛 `ValueError`，全部密码哈希失效；`pyproject.toml` 钉扎 `bcrypt>=4.1.0,<5.0.0`（4.3.0 验证通过）
- 打包版内置皮套全部不可见：`avatar-manifest.json` 未随 PyInstaller 打包，而工坊以 `/avatar/manifest` 为单一真相源，导致安装后清单为空；现已随包分发，同步修正 `avatar_manifest.py` 过时注释（缺失日志 debug → warning）
- 扩展市场搜索框编译错误：`MarketplaceSearch` 开标签已改 `SearchInput` 但闭标签残留 `</LumiInput>`；`SearchInput` 内置搜索图标，冗余 `#icon` 插槽一并移除
- `SettingsTtsSection` 模板引用未定义的 `ttsDeviceLabel` / `ttsDeviceHint`（vue-tsc 报错），补齐对应计算属性
- 侧边栏导航树形子项圆点与图标重叠：圆点缩小并锚定到树枝线末端、图标缩进后移（`--space-5` → `--space-6`）；激活子项的圆点与连接枝干点亮品牌色，形成位置指向
- `voice_config_store` 迁移动作时间戳由本地无时区 `datetime.now()` 修正为 UTC（与同文件其他 UTC ISO 串混存导致排序/比较错乱）
- 桌面端启动报 `Error: Electron uninstall`：pnpm 已不读取 package.json 的 `pnpm` 字段（且原文件键名重复），`onlyBuiltDependencies` 白名单与 `overrides` 全部失效，electron 二进制下载脚本被 pnpm 10 默认拦截；构建白名单统一迁至 pnpm-workspace.yaml `allowBuilds`（补 `vue-demi`），移除 package.json 两处死配置
- 存储位置核验：dev（`backend/data/`）与打包版（userData/Data/backend）后端数据分离正确、gitignore 覆盖实测通过（db/密钥/上传/记忆均不可入库）、API key 为 Fernet 密文落盘且 SECRET_KEY 机器指纹绑定加密；修正 `.gitignore` 中打包版 userData 路径注释（实际为 `%APPDATA%/luominest-desktop`，与开发版共用，经确认维持共用）

### Removed

- 移除超长（ULTRA）工作流模式及其高迭代预算配置
- 移除 29 个浏览器自动化工具中的 27 个交互类工具（导航/点击/输入/标签页管理等）及 `browser.search`、`create_browser_tab`；仅保留页面截图与读取当前页 HTML 两个观察类工具，交互能力保留在前端开发者面板
- 后端死代码清理：`services/browser_automation_client.py`（废弃兼容门面）、`infrastructure/mqtt/publisher.py`（零引用）、3 个 0 字节 security 占位文件（tls_manager/oauth_provider/audit exporter）、5 个仅剩 `__pycache__` 的空壳目录、`core/exceptions.register_exception_handlers`（从未注册）、`deps.py` 8 个无消费者的 Depends 工厂

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

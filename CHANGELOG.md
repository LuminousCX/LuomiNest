# Changelog

All notable changes to LuomiNest will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.8.2] - 2026-09-20

> 本版本聚焦「安全合规与加固」、「记忆系统性能与架构跃升」及「跨平台主 Agent 全量身份接管」：
> 包含 6 批次安全与架构审计全量收口（命令沙箱管道绕过防御、JWT Token 细粒度版本吊销与类型校验、
> 查询与日志深度脱敏、PBKDF2 动态盐密钥派生、跨库迁移与 WAL 恢复健全性）、
> 记忆系统重大性能突破（向量索引 25x 批量化与长连接池、(n,d) 矩阵并发检索、事实原子读改写与死代码清除）、
> 主 Agent 跨平台全量身份接管、多平台脚手架与防封实战指南、Minecraft 26.2 协议动态适配与遥测回退修复、
> 以及全套中英日三语社区规范与指示性文件体系。
>
> This release focuses on security hardening, memory subsystem performance leap, and cross-platform agent identity takeover:
> Comprehensive completion of security and architecture audit batches (command sandbox pipeline defense, JWT token version revocation,
> query and log redaction, PBKDF2 salted keys, robust cross-database migration and WAL recovery),
> major memory breakthroughs (vector retrieval 25x batching with keep-alive connection pool, (n,d) matmul candidate scoring, atomic store mutation),
> cross-platform primary agent identity takeover, Minecraft 26.2 dynamic compatibility & telemetry fix,
> and full trilingual (EN/ZH/JA) community health and indicator documentation.

### Added（新增）

- 平台与身份：统一主 Agent 跨平台全量身份接管、多平台脚手架与防封实战指南；Minecraft 26.2（协议 776）动态兼容补丁与自动 Bot 启动支持 — Platform & Identity: unified cross-platform identity takeover for the main agent, platform scaffolding & account safety guide; Minecraft 26.2 (protocol 776) dynamic compatibility patch & auto bot launcher
- 记忆体系：子 Agent 独立记忆轨开通、记忆注入闸门、事实与向量生命周期联动、记忆中枢可选页 — Memory: dedicated memory tracks for sub-agents, memory injection gates, fact-vector lifecycle linkage, configurable memory center view
- 国际化与社区：中英日三语指示性与规范文件体系（README / CONTRIBUTING / CODE_OF_CONDUCT / SECURITY）— Trilingual (EN/ZH/JA) community health & indicator documentation suite

### Changed（变更）

- 性能优化：记忆向量索引 25x 批量加速（HTTP RTT 6331ms→253ms）与长连接池、检索候选堆叠 (n,d) 单次 matmul 计算（10-100x）、分词预计算与词表剪枝 — Performance: 25x vector index batching (RTT 6331ms→253ms) with keep-alive pool, stacked (n,d) matmul candidate scoring (10-100x), tokenization precomputation
- 数据持久化：BaseRepository.save 单语句原子 upsert、存储层 store.mutate 原子读写消灭竞态、跨库迁移表清单 ORM 动态化与行级校验 — Data persistence: single-statement atomic upsert, atomic store.mutate against write races, dynamic ORM schema migration with row verification
- API 契约：RequestValidationError 422 统一转规范信封，回收站失败路径显式抛出 NotFoundError，调度器端点统一 ok 信封 — API Contracts: standardized 422 validation error envelopes, explicit NotFoundError on trash failure paths, unified scheduler ok envelopes

### Security（安全加固）

- 沙箱防御：validate_command 强化命令拆段安全审查，封堵管道符 `|` 与反引号/`$()` 命令替换绕过 — Sandbox: hardened command tokenization and validation, blocking pipe `|` and command substitution (`$()`, backticks) bypasses
- 鉴权治理：JWT token_type 校验（区分 access/refresh）、登出/吊销校验 token_version 并实时清空缓存；SECRET_KEY 派生升级为 PBKDF2 动态随机盐 — Authentication: strict token_type check (access vs refresh), real logout token_version verification with cache invalidation; PBKDF2 random-salted SECRET_KEY derivation
- 深度脱敏：请求日志 Query 参数与 URL 敏感键深度脱敏，禁止 HTTP ?token= query 鉴权回退，诊断日志导出自动抹除机密 — Redaction: deep query & URL secret parameter redaction, removal of HTTP ?token= query fallback, auto-redacted diagnostic logs
- 供应链安全：插件与市场下载强制主机白名单与 500MB 大小上限，字符集与路径规范防止遍历逃逸 — Supply Chain: strict trusted download host whitelist, 500MB payload guard, character set and path traversal validation

### Fixed（修复）

- 修复平台工具调用跟进大模型 400 报错与遥测数据回退 — Fixed platform tool call upstream 400 errors and telemetry data fallback
- 修复 OpenAI/DeepSeek 工具名称包含点号不兼容问题与 tool_call_id 规范化 — Sanitized dot-separated tool names for OpenAI/DeepSeek API compliance and normalized tool call IDs
- 修复备份恢复 WAL/SHM 残留重放损坏与并发文件锁冲突 — Fixed backup recovery WAL/SHM remnant replay corruption and concurrent file lock races

## [0.8.1] - 2026-09-16

> 本版本聚焦「可诊断性」与「首次体验」：统一日志中心与诊断上传、首启引导合规化
> （协议/隐私门禁 + 三语法律文本）、内置浏览器精简为只读、群友画像双轨记忆、
> 云端群聊与显示偏好云同步客户端、Home Assistant 设备列表接入。
>
> This release focuses on diagnosability and first-run experience: unified log center
> with diagnostic upload, compliance-ready onboarding (consent gate + trilingual legal
> texts), read-only built-in browser, per-member persona memory tracks, cloud group
> chat & display-preference sync clients, and Home Assistant device listing.

### Added（新增）

- 统一日志中心：前端/主进程/后端/平台四路日志归一，新日志页支持近 1000 条查看、来源与级别筛选、搜索、实时尾随（上翻暂停）、导出与轮转文件管理 — Unified log center: renderer/main/backend/platform logs merged into a new log page with recent-1000 view, source & level filters, search, live tail (pauses on scroll up), export and rotation-segment management
- 诊断日志上传：登录洛米通行证后可在日志页手动上传近期日志用于问题排查；上传前自动抹除令牌片段并丢弃附件类数据，云端保留 30 天，绝不自动上传 — Diagnostic log upload: manually upload recent logs from the log page after signing in to Lumi Pass; secrets redacted and attachments dropped before upload, kept 30 days server-side, never automatic
- 首次启动引导重编排：用户协议与隐私政策双勾选门禁（版本化同意记录）→ 语言选择 → 登录（洛米通行证 / 本地账号 / 稍后再说）→ 新手指引卡片 → 就绪 — Redesigned first-run wizard: dual-checkbox Terms & Privacy consent gate (versioned record) → language → sign-in (Lumi Pass / local account / later) → feature-tour cards → ready
- 新增用户协议页，隐私政策扩写：中国《个人信息保护法》专章、美国州法（CCPA/CPRA、VCDPA、CPA、CTDPA、UCPA）统一权利行使入口、未成年人保护、第三方处理与数据安全措施（三语） — New Terms of Service page; Privacy Policy expanded with a PIPL chapter, US state-law rights (CCPA/CPRA, VCDPA, CPA, CTDPA, UCPA) with a unified exercise channel, minors' protection, third-party processing and security measures (trilingual)
- 显示偏好云同步（可关闭）：语言、主题与协议同意记录跨设备同步，仅同步白名单字段；聊天、记忆、凭证等本地数据永不自动上云 — Optional display-preference sync: language, theme and consent record across devices, whitelisted fields only; chats, memories and credentials are never uploaded automatically
- 云端群聊客户端（服务开通后可用）：联系人面板云端群分组、创建/邀请/消息线程、增量拉取与失焦暂停轮询；服务未开通时优雅空态 — Cloud group chat client (activates when the service is live): cloud-group section in contacts, create/invite/message thread with incremental fetch and focus-aware polling; graceful empty state while unavailable
- 双轨记忆群友画像（实验性）：群聊按「平台+实例+成员」建画像轨，同一成员跨群共用；上下文自动注入在场群友画像摘要（受平台记忆写入开关控制） — Dual-track memory, member personas (experimental): per-member tracks keyed by platform+instance+sender shared across groups; in-context persona summaries injected for group chats (gated by the platform memory-write switch)
- 智能家居：Home Assistant 设备列表接入（12 类设备域、只读传感器标注），聚合端点对离线实例统一容错并标注跳过 — Smart home: Home Assistant device listing (12 device domains, read-only sensors labeled); aggregation endpoints skip offline instances gracefully with per-instance status
- 本地登录真化：替换演示性放行，注册/登录走真实后端鉴权；设置页云账号支持一键切换账号 — Local sign-in now performs real authentication (demo bypass removed); one-click account switching added for the cloud account

### Changed（变更）

- 内置浏览器精简为只读浏览：网址导航 + 加载成功自动截图（会话内历史、放大/复制/另存），移除表单填写、点击注入与 DOM 面板 — Built-in browser simplified to read-only browsing: URL navigation with automatic screenshots on load (session history, preview/copy/save); form filling, click injection and the DOM dev panel removed
- AI 侧浏览器工具收敛为 `browser_visit`（导航→等待→自动截图）与 `browser_screenshot` — AI-facing browser tools narrowed to `browser_visit` (navigate → wait → auto-screenshot) and `browser_screenshot`
- Splash 启动后恢复上次活跃页面（带路由表校验与防弹跳兜底）；云同步的偏好即时生效，无需重启 — Splash resumes the last active page (validated against the route table with anti-bounce fallback); synced preferences now apply immediately without restart
- Python 测试安全网 150→203（域策略/轨迹目录/群友画像块/设备列表映射等）；平台实例日志增加 5MB 轮转 — Python test suite 150→203 (domain policy, track dirs, persona blocks, device mapping); platform instance logs now rotate at 5MB

### Fixed（修复）

- 打包版内置皮套模型不可见：`avatar-manifest.json` 纳入版本控制并随包分发 — Built-in avatar models invisible in packaged builds: `avatar-manifest.json` is now tracked and shipped

## [0.8.0] - 2026-09-12

> 本版本合并 v0.7.7 之后的所有开发工作：9.11 调研 P0/P1/P2 全量修复、
> 聊天体验优化与打包链路统一。

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
- 前端聊天公共层：`composables/useChatScroll`（滚动/ResizeObserver/贴底判断/isLastAssistantMessage 三份合一）、`composables/useChatSession`（输入态/模式切换守卫/发送参数公共编排）、`utils/ttsTextFilter.createCodeBlockFilter`（filterCodeForTts 两份合一）、`styles/chat.css`（逐字相同的聊天气泡样式入 `.lumi-chat-*` 命名空间，两端不同视觉体系原地保留）
- 备份恢复加固配套：`restore_backup` 增加 zip 完整性预检与解出库 `PRAGMA integrity_check`，不通过拒绝落盘；新增 `tests/unit/test_backup_manager.py`（备份存活/一致性、list_backups、损坏 zip 拒绝）
- 关键路径测试安全网 76→107：conftest 全局夹具（LUOMINEST_DATA_DIR 会话级临时库，pytest 不碰真实数据）；auth JWT 全链路、chat_service 记忆管线后台化行为、conversation keyset 分页、vector_store to_thread 化行为、context 纯文本注入零 embedding 共 21 用例
- 群聊拆表配套 `tests/unit/test_group_message_store.py` 10 用例（回填幂等、同构读回、追加语义）
- 前端新增 `composables/useChatWindow.ts`（消息列表尾部窗口化）与 `utils/markdown.renderMarkdownThrottled`（按消息 id 缓存 + 120ms 流式节流，最终输出逐字节一致）
- `package.json` 新增 `clean:out`（rmSync maxRetries 兜底文件锁）置于 build 链头部

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
- 记忆子系统异步化：`vector_store` / `extractor` / `memory_engine` / `context_service` 的同步 SQLite 读写与余弦扫描全部 `asyncio.to_thread` 化（对齐 repo 层既有约定），`batch_add` N+1 合并为单查询
- 非流式回复的记忆写入+蒸馏改为后台任务（对照 platform_router 模式），响应不再等待 LLM/embedding 往返；推荐问题生成移至 done 事件之后后台执行并写入 assistant version（前端 SSE 收到 done 即停读、事后推送不可达；done 不再被推荐问题 LLM 阻塞，推荐问题随对话重载展示）
- 构建产物治理：out/ 构建前清理，安装包不再打入陈旧 hash chunk（实测 1519 文件 94MB → 124 文件 9.7MB）
- 消息列表窗口化渲染：初始仅挂载最近 40 条，向上滚动按锚点补偿前扩 30 条（视口零跳动），长会话 DOM 不再线性增长；搜索定位自动展开全量，历史行动画抑制保持视觉一致；WorkspaceAgentChat/WorkspaceGroupChat 共用
- Electron IPC channel 全量常量化：100 个唯一 channel 收口 `shared/ipc-types.ts`（按域 + invoke/send/push 方向分组），main/preload 两端引用同一常量来源并经 `typed-ipc.ts` 类型收窄，channel 增改未登记即编译报错（运行时 channel 值零变化）
- 版本号 0.7.7 → 0.8.0（frontend/package.json 与 backend/pyproject.toml）
- 打包链路统一 electron-builder：Windows 改 NSIS 安装包 + 便携版（此前 electron-builder 只打 `dir` 中间产物、由 Inno Setup 接管安装器，与 CI/BUILD.md 宣称的链路互相矛盾），`build-all.ps1` 移除 Inno 依赖与 CI 完全同链路；架构收敛为构建 runner 原生（Win/Linux x64、macOS arm64），消除 arm64 包内装 x64 后端的残废产物；mac 图标新增 `icon.mac.png`（1024px，electron-builder 不接受 svg 低于 512px 的图标源）；可执行文件元数据（FileDescription）去除 "Electron桌面客户端" 字样，安装包/任务管理器/文件属性统一显示 LuomiNest
- release.yml 修正：pnpm 版本改从 packageManager 字段读取（避免 action-setup 版本冲突）；新增 TTS 模型下载步骤（extraResources 硬引用 `vits-melo-tts-zh_en`，CI 上缺失会导致三平台打包全挂）；electron-builder 统一 `--publish never`（Release 由独立 job 创建，避免双重发布）；macOS 跳过签名探测产出未签名包

### Fixed

- 鉴权兼容性：passlib 1.7.4（已停更）与 bcrypt 5.x 不兼容，`hash()` 直接抛 `ValueError`，全部密码哈希失效；`pyproject.toml` 钉扎 `bcrypt>=4.1.0,<5.0.0`（4.3.0 验证通过）
- 打包版内置皮套全部不可见：`avatar-manifest.json` 未随 PyInstaller 打包，而工坊以 `/avatar/manifest` 为单一真相源，导致安装后清单为空；现已随包分发，同步修正 `avatar_manifest.py` 过时注释（缺失日志 debug → warning）
- 扩展市场搜索框编译错误：`MarketplaceSearch` 开标签已改 `SearchInput` 但闭标签残留 `</LumiInput>`；`SearchInput` 内置搜索图标，冗余 `#icon` 插槽一并移除
- `SettingsTtsSection` 模板引用未定义的 `ttsDeviceLabel` / `ttsDeviceHint`（vue-tsc 报错），补齐对应计算属性
- 侧边栏导航树形子项圆点与图标重叠：圆点缩小并锚定到树枝线末端、图标缩进后移（`--space-5` → `--space-6`）；激活子项的圆点与连接枝干点亮品牌色，形成位置指向
- `voice_config_store` 迁移动作时间戳由本地无时区 `datetime.now()` 修正为 UTC（与同文件其他 UTC ISO 串混存导致排序/比较错乱）
- 桌面端启动报 `Error: Electron uninstall`：pnpm 已不读取 package.json 的 `pnpm` 字段（且原文件键名重复），`onlyBuiltDependencies` 白名单与 `overrides` 全部失效，electron 二进制下载脚本被 pnpm 10 默认拦截；构建白名单统一迁至 pnpm-workspace.yaml `allowBuilds`（补 `vue-demi`），移除 package.json 两处死配置
- 存储位置核验：dev（`backend/data/`）与打包版（userData/Data/backend）后端数据分离正确、gitignore 覆盖实测通过（db/密钥/上传/记忆均不可入库）、API key 为 Fernet 密文落盘且 SECRET_KEY 机器指纹绑定加密；修正 `.gitignore` 中打包版 userData 路径注释（实际为 `%APPDATA%/luominest-desktop`，与开发版共用，经确认维持共用）
- 自动备份"死亡螺旋"修复：`backup_manager.py` 缺失 `timezone` 导入致 `_auto_cleanup` 必抛 NameError、外层 except 把刚创建的备份删掉（data/backups 长期零产出的根因）；`create_backup` 活库改经 sqlite3 backup API 取在线一致快照，`-wal`/`-shm` 中间态不再入包
- dev 启动期控制台刷 `net::ERR_CONNECTION_REFUSED`：主进程「先建窗口、后启后端」，渲染层挂载即发的业务请求（agents/conversations 等）必撞后端未就绪且失败不重发；新增 `composables/useBackendGate` 就绪门闩（订阅主进程 backend stage 推送，preload 缺失时轮询 /health 兜底，30s 超时放行走正常错误路径），`useApi` 请求与 SSE 流式入口统一接入，`checkHealth` 探测请求绕过门闩防死锁
- 三平台可运行性审查（GUI/后端/产物三层静态审查 + win 产物实检）修复：Linux 后端构建 runner 降至 ubuntu-22.04（PyInstaller 不做 glibc 向后兼容，24.04 构建的二进制在 22.04/Debian 12 直接无法启动）；Linux 桌宠不再启用点击穿透（无 forward 通道，穿透后渲染层收不到鼠标事件会永久锁死交互）；deb 依赖补全 libgtk-3-0/libgbm1/xdg-utils 等（自定义 depends 整体替换默认列表导致极简系统装完无法建窗）；macOS 麦克风 entitlement 键名修正为 `com.apple.security.device.audio-input`（原键名无效，签名后语音权限会失效）；macOS 红绿灯与自绘标题栏品牌区重叠避让（preload 暴露 `app.platform`）；welcome/splash/login 极简布局新增窗口拖拽条（frameless 无 TitleBar 时整窗不可移动）

### Removed

- 移除超长（ULTRA）工作流模式及其高迭代预算配置
- 移除 29 个浏览器自动化工具中的 27 个交互类工具（导航/点击/输入/标签页管理等）及 `browser.search`、`create_browser_tab`；仅保留页面截图与读取当前页 HTML 两个观察类工具，交互能力保留在前端开发者面板
- 后端死代码清理：`services/browser_automation_client.py`（废弃兼容门面）、`infrastructure/mqtt/publisher.py`（零引用）、3 个 0 字节 security 占位文件（tls_manager/oauth_provider/audit exporter）、5 个仅剩 `__pycache__` 的空壳目录、`core/exceptions.register_exception_handlers`（从未注册）、`deps.py` 8 个无消费者的 Depends 工厂
- Alembic 迁移双轨废弃（`scripts/migrate/`、pyproject 依赖、selfcheck 迁移用例）：运行时零引用且版本漂移落后两个版本，schema 演进统一走 `engine.py` 幂等 ALTER；运行库残留 `alembic_version` 表无害保留
- `endpoints/mcp.py` 安全环境变量死副本删除（与 `core/tools/mcp/manager.py` 逐字重复且本文件零调用的重构残留）
- `groups.messages` JSON 整列拆为 `group_messages` 行式表（seq keyset 游标 + 复合索引 + FK CASCADE），消群聊路径写放大；存量数据幂等回填（兼容 snake/camelCase 键风格），仅回填成功才 DROP 旧列，真实库实测 14 项验证通过
- Inno Setup 资产移除（`build/luominest.iss`、`build/ChineseSimplified.isl`）：安装器统一由 electron-builder NSIS 产出，双链路并存期已结束

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
| 0.8.0 | 2026-09-12 | Desktop Electron shell, JSON→SQLite row-based storage, plugin/skill system, cross-platform packaging |
| 0.8.1 | 2026-09-16 | Cloud access (device flow/PKCE), log hub, memory subsystem hardening |
| 0.8.2 | 2026-09-20 | Security hardening, 25x memory overhaul, cross-platform agent takeover |

---

[Unreleased]: https://github.com/LuminousCX/LuomiNest/compare/v0.8.2...HEAD
[0.8.2]: https://github.com/LuminousCX/LuomiNest/releases/tag/v0.8.2
[0.8.1]: https://github.com/LuminousCX/LuomiNest/releases/tag/v0.8.1
[0.8.0]: https://github.com/LuminousCX/LuomiNest/releases/tag/v0.8.0
[0.7.7]: https://github.com/LuminousCX/LuomiNest/releases/tag/v0.7.7
[0.7.4]: https://github.com/LuminousCX/LuomiNest/releases/tag/v0.7.4
[0.7.0]: https://github.com/LuminousCX/LuomiNest/releases/tag/0.7.0
[v0.4.0]: https://github.com/LuminousCX/LuomiNest/releases/tag/v0.4.0
[v0.3.0]: https://github.com/LuminousCX/LuomiNest/releases/tag/v0.3.0
[v0.2.0-alpha]: https://github.com/LuminousCX/LuomiNest/releases/tag/v0.2.0-alpha
[0.1.0]: https://github.com/LuminousCX/LuomiNest/releases/tag/v0.1.0

# 贡献指南 (Contributing to LuomiNest)

[English](CONTRIBUTING.md) | [简体中文](CONTRIBUTING_zh.md) | [日本語](CONTRIBUTING_ja.md)

感谢你对 **LuomiNest - 分布式多用户关系型 AI 智能体平台** 的关注与支持！我们热忱欢迎社区各类形式的贡献，包括提交 Bug 报告、提出功能建议、完善技术文档以及直接贡献代码。

请在参与贡献前仔细阅读本指南，以便顺利搭建本地开发环境并了解项目的开发与协作规范。

---

## 行为准则 (Code of Conduct)

所有参与 LuomiNest 社区交流与代码贡献的开发者均须遵守我们的 [行为准则 (Code of Conduct)](CODE_OF_CONDUCT_zh.md)（[English](CODE_OF_CONDUCT.md) / [日本語](CODE_OF_CONDUCT_ja.md)）。如在社区中发现任何不当言行，请发送邮件至 [luminouschenxi@outlook.com](mailto:luminouschenxi@outlook.com) 报告。

---

## 如何参与贡献

### 1. 提交 Bug 报告与功能需求
- **Bug 报告**：在提交前，请先在 [Issues 列表](https://github.com/LuminousCX/LuomiNest/issues) 中搜索，确认该问题尚未被报告。请使用我们的 [Bug 报告模板](https://github.com/LuminousCX/LuomiNest/issues/new?template=bug_report.yaml)，详细填写复现步骤、报错日志、预期表现与运行环境。
- **功能建议**：对于重大的功能规划或架构调整，建议先在 [GitHub Discussions](https://github.com/LuminousCX/LuomiNest/discussions) 中发起讨论，或通过 [功能请求模板](https://github.com/LuminousCX/LuomiNest/issues/new?template=feature_request.yaml) 描述背景、应用场景与设计思路。

### 2. 代码贡献流程
1. 在 GitHub 上 Fork 本仓库至个人账号。
2. 基于 `master` 分支创建描述清晰的特性或修复分支：
   ```bash
   git checkout -b feature/your-feature-name
   # 或
   git checkout -b fix/issue-description
   ```
3. 按照下文说明搭建本地开发环境并进行代码编写与测试。
4. 在本地运行代码格式化、类型检查与自动化测试。
5. 推送分支并向官方仓库的 `master` 分支发起 Pull Request。

---

## 本地开发环境搭建

### 环境依赖
- **Python**: 3.12 或更高版本
- **Node.js**: 22 或更高版本
- **pnpm**: 10.x 或更高版本
- **Docker**: 可选（用于 PostgreSQL、Redis、MQTT 等配套基础设施调试）

### 后端服务启动

```bash
cd backend

# 创建并激活 Python 虚拟环境
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

# 以可编辑模式安装后端及开发依赖
pip install -e ".[dev]"

# 配置本地环境变量
cp config/.env.example config/.env
# 编辑 config/.env，填入所需的大模型 API Key 等配置

# 启动后端服务
python main.py
```

后端服务启动后默认监听 `http://127.0.0.1:18000`，可通过浏览器访问 `http://127.0.0.1:18000/docs` 查看交互式 API 文档。

### 前端客户端启动

```bash
cd frontend

# 使用 pnpm 安装依赖
pnpm install

# 启动 Vite 开发服务器并调起 Electron 桌面端
pnpm dev

# 构建生产版本静态产物
pnpm build
```

### Docker 基础设施（可选）

```bash
cd docker

# 启动开发配套基础设施（PostgreSQL、Redis、MQTT）
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

> **说明**：LuomiNest 默认采用单文件 SQLite（WAL 模式）进行数据持久化，在单机上即可闭环运行。Docker 中的 PostgreSQL 与 Redis 为云端扩展与分布式测试预留。

---

## 质量标准与提交前自检

在发起 Pull Request 前，请确保通过了相关的静态检查与自动化测试。

### 后端检查项

```bash
cd backend

# 运行自动化测试套件
pytest tests/

# 代码风格与语法检查
ruff check app tests
ruff format --check app tests

# 严格类型检查
mypy app
```

### 前端检查项

```bash
cd frontend

# 运行 TypeScript 类型检查（覆盖 Web 与 Node 进程）
pnpm typecheck

# 验证前端构建是否正常
pnpm build
```

---

## 代码规范与风格

### Python 规范
- 严格遵循 **PEP 8** 规范。
- 所有函数与方法必须包含明确的参数与返回值类型注解（Type Hints）。
- 使用 **Ruff** 进行格式化与语法检测（单行长度限制为 `120` 字符）。
- 所有涉及 I/O、数据库操作与网络请求均使用 `async`/`await` 异步语法。
- 禁止通配符导入（如 `from module import *`），必须显式导入所需对象。
- 命名规则：函数与变量使用 `snake_case`，类名使用 `PascalCase`，常量使用 `UPPER_SNAKE_CASE`。

### TypeScript / Vue 规范
- 采用 Vue 3 Composition API 与 `<script setup lang="ts">` 风格。
- 坚持强类型约束，尽量避免使用 `any`。
- 全局状态统一收拢至 Pinia store 中管理。
- 严格保持组件与组合式函数（Composables）的高内聚与可复用性。
- 组件文件使用 `PascalCase.vue`，工具脚本使用 `camelCase.ts`。

### Git 提交规范 (Conventional Commits)
项目严格遵循 Conventional Commits 提交信息规范：

格式：`<type>(<scope>): <subject>`

**常用类型：**
- `feat`: 新增特性或功能
- `fix`: 修复 Bug
- `docs`: 文档变更
- `style`: 代码格式调整（不影响业务逻辑）
- `refactor`: 代码重构（既不新增特性也不修复 Bug）
- `test`: 增加或更新测试用例
- `chore`: 构建系统、依赖更新或辅助工具变动

**示例：**
```
feat(memory): 新增群聊成员独立画像轨追踪
fix(browser): 将内嵌浏览器工具严格收敛为只读访问
docs(readme): 更新 v0.8.2 发布说明与文档链接
refactor(security): 统一令牌解析逻辑与诊断日志脱敏
```

### 分支命名规则
- `feature/<name>` — 新功能开发
- `fix/<name>` — 缺陷修复
- `docs/<name>` — 文档类变动
- `refactor/<name>` — 代码重构

---

## 模型资产分发政策 (Avatar / Voice Models)

随 LuomiNest 一同分发的模型资产文件——包括内置虚拟形象模型（Live2D、PixelPet、PNG Tuber 及未来的 VRM/Spine 模型）和自带的语音模型——严格遵循**官方维护唯一分发原则**。

### 官方内置模型目录仅限核心团队维护
以下目录**不对社区 PR 开放资产提交**。任何旨在向这些路径添加、替换或调换模型二进制资产的 Pull Request 将被直接关闭：

- `frontend/src/renderer/public/live2d/` — 内置 Live2D 模型
- `frontend/src/renderer/public/pixel/` — 内置 PixelPet 模型
- `frontend/src/renderer/public/png/` — 内置 PNG Tuber 模型
- `backend/models/` — 内置语音模型
- `backend/app/data/avatar-manifest.json` — 内置模型清单文件

> 涉及上述路径的代码级调整（如模型加载器 Bug 修复、清单 Schema 字段兼容等）不受此限，热烈欢迎贡献；但严禁提交外部二进制模型包。

### 设立此规则的原因
1. **版权与二次分发授权**：网络上流传的大多数虚拟形象与语音模型并未明确授予开源分发权。若在官方仓库中收纳，可能给项目及下游使用者带来潜在版权风险。
2. **安全性与审查困难**：二进制模型包无法通过常规代码审查工具进行恶意载荷与授权合规性审计。为保障用户安全，官方仅提供经合规审查的内置资产。

### 用户自导入模型完全保存在本地
用户通过客户端内置的“皮套工坊”（**皮套工坊 → 导入模型**）添加的私有模型，将直接拷贝至本地应用数据目录（Electron `userData`），该目录**完全处于 Git 仓库之外**。它们绝不会随代码被提交，请勿通过 PR 上传私有资产。

### 申请收录新的官方内置模型
如果你是模型作者，或拥有经过确权并明确允许在 AGPL-3.0 项目中免费再分发的开放模型，请先通过 Issue 提出申请，并提供：
1. 模型的原始出处与公开许可证链接；
2. 确认该模型允许在 AGPL-3.0 开源项目中分发与二次衍生。

---

## Pull Request 规范

1. **专注单一目标**：一个 PR 应集中解决一个具体问题或实现一个独立功能，切勿将不相关的修改揉合在一个 PR 中。
2. **完整填写模板**：提交时请按照 [.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md) 认真填写变更说明与测试记录。
3. **完成本地验证**：在发起审查前，请务必在本地确认测试套件、Ruff、Mypy 以及 TypeScript 类型检查全绿。
4. **积极响应审查意见**：维护者会在代码审查中提出改进意见，请保持友善交流并及时跟进修改。

---

## 内部文档说明

项目维护的完整中文架构与设计文档（`文档/` 目录）仅随本地工作区提供，已在 `.gitignore` 中忽略，不随 Git 仓库公开分发。请在本地目录中查阅，切勿将文档草稿意外提交至仓库。

---

## 许可证协议

在参与 LuomiNest 项目贡献时，即视为你同意将所贡献的代码与内容根据项目的 [GNU Affero General Public License v3.0](LICENSE) 协议进行开源授权。

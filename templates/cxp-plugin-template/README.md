# LuomiNest CxPlugin Template

CxPlugin 插件起始模板 — 社区开发者通过 GitHub 的「Use this template」功能 fork 此仓库，快速创建自己的 LuomiNest 插件项目。

## 使用方法

### 1. 从模板创建仓库

点击 GitHub 右上角「Use this template」→「Create a new repository」，或：

```bash
git clone https://github.com/luminous-ChenXi/LuomiNest-cxp-plugin-template.git LuomiNest-cxp-my-plugin
cd LuomiNest-cxp-my-plugin
rm -rf .git
git init
```

仓库命名格式：`LuomiNest-cxp-<plugin-name>`（如 `LuomiNest-cxp-pdf-reader`），其中 `<plugin-name>` 应与 `manifest.json` 中的 `id` 字段（去掉 `cxp-` 前缀）保持一致。

### 2. 修改 manifest.json

```json
{
  "id": "cxp-my-plugin",
  "name": "我的插件",
  "version": "1.0.0",
  "description": "请改为你的插件描述（20-80 字）",
  "platform": "backend",
  "category": "tool",
  "permissions": ["event_listen"]
}
```

字段说明：`id` 改为你的插件 ID；`name` 改为插件名称；`platform` 可选 `backend` / `frontend` / `fullstack` / `hardware`；`category` 可选 `tool` / `integration` / `ui` / `adapter` / `device` / `theme` / `automation`。

完整字段说明见 [docs/development/plugin-system.md](https://github.com/luminous-ChenXi/LuomiNest/blob/main/docs/development/plugin-system.md)。

### 3. 实现 main.py

继承 `CxPluginBase`，实现 `initialize` / `terminate`，按需注册事件处理器、工具、API 路由。

```python
from app.runtime.plugin.cxplugin.base import CxPluginBase, cx_handler
from app.models.plugin import CxEventType


class MyPlugin(CxPluginBase):
    async def initialize(self) -> None:
        self.logger.info("My plugin initialized!")

    @cx_handler(CxEventType.ON_CHAT_MESSAGE)
    async def on_message(self, event: dict) -> None:
        # 安全提示：不要原样记录事件 payload（可能包含用户隐私内容），
        # 仅记录事件类型；确需业务字段时请显式提取白名单字段并脱敏。
        self.logger.info("Received event: ON_CHAT_MESSAGE")

    async def terminate(self) -> None:
        self.logger.info("My plugin terminated.")
```

### 4. 本地打包测试

在 LuomiNest 项目根目录的 `backend/` 下执行：

```bash
cd backend
python -m scripts.package_plugin /abs/path/to/your/plugin --dry-run
python -m scripts.package_plugin /abs/path/to/your/plugin
```

输出文件：`backend/dist/{plugin_id}-v{version}.zip`

### 5. 发布 Release

```bash
git tag v1.0.0
git push origin v1.0.0
# GitHub Actions 会自动打包并发布 Release
```

或手动使用 gh CLI：

```bash
gh release create v1.0.0 --title "v1.0.0" --notes "首个版本" \
  "dist/cxp-my-plugin-v1.0.0.zip#cxp-my-plugin.zip"
```

注意：Release 资产名必须为稳定的 `cxp-my-plugin.zip`（不带版本号），registry 通过 `releases/latest/download/<plugin_id>.zip` 下载；上面的 `本地文件#资产名` 语法会在上传时自动重命名。

### 6. 注册到 cxp-registry

向 [LuomiNest-cxp-registry](https://github.com/luminous-ChenXi/LuomiNest-cxp-registry) 仓库提交 PR，在 `index.json` 的 `plugins` 数组中添加：

```json
{
  "id": "cxp-my-plugin",
  "name": "我的插件",
  "version": "1.0.0",
  "description": "...",
  "author": { "name": "YourName", "url": "https://github.com/yourname" },
  "category": "tool",
  "tags": ["example"],
  "icon": "Puzzle",
  "platform": "backend",
  "license": "MIT",
  "minAppVersion": "0.7.6",
  "repo": "https://github.com/luminous-ChenXi/LuomiNest-cxp-my-plugin",
  "downloadUrl": "https://github.com/luminous-ChenXi/LuomiNest-cxp-my-plugin/releases/latest/download/cxp-my-plugin.zip",
  "createdAt": "2026-07-20",
  "updatedAt": "2026-07-20"
}
```

PR 合并后，所有 LuomiNest 用户在「插件市场」中即可看到并安装你的插件。

## 目录结构

```
LuomiNest-cxp-my-plugin/
├── manifest.json       ← 必需，插件元数据
├── main.py             ← 必需，入口模块
├── helpers.py          ← 可选，辅助模块
├── README.md           ← 使用说明
└── .github/
    └── workflows/
        └── release.yml ← 自动打包发布 CI
```

**重要**：zip 包解压后必须为平铺结构（manifest.json 与 main.py 直接在根目录），不可有多余嵌套。

## 注意事项

- `manifest.json` 中的 `id` 应使用 kebab-case，并以 `cxp-` 前缀
- 仓库名与 `id`（去掉 `cxp-` 前缀）保持一致，便于 registry 自动推导 downloadUrl
- 不要在 zip 中包含 `__pycache__/`、`.git/`、`data/` 等运行时/版本控制目录
- `minAppVersion` 应为你测试通过的最低 LuomiNest 版本
- 若插件依赖第三方 pip 包，请在 `dependencies.pip` 中声明，用户安装时会被自动安装（规划中）

# Discord 平台接入指南

LuomiNest 支持通过 Discord 官方 Gateway 协议将系统内的 **【主Agent】** 接入到你的 Discord 频道或服务器中，成为随叫随到的专属社群伴侣。

---

## 🌟 核心特性与主 Agent 继承机制

- **主 Agent 身份全量接管**：Discord 端伴侣的回复口吻、性格设限、上下文记忆均 100% 继承自系统设置中的 **【主Agent】**。
- **免科学网络直连/反代支持**：适配器原生支持 HTTP/SOCKS5 代理配置，保障在国内或不同网络环境下的稳定连接。
- **双向消息监听与富文本交互**：支持频道艾特回复、私聊互动、Markdown 格式渲染、Emoji 互动与图片消息分析。

---

## 🚀 接入配置步骤

### 1. 创建 Discord Bot 并获取 Token

1. 访问 [Discord Developer Portal](https://discord.com/developers/applications) 并登录你的 Discord 账号。
2. 点击右上角 **New Application**，输入名称（如你的主 Agent 名称）。
3. 在左侧菜单点击 **Bot**：
   - 点击 **Reset Token** 生成专属的 `Bot Token`，**妥善复制保存该 Token**。
   - **非常重要（Privileged Gateway Intents）**：向下拉动页面，务必开启以下三项权限：
     -  **Presence Intent**
     -  **Server Members Intent**
     -  **Message Content Intent**（若未开启此项，机器人将无法读取用户发送的文本内容）。
   - 点击 **Save Changes**。
4. 生成机器人邀请链接：
   - 在左侧菜单点击 **OAuth2** -> **URL Generator**。
   - 在 **Scopes** 中勾选 `bot`。
   - 在 **Bot Permissions** 中勾选：
     - `Send Messages`
     - `Read Messages/View Channels`
     - `Read Message History`
     - `Attach Files`
     - `Embed Links`
   - 复制底部生成的链接并在浏览器中打开，将机器人邀请到你管理的 Discord 服务器中。

---

### 2. 在 LuomiNest 桌面客户端中配置

1. 打开 LuomiNest 桌面客户端 -> **工作台** -> **平台对接**。
2. 找到 **Discord** 平台实例，点击 **设置**（齿轮图标）。
3. 在弹窗配置字段中：
   - `bot_token`: 粘贴你在 Discord 开发者后台获取的 Bot Token。
4. 点击 **保存配置**。
5. 点击该实例的 **启动** 开关。实例状态将变为绿色“运行中”。
6. 在 Discord 服务器中 @ 机器人或在私聊中发送消息，主 Agent 即可实时作答！

---

## 🛡️ Discord 平台风控与安全准则

1. **Token 保密原则**：
   - 绝不要将 Bot Token 提交到公开的 GitHub 仓库或公开发送在群聊中，Discord 爬虫一旦检测到公开泄漏会立即吊销该 Token。
2. **频率与速率限制 (Rate Limit)**：
   - Discord API 全局单个 Bot 限速通常为 50 次请求/秒。LuomiNest 内部实现了请求缓冲队列，避免触发 Cloudflare 429 Too Many Requests 封禁。

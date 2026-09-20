# QQ OneBot 接入脚手架 (NapCatQQ)

本目录为 LuomiNest 的 QQ 平台接入提供本地化运行脚手架。通过 [NapCatQQ](https://github.com/NapNeko/NapCatQQ)（新一代无头架构 OneBot v11 实现），你可以将任意 QQ 账号化身为 LuomiNest 的伴侣智能体。

---

## 🌟 核心特性与主 Agent 继承机制

- **主 Agent 身份全量接管**：该机器人账号的人设、对话风格、音色、记忆与名称，直接继承自 LuomiNest 系统设置中的 **【主Agent】**。
- **无需硬编码**：在 LuomiNest 设置页面中修改“主Agent名称”或“主Agent人设提示词”，QQ 端的伴侣会实时自动同步更新！
- **反向 WebSocket 极速双向通信**：NapCat 作为客户端主动连接 LuomiNest（默认监听端口 `8080`，路径 `/ws/qq`），穿透局域网无需公网 IP。

---

## 🚀 快速启动指南

### 方式一：Docker Compose（推荐，支持扫码后台）

1. 进入本目录：
   ```bash
   cd integrations/qq_napcat
   ```
2. 启动 NapCatQQ 容器：
   ```bash
   docker compose up -d
   ```
3. 扫码登录：
   - 打开浏览器访问：`http://localhost:6099/webui`
   - 使用待作为机器人的 QQ 手机端扫描页面中的二维码进行授权登录。
   - 登录凭据会自动保存在本目录下的 `data/` 与 `config/` 目录中，重启容器无需重复扫码。
4. 在 LuomiNest 桌面客户端中配置：
   - 打开 **工作台 -> 平台对接** 页面。
   - 找到 **QQ OneBot** 实例，点击 **设置** 图标。
   - 确认反向 WS 监听端口为 `8080`（若配置了密钥请保持两端一致）。
   - 启动该平台实例，即可看到连接成功状态变成绿色的“运行中”。

---

### 方式二：Windows 本地原生安装 (Shell / GUI)

如果你在本地 Windows 运行且不想安装 Docker：
1. 访问 [NapCatQQ Releases](https://github.com/NapNeko/NapCatQQ/releases) 下载 `NapCat.Shell.zip` 或 `NapCat.Framework.zip`。
2. 解压后运行 `napcat.bat` 启动。
3. 按照命令行提示扫码登录。
4. 打开生成的 `config/onebot11_<QQ号>.json`，将 `reverseWs.enable` 设为 `true`，`reverseWs.urls` 添加 `["ws://127.0.0.1:8080/ws/qq"]`。

---

## 🛡️ 防封号与官方风控安全准则 (Anti-Ban Best Practices)

腾讯官方对第三方 QQ 协议客户端有较为严格的行为检测系统，请务必严格遵守以下准则：

1. **账号资质建议**：
   - **严禁使用刚注册的全新“白号”**（注册不满 30 天极易触发安全风控限制）。
   - 推荐使用注册时间大于 6 个月、已完成实名认证且日常有正常使用痕迹（活跃度高）的常用账号或小号。
2. **IP 网络环境一致性**：
   - 尽量在**家庭宽带或常用 WiFi**网络下运行 NapCatQQ。
   - 避免直接将 NapCatQQ 部署在阿里云、腾讯云等公网数据中心服务器机房（数据中心 IP 段已被官方严格重点监控）。
3. **频率与拟人防刷机制**：
   - LuomiNest 内置了**防封拟人延迟引擎**：消息发送之间包含 1~3 秒随机自然停顿并模拟“正在输入”状态。
   - 单账号单分钟向同一私聊或群聊发送消息数控制在 10 条以内。
   - 避免短时间内被频繁拉入几十个未知大群；建议从小范围熟人群、私聊开始逐步养号。
4. **消息内容敏感度防范**：
   - 避免让伴侣发送任何涉政、违规、营销导流推广链接或带防屏蔽符号的敏感文本。
   - 敏感内容会直接触发腾讯云端文本过滤系统导致临时冻结。

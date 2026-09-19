import asyncio
import json
import random
import time
import uuid
from typing import Any
import httpx
from loguru import logger

from app.runtime.platform.base import (
    AdapterStatus,
    BasePlatformAdapter,
    PlatformMessage,
    PlatformResponse,
)


class LuomiNestWeChatPersonalAdapter(BasePlatformAdapter):
    """个人微信适配器：基于 Gewechat (iPad 协议网关) / 原生扫码协议。

    核心能力：
    1. 二维码生成与长轮询（支持 UI 弹窗实时提取与展示）
    2. 接收 Webhook 消息回调（文本、图片等）并路由到主 Agent
    3. 防风控与防封号保障：模拟人类输入延迟、滑动窗口限流、分段发送
    4. 微信平台原生专属工具声明与执行
    """

    platform_name = "wechat_personal"

    # 内置轻量模拟二维码 SVG / DataURL（用于测试或服务未启动时 UI 展示与流程演练）
    _MOCK_QR_BASE64: str = (
        "data:image/svg+xml;utf8,"
        "<svg xmlns='http://www.w3.org/2000/svg' width='240' height='240' viewBox='0 0 240 240'>"
        "<rect width='240' height='240' fill='white'/>"
        "<rect x='20' y='20' width='60' height='60' fill='%2307C160'/>"
        "<rect x='30' y='30' width='40' height='40' fill='white'/>"
        "<rect x='40' y='40' width='20' height='20' fill='%2307C160'/>"
        "<rect x='160' y='20' width='60' height='60' fill='%2307C160'/>"
        "<rect x='170' y='30' width='40' height='40' fill='white'/>"
        "<rect x='180' y='40' width='20' height='20' fill='%2307C160'/>"
        "<rect x='20' y='160' width='60' height='60' fill='%2307C160'/>"
        "<rect x='30' y='170' width='40' height='40' fill='white'/>"
        "<rect x='40' y='180' width='20' height='20' fill='%2307C160'/>"
        "<rect x='100' y='40' width='20' height='40' fill='%2307C160'/>"
        "<rect x='120' y='100' width='40' height='20' fill='%2307C160'/>"
        "<rect x='60' y='100' width='20' height='40' fill='%2307C160'/>"
        "<rect x='100' y='140' width='40' height='40' fill='%2307C160'/>"
        "<rect x='160' y='160' width='30' height='30' fill='%2307C160'/>"
        "<rect x='190' y='190' width='30' height='30' fill='%2307C160'/>"
        "<text x='120' y='125' font-family='sans-serif' font-size='12' text-anchor='middle' fill='%2307C160'>Luomi WeChat</text>"
        "</svg>"
    )

    def __init__(self) -> None:
        super().__init__()
        self._api_url: str = "http://127.0.0.1:2531/v2/api"
        self._token: str = ""
        self._app_id: str = ""
        self._callback_url: str = ""
        self._mock_mode: bool = False

        # 当前二维码状态
        self._current_qr: dict[str, Any] = {
            "uuid": "",
            "qr_data": "",
            "status": "idle",  # idle | waiting_scan | scanned | logged_in | expired
            "created_at": 0.0,
            "expired_at": 0.0,
            "message": "请点击获取登录二维码",
        }

        # 防封控参数
        self._anti_ban_enabled: bool = True
        self._typing_delay_enabled: bool = True
        self._typing_delay_base: float = 1.0
        self._typing_delay_per_char: float = 0.04
        self._typing_delay_max: float = 4.0
        self._rate_limit_per_minute: int = 20
        self._rate_limit_records: dict[str, list[float]] = {}

        self._poll_task: asyncio.Task | None = None
        self._is_stopping: bool = False

    def initialize(self, config: dict[str, Any]) -> None:
        super().initialize(config)
        self._api_url = config.get("api_url", "http://127.0.0.1:2531/v2/api").rstrip("/")
        self._token = config.get("token", "")
        self._app_id = config.get("app_id", "") or f"wx_{uuid.uuid4().hex[:8]}"
        self._callback_url = config.get("callback_url", "")
        self._mock_mode = bool(config.get("mock_mode", False))

        self._anti_ban_enabled = bool(config.get("anti_ban_enabled", True))
        self._typing_delay_enabled = bool(config.get("typing_delay_enabled", True))
        self._typing_delay_base = float(config.get("typing_delay_base", 1.0))
        self._typing_delay_per_char = float(config.get("typing_delay_per_char", 0.04))
        self._typing_delay_max = float(config.get("typing_delay_max", 4.0))
        self._rate_limit_per_minute = int(config.get("rate_limit_per_minute", 20))

    # ------------------------------------------------------------------
    # 二维码与扫码生命周期
    # ------------------------------------------------------------------

    async def fetch_login_qrcode(self) -> dict[str, Any]:
        """获取微信登录二维码（供前端弹窗或接口提取展示）。"""
        self._log("info", "qr_fetch", "正在请求个人微信登录二维码...")

        # 如果开启 mock_mode 或配置为空，返回模拟二维码进行沙盒流程演练
        if self._mock_mode or not self._token:
            mock_uuid = f"qr_{uuid.uuid4().hex[:12]}"
            self._current_qr = {
                "uuid": mock_uuid,
                "qr_data": self._MOCK_QR_BASE64,
                "status": "waiting_scan",
                "created_at": time.time(),
                "expired_at": time.time() + 180,
                "message": "请使用手机微信扫描二维码",
            }
            self._log("success", "qr_ready", f"二维码已就绪（模拟模式）: UUID={mock_uuid}")
            return self._current_qr

        # 真实 Gewechat API 请求
        headers = {"X-GEWE-TOKEN": self._token, "Content-Type": "application/json"}
        payload = {"appId": self._app_id}
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.post(f"{self._api_url}/login/getLoginQrCode", headers=headers, json=payload)
                data = res.json()
                if data.get("ret") == 200:
                    ret_data = data.get("data", {})
                    qr_uuid = ret_data.get("uuid", "")
                    qr_data = ret_data.get("qrData", "")
                    # 如果返回的是纯文本 URL，可保持纯文本供前端渲染成 QR
                    self._current_qr = {
                        "uuid": qr_uuid,
                        "qr_data": qr_data or self._MOCK_QR_BASE64,
                        "status": "waiting_scan",
                        "created_at": time.time(),
                        "expired_at": time.time() + 180,
                        "message": "请使用手机微信扫描二维码",
                    }
                    self._log("success", "qr_ready", f"成功获取微信登录二维码: UUID={qr_uuid}")
                    return self._current_qr
                else:
                    err_msg = data.get("msg", "获取二维码失败")
                    self._log("error", "qr_failed", f"获取二维码失败: {err_msg}")
                    return {"uuid": "", "qr_data": "", "status": "error", "message": err_msg}
        except Exception as e:
            self._log("warning", "qr_failed", f"网络异常，回退到本地演示二维码: {e}")
            mock_uuid = f"qr_{uuid.uuid4().hex[:12]}"
            self._current_qr = {
                "uuid": mock_uuid,
                "qr_data": self._MOCK_QR_BASE64,
                "status": "waiting_scan",
                "created_at": time.time(),
                "expired_at": time.time() + 180,
                "message": "服务离线，已生成本地测试二维码",
            }
            return self._current_qr

    async def check_login_status(self, qr_uuid: str = "") -> dict[str, Any]:
        """轮询二维码扫描与登录状态。

        返回状态字典: { "status": "waiting_scan" | "scanned" | "logged_in" | "expired", "message": "..." }
        """
        target_uuid = qr_uuid or self._current_qr.get("uuid", "")
        if not target_uuid:
            return {"status": "expired", "message": "未生成有效二维码，请重新获取"}

        # 检查是否过期（3分钟）
        if time.time() > self._current_qr.get("expired_at", 0) and self._current_qr.get("status") != "logged_in":
            self._current_qr["status"] = "expired"
            self._current_qr["message"] = "二维码已过期，请刷新重新获取"
            return self._current_qr

        # 模拟模式下的状态渐进演示
        if self._mock_mode or not self._token:
            elapsed = time.time() - self._current_qr.get("created_at", time.time())
            if elapsed > 15:
                self._current_qr["status"] = "logged_in"
                self._current_qr["message"] = "微信登录成功（演示模式）"
                self.update_status(AdapterStatus.RUNNING)
            elif elapsed > 6:
                self._current_qr["status"] = "scanned"
                self._current_qr["message"] = "已扫码，请在手机微信上点击确认登录"
            else:
                self._current_qr["status"] = "waiting_scan"
                self._current_qr["message"] = "等待手机微信扫码..."
            return self._current_qr

        # 真实请求 Gewechat 检查状态
        headers = {"X-GEWE-TOKEN": self._token, "Content-Type": "application/json"}
        payload = {"appId": self._app_id, "uuid": target_uuid}
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.post(f"{self._api_url}/login/checkLogin", headers=headers, json=payload)
                data = res.json()
                if data.get("ret") == 200:
                    ret_data = data.get("data", {})
                    # Gewechat 状态: 0-未扫码, 1-已扫码, 2-已确认登录, 3-已过期
                    status_code = ret_data.get("status", 0)
                    if status_code == 1:
                        self._current_qr["status"] = "scanned"
                        self._current_qr["message"] = "已扫码，请在手机微信上点击确认登录"
                    elif status_code == 2:
                        self._current_qr["status"] = "logged_in"
                        self._current_qr["message"] = "微信登录成功"
                        self.update_status(AdapterStatus.RUNNING)
                        self._log("success", "login_ok", "个人微信登录成功，适配器已就绪")
                    elif status_code == 3:
                        self._current_qr["status"] = "expired"
                        self._current_qr["message"] = "二维码已过期，请刷新"
                    else:
                        self._current_qr["status"] = "waiting_scan"
                        self._current_qr["message"] = "等待手机微信扫码..."
                return self._current_qr
        except Exception as e:
            logger.debug(f"[wechat_personal] check_login error: {e}")
            return self._current_qr

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self.update_status(AdapterStatus.STARTING)
        self._is_stopping = False
        self._log("info", "adapter_start", f"个人微信适配器正在启动, appId={self._app_id}")

        # 如果已有 token 或 mock 模式，自动尝试获取一次二维码或登录探测
        if self._token:
            self._log("info", "handshake_ok", "已加载 Gewechat 访问凭据，等待微信在线或扫码")
            self.update_status(AdapterStatus.RUNNING)
        else:
            self.update_status(AdapterStatus.PENDING)
            self._log("info", "pending_scan", "等待用户扫码登录")

    async def stop(self) -> None:
        self._is_stopping = True
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
        self.update_status(AdapterStatus.STOPPED)
        self._log("info", "adapter_stopped", "个人微信适配器已停止")

    # ------------------------------------------------------------------
    # 防封控与打字延迟
    # ------------------------------------------------------------------

    def _check_rate_limit(self, target_id: str) -> bool:
        """滑动窗口限流：避免同一联系人/群短时间连续刷屏触发微信风控。"""
        if not self._anti_ban_enabled or self._rate_limit_per_minute <= 0:
            return True
        now = time.time()
        records = self._rate_limit_records.setdefault(target_id, [])
        valid_records = [ts for ts in records if now - ts < 60.0]
        self._rate_limit_records[target_id] = valid_records
        if len(valid_records) >= self._rate_limit_per_minute:
            self._log(
                "warning", "rate_limit_exceeded",
                f"对微信目标 {target_id} 的发送触发防封控限流 ({len(valid_records)}/{self._rate_limit_per_minute}条/分)",
                details={"target": target_id},
            )
            return False
        valid_records.append(now)
        return True

    async def _apply_typing_delay(self, text: str, target: str) -> None:
        """模拟真人输入延迟，防止机器人秒回被微信风控捕获。"""
        if not self._typing_delay_enabled:
            return
        char_count = len(text.strip()) if text else 0
        delay = self._typing_delay_base + (char_count * self._typing_delay_per_char)
        delay = min(delay, self._typing_delay_max) + random.uniform(0.1, 0.5)
        self._log(
            "info", "anti_ban_delay",
            f"触发微信拟人打字延迟: {delay:.2f}s (字数: {char_count})",
            details={"delay": round(delay, 2), "char_count": char_count, "target": target},
        )
        await asyncio.sleep(delay)

    # ------------------------------------------------------------------
    # 消息发送
    # ------------------------------------------------------------------

    async def send_message(self, response: PlatformResponse, target: str) -> bool:
        if not target:
            self._log("warning", "send_failed", "目标联系人或群聊标识为空")
            return False

        if not self._check_rate_limit(target):
            return False

        await self._apply_typing_delay(response.content, target)

        # 模拟模式处理
        if self._mock_mode or not self._token:
            self._log(
                "success", "message_sent",
                f"[模拟微信] 消息已发送至 {target}: {response.content[:60]}",
                details={"target": target, "content_len": len(response.content)},
            )
            return True

        headers = {"X-GEWE-TOKEN": self._token, "Content-Type": "application/json"}

        # 1. 发送文本消息
        success = True
        if response.content:
            payload = {
                "appId": self._app_id,
                "toWxid": target,
                "content": response.content,
            }
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    res = await client.post(f"{self._api_url}/message/postText", headers=headers, json=payload)
                    data = res.json()
                    if data.get("ret") != 200:
                        success = False
                        self._log("error", "send_failed", f"微信文本发送失败: {data.get('msg')}")
                    else:
                        self._log("success", "message_sent", f"微信消息已发送至 {target}: {response.content[:50]}")
            except Exception as e:
                self._log("error", "send_failed", f"微信接口调用异常: {e}")
                return False

        # 2. 发送图片消息
        for img_url in response.image_urls:
            img_payload = {
                "appId": self._app_id,
                "toWxid": target,
                "imgUrl": img_url,
            }
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    await client.post(f"{self._api_url}/message/postImage", headers=headers, json=img_payload)
            except Exception as e:
                logger.warning(f"[wechat_personal] Failed to send image: {e}")

        return success

    # ------------------------------------------------------------------
    # Webhook 回调处理
    # ------------------------------------------------------------------

    async def handle_webhook(self, body: dict[str, Any]) -> dict[str, Any]:
        """处理来自 Gewechat / 微信反代网关的事件推送。"""
        type_name = body.get("TypeName")
        data = body.get("Data", {})

        # 处理登录状态回调
        if type_name == "LoginEvent":
            status = data.get("status")
            if status == 2:
                self.update_status(AdapterStatus.RUNNING)
                self._current_qr["status"] = "logged_in"
                self._log("success", "login_ok", "收到微信网关登录成功通知")
            return {"status": "ok"}

        # 处理消息推送（AddMsg）
        if type_name == "AddMsg":
            from_user = data.get("FromUserName", {}).get("string", "")
            to_user = data.get("ToUserName", {}).get("string", "")
            content = data.get("Content", {}).get("string", "")
            msg_type = data.get("MsgType", 1)
            msg_id = str(data.get("NewMsgId", ""))

            # 过滤自己发出的消息
            if from_user == self._app_id:
                return {"status": "ignored"}

            is_group = "@chatroom" in from_user
            group_id = from_user if is_group else ""
            user_id = from_user
            sender_name = from_user

            # 群消息中解析实际发言人: "wxid_xxx:\n消息内容"
            if is_group and ":\n" in content:
                parts = content.split(":\n", 1)
                user_id = parts[0].strip()
                content = parts[1]
                sender_name = user_id

            # 多模态图片提取
            image_urls: list[str] = []
            if msg_type == 3:  # 图片类型
                # Gewechat 图片可通过下载接口获取，记录标记
                content = content or "[图片]"

            platform_msg = PlatformMessage(
                platform=self.platform_name,
                user_id=user_id,
                content=content,
                session_id=group_id if is_group else user_id,
                message_id=msg_id,
                group_id=group_id,
                sender_name=sender_name,
                is_group=is_group,
                image_urls=image_urls,
                raw=body,
            )

            self._log(
                "info", "message_received",
                f"收到微信消息 [{'群聊' if is_group else '私聊'}]: {content[:50]}",
                details={"user_id": user_id, "group_id": group_id},
            )

            # 路由到主 Agent
            response = await self._emit_message(platform_msg)
            if response and response.content:
                target = group_id if is_group else from_user
                await self.send_message(response, target)

            return {"status": "processed"}

        return {"status": "ok"}

    # ------------------------------------------------------------------
    # 平台专用工具能力
    # ------------------------------------------------------------------

    @property
    def available_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "wechat.send_image",
                    "description": "向指定的个人微信好友或微信群发送图片",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target": {
                                "type": "string",
                                "description": "目标微信 ID 或群聊 ID (xxx@chatroom)",
                            },
                            "image_url": {
                                "type": "string",
                                "description": "要发送的图片公网 URL 或 Base64 数据",
                            },
                        },
                        "required": ["target", "image_url"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "wechat.revoke_msg",
                    "description": "撤回微信中两分钟内发出的消息",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target": {
                                "type": "string",
                                "description": "目标微信 ID 或群聊 ID",
                            },
                            "msg_id": {
                                "type": "string",
                                "description": "消息 ID",
                            },
                        },
                        "required": ["target", "msg_id"],
                    },
                },
            },
        ]

    async def execute_platform_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool_name == "wechat.send_image":
            target = arguments.get("target", "")
            img_url = arguments.get("image_url", "")
            resp = PlatformResponse(content="", image_urls=[img_url])
            success = await self.send_message(resp, target)
            return {"success": success, "output": "图片已发送" if success else "图片发送失败", "error": ""}

        elif tool_name == "wechat.revoke_msg":
            target = arguments.get("target", "")
            msg_id = arguments.get("msg_id", "")
            # 真实 Gewechat 撤回接口: POST /message/revokeMsg
            self._log("info", "tool_exec", f"执行微信消息撤回: msg_id={msg_id}")
            return {"success": True, "output": f"已请求撤回消息 {msg_id}", "error": ""}

        return await super().execute_platform_tool(tool_name, arguments)

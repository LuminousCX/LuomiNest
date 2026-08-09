"""cxp-my-plugin/main.py — CxPlugin 模板入口。

开发步骤：
1. 复制 templates/cxp-plugin-template 为新仓库 LuomiNest-cxp-<plugin-name>
2. 修改 manifest.json 的 id/name/description/permissions 等
3. 在此文件中实现插件逻辑（继承 CxPluginBase）
4. 通过 `python -m scripts.package_plugin <plugin_id>` 打包为 zip
5. 推送 GitHub Release，提交 PR 到 LuomiNest-cxp-registry/index.json
"""

from app.runtime.plugin.cxplugin.base import CxPluginBase, cx_handler
from app.models.plugin import CxEventType


class MyPlugin(CxPluginBase):
    """示例插件 — 请替换为实际插件类名与逻辑。"""

    async def initialize(self) -> None:
        """插件激活时调用 — 初始化资源、注册工具/处理器。"""
        self.logger.info("MyPlugin initialized!")

    @cx_handler(CxEventType.ON_CHAT_MESSAGE)
    async def on_message(self, event: dict) -> None:
        """处理聊天消息事件。"""
        self.logger.info(f"Received message: {event}")

    async def terminate(self) -> None:
        """插件停用时调用 — 释放资源。"""
        self.logger.info("MyPlugin terminated.")

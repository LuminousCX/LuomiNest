"""本地沙盒 Provider — 创建和管理 LocalSandbox 实例。"""

import logging
from pathlib import Path

from app.core.config import settings
from app.security.sandbox.local_sandbox import LocalSandbox

logger = logging.getLogger(__name__)


class LocalSandboxProvider:
    """本地沙盒工厂。

    为每个 session 创建独立的 workspace 子目录，确保会话间数据隔离。

    Args:
        base_workspace: 沙盒根目录。为 None 时使用 ``settings.DATA_DIR/sandbox``。
    """

    def __init__(self, base_workspace: Path | None = None) -> None:
        if base_workspace is None:
            self.base_workspace = Path(settings.DATA_DIR) / "sandbox"
        else:
            self.base_workspace = base_workspace

        # 确保根目录存在
        self.base_workspace.mkdir(parents=True, exist_ok=True)
        logger.info(f"LocalSandboxProvider 初始化，base_workspace={self.base_workspace}")

    def create_sandbox(self, session_id: str) -> LocalSandbox:
        """为指定 session 创建独立的 LocalSandbox 实例。

        每个 session 拥有独立的 workspace 子目录：
        ``{base_workspace}/{session_id}/``

        Args:
            session_id: 会话标识符。

        Returns:
            配置好的 LocalSandbox 实例。
        """
        workspace = self.base_workspace / session_id
        workspace.mkdir(parents=True, exist_ok=True)

        sandbox = LocalSandbox(workspace=workspace, session_id=session_id)
        logger.debug(f"为 session '{session_id}' 创建沙盒: workspace={workspace}")
        return sandbox

    def get_session_workspace(self, session_id: str) -> Path:
        """获取指定 session 的 workspace 路径（不创建沙盒实例）。

        Args:
            session_id: 会话标识符。

        Returns:
            workspace 目录的绝对路径。
        """
        workspace = (self.base_workspace / session_id).resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace

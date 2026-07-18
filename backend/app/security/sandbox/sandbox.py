"""Sandbox 抽象基类与 CommandResult 数据类。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CommandResult:
    """命令执行结果。

    Attributes:
        stdout: 标准输出内容。
        stderr: 标准错误内容。
        exit_code: 进程退出码（0 表示成功）。
        timed_out: 是否因超时被终止。
    """

    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        """命令是否成功（exit_code == 0 且未超时）。"""
        return self.exit_code == 0 and not self.timed_out

    @property
    def output(self) -> str:
        """合并 stdout 与 stderr 的便捷属性。"""
        parts: list[str] = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(f"Std Error:\n{self.stderr}" if self.stdout else self.stderr)
        if self.timed_out:
            parts.append("[timed out]")
        elif self.exit_code != 0:
            parts.append(f"Exit Code: {self.exit_code}")
        return "\n".join(parts) if parts else "(no output)"


class Sandbox(ABC):
    """沙盒环境抽象基类。

    所有沙盒实现必须继承此类并实现全部抽象方法。
    方法均为异步（async），调用方无需关心底层是否涉及线程/进程切换。
    """

    _id: str

    def __init__(self, id: str) -> None:
        self._id = id

    @property
    def id(self) -> str:
        """沙盒唯一标识。"""
        return self._id

    @abstractmethod
    async def execute_command(self, cmd: str | list[str], timeout: int = 120) -> CommandResult:
        """在沙盒内执行命令。

        Args:
            cmd: 命令字符串或参数列表。
            timeout: 超时秒数，默认 120。

        Returns:
            CommandResult 包含 stdout / stderr / exit_code / timed_out。

        Raises:
            SandboxCommandError: 命令执行失败。
            SandboxPermissionError: 命令被安全策略拒绝。
            SandboxTimeoutError: 命令超时。
        """

    @abstractmethod
    async def read_file(self, path: str) -> str:
        """读取沙盒内文件内容。

        Args:
            path: 文件路径（可以是虚拟路径或相对路径）。

        Returns:
            文件文本内容。

        Raises:
            SandboxPermissionError: 路径越界。
            FileNotFoundError: 文件不存在。
        """

    @abstractmethod
    async def write_file(self, path: str, content: str) -> None:
        """向沙盒内文件写入内容（覆盖）。

        Args:
            path: 文件路径。
            content: 文本内容。

        Raises:
            SandboxPermissionError: 路径越界或只读。
        """

    @abstractmethod
    async def list_dir(self, path: str) -> list[dict]:
        """列举沙盒内目录内容。

        Args:
            path: 目录路径。

        Returns:
            条目列表，每个条目为 dict，包含 name / type / size 等字段。

        Raises:
            SandboxPermissionError: 路径越界。
            FileNotFoundError: 目录不存在。
        """

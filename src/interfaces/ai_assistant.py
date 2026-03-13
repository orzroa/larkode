"""
AI 编程助手抽象层

定义接口以解耦特定 AI 助手（Claude Code、Open Code、Code Body 等）
"""
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional, Dict, Any
from pathlib import Path
from enum import Enum


class AssistantType(str, Enum):
    """AI 助手类型"""
    DEFAULT = "default"
    CLAUDE_CODE = "claude_code"
    OPEN_CODE = "open_code"
    CODE_BODY = "code_body"


class SessionStatus(str, Enum):
    """会话状态"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNKNOWN = "unknown"


class AssistantConfig:
    """AI 助手配置"""
    def __init__(
        self,
        assistant_type: AssistantType,
        workspace: Optional[Path] = None,
        cli_path: Optional[str] = None,
        session_id: Optional[str] = None,
        **kwargs
    ):
        self.assistant_type = assistant_type
        self.workspace = workspace or Path.cwd()
        self.cli_path = cli_path
        self.session_id = session_id
        self.extra = kwargs

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "assistant_type": self.assistant_type.value,
            "workspace": str(self.workspace) if self.workspace else None,
            "cli_path": self.cli_path,
            "session_id": self.session_id,
            "extra": self.extra,
        }


class SessionInfo:
    """会话信息"""
    def __init__(
        self,
        session_id: str,
        status: SessionStatus,
        workspace: Optional[Path] = None,
        pid: Optional[int] = None
    ):
        self.session_id = session_id
        self.status = status
        self.workspace = workspace
        self.pid = pid

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "session_id": self.session_id,
            "status": self.status.value,
            "workspace": str(self.workspace) if self.workspace else None,
            "pid": self.pid,
        }


class ISessionManager(ABC):
    """会话管理器接口"""

    @abstractmethod
    def find_running_session(self) -> Optional[SessionInfo]:
        """查找当前运行的会话"""
        pass

    @abstractmethod
    def ensure_session(self) -> Optional[SessionInfo]:
        """确保有可用会话（获取现有会话）"""
        pass


class IAIAssistantExecutor(ABC):
    """AI 助手执行器接口"""

    @abstractmethod
    async def execute_command(
        self,
        command: str,
        workspace: Optional[Path] = None,
        streaming: bool = False,
        streaming_manager = None,
        user_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """执行命令并流式输出

        Args:
            command: 命令内容
            workspace: 工作目录
            streaming: 是否启用流式输出
            streaming_manager: 流式输出管理器
            user_id: 用户 ID（流式输出需要）
        """
        pass

    @abstractmethod
    def cancel(self) -> bool:
        """取消当前执行"""
        pass

    @abstractmethod
    def get_session_info(self) -> Optional[SessionInfo]:
        """获取当前会话信息"""
        pass


class IAIAssistantInterface(ABC):
    """高级 AI 助手接口"""

    @abstractmethod
    async def execute_command(
        self,
        command: str,
        user_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """执行命令并流式输出

        Args:
            command: 命令内容
            user_id: 用户 ID（用于流式输出）
        """
        pass

    @abstractmethod
    def cancel(self) -> bool:
        """取消当前执行"""
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """获取助手状态"""
        pass